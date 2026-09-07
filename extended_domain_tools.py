"""基于三份外部接口文档构造的养老、设备诊断、通用物联网演示工具。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from langchain_core.tools import tool


def _dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


ELDERLY = [
    {"id": "E001", "name": "李桂兰", "age": 78, "careLevel": "三级护理", "building": "颐养1号楼", "floor": "2F", "room": "203", "area": "二楼康复活动区", "online": True, "lastSeen": "09:42:18", "heartRate": 76, "steps": 1260, "sleepHours": 7.2},
    {"id": "E002", "name": "王建国", "age": 82, "careLevel": "二级护理", "building": "颐养1号楼", "floor": "3F", "room": "306", "area": "三楼护理站", "online": True, "lastSeen": "09:41:52", "heartRate": 88, "steps": 640, "sleepHours": 6.1},
    {"id": "E003", "name": "陈淑芬", "age": 75, "careLevel": "一级护理", "building": "颐养2号楼", "floor": "1F", "room": "108", "area": "一楼花园连廊", "online": True, "lastSeen": "09:42:03", "heartRate": 72, "steps": 1880, "sleepHours": 7.8},
    {"id": "E004", "name": "赵德明", "age": 86, "careLevel": "特级护理", "building": "照护中心", "floor": "1F", "room": "A06", "area": "照护中心A区", "online": True, "lastSeen": "09:41:44", "heartRate": 94, "steps": 210, "sleepHours": 5.4},
    {"id": "E005", "name": "周月琴", "age": 80, "careLevel": "二级护理", "building": "颐养2号楼", "floor": "2F", "room": "218", "area": "餐厅", "online": False, "lastSeen": "08:56:17", "heartRate": 79, "steps": 930, "sleepHours": 6.8},
]
ELDER_DEVICES = [
    {"sn": "WATCH-1001", "name": "智能健康手表", "owner": "李桂兰", "type": "智能手表", "battery": 82, "online": True, "area": "二楼康复活动区"},
    {"sn": "WATCH-1002", "name": "智能健康手表", "owner": "王建国", "type": "智能手表", "battery": 24, "online": True, "area": "三楼护理站"},
    {"sn": "BED-0203", "name": "智能床垫", "owner": "李桂兰", "type": "床位传感器", "battery": 100, "online": True, "area": "203房"},
    {"sn": "SOS-A06", "name": "床旁SOS按钮", "owner": "赵德明", "type": "报警终端", "battery": 91, "online": True, "area": "照护中心A区"},
    {"sn": "WATCH-1005", "name": "智能健康手表", "owner": "周月琴", "type": "智能手表", "battery": 12, "online": False, "area": "餐厅"},
]
ELDER_ALARMS = [
    {"alarmId": "EA-2401", "type": "长时间静止", "person": "赵德明", "area": "照护中心A区", "level": "高", "time": "09:28:12", "status": "待处理"},
    {"alarmId": "EA-2402", "type": "设备离线", "person": "周月琴", "area": "餐厅", "level": "中", "time": "08:56:17", "status": "处理中"},
    {"alarmId": "EA-2403", "type": "低电量", "person": "王建国", "area": "三楼护理站", "level": "低", "time": "09:12:40", "status": "待处理"},
    {"alarmId": "EA-2404", "type": "夜间离床", "person": "李桂兰", "area": "203房", "level": "中", "time": "02:18:06", "status": "已处理"},
]


@tool
def summarize_eldercare_operations() -> str:
    """汇总智慧养老机构的人员在线、床位、设备和告警总体态势。"""
    return _dumps({"source": "钛颐康智慧养老物联网平台API v2.16（模拟）", "residentCount": len(ELDERLY), "onlineResidents": sum(x["online"] for x in ELDERLY), "occupiedBeds": 4, "totalBeds": 6, "onlineDevices": sum(x["online"] for x in ELDER_DEVICES), "deviceCount": len(ELDER_DEVICES), "openAlarms": sum(x["status"] != "已处理" for x in ELDER_ALARMS), "highRisk": [x for x in ELDER_ALARMS if x["level"] == "高" and x["status"] != "已处理"]})


@tool
def query_elderly_locations(keyword: str = "所有") -> str:
    """查询老人实时位置、楼栋、楼层、房间、在线状态和最后定位时间。对应人员、区域、床位接口。"""
    rows = ELDERLY if keyword in {"", "所有", "全部"} else [x for x in ELDERLY if keyword in x["name"] or keyword in x["area"] or keyword in x["building"]]
    return _dumps({"source": "钛颐康人员/区域/床位接口（模拟）", "count": len(rows), "data": rows})


@tool
def query_eldercare_alarms(status: str = "未处理", alarm_type: str = "") -> str:
    """查询跌倒、静止、离床、越界、低电量和设备离线等养老告警。"""
    rows = [x for x in ELDER_ALARMS if (status in {"", "全部"} or (status == "未处理" and x["status"] != "已处理") or x["status"] == status) and (not alarm_type or alarm_type in x["type"])]
    return _dumps({"source": "钛颐康报警接口/消息推送（模拟）", "count": len(rows), "data": rows})


@tool
def query_eldercare_devices(keyword: str = "所有") -> str:
    """查询养老院智能手表、床位传感器、SOS按钮等物联网设备状态。"""
    rows = ELDER_DEVICES if keyword in {"", "所有", "全部"} else [x for x in ELDER_DEVICES if keyword in x["name"] or keyword in x["owner"] or keyword in x["type"] or keyword in x["sn"]]
    return _dumps({"source": "钛颐康设备与设备分组接口（模拟）", "count": len(rows), "data": rows})


@tool
def query_eldercare_health(keyword: str = "所有") -> str:
    """查询老人心率、步数和睡眠等智能健康终端演示指标。"""
    rows = [{k: x[k] for k in ("id", "name", "age", "careLevel", "heartRate", "steps", "sleepHours")} for x in ELDERLY if keyword in {"", "所有", "全部"} or keyword in x["name"]]
    return _dumps({"source": "钛颐康设备物模型数据（模拟）", "notice": "健康指标仅用于养老运营演示，不构成医疗诊断。", "count": len(rows), "data": rows})


@tool
def query_eldercare_geofences() -> str:
    """查询养老场景电子围栏和区域进出规则。"""
    return _dumps({"source": "钛颐康围栏/区域接口（模拟）", "data": [{"name": "院区边界", "target": "全体老人", "rule": "离开即告警", "enabled": True}, {"name": "照护中心A区", "target": "特级护理", "rule": "未经陪护离开即告警", "enabled": True}, {"name": "屋顶花园", "target": "全体老人", "rule": "18:00后进入告警", "enabled": True}]})


DIAG_DEVICES = [
    {"deviceCode": "EQP-001", "deviceName": "一号空压机", "location": "动力站", "status": "预警", "health": 68, "online": True, "rpm": 2960, "temperature": 78.4, "vibration": 7.2},
    {"deviceCode": "EQP-002", "deviceName": "二号循环泵", "location": "水泵房", "status": "正常", "health": 91, "online": True, "rpm": 1480, "temperature": 54.2, "vibration": 2.4},
    {"deviceCode": "EQP-003", "deviceName": "主引风机", "location": "锅炉间", "status": "报警", "health": 52, "online": True, "rpm": 980, "temperature": 86.7, "vibration": 9.6},
    {"deviceCode": "EQP-004", "deviceName": "10kV主变压器", "location": "变电站", "status": "正常", "health": 88, "online": True, "rpm": 0, "temperature": 63.1, "vibration": 1.1},
    {"deviceCode": "EQP-005", "deviceName": "冷却塔风机", "location": "屋面设备区", "status": "离线", "health": 0, "online": False, "rpm": 0, "temperature": 0, "vibration": 0},
]
DIAG_ALARMS = [
    {"alarmId": "FA-301", "deviceCode": "EQP-003", "deviceName": "主引风机", "pointIdentifier": "VIB_RMS", "alarmMetric": "振动有效值", "value": 9.6, "threshold": 7.1, "level": "严重", "fault": "叶轮不平衡/轴承磨损", "status": "待确认", "time": "09:35:20"},
    {"alarmId": "FA-302", "deviceCode": "EQP-001", "deviceName": "一号空压机", "pointIdentifier": "TEMPERATURE", "alarmMetric": "轴承温度", "value": 78.4, "threshold": 75, "level": "预警", "fault": "润滑不足", "status": "处理中", "time": "09:18:43"},
    {"alarmId": "FA-303", "deviceCode": "EQP-005", "deviceName": "冷却塔风机", "pointIdentifier": "COMM", "alarmMetric": "通信状态", "value": 0, "threshold": 1, "level": "一般", "fault": "终端离线", "status": "待确认", "time": "08:51:09"},
]


def _find_diag(keyword: str):
    return [x for x in DIAG_DEVICES if keyword in {"", "所有", "全部"} or keyword in x["deviceCode"] or keyword in x["deviceName"] or keyword in x["location"]]


@tool
def summarize_diagnostic_operations() -> str:
    """汇总设备状态监测、健康度、在线率和故障报警态势。"""
    return _dumps({"source": "设备状态监测与故障诊断接口V1.6（模拟）", "deviceCount": len(DIAG_DEVICES), "online": sum(x["online"] for x in DIAG_DEVICES), "warning": sum(x["status"] == "预警" for x in DIAG_DEVICES), "alarm": sum(x["status"] == "报警" for x in DIAG_DEVICES), "openAlarms": len([x for x in DIAG_ALARMS if x["status"] != "已关闭"]), "averageHealth": round(sum(x["health"] for x in DIAG_DEVICES if x["online"])/sum(x["online"] for x in DIAG_DEVICES), 1)})


@tool
def query_diagnostic_devices(keyword: str = "所有") -> str:
    """查询设备树、设备列表、设备详情、在线状态和健康度。对应/getDeviceList、/getDeviceDetail。"""
    rows = _find_diag(keyword)
    return _dumps({"source": "设备诊断设备树与设备接口（模拟）", "count": len(rows), "data": rows})


@tool
def query_realtime_device_metrics(keyword: str) -> str:
    """查询单台设备的温度、振动、转速等实时指标。对应/lc/getDeviceData。"""
    rows = _find_diag(keyword)
    return _dumps({"source": "/lc/getDeviceData（模拟）", "dataType": "RealData", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "data": rows})


@tool
def query_history_device_metrics(keyword: str, point_identifier: str = "TEMPERATURE") -> str:
    """查询设备历史指标趋势。对应/queryHistoryMetric。"""
    rows = _find_diag(keyword)
    base = rows[0].get("temperature", 60) if rows else 60
    values = [round(base + x, 1) for x in (-3.2, -1.8, -0.5, 1.2, 2.9, 1.7, 0.4)]
    return _dumps({"source": "/queryHistoryMetric（模拟）", "device": rows[0] if rows else None, "pointIdentifier": point_identifier, "unit": "℃" if "TEMP" in point_identifier.upper() else "mm/s", "data": [{"time": f"{h:02d}:00", "value": v} for h, v in zip(range(3, 10), values)]})


@tool
def query_diagnostic_alarms(keyword: str = "所有", status: str = "全部") -> str:
    """查询设备当前/历史报警、诊断故障和处理状态。对应/queryAlarmHistory。"""
    rows = [x for x in DIAG_ALARMS if (keyword in {"", "所有", "全部"} or keyword in x["deviceName"] or keyword in x["deviceCode"] or keyword in x["fault"]) and (status in {"", "全部"} or x["status"] == status)]
    return _dumps({"source": "/queryAlarmHistory（模拟）", "count": len(rows), "data": rows})


@tool
def analyze_device_waveform(keyword: str) -> str:
    """分析设备历史波形/频谱并给出模拟诊断证据。对应波形文件和/getDataByWaveFileId。"""
    rows = _find_diag(keyword); device = rows[0] if rows else None
    return _dumps({"source": "/queryHistoryMetricFileIds + /getDataByWaveFileId（模拟）", "device": device, "spectrum": [{"frequencyHz": 16.3, "amplitude": 2.1}, {"frequencyHz": 32.6, "amplitude": 5.8}, {"frequencyHz": 48.9, "amplitude": 1.9}], "diagnosis": "2倍频成分偏高，疑似不对中或叶轮不平衡", "confidence": 0.82, "notice": "演示诊断结论需由设备工程师复核。"})


@tool
def recommend_diagnostic_action(keyword: str) -> str:
    """结合健康度、报警和波形给出设备检修优先级及建议。"""
    rows = _find_diag(keyword); device = rows[0] if rows else None
    return _dumps({"source": "设备诊断演示规则", "device": device, "priority": "高" if device and device["health"] < 60 else "中", "actions": ["复核轴承与联轴器状态", "采集稳定工况波形进行对比", "检查润滑与地脚紧固", "确认后回传报警处理状态"], "notice": "建议用于辅助决策，实际检修以现场规程为准。"})


IOT_BUILDINGS = [
    {"buildingId": 202861, "name": "研发中心", "city": "苏州市", "address": "工业园区星湖街88号", "floors": 6, "mapStatus": "已配置"},
    {"buildingId": 202885, "name": "综合服务楼", "city": "苏州市", "address": "工业园区星湖街90号", "floors": 5, "mapStatus": "已配置"},
    {"buildingId": 200036, "name": "仓储中心", "city": "苏州市", "address": "工业园区东区16号", "floors": 2, "mapStatus": "已配置"},
    {"buildingId": 203012, "name": "智能制造车间", "city": "苏州市", "address": "工业园区东区18号", "floors": 3, "mapStatus": "已配置"},
    {"buildingId": 203026, "name": "能源动力站", "city": "苏州市", "address": "工业园区东区20号", "floors": 2, "mapStatus": "已配置"},
    {"buildingId": 203108, "name": "访客与物流中心", "city": "苏州市", "address": "工业园区南门1号", "floors": 2, "mapStatus": "已配置"},
]

IOT_TERMINALS = [
    # 网关
    {"sn":"IOT-GW-001","name":"研发中心LoRa网关A","productKey":"gateway-lora","building":"研发中心","floorNo":1,"area":"弱电间","type":"gateway","subjectType":"gateway","communicateStatus":0,"locateStatus":0,"battery":100,"x":12500,"y":8600,"lastSeen":"09:46:31"},
    {"sn":"IOT-GW-002","name":"研发中心定位网关B","productKey":"gateway-ble","building":"研发中心","floorNo":4,"area":"四楼走廊","type":"gateway","subjectType":"gateway","communicateStatus":0,"locateStatus":0,"battery":100,"x":20200,"y":9100,"lastSeen":"09:46:28"},
    {"sn":"IOT-GW-003","name":"服务楼定位网关","productKey":"gateway-ble","building":"综合服务楼","floorNo":1,"area":"一楼大厅","type":"gateway","subjectType":"gateway","communicateStatus":0,"locateStatus":0,"battery":100,"x":8800,"y":7400,"lastSeen":"09:46:22"},
    {"sn":"IOT-GW-004","name":"仓储中心LoRa网关","productKey":"gateway-lora","building":"仓储中心","floorNo":1,"area":"仓库控制室","type":"gateway","subjectType":"gateway","communicateStatus":0,"locateStatus":0,"battery":100,"x":15600,"y":11400,"lastSeen":"09:46:16"},
    {"sn":"IOT-GW-005","name":"制造车间工业网关","productKey":"gateway-industrial","building":"智能制造车间","floorNo":1,"area":"产线控制柜","type":"gateway","subjectType":"gateway","communicateStatus":0,"locateStatus":0,"battery":100,"x":31800,"y":12700,"lastSeen":"09:46:30"},
    {"sn":"IOT-GW-006","name":"动力站工业网关","productKey":"gateway-industrial","building":"能源动力站","floorNo":1,"area":"中控室","type":"gateway","subjectType":"gateway","communicateStatus":1,"locateStatus":1,"battery":100,"x":0,"y":0,"lastSeen":"09:18:42"},
    {"sn":"IOT-GW-007","name":"物流中心定位网关","productKey":"gateway-ble","building":"访客与物流中心","floorNo":1,"area":"车辆入口","type":"gateway","subjectType":"gateway","communicateStatus":0,"locateStatus":0,"battery":100,"x":11600,"y":6200,"lastSeen":"09:46:25"},
    # 人员穿戴终端
    {"sn":"IOT-W-201","name":"人员手表-陈晨","bindName":"陈晨","department":"研发部","productKey":"smart-watch","building":"研发中心","floorNo":2,"area":"算法实验室","type":"direct","subjectType":"person","communicateStatus":0,"locateStatus":0,"battery":82,"x":28400,"y":14200,"lastSeen":"09:46:20"},
    {"sn":"IOT-W-202","name":"人员手表-刘洋","bindName":"刘洋","department":"研发部","productKey":"smart-watch","building":"研发中心","floorNo":4,"area":"硬件实验室","type":"direct","subjectType":"person","communicateStatus":0,"locateStatus":0,"battery":67,"x":17600,"y":9800,"lastSeen":"09:46:12"},
    {"sn":"IOT-W-203","name":"人员手表-王雪","bindName":"王雪","department":"行政部","productKey":"smart-watch","building":"综合服务楼","floorNo":3,"area":"行政办公区","type":"direct","subjectType":"person","communicateStatus":0,"locateStatus":0,"battery":44,"x":9100,"y":17800,"lastSeen":"09:45:58"},
    {"sn":"IOT-W-204","name":"人员胸卡-赵磊","bindName":"赵磊","department":"仓储部","productKey":"person-badge","building":"仓储中心","floorNo":1,"area":"收发货区","type":"terminal","subjectType":"person","communicateStatus":0,"locateStatus":0,"battery":71,"x":22100,"y":8600,"lastSeen":"09:46:03"},
    {"sn":"IOT-W-205","name":"人员胸卡-孙强","bindName":"孙强","department":"制造部","productKey":"person-badge","building":"智能制造车间","floorNo":1,"area":"装配一线","type":"terminal","subjectType":"person","communicateStatus":0,"locateStatus":0,"battery":38,"x":33700,"y":15600,"lastSeen":"09:45:49"},
    {"sn":"IOT-W-206","name":"人员胸卡-周敏","bindName":"周敏","department":"质量部","productKey":"person-badge","building":"智能制造车间","floorNo":2,"area":"质量检测区","type":"terminal","subjectType":"person","communicateStatus":0,"locateStatus":0,"battery":56,"x":13400,"y":10900,"lastSeen":"09:45:55"},
    {"sn":"IOT-W-207","name":"人员手表-黄杰","bindName":"黄杰","department":"动力部","productKey":"smart-watch","building":"能源动力站","floorNo":1,"area":"空压机房","type":"direct","subjectType":"person","communicateStatus":0,"locateStatus":0,"battery":29,"x":26500,"y":8300,"lastSeen":"09:45:41"},
    {"sn":"IOT-W-208","name":"访客卡-V032","bindName":"访客V032","department":"访客","productKey":"visitor-badge","building":"访客与物流中心","floorNo":1,"area":"访客登记区","type":"terminal","subjectType":"person","communicateStatus":0,"locateStatus":0,"battery":91,"x":7800,"y":9200,"lastSeen":"09:46:18"},
    {"sn":"IOT-W-209","name":"人员胸卡-杨帆","bindName":"杨帆","department":"仓储部","productKey":"person-badge","building":"仓储中心","floorNo":2,"area":"高值物料区","type":"terminal","subjectType":"person","communicateStatus":1,"locateStatus":1,"battery":12,"x":0,"y":0,"lastSeen":"08:52:19"},
    # 资产定位终端
    {"sn":"IOT-T-101","name":"资产标签-示波器01","bindName":"示波器01","assetCode":"AS-RD-001","productKey":"asset-tag","building":"研发中心","floorNo":2,"area":"算法实验室","type":"terminal","subjectType":"asset","communicateStatus":0,"locateStatus":0,"battery":76,"x":29200,"y":13900,"lastSeen":"09:46:17"},
    {"sn":"IOT-T-102","name":"资产标签-频谱仪02","bindName":"频谱仪02","assetCode":"AS-RD-002","productKey":"asset-tag","building":"研发中心","floorNo":4,"area":"硬件实验室","type":"terminal","subjectType":"asset","communicateStatus":1,"locateStatus":1,"battery":9,"x":0,"y":0,"lastSeen":"08:44:08"},
    {"sn":"IOT-T-103","name":"资产标签-移动工作站03","bindName":"移动工作站03","assetCode":"AS-IT-003","productKey":"asset-tag","building":"综合服务楼","floorNo":2,"area":"会议中心","type":"terminal","subjectType":"asset","communicateStatus":0,"locateStatus":0,"battery":61,"x":16400,"y":11700,"lastSeen":"09:45:59"},
    {"sn":"IOT-T-104","name":"资产标签-叉车01","bindName":"电动叉车01","assetCode":"AS-WH-011","productKey":"vehicle-tag","building":"仓储中心","floorNo":1,"area":"B库通道","type":"terminal","subjectType":"asset","communicateStatus":0,"locateStatus":0,"battery":73,"x":34200,"y":10100,"lastSeen":"09:46:09"},
    {"sn":"IOT-T-105","name":"资产标签-危化品柜02","bindName":"危化品柜02","assetCode":"AS-WH-026","productKey":"asset-tag","building":"仓储中心","floorNo":1,"area":"危险品区","type":"terminal","subjectType":"asset","communicateStatus":0,"locateStatus":0,"battery":46,"x":38100,"y":18900,"lastSeen":"09:45:45"},
    {"sn":"IOT-T-106","name":"资产标签-AGV07","bindName":"AGV搬运车07","assetCode":"AS-MF-107","productKey":"vehicle-tag","building":"智能制造车间","floorNo":1,"area":"装配二线","type":"terminal","subjectType":"asset","communicateStatus":0,"locateStatus":0,"battery":58,"x":29800,"y":18100,"lastSeen":"09:46:13"},
    {"sn":"IOT-T-107","name":"资产标签-扭矩仪05","bindName":"数字扭矩仪05","assetCode":"AS-QA-205","productKey":"asset-tag","building":"智能制造车间","floorNo":2,"area":"质量检测区","type":"terminal","subjectType":"asset","communicateStatus":0,"locateStatus":0,"battery":21,"x":14100,"y":11600,"lastSeen":"09:45:52"},
    {"sn":"IOT-T-108","name":"资产标签-应急箱01","bindName":"应急抢修箱01","assetCode":"AS-EN-301","productKey":"asset-tag","building":"能源动力站","floorNo":1,"area":"中控室外走廊","type":"terminal","subjectType":"asset","communicateStatus":0,"locateStatus":0,"battery":88,"x":11900,"y":13200,"lastSeen":"09:45:38"},
    {"sn":"IOT-T-109","name":"资产标签-物流笼车12","bindName":"物流笼车12","assetCode":"AS-LG-412","productKey":"asset-tag","building":"访客与物流中心","floorNo":1,"area":"物流暂存区","type":"terminal","subjectType":"asset","communicateStatus":0,"locateStatus":0,"battery":35,"x":18800,"y":14600,"lastSeen":"09:46:07"},
    {"sn":"IOT-T-110","name":"资产标签-投影仪06","bindName":"移动投影仪06","assetCode":"AS-AD-506","productKey":"asset-tag","building":"综合服务楼","floorNo":4,"area":"培训室","type":"terminal","subjectType":"asset","communicateStatus":0,"locateStatus":0,"battery":64,"x":12100,"y":8700,"lastSeen":"09:45:33"},
    # 环境、安防与设备传感器
    {"sn":"IOT-S-301","name":"温湿度传感器301","productKey":"th-sensor","building":"仓储中心","floorNo":1,"area":"A库","type":"terminal","subjectType":"sensor","communicateStatus":0,"locateStatus":0,"battery":61,"x":26600,"y":9700,"lastSeen":"09:46:14"},
    {"sn":"IOT-S-302","name":"温湿度传感器302","productKey":"th-sensor","building":"研发中心","floorNo":2,"area":"服务器实验室","type":"terminal","subjectType":"sensor","communicateStatus":0,"locateStatus":0,"battery":79,"x":23800,"y":16400,"lastSeen":"09:46:21"},
    {"sn":"IOT-S-303","name":"空气质量传感器303","productKey":"air-sensor","building":"综合服务楼","floorNo":1,"area":"一楼大厅","type":"terminal","subjectType":"sensor","communicateStatus":0,"locateStatus":0,"battery":84,"x":9600,"y":7100,"lastSeen":"09:46:11"},
    {"sn":"IOT-S-304","name":"烟感探测器304","productKey":"smoke-sensor","building":"仓储中心","floorNo":1,"area":"危险品区","type":"terminal","subjectType":"sensor","communicateStatus":0,"locateStatus":0,"battery":93,"x":37400,"y":17600,"lastSeen":"09:45:48"},
    {"sn":"IOT-S-305","name":"振动传感器305","productKey":"vibration-sensor","building":"能源动力站","floorNo":1,"area":"空压机房","type":"terminal","subjectType":"sensor","communicateStatus":0,"locateStatus":0,"battery":72,"x":27200,"y":7800,"lastSeen":"09:45:50"},
    {"sn":"IOT-S-306","name":"智能电表306","productKey":"smart-meter","building":"智能制造车间","floorNo":1,"area":"配电间","type":"direct","subjectType":"sensor","communicateStatus":0,"locateStatus":0,"battery":100,"x":7900,"y":6300,"lastSeen":"09:46:06"},
    {"sn":"IOT-S-307","name":"门磁传感器307","productKey":"door-sensor","building":"研发中心","floorNo":4,"area":"硬件实验室","type":"terminal","subjectType":"sensor","communicateStatus":0,"locateStatus":0,"battery":18,"x":16800,"y":8700,"lastSeen":"09:45:36"},
    {"sn":"IOT-S-308","name":"水浸传感器308","productKey":"water-sensor","building":"综合服务楼","floorNo":-1,"area":"地下设备间","type":"terminal","subjectType":"sensor","communicateStatus":1,"locateStatus":1,"battery":54,"x":0,"y":0,"lastSeen":"08:57:33"},
    {"sn":"IOT-C-401","name":"新风机远程控制器401","productKey":"hvac-controller","building":"综合服务楼","floorNo":3,"area":"空调机房","type":"direct","subjectType":"actuator","communicateStatus":0,"locateStatus":0,"battery":100,"x":7200,"y":15500,"lastSeen":"09:46:01"},
    {"sn":"IOT-C-402","name":"照明回路控制器402","productKey":"lighting-controller","building":"研发中心","floorNo":2,"area":"公共走廊","type":"direct","subjectType":"actuator","communicateStatus":0,"locateStatus":0,"battery":100,"x":14800,"y":10300,"lastSeen":"09:46:04"},
]

IOT_BEACONS = [
    {"mac":"BEACON-A101","name":"研发大厅东信标","gateway":"IOT-GW-001","building":"研发中心","floorNo":1,"group":"研发中心1F","online":True,"battery":86},
    {"mac":"BEACON-A102","name":"研发大厅西信标","gateway":"IOT-GW-001","building":"研发中心","floorNo":1,"group":"研发中心1F","online":True,"battery":79},
    {"mac":"BEACON-A201","name":"算法实验室东信标","gateway":"IOT-GW-001","building":"研发中心","floorNo":2,"group":"研发中心2F","online":True,"battery":72},
    {"mac":"BEACON-A202","name":"算法实验室西信标","gateway":"IOT-GW-001","building":"研发中心","floorNo":2,"group":"研发中心2F","online":True,"battery":68},
    {"mac":"BEACON-A401","name":"硬件实验室东信标","gateway":"IOT-GW-002","building":"研发中心","floorNo":4,"group":"研发中心4F","online":True,"battery":63},
    {"mac":"BEACON-A402","name":"硬件实验室西信标","gateway":"IOT-GW-002","building":"研发中心","floorNo":4,"group":"研发中心4F","online":False,"battery":7},
    {"mac":"BEACON-B101","name":"服务楼大厅信标","gateway":"IOT-GW-003","building":"综合服务楼","floorNo":1,"group":"服务楼1F","online":True,"battery":81},
    {"mac":"BEACON-B201","name":"会议中心信标","gateway":"IOT-GW-003","building":"综合服务楼","floorNo":2,"group":"服务楼2F","online":True,"battery":75},
    {"mac":"BEACON-B301","name":"行政区信标","gateway":"IOT-GW-003","building":"综合服务楼","floorNo":3,"group":"服务楼3F","online":True,"battery":66},
    {"mac":"BEACON-C101","name":"仓库A区信标","gateway":"IOT-GW-004","building":"仓储中心","floorNo":1,"group":"仓储中心1F","online":True,"battery":58},
    {"mac":"BEACON-C102","name":"仓库B区信标","gateway":"IOT-GW-004","building":"仓储中心","floorNo":1,"group":"仓储中心1F","online":True,"battery":49},
    {"mac":"BEACON-C103","name":"危险品区信标","gateway":"IOT-GW-004","building":"仓储中心","floorNo":1,"group":"仓储中心1F","online":True,"battery":77},
    {"mac":"BEACON-D101","name":"装配一线信标","gateway":"IOT-GW-005","building":"智能制造车间","floorNo":1,"group":"制造车间1F","online":True,"battery":83},
    {"mac":"BEACON-D102","name":"装配二线信标","gateway":"IOT-GW-005","building":"智能制造车间","floorNo":1,"group":"制造车间1F","online":True,"battery":69},
    {"mac":"BEACON-D201","name":"质量检测区信标","gateway":"IOT-GW-005","building":"智能制造车间","floorNo":2,"group":"制造车间2F","online":True,"battery":74},
    {"mac":"BEACON-E101","name":"动力站中控信标","gateway":"IOT-GW-006","building":"能源动力站","floorNo":1,"group":"动力站1F","online":False,"battery":55},
    {"mac":"BEACON-E102","name":"空压机房信标","gateway":"IOT-GW-006","building":"能源动力站","floorNo":1,"group":"动力站1F","online":False,"battery":52},
    {"mac":"BEACON-F101","name":"访客登记区信标","gateway":"IOT-GW-007","building":"访客与物流中心","floorNo":1,"group":"物流中心1F","online":True,"battery":88},
    {"mac":"BEACON-F102","name":"物流暂存区信标","gateway":"IOT-GW-007","building":"访客与物流中心","floorNo":1,"group":"物流中心1F","online":True,"battery":76},
]

IOT_GEOFENCES = [
    {"id":"R01","name":"算法实验室资产围栏","building":"研发中心","floorNo":2,"targetType":"资产","enabled":True,"rule":"离开告警","bound":6},
    {"id":"R02","name":"硬件实验室门禁区域","building":"研发中心","floorNo":4,"targetType":"人员","enabled":True,"rule":"未授权进入告警","bound":9},
    {"id":"R03","name":"会议中心访客区域","building":"综合服务楼","floorNo":2,"targetType":"访客","enabled":True,"rule":"停留超时告警","bound":5},
    {"id":"R04","name":"仓储危险品区域","building":"仓储中心","floorNo":1,"targetType":"人员","enabled":True,"rule":"未授权进入告警","bound":8},
    {"id":"R05","name":"高值物料区域","building":"仓储中心","floorNo":2,"targetType":"资产","enabled":True,"rule":"离开告警","bound":7},
    {"id":"R06","name":"装配产线安全区","building":"智能制造车间","floorNo":1,"targetType":"人员","enabled":True,"rule":"离岗超时告警","bound":10},
    {"id":"R07","name":"质量检测设备区","building":"智能制造车间","floorNo":2,"targetType":"资产","enabled":True,"rule":"离开告警","bound":7},
    {"id":"R08","name":"空压机房受限区","building":"能源动力站","floorNo":1,"targetType":"人员","enabled":True,"rule":"单人进入告警","bound":6},
    {"id":"R09","name":"物流车辆电子围栏","building":"访客与物流中心","floorNo":1,"targetType":"车辆","enabled":True,"rule":"偏离路线告警","bound":12},
    {"id":"R10","name":"园区总边界","building":"全园区","floorNo":0,"targetType":"人员与资产","enabled":True,"rule":"离开园区告警","bound":18},
]

IOT_EVENTS = [
    {"eventId":"IE-001","type":"围栏离开","subject":"示波器01","sn":"IOT-T-101","building":"研发中心","region":"算法实验室资产围栏","time":"09:31:26","level":"高","status":"待确认"},
    {"eventId":"IE-002","type":"设备离线","subject":"频谱仪02","sn":"IOT-T-102","building":"研发中心","region":"硬件实验室","time":"08:44:08","level":"中","status":"处理中"},
    {"eventId":"IE-003","type":"低电量","subject":"频谱仪02","sn":"IOT-T-102","building":"研发中心","region":"硬件实验室","time":"08:42:51","level":"低","status":"待处理"},
    {"eventId":"IE-004","type":"未授权进入","subject":"访客V032","sn":"IOT-W-208","building":"研发中心","region":"硬件实验室门禁区域","time":"09:12:03","level":"高","status":"已处理"},
    {"eventId":"IE-005","type":"人员离线","subject":"杨帆","sn":"IOT-W-209","building":"仓储中心","region":"高值物料区","time":"08:52:19","level":"中","status":"待确认"},
    {"eventId":"IE-006","type":"资产移动","subject":"电动叉车01","sn":"IOT-T-104","building":"仓储中心","region":"B库通道","time":"09:38:12","level":"提示","status":"已确认"},
    {"eventId":"IE-007","type":"危险区进入","subject":"赵磊","sn":"IOT-W-204","building":"仓储中心","region":"仓储危险品区域","time":"09:06:45","level":"高","status":"已处理"},
    {"eventId":"IE-008","type":"低电量","subject":"数字扭矩仪05","sn":"IOT-T-107","building":"智能制造车间","region":"质量检测区","time":"09:21:37","level":"低","status":"待处理"},
    {"eventId":"IE-009","type":"离岗超时","subject":"孙强","sn":"IOT-W-205","building":"智能制造车间","region":"装配产线安全区","time":"09:27:20","level":"中","status":"处理中"},
    {"eventId":"IE-010","type":"网关离线","subject":"动力站工业网关","sn":"IOT-GW-006","building":"能源动力站","region":"中控室","time":"09:18:42","level":"高","status":"待处理"},
    {"eventId":"IE-011","type":"振动超限","subject":"振动传感器305","sn":"IOT-S-305","building":"能源动力站","region":"空压机房","time":"09:33:56","level":"高","status":"处理中"},
    {"eventId":"IE-012","type":"传感器离线","subject":"水浸传感器308","sn":"IOT-S-308","building":"综合服务楼","region":"地下设备间","time":"08:57:33","level":"中","status":"待处理"},
    {"eventId":"IE-013","type":"门磁长开","subject":"门磁传感器307","sn":"IOT-S-307","building":"研发中心","region":"硬件实验室","time":"09:40:02","level":"中","status":"待确认"},
    {"eventId":"IE-014","type":"低电量","subject":"人员手表-黄杰","sn":"IOT-W-207","building":"能源动力站","region":"空压机房","time":"09:41:18","level":"低","status":"待处理"},
    {"eventId":"IE-015","type":"车辆偏航","subject":"物流笼车12","sn":"IOT-T-109","building":"访客与物流中心","region":"物流车辆电子围栏","time":"09:29:44","level":"中","status":"已确认"},
]

IOT_DOWNLINK_TASKS = [
    {"taskId":"DL-001","terminal":"IOT-C-401","command":"setFanSpeed","value":45,"createdAt":"09:05:12","status":"成功","operator":"运营中心"},
    {"taskId":"DL-002","terminal":"IOT-C-402","command":"setBrightness","value":70,"createdAt":"09:08:31","status":"成功","operator":"节能策略"},
    {"taskId":"DL-003","terminal":"IOT-S-302","command":"setReportInterval","value":60,"createdAt":"09:10:18","status":"成功","operator":"平台管理员"},
    {"taskId":"DL-004","terminal":"IOT-GW-006","command":"restart","value":1,"createdAt":"09:22:40","status":"失败","operator":"运维工单"},
    {"taskId":"DL-005","terminal":"IOT-S-307","command":"setReportInterval","value":30,"createdAt":"09:42:07","status":"已下发","operator":"告警联动"},
]


@tool
def summarize_iot_operations() -> str:
    """汇总通用物联网平台的建筑、终端、在线率、围栏和事件态势。"""
    online = sum(x["communicateStatus"] == 0 for x in IOT_TERMINALS)
    return _dumps({"source":"真趣物联网平台接口V2.9（模拟）","buildings":len(IOT_BUILDINGS),"terminals":len(IOT_TERMINALS),"online":online,"offline":len(IOT_TERMINALS)-online,"onlineRate":round(online/len(IOT_TERMINALS)*100,1),"gateways":sum(x["subjectType"]=="gateway" for x in IOT_TERMINALS),"peopleTags":sum(x["subjectType"]=="person" for x in IOT_TERMINALS),"assetTags":sum(x["subjectType"]=="asset" for x in IOT_TERMINALS),"sensors":sum(x["subjectType"]=="sensor" for x in IOT_TERMINALS),"beacons":len(IOT_BEACONS),"beaconsOnline":sum(x["online"] for x in IOT_BEACONS),"geofences":len(IOT_GEOFENCES),"openEvents":sum(x["status"] not in {"已处理","已确认"} for x in IOT_EVENTS),"highEvents":sum(x["level"]=="高" and x["status"] not in {"已处理","已确认"} for x in IOT_EVENTS)})


@tool
def query_iot_buildings(keyword: str = "所有") -> str:
    """查询物联网平台建筑列表。对应/building/getBuildingByUser/{username}。"""
    rows = IOT_BUILDINGS if keyword in {"", "所有", "全部"} else [x for x in IOT_BUILDINGS if keyword in x["name"] or keyword in x["city"] or keyword in x["address"]]
    return _dumps({"source":"/building/getBuildingByUser（模拟）","count":len(rows),"data":rows})


@tool
def query_iot_terminals(keyword: str = "所有", terminal_type: str = "", status: str = "全部") -> str:
    """查询网关、子设备、直连设备及其通信/定位状态。对应/device/terminal。"""
    rows = [x for x in IOT_TERMINALS if keyword in {"", "所有", "全部"} or any(keyword in str(x.get(k,"")) for k in ("sn","name","bindName","assetCode","building","area","productKey","department"))]
    if terminal_type:
        rows = [x for x in rows if terminal_type in {x["type"], x["subjectType"], x["productKey"]} or terminal_type in x["name"]]
    if status == "在线": rows = [x for x in rows if x["communicateStatus"] == 0]
    elif status == "离线": rows = [x for x in rows if x["communicateStatus"] != 0]
    elif status == "未定位": rows = [x for x in rows if x["locateStatus"] != 0]
    elif status == "低电量": rows = [x for x in rows if x["battery"] < 25]
    return _dumps({"source": "/device/terminal（模拟）", "count": len(rows), "data": rows})


@tool
def query_iot_beacons(building: str = "", online: str = "全部") -> str:
    """查询定位信标及其所属网关、节点组和在线状态。对应/device/terminal/beacon/list。"""
    rows = [x for x in IOT_BEACONS if not building or building in x["building"]]
    if online == "在线": rows = [x for x in rows if x["online"]]
    elif online == "离线": rows = [x for x in rows if not x["online"]]
    return _dumps({"source":"/device/terminal/beacon/list（模拟）","count":len(rows),"data":rows})


@tool
def query_iot_geofences(building: str = "", target_type: str = "") -> str:
    """查询电子围栏、电子区域及启用状态。对应/rail、/region接口。"""
    rows = [x for x in IOT_GEOFENCES if (not building or building in x["building"]) and (not target_type or target_type in x["targetType"])]
    return _dumps({"source":"/rail + /region（模拟）","count":len(rows),"data":rows})


@tool
def query_iot_history(keyword: str) -> str:
    """查询终端历史轨迹和区域进出事件。对应/datacenter/historypathV2。"""
    rows = [x for x in IOT_TERMINALS if any(keyword in str(x.get(k,"")) for k in ("sn","name","bindName","assetCode"))]
    terminal = rows[0] if rows else None
    area = terminal["area"] if terminal else "未知区域"; floor = terminal["floorNo"] if terminal else 1
    track = [{"time":"07:56:12","building":terminal["building"] if terminal else "未知","floorNo":max(1,floor-1),"area":"入口大厅","action":"进入","stayMinutes":12},{"time":"08:08:34","building":terminal["building"] if terminal else "未知","floorNo":floor,"area":area,"action":"进入","stayMinutes":51},{"time":"08:59:48","building":terminal["building"] if terminal else "未知","floorNo":floor,"area":"公共走廊","action":"经过","stayMinutes":6},{"time":"09:06:10","building":terminal["building"] if terminal else "未知","floorNo":floor,"area":area,"action":"返回","stayMinutes":40}]
    return _dumps({"source":"/datacenter/historypathV2（模拟）","terminal":terminal,"count":len(track) if terminal else 0,"track":track if terminal else []})


@tool
def query_iot_model_data(keyword: str, mode: str = "realtime") -> str:
    """查询终端物模型实时或历史数据。对应/device/terminal/realTime和/device/terminal/history。"""
    rows = [x for x in IOT_TERMINALS if any(keyword in str(x.get(k,"")) for k in ("sn","name","bindName","assetCode"))]
    terminal = rows[0] if rows else None; product = terminal["productKey"] if terminal else ""
    metrics = {
        "th-sensor":[("temperature","温度",24.8,"℃"),("humidity","湿度",51.2,"%RH")],
        "air-sensor":[("pm25","PM2.5",18,"μg/m³"),("co2","二氧化碳",612,"ppm"),("tvoc","TVOC",0.21,"mg/m³")],
        "smoke-sensor":[("smoke","烟雾浓度",0.03,"%obs/m"),("alarm","报警状态",0,"")],
        "vibration-sensor":[("vibration","振动有效值",6.8,"mm/s"),("temperature","轴承温度",72.4,"℃")],
        "smart-meter":[("activePower","有功功率",186.5,"kW"),("energyToday","今日电量",2240,"kWh"),("powerFactor","功率因数",0.96,"")],
        "door-sensor":[("doorState","门状态",1,"开启"),("openDuration","持续时间",362,"秒")],
        "water-sensor":[("waterAlarm","水浸状态",0,"")],
        "smart-watch":[("heartRate","心率",78,"bpm"),("steps","步数",4260,"步"),("sos","SOS",0,"")],
        "hvac-controller":[("runState","运行状态",1,"运行"),("fanSpeed","风机频率",45,"Hz"),("supplyTemp","送风温度",18.6,"℃")],
        "lighting-controller":[("switch","开关",1,"开启"),("brightness","亮度",70,"%")],
    }.get(product, [("battery","电量",terminal["battery"] if terminal else 0,"%"),("rssi","信号强度",-62,"dBm"),("moving","移动状态",1,"移动")])
    if mode.lower() in {"history","历史"}:
        data = [{"time":f"{hour:02d}:00","identifier":m[0],"name":m[1],"value":round(float(m[2])*(0.94+idx*0.02),2) if isinstance(m[2],(int,float)) else m[2],"unit":m[3]} for idx,hour in enumerate(range(4,10)) for m in metrics[:2]]
    else:
        data = [{"identifier":x[0],"name":x[1],"value":x[2],"unit":x[3]} for x in metrics]
    return _dumps({"source":"/device/terminal/realTime|history（模拟）","terminal":terminal,"mode":mode,"count":len(data),"data":data})


@tool
def query_iot_events(event_type: str = "全部", building: str = "", level: str = "", status: str = "") -> str:
    """查询设备事件、围栏进出事件和低电量/离线异常。对应RocketMQ事件订阅。"""
    rows = [x for x in IOT_EVENTS if (event_type in {"", "全部", "所有"} or event_type in x["type"]) and (not building or building in x["building"]) and (not level or level == x["level"]) and (not status or status == x["status"])]
    return _dumps({"source": "真趣物联网平台RocketMQ订阅（模拟）", "count": len(rows), "data": rows})


@tool
def query_iot_people_locations(keyword: str = "所有", building: str = "") -> str:
    """查询人员手表、胸卡和访客卡绑定人员的实时位置与在线状态。"""
    rows = [x for x in IOT_TERMINALS if x["subjectType"] == "person" and (keyword in {"","所有","全部"} or any(keyword in str(x.get(k,"")) for k in ("name","bindName","department","area"))) and (not building or building in x["building"])]
    return _dumps({"source":"/device/terminal + 定位事件（模拟）","count":len(rows),"online":sum(x["communicateStatus"]==0 for x in rows),"data":rows})


@tool
def query_iot_asset_locations(keyword: str = "所有", building: str = "") -> str:
    """查询绑定到定位标签的资产、车辆和工具实时位置。"""
    rows = [x for x in IOT_TERMINALS if x["subjectType"] == "asset" and (keyword in {"","所有","全部"} or any(keyword in str(x.get(k,"")) for k in ("name","bindName","assetCode","area"))) and (not building or building in x["building"])]
    return _dumps({"source":"/device/terminal + 定位事件（模拟）","count":len(rows),"online":sum(x["communicateStatus"]==0 for x in rows),"data":rows})


@tool
def query_iot_gateway_topology(building: str = "") -> str:
    """查询网关、节点组、定位信标和下挂终端拓扑。对应网关应用、节点组与节点类型接口。"""
    gateways = [x for x in IOT_TERMINALS if x["subjectType"] == "gateway" and (not building or building in x["building"])]
    data = []
    for gateway in gateways:
        beacons = [x for x in IOT_BEACONS if x["gateway"] == gateway["sn"]]
        children = [x for x in IOT_TERMINALS if x["building"] == gateway["building"] and x["subjectType"] != "gateway"]
        data.append({"gateway":gateway,"nodeGroups":sorted({x["group"] for x in beacons}),"beaconCount":len(beacons),"onlineBeacons":sum(x["online"] for x in beacons),"terminalCount":len(children)})
    return _dumps({"source":"网关应用/节点组/节点类型接口（模拟）","count":len(data),"data":data})


@tool
def summarize_iot_device_statistics(dimension: str = "building") -> str:
    """按建筑、产品类型或对象类型统计终端数量、在线率和低电量数量。"""
    key = {"building":"building","product":"productKey","type":"subjectType","建筑":"building","产品":"productKey","类型":"subjectType"}.get(dimension,"building")
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in IOT_TERMINALS: groups.setdefault(str(row[key]), []).append(row)
    data = [{"name":name,"total":len(rows),"online":sum(x["communicateStatus"]==0 for x in rows),"offline":sum(x["communicateStatus"]!=0 for x in rows),"lowBattery":sum(x["battery"]<25 for x in rows),"onlineRate":round(sum(x["communicateStatus"]==0 for x in rows)/len(rows)*100,1)} for name,rows in groups.items()]
    return _dumps({"source":"终端统计接口（模拟）","dimension":key,"count":len(data),"data":data})


@tool
def query_iot_downlink_tasks(status: str = "全部") -> str:
    """查询物模型属性设置、服务调用和网关重启等下行控制记录。"""
    rows = IOT_DOWNLINK_TASKS if status in {"","所有","全部"} else [x for x in IOT_DOWNLINK_TASKS if x["status"] == status]
    return _dumps({"source":"物模型下行控制接口（模拟，只读）","count":len(rows),"data":rows})


ELDERCARE_TOOLS = [summarize_eldercare_operations, query_elderly_locations, query_eldercare_alarms, query_eldercare_devices, query_eldercare_health, query_eldercare_geofences]
DIAGNOSTIC_TOOLS = [summarize_diagnostic_operations, query_diagnostic_devices, query_realtime_device_metrics, query_history_device_metrics, query_diagnostic_alarms, analyze_device_waveform, recommend_diagnostic_action]
IOT_PLATFORM_TOOLS = [summarize_iot_operations, query_iot_buildings, query_iot_terminals, query_iot_people_locations, query_iot_asset_locations, query_iot_beacons, query_iot_gateway_topology, query_iot_geofences, query_iot_history, query_iot_model_data, query_iot_events, summarize_iot_device_statistics, query_iot_downlink_tasks]
