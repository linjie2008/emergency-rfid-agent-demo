"""把进出事件收成轨迹和停留时长。数字只从记录计算，不让模型估。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from rfid_data import PATIENTS, TYPE2_LABEL, TYPE_LABEL, filter_records


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def minutes_between(a: str, b: str) -> float:
    return round((parse_time(b) - parse_time(a)).total_seconds() / 60.0, 1)


def event_action(row: dict[str, Any]) -> str:
    if row.get("type") == 5:
        return TYPE2_LABEL.get(row.get("type2") or 0, "进出")
    return TYPE_LABEL.get(row.get("type") or 0, "未知")


def build_timeline(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {"ok": False, "message": "没有进出记录"}

    events = sorted(events, key=lambda r: r["createTime"])
    first = events[0]
    last = events[-1]
    hospital_no = first["hospitalNo"]
    meta = PATIENTS.get(hospital_no, {})

    steps = []
    stays: dict[str, float] = defaultdict(float)
    open_area: dict[str, str] = {}

    for row in events:
        action = event_action(row)
        area = row.get("areaName") or ""
        node = row.get("importName2") or row.get("importName") or ""
        steps.append(
            {
                "time": row["createTime"],
                "action": action,
                "area": area,
                "node": node,
                "gate": row.get("importName") or "",
                "type": row.get("type"),
                "type2": row.get("type2"),
            }
        )
        if action in ("进", "抵达") and area:
            # RFID 常漏刷「出」：进入新区时，自动结束上一区域停留
            for prev, start in list(open_area.items()):
                if prev != area:
                    stays[prev] += minutes_between(start, row["createTime"])
                    open_area.pop(prev)
            if area not in open_area:
                open_area[area] = row["createTime"]
        elif action == "出" and area in open_area:
            stays[area] += minutes_between(open_area.pop(area), row["createTime"])

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_areas = []
    for area, start in open_area.items():
        dur = minutes_between(start, now_str)
        stays[area] += dur
        current_areas.append({"area": area, "since": start, "minutes": dur})

    stay_list = [
        {"area": k, "minutes": round(v, 1)}
        for k, v in sorted(stays.items(), key=lambda x: -x[1])
    ]
    if current_areas:
        current_location = current_areas[0]["area"]
    elif event_action(last) == "出":
        current_location = "已离开"
    else:
        current_location = last.get("areaName") or "未知"

    return {
        "ok": True,
        "patientName": first.get("patientName"),
        "hospitalNo": hospital_no,
        "wristbandEpc": first.get("wristbandEpc"),
        "channel": meta.get("channel", "急诊绿通"),
        "firstTime": first["createTime"],
        "lastTime": last["createTime"],
        "totalMinutes": minutes_between(first["createTime"], last["createTime"]),
        "currentAreas": current_areas,
        "currentLocation": current_location,
        "stays": stay_list,
        "steps": steps,
        "eventCount": len(events),
    }


def timeout_patients(threshold_minutes: float = 120) -> list[dict[str, Any]]:
    """当前仍在抢救室且停留超过阈值的患者。"""
    hits = []
    for no, meta in PATIENTS.items():
        events = filter_records(hospital_no=no)
        tl = build_timeline(events)
        if not tl.get("ok"):
            continue
        for cur in tl.get("currentAreas") or []:
            if cur["area"] == "抢救室" and cur["minutes"] >= threshold_minutes:
                hits.append(
                    {
                        "patientName": tl["patientName"],
                        "hospitalNo": no,
                        "channel": meta.get("channel"),
                        "area": cur["area"],
                        "minutes": cur["minutes"],
                        "since": cur["since"],
                    }
                )
    return hits


def area_stats(day: str = "today") -> list[dict[str, Any]]:
    totals: dict[str, list[float]] = defaultdict(list)
    for no, meta in PATIENTS.items():
        if day not in ("all", "") and meta.get("day", "today") != day:
            continue
        tl = build_timeline(filter_records(hospital_no=no))
        if not tl.get("ok"):
            continue
        for stay in tl["stays"]:
            totals[stay["area"]].append(stay["minutes"])
    out = []
    for area, vals in totals.items():
        out.append(
            {
                "area": area,
                "patients": len(vals),
                "avgMinutes": round(sum(vals) / len(vals), 1),
                "maxMinutes": round(max(vals), 1),
            }
        )
    out.sort(key=lambda x: -x["avgMinutes"])
    return out


def channel_overview(day: str = "today") -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "locations": defaultdict(int)})
    for no, meta in PATIENTS.items():
        if day not in ("all", "") and meta.get("day", "today") != day:
            continue
        ch = meta.get("channel") or "未分型"
        grouped[ch]["count"] += 1
        grouped[ch]["locations"][meta.get("currentLocation") or "未知"] += 1
    rows = []
    for ch, info in grouped.items():
        rows.append(
            {
                "channel": ch,
                "patients": info["count"],
                "locations": dict(info["locations"]),
            }
        )
    rows.sort(key=lambda x: -x["patients"])
    return rows
