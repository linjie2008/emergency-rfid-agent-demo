"""政企智慧楼宇模拟数据与智能体工具。

数据域依据《长隆项目-综合监控与可视化管理系统-系统接口 V1.2》整理，
与医疗、人员安全场景的数据模块完全分离。
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(fn):
        fn.invoke = lambda args=None, **kwargs: fn(**(args or {}), **kwargs)
        fn.name = fn.__name__
        fn.description = (fn.__doc__ or "").strip()
        return fn


NOW = datetime.now().replace(second=0, microsecond=0)
FLOORS = ["B2", "B1", *[f"{i}F" for i in range(1, 16)]]


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _result(rows, **extra):
    return _dumps({"count": len(rows), "data": rows, **extra})


def _match(rows, keyword: str = "", **filters):
    selected = []
    for row in rows:
        if keyword and keyword not in " ".join(str(value) for value in row.values()):
            continue
        if any(value and str(value) not in str(row.get(key, "")) for key, value in filters.items()):
            continue
        selected.append(row)
    return selected


POWER_METERS = []
for i, floor in enumerate(FLOORS):
    for category, base_kw in (("空调", 86), ("照明", 28), ("动力", 54), ("其他", 17)):
        load = round(base_kw * (0.58 + ((i * 7 + len(category)) % 31) / 100), 1)
        POWER_METERS.append({
            "meterId": f"PM-{i + 1:02d}-{category}", "floor": floor, "category": category,
            "voltageV": round(379 + (i % 5) * 0.8, 1), "currentA": round(load * 1.52, 1),
            "activePowerKw": load, "reactivePowerKvar": round(load * 0.19, 1),
            "powerFactor": round(0.91 + (i % 6) * 0.01, 2),
            "voltageThdPct": round(1.4 + (i % 4) * 0.3, 1),
            "currentThdPct": round(2.1 + (i % 5) * 0.4, 1), "status": "正常",
        })

ENERGY_TREND = []
for days_ago in range(31):
    day = NOW.date() - timedelta(days=days_ago)
    total = round(11840 + ((day.toordinal() * 137) % 2800), 1)
    ENERGY_TREND.append({
        "date": day.isoformat(), "totalKwh": total,
        "airConditioningKwh": round(total * 0.38, 1), "lightingKwh": round(total * 0.19, 1),
        "officeKwh": round(total * 0.31, 1), "otherKwh": round(total * 0.12, 1),
        "pue": round(1.38 + days_ago % 5 * 0.02, 2), "euiKwhPerM2": round(total / 68000, 3),
    })

HVAC_UNITS = [
    {"unitId": f"AHU-{i:02d}", "name": f"{floor}空调机组", "floor": floor,
     "supplyAirTempC": round(17.1 + i % 4 * 0.6, 1), "returnAirTempC": round(24.0 + i % 3 * 0.7, 1),
     "chilledWaterSupplyC": round(7.0 + i % 3 * 0.2, 1), "chilledWaterReturnC": round(12.0 + i % 4 * 0.3, 1),
     "loadPct": 52 + i % 7 * 6, "eer": round(3.4 + i % 4 * 0.15, 2),
     "fanStatus": "运行", "status": "告警" if i == 9 else "正常"}
    for i, floor in enumerate(FLOORS[2:], 1)
]

WATER_SYSTEMS = [
    {"pointId": "WS-01", "name": "生活水池", "location": "B2泵房", "type": "给水", "levelPct": 72, "pressureMpa": 0.42, "flowM3h": 38.6, "pumpStatus": "运行", "status": "正常"},
    {"pointId": "WS-02", "name": "高区供水泵组", "location": "B2泵房", "type": "给水", "levelPct": None, "pressureMpa": 0.86, "flowM3h": 27.4, "pumpStatus": "运行", "status": "正常"},
    {"pointId": "WS-03", "name": "消防水池", "location": "B2消防泵房", "type": "消防", "levelPct": 91, "pressureMpa": 0.68, "flowM3h": 0, "pumpStatus": "待机", "status": "正常"},
    {"pointId": "WS-04", "name": "污水提升泵", "location": "B1西区", "type": "排水", "levelPct": 84, "pressureMpa": 0.18, "flowM3h": 11.2, "pumpStatus": "运行", "status": "液位偏高"},
]

LIGHTING = [
    {"floor": floor, "circuits": 18 + i * 2, "onCircuits": 8 + i, "mode": "节能" if i % 3 else "自动",
     "illuminanceLux": 310 + i * 9, "occupancySensorsOnline": 12 + i,
     "dimmingPct": 45 + i % 5 * 10, "status": "正常"}
    for i, floor in enumerate(FLOORS)
]

SOLAR_ARRAYS = [
    {"arrayId": f"PV-{i:02d}", "name": f"屋顶光伏阵列{i}区", "capacityKwp": 180,
     "dcPowerKw": round(112 + i * 8.4, 1), "acPowerKw": round((112 + i * 8.4) * 0.96, 1),
     "todayKwh": round(486 + i * 31.7, 1), "status": "正常" if i != 4 else "效率偏低"}
    for i in range(1, 7)
]

CHARGING_PILES = [
    {"pileId": f"CP-{i:03d}", "location": "B1充电区" if i <= 12 else "B2充电区",
     "type": "交流", "ratedPowerKw": 7, "status": ("充电中" if i % 4 == 0 else "空闲" if i % 7 else "故障"),
     "todayKwh": round(8.2 + i * 1.7, 1), "todayRevenueYuan": round((8.2 + i * 1.7) * 1.25, 2),
     "connectorStatus": "已连接" if i % 4 == 0 else "未连接", "temperatureC": 31 + i % 8}
    for i in range(1, 25)
]

DATA_ROOM = [
    {"deviceId": "IDC-ENV-01", "name": "主机房环境", "room": "4F数据机房", "type": "环境", "temperatureC": 23.4, "humidityPct": 46, "leak": False, "door": "关闭", "status": "正常"},
    {"deviceId": "IDC-UPS-01", "name": "1号UPS", "room": "4F数据机房", "type": "UPS", "loadPct": 61, "batteryMinutes": 48, "status": "正常"},
    {"deviceId": "IDC-UPS-02", "name": "2号UPS", "room": "4F数据机房", "type": "UPS", "loadPct": 73, "batteryMinutes": 41, "status": "关注"},
    {"deviceId": "IDC-STO-01", "name": "核心存储阵列", "room": "4F数据机房", "type": "存储", "cpuPct": 42, "memoryPct": 58, "ioPct": 66, "storageUsedPct": 71, "status": "正常"},
    {"deviceId": "IDC-FW-01", "name": "边界防火墙", "room": "4F数据机房", "type": "网络安全", "cpuPct": 39, "memoryPct": 52, "sessions": 18420, "status": "正常"},
]

PARKING_ZONES = [
    {"zoneId": "PK-B1-A", "floor": "B1", "zone": "A区", "totalSpaces": 128, "occupiedSpaces": 96, "availableSpaces": 32, "status": "正常"},
    {"zoneId": "PK-B1-B", "floor": "B1", "zone": "B区", "totalSpaces": 116, "occupiedSpaces": 109, "availableSpaces": 7, "status": "接近满位"},
    {"zoneId": "PK-B2-A", "floor": "B2", "zone": "A区", "totalSpaces": 142, "occupiedSpaces": 87, "availableSpaces": 55, "status": "正常"},
    {"zoneId": "PK-B2-B", "floor": "B2", "zone": "B区", "totalSpaces": 134, "occupiedSpaces": 101, "availableSpaces": 33, "status": "正常"},
]

ELEVATORS = [
    {"elevatorId": f"EL-{i:02d}", "name": f"{i}号电梯", "group": "高区" if i > 10 else "低区",
     "currentFloor": f"{(i * 3) % 15 + 1}F", "direction": "上行" if i % 3 == 0 else "下行" if i % 3 == 1 else "停止",
     "door": "关闭" if i % 4 else "开启", "todayTrips": 126 + i * 11,
     "todayKm": round(8.4 + i * 0.47, 1), "status": "异常" if i == 17 else "正常"}
    for i in range(1, 21)
]

ACCESS_POINTS = [
    {"pointId": f"AC-{i:02d}", "floor": floor, "name": f"{floor}电梯厅门禁", "door": "关闭",
     "controllerOnline": i != 12, "todayPasses": 86 + i * 37,
     "status": "离线" if i == 12 else "正常"}
    for i, floor in enumerate(FLOORS[2:], 1)
]

FIRE_LINKAGE = [
    {"floor": floor, "firePanel": "正常", "smokeDetectors": 38 + i * 2, "activeAlarms": 1 if floor == "9F" else 0,
     "freshAirLinkage": "已联动" if floor == "9F" else "待命", "hvacLinkage": "已关闭" if floor == "9F" else "正常运行",
     "status": "火警确认中" if floor == "9F" else "正常"}
    for i, floor in enumerate(FLOORS[2:], 1)
]

PATROLS = [
    {"planId": f"PT-{i:03d}", "route": route, "guard": guard, "plannedPoints": points,
     "completedPoints": points if i != 3 else points - 2, "startTime": (NOW - timedelta(hours=i + 1)).strftime("%Y-%m-%d %H:%M"),
     "status": "已完成" if i != 3 else "执行中"}
    for i, (route, guard, points) in enumerate([
        ("地下设备层巡更线", "刘海峰", 18), ("办公楼层巡更线", "陈志远", 24),
        ("屋面与光伏巡更线", "王建军", 12), ("消防重点部位巡更线", "赵明", 21),
    ], 1)
]

VISITORS = [
    {"visitId": f"VIS-{i:04d}", "visitor": name, "company": company, "host": host,
     "purpose": purpose, "checkIn": (NOW - timedelta(minutes=35 * i)).strftime("%Y-%m-%d %H:%M"),
     "status": "在访" if i % 3 else "已离场"}
    for i, (name, company, host, purpose) in enumerate([
        ("周宁", "南方电网", "何磊", "能源系统交流"), ("李悦", "智慧城市研究院", "林杰", "项目调研"),
        ("陈浩", "设备服务有限公司", "顾金龙", "设备维保"), ("张琳", "产业合作集团", "曹伟荣", "商务会议"),
        ("王凯", "消防检测中心", "赵明", "消防检查"), ("刘洋", "信息技术有限公司", "夏志明", "机房服务"),
    ], 1)
]

BUILDING_PEOPLE = [
    {"person": name, "personNo": f"BLD-E{i:04d}", "personType": person_type, "department": department,
     "region": region, "floor": floor, "online": True,
     "lastSeen": (NOW - timedelta(minutes=i % 6)).strftime("%Y-%m-%d %H:%M")}
    for i, (name, person_type, department, region, floor) in enumerate([
        ("何磊", "员工", "信息技术部", "综合监控中心", "3F"),
        ("林杰", "员工", "设施运营部", "空调监控室", "B2"),
        ("顾金龙", "员工", "能源管理部", "配电监控室", "B1"),
        ("曹伟荣", "员工", "行政管理部", "大会议室", "8F"),
        ("夏志明", "员工", "信息技术部", "数据机房", "4F"),
        ("刘海峰", "安保", "安全保卫部", "B1停车场", "B1"),
        ("陈志远", "安保", "安全保卫部", "一楼大厅", "1F"),
        ("王建军", "维保", "设施运营部", "屋面光伏区", "15F"),
        ("赵明", "消防值守", "安全保卫部", "9F消防前室", "9F"),
        ("李颖", "前台", "行政管理部", "访客中心", "1F"),
    ], 1)
] + [
    {"person": row["visitor"], "personNo": row["visitId"], "personType": "访客", "department": row["company"],
     "region": ["一楼展厅", "大会议室", "设备层", "接待室"][i % 4], "floor": ["1F", "8F", "B1", "5F"][i % 4],
     "online": row["status"] == "在访", "lastSeen": row["checkIn"]}
    for i, row in enumerate(VISITORS)
]

ALARMS = [
    {"alarmId": "BLD-A001", "system": "智慧空调", "device": "9F空调机组", "point": "回风温度", "value": "27.8℃", "level": "一般", "time": (NOW - timedelta(minutes=52)).strftime("%Y-%m-%d %H:%M"), "location": "9F", "handled": False},
    {"alarmId": "BLD-A002", "system": "给排水", "device": "污水提升泵", "point": "集水坑液位", "value": "84%", "level": "较重", "time": (NOW - timedelta(minutes=37)).strftime("%Y-%m-%d %H:%M"), "location": "B1西区", "handled": False},
    {"alarmId": "BLD-A003", "system": "充电桩", "device": "CP-007", "point": "通信状态", "value": "离线", "level": "一般", "time": (NOW - timedelta(minutes=29)).strftime("%Y-%m-%d %H:%M"), "location": "B1充电区", "handled": True},
    {"alarmId": "BLD-A004", "system": "数据机房", "device": "2号UPS", "point": "负载率", "value": "73%", "level": "提示", "time": (NOW - timedelta(minutes=18)).strftime("%Y-%m-%d %H:%M"), "location": "4F数据机房", "handled": False},
    {"alarmId": "BLD-A005", "system": "智能门禁", "device": "12F门禁控制器", "point": "在线状态", "value": "离线", "level": "较重", "time": (NOW - timedelta(minutes=12)).strftime("%Y-%m-%d %H:%M"), "location": "12F", "handled": False},
    {"alarmId": "BLD-A006", "system": "消防联动", "device": "9F烟感回路", "point": "烟感预警", "value": "确认中", "level": "严重", "time": (NOW - timedelta(minutes=6)).strftime("%Y-%m-%d %H:%M"), "location": "9F", "handled": False},
    {"alarmId": "BLD-A007", "system": "智慧电梯", "device": "17号电梯", "point": "门机状态", "value": "异常", "level": "较重", "time": (NOW - timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M"), "location": "高区", "handled": False},
]

ASSETS = []
for rows, system in (
    (HVAC_UNITS, "智慧空调"), (WATER_SYSTEMS, "给排水"), (SOLAR_ARRAYS, "光伏发电"),
    (CHARGING_PILES, "充电桩"), (DATA_ROOM, "数据机房"), (ELEVATORS, "智慧电梯"),
    (ACCESS_POINTS, "智能门禁"),
):
    for index, row in enumerate(rows, 1):
        asset_id = row.get("unitId") or row.get("pointId") or row.get("arrayId") or row.get("pileId") or row.get("deviceId") or row.get("elevatorId")
        ASSETS.append({
            "assetId": asset_id, "name": row.get("name") or asset_id, "system": system,
            "location": row.get("floor") or row.get("location") or row.get("room") or "总部大楼",
            "model": f"CL-{system[:2].upper()}-{index:03d}", "vendor": "示范设备厂商",
            "commissionedAt": f"20{18 + index % 7}-0{index % 9 + 1}-15",
            "status": row.get("status", "正常"),
        })

MAINTENANCE = [
    {"workOrderId": f"MT-{i:04d}", "assetId": asset["assetId"], "assetName": asset["name"],
     "system": asset["system"], "location": asset["location"], "frequency": "每季度" if i % 3 else "每月",
     "lastMaintenance": (NOW.date() - timedelta(days=18 + i % 36)).isoformat(),
     "nextMaintenance": (NOW.date() + timedelta(days=i % 12 - 3)).isoformat(),
     "method": "运行检查、清洁与关键参数校验", "maintainer": ["陈志远", "王建军", "刘海峰"][i % 3],
     "dueStatus": "逾期" if i % 12 < 3 else "即将到期" if i % 12 < 6 else "正常"}
    for i, asset in enumerate(ASSETS[:36], 1)
]


@tool
def summarize_building_operations() -> str:
    """汇总总部大楼综合运营态势：能耗、设备、告警、停车、电梯、光伏和访客。"""
    return _dumps({
        "asOf": NOW.strftime("%Y-%m-%d %H:%M"), "building": "总部大楼", "floors": 17,
        "todayEnergyKwh": ENERGY_TREND[0]["totalKwh"], "pue": ENERGY_TREND[0]["pue"],
        "solarPowerKw": round(sum(row["acPowerKw"] for row in SOLAR_ARRAYS), 1),
        "availableParkingSpaces": sum(row["availableSpaces"] for row in PARKING_ZONES),
        "elevatorsNormal": sum(row["status"] == "正常" for row in ELEVATORS),
        "visitorsOnSite": sum(row["status"] == "在访" for row in VISITORS),
        "activeAlarms": sum(not row["handled"] for row in ALARMS),
        "systems": 19, "dataSource": "政企楼宇综合监控模拟接口",
    })


@tool
def query_building_power(floor: str = "", category: str = "", status: str = "") -> str:
    """查询楼宇电力实时监测数据，包括电压、电流、功率、功率因数和谐波。"""
    return _result(_match(POWER_METERS, "", floor=floor, category=category, status=status), asOf=NOW.strftime("%Y-%m-%d %H:%M"))


@tool
def query_building_energy(days: int = 7) -> str:
    """查询楼宇用电趋势、空调/照明/办公分项能耗、PUE 和 EUI。"""
    rows = list(reversed(ENERGY_TREND[:max(1, min(days, 31))]))
    return _result(rows, totalKwh=round(sum(row["totalKwh"] for row in rows), 1))


@tool
def query_hvac_status(floor: str = "", status: str = "") -> str:
    """查询智慧空调机组温度、水温、负载、EER 和运行状态。"""
    return _result(_match(HVAC_UNITS, "", floor=floor, status=status))


@tool
def query_water_system(system_type: str = "", status: str = "") -> str:
    """查询给排水实时用量、液位、压力、流量和水泵状态。"""
    return _result(_match(WATER_SYSTEMS, "", type=system_type, status=status))


@tool
def query_lighting_status(floor: str = "", mode: str = "") -> str:
    """查询各楼层照明回路、开灯数量、照度、人体感应和调光模式。"""
    return _result(_match(LIGHTING, "", floor=floor, mode=mode))


@tool
def query_solar_generation(status: str = "") -> str:
    """查询光伏阵列装机容量、交直流功率、当日发电量和运行状态。"""
    rows = _match(SOLAR_ARRAYS, "", status=status)
    return _result(rows, totalCapacityKwp=sum(row["capacityKwp"] for row in rows), todayKwh=round(sum(row["todayKwh"] for row in rows), 1))


@tool
def query_charging_piles(status: str = "", location: str = "") -> str:
    """查询充电桩状态、电量、营收、接口连接状态和温度。"""
    rows = _match(CHARGING_PILES, "", status=status, location=location)
    return _result(rows, statusSummary=dict(Counter(row["status"] for row in rows)))


@tool
def query_data_room(device_type: str = "", status: str = "") -> str:
    """查询数据机房环境、UPS、存储、网络设备的实时监测数据。"""
    return _result(_match(DATA_ROOM, "", type=device_type, status=status))


@tool
def query_parking_status(floor: str = "", status: str = "") -> str:
    """查询停车分区总车位、占用和空余车位。"""
    rows = _match(PARKING_ZONES, "", floor=floor, status=status)
    return _result(rows, totalSpaces=sum(row["totalSpaces"] for row in rows), availableSpaces=sum(row["availableSpaces"] for row in rows))


@tool
def query_elevator_status(status: str = "", group: str = "") -> str:
    """查询 20 部电梯的楼层、方向、门状态、运行里程和异常。"""
    return _result(_match(ELEVATORS, "", status=status, group=group))


@tool
def query_security_operations(system: str = "全部", status: str = "") -> str:
    """查询门禁、巡更和访客安全运营数据；system 支持门禁、巡更、访客或全部。"""
    payload = {}
    if system in {"", "全部", "门禁"}:
        payload["access"] = _match(ACCESS_POINTS, "", status=status)
    if system in {"", "全部", "巡更"}:
        payload["patrols"] = _match(PATROLS, "", status=status)
    if system in {"", "全部", "访客"}:
        payload["visitors"] = _match(VISITORS, "", status=status)
    return _dumps({"system": system or "全部", "data": payload})


def _building_person_history(person: str):
    found = next((row for row in BUILDING_PEOPLE if person in {row["person"], row["personNo"]}), None)
    if not found:
        return []
    route = ["一楼入口", "访客/员工闸机", "电梯厅", found["region"]]
    return [{"person": found["person"], "personNo": found["personNo"], "region": region,
             "enterTime": (NOW - timedelta(minutes=165 - i * 43)).strftime("%Y-%m-%d %H:%M"),
             "stayMinutes": 20 + i * 12} for i, region in enumerate(route)]


def _building_asset_history(asset: str):
    found = next((row for row in ASSETS if asset in {row["name"], row["assetId"]}), None)
    if not found:
        return []
    regions = ["设备库", "维修工作间", str(found["location"])]
    return [{"asset": found["name"], "assetNo": found["assetId"], "region": region,
             "enterTime": (NOW - timedelta(minutes=138 - i * 49)).strftime("%Y-%m-%d %H:%M"),
             "stayMinutes": 31 + i * 14} for i, region in enumerate(regions)]


@tool
def query_locations_realtime(keyword: str = "", region: str = "", person_type: str = "") -> str:
    """查询政企楼宇人员实时位置，可按姓名/编号、区域和人员类型筛选。"""
    rows = [row for row in BUILDING_PEOPLE if (not keyword or keyword in " ".join(str(v) for v in row.values())) and (not region or region in row["region"]) and (not person_type or person_type in row["personType"])]
    return _result(rows, asOf=NOW.strftime("%Y-%m-%d %H:%M"), dataSource="政企楼宇人员定位模拟接口")


@tool
def query_locations_history(person: str, start_time: str = "", end_time: str = "") -> str:
    """查询政企楼宇单人历史轨迹，接口字段与人员安全场景一致。"""
    return _result(_building_person_history(person), person=person, dataSource="政企楼宇人员定位模拟接口")


@tool
def query_region_enter_leave(person: str, region: str = "") -> str:
    """查询政企楼宇单人区域进出明细。"""
    rows = [row for row in _building_person_history(person) if not region or region in row["region"]]
    return _result(rows, person=person)


@tool
def query_asset_locations_realtime(keyword: str = "", region: str = "", asset_type: str = "") -> str:
    """查询政企楼宇资产实时位置，可按名称/编号、区域和资产类型筛选。"""
    rows = [{"asset": row["name"], "assetNo": row["assetId"], "assetType": row["system"],
             "department": "楼宇设施运营部", "region": str(row["location"]), "floor": str(row["location"]).split(" ")[0],
             "online": row["status"] not in {"离线", "异常"}, "status": row["status"],
             "lastSeen": NOW.strftime("%Y-%m-%d %H:%M")} for row in ASSETS]
    selected = [row for row in rows if (not keyword or keyword in " ".join(str(v) for v in row.values())) and (not region or region in row["region"]) and (not asset_type or asset_type in row["assetType"])]
    return _result(selected, asOf=NOW.strftime("%Y-%m-%d %H:%M"), dataSource="政企楼宇资产定位模拟接口")


@tool
def query_asset_locations_history(asset: str, start_time: str = "", end_time: str = "") -> str:
    """查询政企楼宇资产历史位置与区域停留。"""
    return _result(_building_asset_history(asset), asset=asset, dataSource="政企楼宇资产定位模拟接口")


@tool
def query_asset_region_enter_leave(asset: str, region: str = "") -> str:
    """查询政企楼宇资产区域进出明细。"""
    rows = [row for row in _building_asset_history(asset) if not region or region in row["region"]]
    return _result(rows, asset=asset)


@tool
def query_fire_linkage(floor: str = "", status: str = "") -> str:
    """查询各楼层消防状态以及与空调、新风系统的联动状态。"""
    return _result(_match(FIRE_LINKAGE, "", floor=floor, status=status))


@tool
def query_building_alarms(system: str = "", level: str = "", handled: str = "") -> str:
    """查询楼宇各子系统告警，可按系统、等级和处理状态筛选。"""
    rows = _match(ALARMS, "", system=system, level=level)
    if handled:
        expected = handled.lower() in {"true", "1", "yes", "已处理"}
        rows = [row for row in rows if row["handled"] == expected]
    return _result(rows, activeCount=sum(not row["handled"] for row in rows))


@tool
def query_building_assets(system: str = "", keyword: str = "", status: str = "") -> str:
    """查询政企楼宇独立资产台账：设备编号、系统、位置、型号、厂商和投用时间。"""
    return _result(_match(ASSETS, keyword, system=system, status=status))


@tool
def query_building_maintenance(system: str = "", due_status: str = "") -> str:
    """查询楼宇设备维护计划、最近/下次维护时间、方法、人员和到期状态。"""
    return _result(_match(MAINTENANCE, "", system=system, dueStatus=due_status))


@tool
def get_building_emergency_response(alarm_id: str = "") -> str:
    """根据楼宇告警生成事故点定位、联动状态、视频调度和应急处置建议。"""
    alarm = next((row for row in ALARMS if row["alarmId"] == alarm_id), None) if alarm_id else next((row for row in ALARMS if not row["handled"]), None)
    if not alarm:
        return _dumps({"ok": False, "message": "未找到待处置告警"})
    return _dumps({
        "ok": True, "alarm": alarm, "nearbyCamera": f"{alarm['location']}走廊摄像机",
        "voiceDispatchGroup": "楼宇应急处置组", "materials": ["应急照明", "警戒带", "便携检测仪"],
        "steps": ["值班人员复核告警", "调取事故点视频", "通知现场处置组", "按预案执行联动", "记录处置结果并复盘"],
        "notice": "演示研判结果，实际处置以现场预案和值班负责人指令为准。",
    })


BUILDING_TOOLS = [
    summarize_building_operations, query_building_power, query_building_energy,
    query_hvac_status, query_water_system, query_lighting_status, query_solar_generation,
    query_charging_piles, query_data_room, query_parking_status, query_elevator_status,
    query_security_operations, query_fire_linkage, query_building_alarms,
    query_building_assets, query_building_maintenance, get_building_emergency_response,
    query_locations_realtime, query_locations_history, query_region_enter_leave,
    query_asset_locations_realtime, query_asset_locations_history, query_asset_region_enter_leave,
]

BUILDING_TOOL_BY_NAME = {item.name: item for item in BUILDING_TOOLS}
