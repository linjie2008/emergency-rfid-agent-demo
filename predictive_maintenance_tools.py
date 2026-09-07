"""能源设备预测性维护演示数据与智能体工具。"""

from __future__ import annotations

import json
import math
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


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


ASSET_TEMPLATES = [
    ("北区热电厂", "汽轮机", "1号汽轮机#2轴承", "振动偏高", "振动", "mm/s", 7.1, 7.5, 9.0),
    ("北区热电厂", "锅炉辅机", "2号炉引风机A", "轴承温升", "轴承温度", "℃", 78.4, 80.0, 90.0),
    ("北区热电厂", "给水系统", "1号给水泵B", "机械密封磨损", "振动", "mm/s", 5.8, 6.3, 7.1),
    ("南区电厂", "发电机", "3号发电机定子", "绝缘劣化", "局放量", "pC", 126.0, 150.0, 220.0),
    ("南区电厂", "磨煤系统", "3号炉磨煤机C", "齿轮磨损", "振动", "mm/s", 8.3, 8.8, 10.2),
    ("开发区220kV变电站", "主变压器", "1号主变", "油色谱异常", "总烃", "μL/L", 112.0, 150.0, 250.0),
    ("北工业园110kV变电站", "主变压器", "2号主变", "绕组热点温升", "热点温度", "℃", 91.6, 95.0, 105.0),
    ("北工业园110kV变电站", "高压开关", "110kV母联断路器", "操作机构卡涩", "分闸线圈电流", "A", 4.8, 5.2, 6.0),
    ("开发区供热站", "热网循环泵", "循环泵P-03", "叶轮汽蚀", "振动", "mm/s", 6.4, 7.1, 8.5),
    ("南区调峰锅炉房", "燃烧系统", "2号燃烧器", "空燃比漂移", "排烟氧量", "%", 5.9, 6.5, 8.0),
    ("开发区门站", "燃气压缩机", "压缩机C-02", "轴承磨损", "振动", "mm/s", 7.7, 8.0, 9.2),
    ("光伏示范站", "光伏逆变器", "逆变器A-07", "功率模块老化", "模块温度", "℃", 73.5, 78.0, 88.0),
]


HEALTH_RECORDS: list[dict[str, Any]] = []
for i in range(36):
    site, asset_type, base_name, failure_mode, metric, unit, base, warning, critical = ASSET_TEMPLATES[i % len(ASSET_TEMPLATES)]
    cycle = i // len(ASSET_TEMPLATES)
    score = max(42, 96 - (i * 7 % 49) - cycle * 2)
    anomaly = round(max(0.04, min(0.96, (100 - score) / 70 + (i % 5) * 0.035)), 2)
    probability = round(max(3.0, min(92.0, anomaly * 91 + (i % 4) * 2.2)), 1)
    level = "高" if probability >= 65 else ("中" if probability >= 35 else "低")
    suffix = "" if cycle == 0 else f"-{cycle + 1}"
    asset_id = f"PM-{i + 1:03d}"
    current = round(base * (0.91 + (i % 7) * 0.025), 2)
    HEALTH_RECORDS.append({
        "assetId": asset_id,
        "assetName": f"{base_name}{suffix}",
        "site": site,
        "assetType": asset_type,
        "healthScore": score,
        "healthStatus": "需检修" if score < 60 else ("关注" if score < 80 else "健康"),
        "riskLevel": level,
        "anomalyScore": anomaly,
        "predictedFailureMode": failure_mode,
        "failureProbabilityPct": probability,
        "predictionHorizonDays": 30,
        "remainingUsefulLifeDays": max(12, int(420 * score / 100 - i * 2.3)),
        "primaryMetric": metric,
        "currentValue": current,
        "unit": unit,
        "warningThreshold": warning,
        "criticalThreshold": critical,
        "trend": "上升" if i % 4 != 0 else "平稳",
        "modelConfidencePct": round(84.2 + (i % 8) * 1.6, 1),
        "lastInspectionAt": (NOW - timedelta(days=i % 18, hours=i % 9)).strftime("%Y-%m-%d %H:%M"),
        "lastUpdatedAt": (NOW - timedelta(minutes=i % 12)).strftime("%Y-%m-%d %H:%M"),
    })


TERMINAL_TYPES = [
    ("无线振动监测终端", "LoRaWAN", "振动/包络/转速", 10),
    ("无线温度监测终端", "LoRaWAN", "温度", 30),
    ("电机电流采集终端", "Modbus TCP", "三相电流/功率", 5),
    ("局放在线监测终端", "IEC 61850", "局放量/相位", 1),
    ("油色谱在线监测终端", "IEC 61850", "H2/CH4/C2H2/总烃", 60),
    ("压力流量监测终端", "NB-IoT", "压力/流量/温度", 15),
    ("红外测温终端", "以太网", "最高温/温差", 10),
    ("设备边缘智能网关", "5G/以太网", "多传感器融合", 1),
]

MONITORING_TERMINALS: list[dict[str, Any]] = []
for i in range(72):
    terminal_type, protocol, metrics, interval = TERMINAL_TYPES[i % len(TERMINAL_TYPES)]
    asset = HEALTH_RECORDS[i % len(HEALTH_RECORDS)]
    offline = i in {17, 46, 63}
    weak = i in {8, 29, 51, 68}
    battery = None if "在线" in terminal_type or "网关" in terminal_type or protocol in {"IEC 61850", "Modbus TCP", "以太网"} else max(12, 98 - (i * 9 % 91))
    signal = 0 if offline else (42 + (i * 11 % 54))
    quality = 0 if offline else round(91.2 + (i % 9) * 0.9 - (5 if weak else 0), 1)
    status = "离线" if offline else ("信号弱" if weak else "在线")
    alarm = "通信中断" if offline else ("低电量" if battery is not None and battery < 20 else ("信号质量低" if weak else "无"))
    MONITORING_TERMINALS.append({
        "terminalId": f"PDT-{i + 1:04d}",
        "terminalName": f"{terminal_type}-{i + 1:02d}",
        "terminalType": terminal_type,
        "site": asset["site"],
        "boundAssetId": asset["assetId"],
        "boundAssetName": asset["assetName"],
        "protocol": protocol,
        "metrics": metrics,
        "sampleIntervalSeconds": interval,
        "onlineStatus": status,
        "signalStrengthPct": signal,
        "batteryPct": battery,
        "dataQualityPct": quality,
        "firmwareVersion": f"v2.{i % 6}.{3 + i % 10}",
        "ipAddress": f"10.26.{i // 250 + 10}.{i % 250 + 1}" if protocol not in {"LoRaWAN", "NB-IoT"} else "",
        "installedAt": (NOW - timedelta(days=80 + i * 7)).strftime("%Y-%m-%d"),
        "lastCalibrationAt": (NOW - timedelta(days=8 + i % 95)).strftime("%Y-%m-%d"),
        "lastSeenAt": (NOW - timedelta(hours=3 + i % 8) if offline else NOW - timedelta(minutes=i % 9)).strftime("%Y-%m-%d %H:%M"),
        "alarm": alarm,
    })


def _filter(keyword: str = "", asset_type: str = "", risk_level: str = "") -> list[dict[str, Any]]:
    rows = HEALTH_RECORDS
    if keyword:
        rows = [row for row in rows if keyword.lower() in " ".join(str(v) for v in row.values()).lower()]
    if asset_type:
        rows = [row for row in rows if asset_type in row["assetType"]]
    if risk_level:
        rows = [row for row in rows if risk_level == row["riskLevel"]]
    return rows


def _resolve_asset(asset_id: str = "", keyword: str = "") -> dict[str, Any] | None:
    needle = asset_id or keyword
    if not needle:
        return None
    return next((row for row in HEALTH_RECORDS if needle.lower() in f"{row['assetId']} {row['assetName']}".lower()), None)


@tool
def query_predictive_monitoring_terminals(keyword: str = "", terminal_type: str = "", online_status: str = "") -> str:
    """查询预测性维护监测终端，包括绑定设备、协议、采样频率、在线状态、信号、电量、数据质量和校准时间。"""
    rows = MONITORING_TERMINALS
    if keyword:
        rows = [row for row in rows if keyword.lower() in " ".join(str(v) for v in row.values()).lower()]
    if terminal_type:
        rows = [row for row in rows if terminal_type in row["terminalType"]]
    if online_status:
        rows = [row for row in rows if online_status == row["onlineStatus"]]
    return _json({"count": len(rows), "data": rows, "asOf": NOW.strftime("%Y-%m-%d %H:%M"), "dataMode": "demo"})


@tool
def summarize_predictive_monitoring_terminals(site: str = "") -> str:
    """汇总预测性维护监测终端数量、在线率、低电量、弱信号、通信中断和数据质量。"""
    rows = [row for row in MONITORING_TERMINALS if not site or site in row["site"]]
    online = sum(row["onlineStatus"] != "离线" for row in rows)
    batteries = [row["batteryPct"] for row in rows if row["batteryPct"] is not None]
    type_stats = []
    for terminal_type in sorted({row["terminalType"] for row in rows}):
        group = [row for row in rows if row["terminalType"] == terminal_type]
        type_stats.append({"terminalType": terminal_type, "count": len(group), "online": sum(row["onlineStatus"] != "离线" for row in group)})
    return _json({
        "site": site or "全部场站", "total": len(rows), "online": online, "offline": len(rows) - online,
        "onlineRatePct": round(online / len(rows) * 100, 1) if rows else 0,
        "weakSignal": sum(row["onlineStatus"] == "信号弱" for row in rows),
        "lowBattery": sum(value < 20 for value in batteries),
        "averageBatteryPct": round(sum(batteries) / len(batteries), 1) if batteries else None,
        "averageDataQualityPct": round(sum(row["dataQualityPct"] for row in rows) / len(rows), 1) if rows else 0,
        "alarmCount": sum(row["alarm"] != "无" for row in rows), "byType": type_stats,
        "asOf": NOW.strftime("%Y-%m-%d %H:%M"), "dataMode": "demo",
    })


@tool
def query_equipment_health(keyword: str = "", asset_type: str = "", risk_level: str = "") -> str:
    """查询能源设备健康度、异常分数、主要监测指标和预测风险。可按设备名称、场站、类型或高/中/低风险筛选。"""
    rows = _filter(keyword, asset_type, risk_level)
    return _json({"count": len(rows), "data": rows, "asOf": NOW.strftime("%Y-%m-%d %H:%M"), "dataMode": "demo"})


@tool
def query_condition_monitoring(asset_id: str = "", keyword: str = "", metric: str = "", hours: int = 24) -> str:
    """查询单台设备振动、温度、电流、局放、油色谱等状态监测时序，用于趋势图和异常分析。"""
    asset = _resolve_asset(asset_id, keyword)
    if asset is None:
        return _json({"ok": False, "message": "未找到设备，请提供 asset_id 或设备名称"})
    selected_metric = metric or asset["primaryMetric"]
    points = max(6, min(int(hours), 168))
    start = NOW - timedelta(hours=points - 1)
    base = float(asset["currentValue"])
    slope = base * (0.08 if asset["trend"] == "上升" else 0.015) / max(points, 1)
    data = []
    for i in range(points):
        wave = math.sin(i * 0.72 + int(asset["assetId"][-2:])) * base * 0.018
        value = round(base - slope * (points - 1 - i) + wave, 2)
        data.append({"time": (start + timedelta(hours=i)).strftime("%m-%d %H:%M"), "value": value})
    return _json({
        "ok": True, "assetId": asset["assetId"], "assetName": asset["assetName"],
        "metric": selected_metric, "unit": asset["unit"], "warningThreshold": asset["warningThreshold"],
        "criticalThreshold": asset["criticalThreshold"], "trend": asset["trend"], "data": data,
        "asOf": NOW.strftime("%Y-%m-%d %H:%M"), "dataMode": "demo",
    })


@tool
def predict_equipment_failures(keyword: str = "", horizon_days: int = 30, min_probability_pct: float = 35) -> str:
    """预测未来一段时间的设备故障风险，返回故障模式、概率、风险级别、证据和模型置信度。"""
    horizon = max(1, min(int(horizon_days), 180))
    rows = []
    for asset in _filter(keyword):
        adjusted = min(96.0, asset["failureProbabilityPct"] * (0.72 + horizon / 100))
        if adjusted < min_probability_pct:
            continue
        rows.append({
            "assetId": asset["assetId"], "assetName": asset["assetName"], "site": asset["site"],
            "predictedFailureMode": asset["predictedFailureMode"], "failureProbabilityPct": round(adjusted, 1),
            "riskLevel": "高" if adjusted >= 65 else ("中" if adjusted >= 35 else "低"),
            "predictionWindow": f"未来{horizon}天", "evidence": [f"{asset['primaryMetric']}{asset['trend']}", f"健康度{asset['healthScore']}分"],
            "modelConfidencePct": asset["modelConfidencePct"],
        })
    rows.sort(key=lambda row: row["failureProbabilityPct"], reverse=True)
    return _json({"count": len(rows), "data": rows, "asOf": NOW.strftime("%Y-%m-%d %H:%M"), "dataMode": "demo"})


@tool
def query_remaining_useful_life(keyword: str = "", max_days: int = 365) -> str:
    """查询设备关键部件剩余可用寿命 RUL，并筛选需要提前安排备件或停机窗口的设备。"""
    rows = [
        {k: row[k] for k in ("assetId", "assetName", "site", "assetType", "remainingUsefulLifeDays", "healthScore", "riskLevel", "modelConfidencePct")}
        for row in _filter(keyword) if row["remainingUsefulLifeDays"] <= max(1, int(max_days))
    ]
    rows.sort(key=lambda row: row["remainingUsefulLifeDays"])
    return _json({"count": len(rows), "data": rows, "asOf": NOW.strftime("%Y-%m-%d %H:%M"), "dataMode": "demo"})


@tool
def recommend_predictive_maintenance(keyword: str = "", priority: str = "") -> str:
    """根据预测风险生成维护优先级、建议动作、建议窗口、预计停机时长和备件需求。"""
    actions = {
        "振动": ("开展频谱诊断并检查轴承对中与润滑", "轴承组件、润滑脂"),
        "温度": ("红外复测并检查冷却、接触电阻和负载", "温度传感器、冷却风机"),
        "局放量": ("安排局放复测与绝缘诊断", "绝缘材料、槽楔"),
        "总烃": ("缩短油色谱周期并开展绕组诊断", "变压器油、密封件"),
        "分闸线圈电流": ("检查操作机构、线圈和储能系统", "分闸线圈、机构润滑件"),
        "排烟氧量": ("校验氧量探头并优化空燃比", "氧量探头"),
        "模块温度": ("清洁风道并检测功率模块热阻", "散热风机、IGBT模块"),
    }
    rows = []
    for asset in _filter(keyword):
        if asset["failureProbabilityPct"] < 35:
            continue
        item_priority = "紧急" if asset["riskLevel"] == "高" else "计划"
        if priority and priority != item_priority:
            continue
        action, spare = next((value for key, value in actions.items() if key in asset["primaryMetric"]), ("开展专项点检和趋势复核", "按设备BOM核查"))
        window_days = 3 if item_priority == "紧急" else min(30, max(7, asset["remainingUsefulLifeDays"] // 4))
        rows.append({
            "assetId": asset["assetId"], "assetName": asset["assetName"], "site": asset["site"],
            "priority": item_priority, "riskLevel": asset["riskLevel"], "reason": f"{asset['predictedFailureMode']}概率{asset['failureProbabilityPct']}%",
            "recommendedAction": action, "recommendedWindow": f"{window_days}天内", "estimatedDowntimeHours": 8 if item_priority == "紧急" else 4,
            "spareParts": spare, "workOrderStatus": "待审批" if item_priority == "紧急" else "待排期",
        })
    rows.sort(key=lambda row: 0 if row["priority"] == "紧急" else 1)
    return _json({"count": len(rows), "data": rows, "asOf": NOW.strftime("%Y-%m-%d %H:%M"), "dataMode": "demo"})


@tool
def summarize_predictive_maintenance(site: str = "") -> str:
    """汇总全厂或指定场站预测性维护 KPI，包括健康度、风险设备、近30天故障和维护工单。"""
    rows = [row for row in HEALTH_RECORDS if not site or site in row["site"]]
    high = [row for row in rows if row["riskLevel"] == "高"]
    medium = [row for row in rows if row["riskLevel"] == "中"]
    return _json({
        "site": site or "全部场站", "assetCount": len(rows),
        "averageHealthScore": round(sum(row["healthScore"] for row in rows) / len(rows), 1) if rows else 0,
        "highRiskAssets": len(high), "mediumRiskAssets": len(medium),
        "predictedFailures30d": sum(row["failureProbabilityPct"] >= 50 for row in rows),
        "urgentMaintenanceOrders": len(high), "estimatedAvoidedDowntimeHours": len(high) * 18 + len(medium) * 6,
        "estimatedAvoidedLoss10kYuan": round(len(high) * 22.5 + len(medium) * 6.8, 1),
        "topRisks": [{"assetName": row["assetName"], "failureMode": row["predictedFailureMode"], "probabilityPct": row["failureProbabilityPct"]} for row in sorted(rows, key=lambda item: item["failureProbabilityPct"], reverse=True)[:5]],
        "asOf": NOW.strftime("%Y-%m-%d %H:%M"), "dataMode": "demo",
    })


PREDICTIVE_MAINTENANCE_TOOLS = [
    query_predictive_monitoring_terminals,
    summarize_predictive_monitoring_terminals,
    query_equipment_health,
    query_condition_monitoring,
    predict_equipment_failures,
    query_remaining_useful_life,
    recommend_predictive_maintenance,
    summarize_predictive_maintenance,
]
