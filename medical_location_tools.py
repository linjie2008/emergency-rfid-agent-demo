"""医疗场景独立的人与资产定位模拟接口。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from langchain_core.tools import tool

from rfid_data import PATIENTS, RECORDS


NOW = datetime.now().replace(second=0, microsecond=0)
AREA_FLOORS = {
    "分诊台": "1F", "抢救室": "1F", "CT室": "1F", "DR室": "1F",
    "介入室": "2F", "卒中单元": "2F", "观察室": "1F", "手术室": "3F",
    "产房": "3F", "儿科急诊": "1F", "已离开": "院外",
}


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _result(rows, **extra):
    return _dumps({"count": len(rows), "data": rows, **extra})


CLINICAL_STAFF = [
    {"person": "林医生", "personNo": "DOC-1001", "personType": "医生", "department": "急诊科", "region": "抢救室", "floor": "1F", "online": True},
    {"person": "周医生", "personNo": "DOC-1002", "personType": "医生", "department": "介入科", "region": "介入室", "floor": "2F", "online": True},
    {"person": "王护士", "personNo": "NUR-2001", "personType": "护士", "department": "急诊科", "region": "分诊台", "floor": "1F", "online": True},
    {"person": "李护士", "personNo": "NUR-2002", "personType": "护士", "department": "急诊科", "region": "观察室", "floor": "1F", "online": True},
    {"person": "赵技师", "personNo": "TEC-3001", "personType": "医技", "department": "影像科", "region": "CT室", "floor": "1F", "online": True},
    {"person": "陈护工", "personNo": "AID-4001", "personType": "护工", "department": "护理部", "region": "卒中单元", "floor": "2F", "online": True},
]


def _patient_locations():
    rows = []
    for hospital_no, meta in PATIENTS.items():
        if meta.get("day", "today") != "today":
            continue
        region = meta.get("currentLocation") or "未知"
        rows.append({
            "person": meta["name"], "personNo": hospital_no, "personType": "患者",
            "department": meta.get("channel", "急诊"), "region": region,
            "floor": AREA_FLOORS.get(region, "1F"), "online": region != "已离开",
            "lastSeen": NOW.strftime("%Y-%m-%d %H:%M"),
        })
    return rows


MEDICAL_ASSETS = [
    {"asset": "输液泵12号", "assetNo": "YP-012", "assetType": "输液泵", "department": "急诊抢救室", "region": "抢救室", "floor": "1F", "online": True, "alarm": "无报警", "energyStatus": "运行", "useRate": 68.2},
    {"asset": "呼吸机3号", "assetNo": "HXJ-03", "assetType": "呼吸机", "department": "EICU", "region": "EICU-2床", "floor": "2F", "online": True, "alarm": "无报警", "energyStatus": "运行", "useRate": 82.5},
    {"asset": "监护仪8号", "assetNo": "JH-08", "assetType": "监护仪", "department": "急诊观察室", "region": "观察室3床", "floor": "1F", "online": False, "alarm": "离线报警", "energyStatus": "关机", "useRate": 34.6},
    {"asset": "手术床1号", "assetNo": "CT-BED-01", "assetType": "手术床", "department": "手术室", "region": "3F走廊", "floor": "3F", "online": True, "alarm": "越界报警", "energyStatus": "闲置", "useRate": 22.0},
    {"asset": "心电图机2号", "assetNo": "ECG-02", "assetType": "心电图机", "department": "急诊分诊台", "region": "分诊台", "floor": "1F", "online": True, "alarm": "低电量报警", "energyStatus": "待机", "useRate": 45.1},
    {"asset": "移动DR", "assetNo": "DR-01", "assetType": "DR", "department": "放射科", "region": "急诊抢救室", "floor": "1F", "online": True, "alarm": "无报警", "energyStatus": "运行", "useRate": 71.4},
    {"asset": "麻醉机B", "assetNo": "Y18", "assetType": "麻醉机", "department": "手术室", "region": "手术间3", "floor": "3F", "online": True, "alarm": "无报警", "energyStatus": "待机", "useRate": 18.2},
    {"asset": "婴儿保温箱1号", "assetNo": "Y30", "assetType": "婴儿保温箱", "department": "新生儿科", "region": "NICU", "floor": "4F", "online": True, "alarm": "无报警", "energyStatus": "运行", "useRate": 65.0},
]


def _asset_history(asset: str):
    row = next((item for item in MEDICAL_ASSETS if asset in {item["asset"], item["assetNo"]}), None)
    if not row:
        return []
    routes = {
        "YP-012": ["抢救室设备带", "抢救1床", "CT室", "抢救2床", "抢救室"],
        "DR-01": ["DR机房", "急诊抢救室", "观察室", "CT室门口", "急诊抢救室"],
    }
    regions = routes.get(row["assetNo"], [row["department"], row["region"]])
    return [
        {"asset": row["asset"], "assetNo": row["assetNo"], "region": region,
         "floor": row["floor"], "enterTime": (NOW - timedelta(minutes=(len(regions) - i) * 46)).strftime("%Y-%m-%d %H:%M"),
         "stayMinutes": 24 + i * 9}
        for i, region in enumerate(regions)
    ]


@tool
def query_locations_realtime(keyword: str = "", region: str = "", person_type: str = "") -> str:
    """查询医疗场景人员实时位置，可按姓名/编号、区域和人员类型筛选。"""
    rows = _patient_locations() + [dict(row, lastSeen=NOW.strftime("%Y-%m-%d %H:%M")) for row in CLINICAL_STAFF]
    selected = [row for row in rows if (not keyword or keyword in " ".join(str(v) for v in row.values())) and (not region or region in row["region"]) and (not person_type or person_type in row["personType"])]
    return _result(selected, asOf=NOW.strftime("%Y-%m-%d %H:%M"), dataSource="医疗人员定位模拟接口")


@tool
def query_locations_history(person: str, start_time: str = "", end_time: str = "") -> str:
    """查询医疗场景单人历史轨迹，接口字段与人员安全场景一致。"""
    patient_rows = [row for row in RECORDS if person in {row.get("patientName"), row.get("hospitalNo")}]
    if patient_rows:
        rows = [{"person": row["patientName"], "region": row["areaName"], "enterTime": row["createTime"][:16], "stayMinutes": 8 + i * 3} for i, row in enumerate(patient_rows)]
    else:
        base = next((row for row in CLINICAL_STAFF if person in {row["person"], row["personNo"]}), None)
        route = ["员工通道", "更衣区", base["department"] if base else "急诊科", base["region"] if base else "未知"]
        rows = [{"person": person, "region": region, "enterTime": (NOW - timedelta(minutes=180 - i * 48)).strftime("%Y-%m-%d %H:%M"), "stayMinutes": 32 + i * 7} for i, region in enumerate(route)]
    return _result(rows, person=person, dataSource="医疗人员定位模拟接口")


@tool
def query_region_enter_leave(person: str, region: str = "") -> str:
    """查询医疗场景单人区域进出明细。"""
    payload = json.loads(query_locations_history.invoke({"person": person}))
    rows = [row for row in payload["data"] if not region or region in row["region"]]
    return _result(rows, person=person)


@tool
def query_asset_locations_realtime(keyword: str = "", region: str = "", asset_type: str = "") -> str:
    """查询医疗资产实时位置，可按名称/编号、区域和资产类型筛选。"""
    rows = [dict(row, status="正常" if row["online"] and row["alarm"] == "无报警" else row["alarm"], lastSeen=NOW.strftime("%Y-%m-%d %H:%M")) for row in MEDICAL_ASSETS]
    selected = [row for row in rows if (not keyword or keyword in " ".join(str(v) for v in row.values())) and (not region or region in row["region"]) and (not asset_type or asset_type in row["assetType"])]
    return _result(selected, asOf=NOW.strftime("%Y-%m-%d %H:%M"), dataSource="医疗资产定位模拟接口")


@tool
def query_asset_locations_history(asset: str, start_time: str = "", end_time: str = "") -> str:
    """查询医疗资产历史位置与区域停留。"""
    return _result(_asset_history(asset), asset=asset, dataSource="医疗资产定位模拟接口")


@tool
def query_asset_region_enter_leave(asset: str, region: str = "") -> str:
    """查询医疗资产区域进出明细。"""
    rows = [row for row in _asset_history(asset) if not region or region in row["region"]]
    return _result(rows, asset=asset)


@tool
def list_assets(keyword: str = "", dept: str = "", alarm: str = "", asset_type: str = "") -> str:
    """查询医疗设备资产清单。"""
    rows = [row for row in MEDICAL_ASSETS if (not keyword or keyword in " ".join(str(v) for v in row.values())) and (not dept or dept in row["department"]) and (not alarm or alarm in row["alarm"]) and (not asset_type or asset_type in row["assetType"])]
    return _result(rows)


@tool
def locate_asset(keyword: str) -> str:
    """查询单台医疗设备当前所在区域。"""
    rows = json.loads(query_asset_locations_realtime.invoke({"keyword": keyword}))["data"]
    return _dumps({"ok": len(rows) == 1, "data": rows[0] if len(rows) == 1 else None, "candidates": rows if len(rows) != 1 else []})


@tool
def list_asset_alarms() -> str:
    """查询当前存在离线、低电量或越界报警的医疗设备。"""
    rows = [row for row in MEDICAL_ASSETS if row["alarm"] != "无报警"]
    return _result(rows)


@tool
def analyze_energy(dept: str = "", status: str = "") -> str:
    """分析医疗设备运行状态与使用率。"""
    rows = [row for row in MEDICAL_ASSETS if (not dept or dept in row["department"]) and (not status or status in row["energyStatus"])]
    return _result(rows, avgUseRate=round(sum(row["useRate"] for row in rows) / len(rows), 1) if rows else 0)


@tool
def get_asset_power(keyword: str) -> str:
    """查询医疗设备近 7 日模拟耗电。"""
    asset = next((row for row in MEDICAL_ASSETS if keyword in {row["asset"], row["assetNo"]}), None)
    if not asset:
        return _dumps({"ok": False, "message": "未找到医疗设备"})
    daily = [{"date": (NOW.date() - timedelta(days=i)).isoformat(), "electricQuantity": round(3.6 + ((i + len(keyword)) % 7) * 0.8, 1)} for i in range(6, -1, -1)]
    return _dumps({"ok": True, "device": asset, "daily": daily, "total": round(sum(row["electricQuantity"] for row in daily), 1)})


@tool
def get_asset_track(keyword: str) -> str:
    """查询医疗设备历史轨迹与区域停留。"""
    rows = _asset_history(keyword)
    return _dumps({"ok": bool(rows), "stays": rows, "asset": keyword})


MEDICAL_LOCATION_TOOLS = [
    query_locations_realtime, query_locations_history, query_region_enter_leave,
    query_asset_locations_realtime, query_asset_locations_history, query_asset_region_enter_leave,
    list_assets, locate_asset, list_asset_alarms, analyze_energy, get_asset_power, get_asset_track,
]
