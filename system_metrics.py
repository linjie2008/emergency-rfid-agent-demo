"""本机推理资源监控。

WSL2 环境下：
- WSL 虚拟机内的 /proc/meminfo、/proc/stat 只能反映分配给虚拟机的资源，
  与 Windows 任务管理器看到的宿主机真实使用率不一致。
- 因此优先通过 WSL interop 调用 Windows 侧 WMI 读取宿主机口径的内存与 CPU，
  读取失败时回退为 WSL 虚拟机内部数值。
- GPU 使用 nvidia-smi（WSL 内直接查询物理显卡，本身就是设备级真实值）。
"""
from __future__ import annotations
import os, shutil, subprocess, time

# WSL2 下 nvidia-smi 位于 /usr/lib/wsl/lib，而 systemd 服务的 PATH 不含该目录，
# 直接写 "nvidia-smi" 会找不到，导致 GPU 永远显示不出来。这里显式探测常见位置。
_NVIDIA_SMI_CANDIDATES = [
    "/usr/lib/wsl/lib/nvidia-smi",
    "/usr/bin/nvidia-smi",
    "/usr/local/bin/nvidia-smi",
]

_HOST_CACHE = {"t": 0.0, "data": None, "fail_t": 0.0}
_HOST_TTL = 5.0          # Windows WMI 调用较慢，结果缓存 5 秒
_HOST_FAIL_TTL = 30.0    # interop 不可用时，30 秒内不再重试

# systemd 服务的 PATH 不含 Windows 目录，必须用绝对路径找 powershell.exe
_POWERSHELL_CANDIDATES = [
    "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
    "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/pwsh.exe",
]


def _find_powershell() -> str | None:
    found = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if found:
        return found
    for path in _POWERSHELL_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def _find_nvidia_smi() -> str | None:
    found = shutil.which("nvidia-smi")
    if found:
        return found
    for path in _NVIDIA_SMI_CANDIDATES:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def _memory():
    values = {}
    with open("/proc/meminfo", encoding="utf-8") as handle:
        for line in handle:
            key, value = line.split(":", 1); values[key] = int(value.strip().split()[0])
    total = values.get("MemTotal", 0); available = values.get("MemAvailable", 0)
    return {"usedGb": round((total-available)/1048576,1), "totalGb": round(total/1048576,1),
            "percent": round((total-available)/total*100,1) if total else 0}


def _gpu():
    binary = _find_nvidia_smi()
    if not binary:
        return None
    try:
        output = subprocess.check_output(
            [binary, "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"], text=True, timeout=2
        ).strip().splitlines()[0]
        name, util, used, total, temp = [x.strip() for x in output.split(",")]
        return {"name":name, "percent":float(util), "usedGb":round(float(used)/1024,1),
                "totalGb":round(float(total)/1024,1), "temperatureC":float(temp)}
    except Exception:
        return None


def _host_stats() -> dict | None:
    """读取 Windows 宿主机（任务管理器口径）的内存与 CPU，带缓存与失败回退。"""
    now = time.monotonic()
    if _HOST_CACHE["data"] is not None and now - _HOST_CACHE["t"] < _HOST_TTL:
        return _HOST_CACHE["data"]
    if _HOST_CACHE["data"] is None and now - _HOST_CACHE["fail_t"] < _HOST_FAIL_TTL:
        return None
    script = (
        "$os=Get-CimInstance Win32_OperatingSystem;"
        "$cpu=Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average;"
        "Write-Output ('{0}|{1}|{2}' -f "
        "[math]::Round($os.TotalVisibleMemorySize/1MB,0),"
        "[math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,0),"
        "[math]::Round($cpu.Average,1))"
    )
    binary = _find_powershell()
    if not binary:
        return None
    try:
        output = subprocess.check_output(
            [binary, "-NoProfile", "-NonInteractive", "-Command", script],
            text=True, timeout=8
        ).strip().splitlines()[-1]
        total_gb, used_gb, cpu_pct = [float(x) for x in output.split("|")]
        data = {
            "memory": {"usedGb": used_gb, "totalGb": total_gb,
                       "percent": round(used_gb/total_gb*100, 1) if total_gb else 0},
            "cpu": round(cpu_pct, 1),
        }
        _HOST_CACHE.update(t=time.monotonic(), data=data)
        return data
    except Exception:
        _HOST_CACHE.update(fail_t=time.monotonic())
        return None


def _read_cpu_stat():
    """读取 /proc/stat 第一行，返回 (总时间, 空闲时间)，单位为 jiffies。"""
    with open("/proc/stat", encoding="utf-8") as handle:
        parts = handle.readline().split()
    fields = [int(x) for x in parts[1:]]
    total = sum(fields)
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)  # idle + iowait
    return total, idle


def _cpu_percent(sample_seconds: float = 0.25):
    """WSL 虚拟机内部口径的 CPU 占用（/proc/stat 前后采样，与 top 同口径）。"""
    t0, i0 = _read_cpu_stat()
    time.sleep(sample_seconds)
    t1, i1 = _read_cpu_stat()
    delta_total = t1 - t0
    delta_idle = i1 - i0
    if delta_total <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (delta_total - delta_idle) / delta_total * 100)), 1)


def system_metrics():
    cores = os.cpu_count() or 1
    host = _host_stats()
    if host is not None:
        cpu = {"percent": host["cpu"], "cores": cores, "scope": "host"}
        memory = {**host["memory"], "scope": "host"}
    else:
        cpu = {"percent": _cpu_percent(), "cores": cores, "scope": "wsl"}
        memory = {**_memory(), "scope": "wsl"}
    return {"cpu": cpu, "memory": memory, "gpu": _gpu()}
