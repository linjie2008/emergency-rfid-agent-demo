"""资产定位 + 能效 mock，字段对齐《设备追踪与能效分析接口文档》查询接口。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

ALARM_LABEL = {
    "over_boundary": "越界报警",
    "tamper": "防拆报警",
    "off_line": "离线报警",
    "low_power": "低电量报警",
    "": "无报警",
    "无报警": "无报警",
}
ENERGY_LABEL = {"0": "关机", "1": "待机", "2": "运行", "3": "闲置"}
ASSET_TYPE_LABEL = {0: "能效", 1: "定位"}


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


DEVICES: list[dict[str, Any]] = [
    {
        "id": 2001, "number": "YP-012", "name": "输液泵12号", "kindName": "输液泵",
        "brandName": "迈瑞", "deptName": "急诊抢救室", "assetType": 1,
        "sn": "1918E0047201", "storePositionName": "抢救室设备带",
        "communicateStatus": 1, "locateStatus": 1, "alarmStatus": "无报警",
        "positionFloorNo": "1F", "currentPosition": "抢救室",
        "energyEfficiencyStatus": "2", "useRate": None, "useTime": None, "onNum": None, "useNum": None,
    },
    {
        "id": 2002, "number": "HXJ-03", "name": "呼吸机3号", "kindName": "呼吸机",
        "brandName": "德尔格", "deptName": "EICU", "assetType": 1,
        "sn": "1918E0047202", "storePositionName": "EICU-2床",
        "communicateStatus": 1, "locateStatus": 1, "alarmStatus": "无报警",
        "positionFloorNo": "2F", "currentPosition": "EICU",
        "energyEfficiencyStatus": "2", "useRate": None, "useTime": None, "onNum": None, "useNum": None,
    },
    {
        "id": 2003, "number": "JH-08", "name": "监护仪8号", "kindName": "监护仪",
        "brandName": "飞利浦", "deptName": "急诊观察室", "assetType": 1,
        "sn": "1918E0047203", "storePositionName": "观察室3床",
        "communicateStatus": 0, "locateStatus": 0, "alarmStatus": "off_line",
        "positionFloorNo": "1F", "currentPosition": "观察室",
        "energyEfficiencyStatus": "0", "useRate": None, "useTime": None, "onNum": None, "useNum": None,
    },
    {
        "id": 2004, "number": "CT-BED-01", "name": "手术床1号", "kindName": "手术床",
        "brandName": "迈柯唯", "deptName": "手术室", "assetType": 1,
        "sn": "1918E00472B2", "storePositionName": "手术间1",
        "communicateStatus": 1, "locateStatus": 1, "alarmStatus": "over_boundary",
        "positionFloorNo": "3F", "currentPosition": "走廊（越界）",
        "energyEfficiencyStatus": "3", "useRate": None, "useTime": None, "onNum": None, "useNum": None,
    },
    {
        "id": 2005, "number": "ECG-02", "name": "心电图机2号", "kindName": "心电图机",
        "brandName": "光电", "deptName": "急诊分诊台", "assetType": 1,
        "sn": "1918E0047205", "storePositionName": "分诊台抽屉",
        "communicateStatus": 1, "locateStatus": 1, "alarmStatus": "low_power",
        "positionFloorNo": "1F", "currentPosition": "分诊台",
        "energyEfficiencyStatus": "1", "useRate": None, "useTime": None, "onNum": None, "useNum": None,
    },
    {
        "id": 2048, "number": "Y04", "name": "妇产科心电监测一体机", "kindName": "心电监测一体机",
        "brandName": "强生", "deptName": "妇产科", "assetType": 0,
        "sn": "04EE039D92DC", "storePositionName": "产科监护区",
        "communicateStatus": 1, "locateStatus": 1, "alarmStatus": "无报警",
        "positionFloorNo": "3F", "currentPosition": "产科监护区",
        "energyEfficiencyStatus": "2", "useRate": 72.4, "useTime": 186, "onNum": 6, "useNum": 5,
        "useRateLower": 20.5, "useRateUpper": 60.5,
    },
    {
        "id": 2049, "number": "Y11", "name": "超声诊断仪A", "kindName": "超声仪",
        "brandName": "GE", "deptName": "超声科", "assetType": 0,
        "sn": "04EE039D9301", "storePositionName": "超声1室",
        "communicateStatus": 1, "locateStatus": 1, "alarmStatus": "无报警",
        "positionFloorNo": "2F", "currentPosition": "超声1室",
        "energyEfficiencyStatus": "2", "useRate": 41.0, "useTime": 98, "onNum": 4, "useNum": 4,
        "useRateLower": 15, "useRateUpper": 70,
    },
    {
        "id": 2050, "number": "Y18", "name": "麻醉机B", "kindName": "麻醉机",
        "brandName": "德尔格", "deptName": "手术室", "assetType": 0,
        "sn": "04EE039D9302", "storePositionName": "手术间3",
        "communicateStatus": 1, "locateStatus": 1, "alarmStatus": "无报警",
        "positionFloorNo": "3F", "currentPosition": "手术间3",
        "energyEfficiencyStatus": "1", "useRate": 18.2, "useTime": 44, "onNum": 2, "useNum": 1,
        "useRateLower": 25, "useRateUpper": 80,
    },
    {
        "id": 2051, "number": "Y22", "name": "呼吸机能效标签-7", "kindName": "呼吸机",
        "brandName": "迈瑞", "deptName": "EICU", "assetType": 0,
        "sn": "04EE039D9303", "storePositionName": "EICU-5床",
        "communicateStatus": 1, "locateStatus": 1, "alarmStatus": "无报警",
        "positionFloorNo": "2F", "currentPosition": "EICU",
        "energyEfficiencyStatus": "2", "useRate": 88.6, "useTime": 240, "onNum": 1, "useNum": 1,
        "useRateLower": 30, "useRateUpper": 85,
    },
    {
        "id": 2052, "number": "YP-003", "name": "输液泵3号", "kindName": "输液泵",
        "brandName": "迈瑞", "deptName": "急诊观察室", "assetType": 1,
        "sn": "1918E0047210", "storePositionName": "设备间",
        "communicateStatus": 0, "locateStatus": 0, "alarmStatus": "off_line",
        "positionFloorNo": "1F", "currentPosition": "未知",
        "energyEfficiencyStatus": "0", "useRate": None, "useTime": None, "onNum": None, "useNum": None,
    },
    {
        "id": 2053, "number": "DR-01", "name": "移动DR", "kindName": "DR",
        "brandName": "西门子", "deptName": "放射科", "assetType": 1,
        "sn": "1918E0047211", "storePositionName": "DR机房",
        "communicateStatus": 1, "locateStatus": 1, "alarmStatus": "无报警",
        "positionFloorNo": "1F", "currentPosition": "急诊抢救室",
        "energyEfficiencyStatus": "2", "useRate": None, "useTime": None, "onNum": None, "useNum": None,
    },
    {
        "id": 2054, "number": "Y30", "name": "保温箱1号", "kindName": "婴儿保温箱",
        "brandName": "戴维", "deptName": "新生儿科", "assetType": 0,
        "sn": "04EE039D9310", "storePositionName": "NICU",
        "communicateStatus": 1, "locateStatus": 1, "alarmStatus": "无报警",
        "positionFloorNo": "4F", "currentPosition": "NICU",
        "energyEfficiencyStatus": "2", "useRate": 65.0, "useTime": 156, "onNum": 1, "useNum": 1,
        "useRateLower": 40, "useRateUpper": 90,
    },
]


def _power_series(gid: int) -> list[dict[str, Any]]:
    base = {2048: 25, 2049: 12, 2050: 8, 2051: 31, 2054: 18}.get(gid, 6)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = []
    for i in range(7, 0, -1):
        d = today - timedelta(days=i - 1)
        rows.append({"dateStr": d.strftime("%Y-%m-%d"), "electricQuantity": round(base * (0.85 + (i % 3) * 0.12), 1)})
    return rows


POWER = {d["id"]: _power_series(d["id"]) for d in DEVICES if d["assetType"] == 0}

ONOFF = {
    2048: [
        {"startDate": f"{_today()} 08:10:00", "endDate": f"{_today()} 11:40:00", "areaName": "产科监护区",
         "runDuration": "3.5h", "standbyDuration": "0.2h", "offDuration": "0h"},
        {"startDate": f"{_today()} 14:00:00", "endDate": f"{_today()} 16:20:00", "areaName": "产科监护区",
         "runDuration": "2.1h", "standbyDuration": "0.3h", "offDuration": "0h"},
    ]
}


def slim(dev: dict[str, Any]) -> dict[str, Any]:
    alarm = dev.get("alarmStatus") or ""
    energy = str(dev.get("energyEfficiencyStatus") or "")
    return {
        "id": dev["id"],
        "name": dev["name"],
        "number": dev["number"],
        "sn": dev.get("sn") or "",
        "kindName": dev.get("kindName"),
        "deptName": dev.get("deptName"),
        "assetType": ASSET_TYPE_LABEL.get(dev.get("assetType"), str(dev.get("assetType"))),
        "online": "在线" if dev.get("communicateStatus") == 1 else "离线",
        "located": "已定位" if dev.get("locateStatus") == 1 else "未定位",
        "alarm": ALARM_LABEL.get(alarm, alarm or "无报警"),
        "floor": dev.get("positionFloorNo") or "",
        "position": dev.get("currentPosition") or dev.get("storePositionName") or "",
        "store": dev.get("storePositionName") or "",
        "energyStatus": ENERGY_LABEL.get(energy, energy or "-"),
        "useRate": dev.get("useRate"),
        "useTimeHours": dev.get("useTime"),
        "onNum": dev.get("onNum"),
        "useNum": dev.get("useNum"),
    }


def find_devices(
    keyword: str = "",
    dept: str = "",
    alarm: str = "",
    asset_type: str = "",
) -> list[dict[str, Any]]:
    keyword = (keyword or "").strip()
    dept = (dept or "").strip()
    alarm = (alarm or "").strip()
    asset_type = (asset_type or "").strip()
    alarm_keys = {v: k for k, v in ALARM_LABEL.items()}
    alarm_code = alarm_keys.get(alarm, alarm)
    type_code = None
    if asset_type in ("能效", "0"):
        type_code = 0
    elif asset_type in ("定位", "1"):
        type_code = 1

    out = []
    for d in DEVICES:
        blob = f"{d['name']} {d['number']} {d.get('sn') or ''} {d.get('kindName') or ''}"
        if keyword and keyword not in blob:
            continue
        if dept and dept not in (d.get("deptName") or ""):
            continue
        if alarm:
            if alarm in ("无报警",) and (d.get("alarmStatus") in ("", "无报警", None)):
                pass
            elif d.get("alarmStatus") not in (alarm, alarm_code):
                continue
        if type_code is not None and d.get("assetType") != type_code:
            continue
        out.append(deepcopy(d))
    return out


def get_device(keyword: str) -> dict[str, Any] | None:
    keyword = (keyword or "").strip()
    if not keyword:
        return None
    for d in DEVICES:
        if keyword in (str(d["id"]), d["name"], d["number"], d.get("sn") or ""):
            return deepcopy(d)
    hits = find_devices(keyword=keyword)
    return deepcopy(hits[0]) if len(hits) == 1 else None


def alarm_devices() -> list[dict[str, Any]]:
    return [d for d in DEVICES if d.get("alarmStatus") not in ("", "无报警", None)]


def energy_devices(dept: str = "", status: str = "") -> list[dict[str, Any]]:
    status = (status or "").strip()
    status_code = {v: k for k, v in ENERGY_LABEL.items()}.get(status, status)
    out = []
    for d in DEVICES:
        if d.get("assetType") != 0:
            continue
        if dept and dept not in (d.get("deptName") or ""):
            continue
        if status_code and str(d.get("energyEfficiencyStatus")) != str(status_code):
            continue
        out.append(deepcopy(d))
    return out


def power_of(keyword: str) -> dict[str, Any] | None:
    d = get_device(keyword)
    if not d:
        return None
    return {"device": slim(d), "daily": POWER.get(d["id"], [])}


def onoff_of(keyword: str) -> dict[str, Any] | None:
    d = get_device(keyword)
    if not d:
        return None
    return {"device": slim(d), "records": ONOFF.get(d["id"], [])}


def _ago(minutes: int) -> datetime:
    return datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=minutes)


def _fmt(t: datetime) -> str:
    return t.strftime("%Y-%m-%d %H:%M:%S")


# 轨迹点：距现在分钟数、区域、楼层。对应 /userPaths/{sn}，给模型前会收成停留段。
TRACK_POINTS: dict[int, list[tuple[int, str, str]]] = {
    2001: [  # 输液泵12号 今天在急诊-CT 之间跑
        (260, "抢救室设备带", "1F"),
        (210, "抢救1床", "1F"),
        (150, "抢救1床", "1F"),
        (95, "CT室门口", "1F"),
        (80, "CT室", "1F"),
        (45, "抢救2床", "1F"),
        (8, "抢救室", "1F"),
    ],
    2002: [  # 呼吸机3号 基本在 EICU，昨天去过维修
        (1600, "设备维修间", "B1"),
        (1480, "EICU-2床", "2F"),
        (60, "EICU-2床", "2F"),
        (10, "EICU", "2F"),
    ],
    2003: [  # 监护仪8号 观察室后离线
        (420, "观察室3床", "1F"),
        (240, "观察室3床", "1F"),
        (180, "观察室走廊", "1F"),
    ],
    2004: [  # 手术床1号 越界
        (300, "手术间1", "3F"),
        (90, "手术间1", "3F"),
        (40, "3F走廊", "3F"),
        (5, "走廊（越界）", "3F"),
    ],
    2005: [  # 心电图机2号 分诊为主，去过抢救
        (360, "分诊台抽屉", "1F"),
        (200, "抢救室", "1F"),
        (140, "分诊台", "1F"),
        (20, "分诊台", "1F"),
    ],
    2052: [  # 输液泵3号 设备间后失联
        (2880, "急诊观察室", "1F"),
        (2000, "设备间", "1F"),
        (1900, "设备间", "1F"),
    ],
    2053: [  # 移动DR 全院跑
        (400, "DR机房", "1F"),
        (320, "急诊抢救室", "1F"),
        (250, "观察室", "1F"),
        (180, "CT室门口", "1F"),
        (90, "急诊抢救室", "1F"),
        (15, "急诊抢救室", "1F"),
    ],
}

# 对应 /move/record 离开存放位置 / 返回
MOVE_RECORDS: dict[int, list[dict[str, str]]] = {
    2001: [
        {"from": "抢救室设备带", "to": "抢救1床", "leaveStoreTime": "", "backStoreTime": ""},
        {"from": "抢救1床", "to": "CT室", "leaveStoreTime": "", "backStoreTime": ""},
        {"from": "CT室", "to": "抢救室", "leaveStoreTime": "", "backStoreTime": ""},
    ],
    2002: [
        {"from": "EICU-2床", "to": "设备维修间", "leaveStoreTime": "", "backStoreTime": ""},
        {"from": "设备维修间", "to": "EICU-2床", "leaveStoreTime": "", "backStoreTime": ""},
    ],
    2004: [
        {"from": "手术间1", "to": "3F走廊", "leaveStoreTime": "", "backStoreTime": ""},
    ],
    2053: [
        {"from": "DR机房", "to": "急诊抢救室", "leaveStoreTime": "", "backStoreTime": ""},
        {"from": "急诊抢救室", "to": "观察室", "leaveStoreTime": "", "backStoreTime": ""},
        {"from": "观察室", "to": "急诊抢救室", "leaveStoreTime": "", "backStoreTime": ""},
    ],
}


def _fill_move_times() -> None:
    for gid, recs in MOVE_RECORDS.items():
        pts = TRACK_POINTS.get(gid) or []
        area_time = {}
        for minutes_ago, area, _floor in pts:
            area_time.setdefault(area, _ago(minutes_ago))
        for rec in recs:
            leave = area_time.get(rec["from"]) or _ago(120)
            back = area_time.get(rec["to"]) or leave + timedelta(minutes=30)
            rec["leaveStoreTime"] = _fmt(leave)
            rec["backStoreTime"] = _fmt(back) if rec["to"] != "3F走廊" else ""


_fill_move_times()


def _stays_from_points(raw: list[tuple[int, str, str]]) -> list[dict[str, Any]]:
    if not raw:
        return []
    seq = [(_ago(m), area, floor) for m, area, floor in sorted(raw, key=lambda x: -x[0])]
    stays: list[dict[str, Any]] = []
    start_t, area, floor = seq[0]
    for i in range(1, len(seq)):
        t, a, f = seq[i]
        if a != area:
            minutes = round((t - start_t).total_seconds() / 60.0, 1)
            stays.append({
                "startTime": _fmt(start_t),
                "endTime": _fmt(t),
                "area": area,
                "floor": floor,
                "minutes": max(minutes, 1),
            })
            start_t, area, floor = t, a, f
    end = datetime.now().replace(second=0, microsecond=0)
    minutes = round((end - start_t).total_seconds() / 60.0, 1)
    stays.append({
        "startTime": _fmt(start_t),
        "endTime": _fmt(end),
        "area": area,
        "floor": floor,
        "minutes": max(minutes, 1),
        "ongoing": True,
    })
    return stays


def track_of(keyword: str) -> dict[str, Any] | None:
    """对应 GET /userPaths/{sn} + /move/record，返回停留段而非原始坐标点。"""
    d = get_device(keyword)
    if not d:
        return None
    raw = TRACK_POINTS.get(d["id"]) or []
    stays = _stays_from_points(raw)
    freq = ""
    if stays:
        longest = max(stays, key=lambda s: s["minutes"])
        freq = longest["area"]
    return {
        "device": slim(d),
        "pointCount": len(raw),
        "highFreqPosition": freq or d.get("currentPosition") or "",
        "lastPosition": stays[-1]["area"] if stays else d.get("currentPosition") or "",
        "stays": stays,
        "moves": deepcopy(MOVE_RECORDS.get(d["id"]) or []),
    }
