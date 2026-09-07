"""Lifecycle management for the real CUDA-backed Qwen3.8-27B server."""

from __future__ import annotations

import ctypes
import gc
import http.client
import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
DEFAULT_BINARY = Path("/home/administrator/llama.cpp-cuda/build-cuda/bin/llama-server")
DEFAULT_MODEL = Path("/home/administrator/models/qwen3.8-27b/Qwen3.8-27B-Q4_K_M.gguf")


class LocalModelManager:
    def __init__(self) -> None:
        self.model_name = os.getenv("LOCAL_MODEL", "qwen3.8-27b-local")
        self.host = os.getenv("LOCAL_MODEL_HOST", "127.0.0.1")
        self.port = int(os.getenv("LOCAL_MODEL_PORT", "8080"))
        self.idle_timeout = max(60, int(os.getenv("LOCAL_MODEL_IDLE_TIMEOUT", "300")))
        self.context_window = max(2048, int(os.getenv("LOCAL_MODEL_CTX", "8192")))
        self.history_tokens = max(0, int(os.getenv("LOCAL_HISTORY_TOKENS", "900")))
        self.max_output_tokens = max(1, int(os.getenv("LOCAL_MODEL_MAX_OUTPUT_TOKENS", "800")))
        self.native_context_window = max(
            self.context_window, int(os.getenv("LOCAL_MODEL_NATIVE_CTX", "262144"))
        )
        self.binary = Path(os.getenv("LOCAL_LLAMA_SERVER", str(DEFAULT_BINARY)))
        self.model_path = Path(os.getenv("LOCAL_MODEL_PATH", str(DEFAULT_MODEL)))
        self.preflight_comfyui = os.getenv("LOCAL_MODEL_PREFLIGHT_COMFYUI", "true").lower() not in {"0", "false", "no", "off"}
        self.preflight_strict = os.getenv("LOCAL_MODEL_PREFLIGHT_STRICT", "true").lower() not in {"0", "false", "no", "off"}
        self.comfyui_host = os.getenv("COMFYUI_HOST", "127.0.0.1")
        self.comfyui_port = int(os.getenv("COMFYUI_PORT", "8188"))
        self.process: subprocess.Popen | None = None
        self.status = "offline"
        self.error = ""
        self.started_at = 0.0
        self.last_active = 0.0
        self.last_cleanup: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._log_handle = None
        threading.Thread(target=self._idle_loop, daemon=True).start()

    def check_health(self) -> bool:
        try:
            conn = http.client.HTTPConnection(self.host, self.port, timeout=1.2)
            conn.request("GET", "/health")
            response = conn.getresponse()
            response.read()
            conn.close()
            return response.status == 200
        except OSError:
            return False

    def touch(self) -> None:
        with self._lock:
            self.last_active = time.time()

    def _comfyui_release(self) -> dict[str, Any]:
        """仅在 ComfyUI 无运行/等待任务时请求其主动卸载模型。"""
        if not self.preflight_comfyui:
            return {"ok": True, "status": "disabled"}
        try:
            conn = http.client.HTTPConnection(self.comfyui_host, self.comfyui_port, timeout=2.0)
            conn.request("GET", "/queue")
            response = conn.getresponse()
            raw = response.read()
            conn.close()
            if response.status != 200:
                return {"ok": not self.preflight_strict, "status": "unavailable", "detail": f"HTTP {response.status}"}
            queue = json.loads(raw or b"{}")
        except (OSError, ValueError, json.JSONDecodeError):
            return {"ok": True, "status": "not_running"}

        running = queue.get("queue_running") or []
        pending = queue.get("queue_pending") or []
        if running or pending:
            return {
                "ok": not self.preflight_strict, "status": "busy",
                "detail": f"ComfyUI 正在执行 {len(running)} 个任务，等待 {len(pending)} 个任务",
            }

        payload = json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8")
        try:
            conn = http.client.HTTPConnection(self.comfyui_host, self.comfyui_port, timeout=10.0)
            conn.request("POST", "/free", body=payload, headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            response.read()
            conn.close()
            if response.status not in {200, 201, 202, 204}:
                return {"ok": not self.preflight_strict, "status": "release_failed", "detail": f"HTTP {response.status}"}
            return {"ok": True, "status": "released"}
        except OSError as exc:
            return {"ok": not self.preflight_strict, "status": "release_failed", "detail": str(exc)}

    def _owned_orphan_model_pids(self) -> list[int]:
        """找出同一用户、同一二进制和同一权重的遗留模型进程。"""
        found = []
        binary = str(self.binary.resolve())
        model = str(self.model_path.resolve())
        managed_pid = self.process.pid if self.process and self.process.poll() is None else None
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            if pid in {os.getpid(), managed_pid}:
                continue
            try:
                if entry.stat().st_uid != os.getuid():
                    continue
                parts = (entry / "cmdline").read_bytes().split(b"\0")
                args = [part.decode("utf-8", "replace") for part in parts if part]
                if not args:
                    continue
                executable = str(Path(args[0]).resolve())
                if executable == binary and model in args:
                    found.append(pid)
            except (FileNotFoundError, PermissionError, OSError):
                continue
        return found

    def _terminate_orphan_models(self) -> list[int]:
        pids = self._owned_orphan_model_pids()
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        deadline = time.time() + 5
        remaining = set(pids)
        while remaining and time.time() < deadline:
            remaining = {pid for pid in remaining if Path(f"/proc/{pid}").exists()}
            if remaining:
                time.sleep(0.1)
        for pid in remaining:
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        return pids

    @staticmethod
    def _trim_python_memory() -> bool:
        gc.collect()
        try:
            libc = ctypes.CDLL("libc.so.6")
            return bool(libc.malloc_trim(0))
        except (OSError, AttributeError):
            return False

    def release_resources_before_start(self) -> bool:
        """启动前释放本项目遗留模型与空闲 ComfyUI 占用，不干预其他应用。"""
        started = time.time()
        orphan_pids = self._terminate_orphan_models()
        comfyui = self._comfyui_release()
        heap_trimmed = self._trim_python_memory()
        self.last_cleanup = {
            "at": datetime_now(), "ok": bool(comfyui.get("ok")),
            "orphanModelPids": orphan_pids, "comfyui": comfyui,
            "pythonHeapTrimmed": heap_trimmed,
            "elapsedMs": int((time.time() - started) * 1000),
        }
        if not comfyui.get("ok"):
            self.error = comfyui.get("detail") or "启动前资源释放失败"
            return False
        return True

    def start(self, wait: bool = True, timeout: float = 90.0) -> bool:
        with self._lock:
            if self.check_health():
                self.status = "online"
                self.last_active = time.time()
                return True
            if self.process and self.process.poll() is None:
                self.stop("unhealthy_before_restart")
            if not self.process or self.process.poll() is not None:
                if not self.binary.is_file() or not self.model_path.is_file():
                    self.status = "error"
                    self.error = "本地模型二进制或权重文件不存在"
                    return False
                self.status = "cleaning"
                if not self.release_resources_before_start():
                    self.status = "error"
                    return False
                self.status = "starting"
                self.error = ""
                self._log_handle = (ROOT / "local-model.log").open("ab", buffering=0)
                env = os.environ.copy()
                libraries = [str(self.binary.parent), "/usr/local/cuda/lib64", "/usr/lib/wsl/lib", "/usr/lib/x86_64-linux-gnu"]
                env["LD_LIBRARY_PATH"] = ":".join(libraries + [env.get("LD_LIBRARY_PATH", "")])
                cmd = [
                    str(self.binary), "-m", str(self.model_path), "--alias", self.model_name,
                    "--host", self.host, "--port", str(self.port),
                    "--ctx-size", str(self.context_window),
                    "--n-gpu-layers", os.getenv("LOCAL_MODEL_GPU_LAYERS", "99"),
                    "--parallel", "1", "--flash-attn", "on", "--jinja",
                    "--reasoning", os.getenv("LOCAL_MODEL_REASONING", "off"),
                ]
                self.process = subprocess.Popen(
                    cmd, cwd=str(self.binary.parent), env=env,
                    stdout=self._log_handle, stderr=subprocess.STDOUT, start_new_session=True,
                )
                self.started_at = self.last_active = time.time()

        if not wait:
            return True
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.check_health():
                with self._lock:
                    self.status = "online"
                    self.last_active = time.time()
                return True
            if self.process and self.process.poll() is not None:
                break
            time.sleep(0.5)
        with self._lock:
            self.error = "本地模型启动失败或超时，请查看 local-model.log"
            self.status = "error"
        self.stop("startup_failed")
        return False

    def ensure_ready(self) -> bool:
        self.touch()
        return self.check_health() or self.start(wait=True)

    def stop(self, reason: str = "manual") -> bool:
        with self._lock:
            self.status = "stopping"
            process = self.process
            if process and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=8)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except OSError:
                        pass
            self.process = None
            if self._log_handle:
                self._log_handle.close()
                self._log_handle = None
            self.status = "offline"
            self.started_at = self.last_active = 0.0
        return True

    def _idle_loop(self) -> None:
        while True:
            time.sleep(5)
            with self._lock:
                should_stop = self.status == "online" and self.process is not None and self.last_active > 0 and time.time() - self.last_active >= self.idle_timeout
            if should_stop:
                self.stop("idle_timeout")

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            healthy = self.check_health()
            if healthy:
                self.status = "online"
            elif self.status == "online":
                self.status = "offline"
            idle = int(time.time() - self.last_active) if healthy and self.last_active else 0
            return {
                "status": self.status, "online": healthy, "model": self.model_name,
                "idleSeconds": idle, "idleTimeout": self.idle_timeout,
                "contextWindow": self.context_window,
                "historyTokens": self.history_tokens,
                "maxOutputTokens": self.max_output_tokens,
                "nativeContextWindow": self.native_context_window,
                "managed": self.process is not None, "error": self.error,
                "lastCleanup": self.last_cleanup,
            }


local_model_manager = LocalModelManager()


def datetime_now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")
