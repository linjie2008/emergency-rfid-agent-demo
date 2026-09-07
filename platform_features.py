"""平台化能力：智能体配置、数据源、演示导演、轨迹数据、报告与总控路由。"""

from __future__ import annotations

import html
import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from langchain_core.tools import StructuredTool, tool

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime"
CONFIG_PATH = RUNTIME / "agent_configs.json"
DEMO_PATH = RUNTIME / "demo_state.json"
REPORT_DIR = RUNTIME / "reports"
_LOCK = threading.RLock()

SCENE_LABELS = {
    "medical": "医脉 AI · 急诊与医疗资产智控中心", "safety": "安域 AI · 人员安全智控中心", "building": "筑境 AI · 楼宇运营智控中心",
    "eldercare": "颐护 AI · 康养物联智控中心", "diagnostics": "机鉴 AI · 设备健康诊断中心", "iot": "万联 AI · 物联网运营中心",
}

DEFAULT_CONFIGS = {
    scene: {
        "scene": scene, "name": label, "enabled": True, "sourceMode": "mock",
        "baseUrl": "", "authHeader": "Authorization", "authValue": "", "timeoutSeconds": 15,
        "endpoints": {}, "updatedAt": "",
    }
    for scene, label in SCENE_LABELS.items()
}

DEMO_SCENARIOS = {
    "safety-high-risk": {"scene":"safety","name":"受限空间人员安全处置","description":"越界、静止告警到就近救援闭环","steps":["查询受限空间当前人员和资产位置","触发周建国长时间静止高风险告警","查询距离告警点最近的监护人员和应急装备","生成告警处置单和管理层摘要"]},
    "medical-green-channel": {"scene":"medical","name":"急诊绿通超时协同","description":"患者超时识别、位置确认与资源协同","steps":["汇总今日急诊绿通患者","识别抢救室停留超时患者","查询患者与关键医疗设备位置","生成急诊绿通运营报告"]},
    "building-fire": {"scene":"building","name":"楼宇消防联动演示","description":"消防告警、联动设备和疏散资源研判","steps":["汇总楼宇未处理告警","触发9楼烟感与消防联动场景","查询附近人员、消防设施和电梯状态","生成消防事件处置报告"]},
    "eldercare-care": {"scene":"eldercare","name":"老人异常静止照护","description":"静止告警、位置核验和照护响应","steps":["汇总养老机构当前态势","触发赵德明长时间静止告警","查询老人位置与附近健康终端","生成照护事件记录"]},
    "diagnostics-fan": {"scene":"diagnostics","name":"主引风机故障诊断","description":"振动超限、频谱分析与检修建议","steps":["汇总设备健康度与报警","查询主引风机实时指标","分析振动波形与频谱","生成检修建议报告"]},
    "iot-fence": {"scene":"iot","name":"物联网资产围栏演示","description":"资产离开围栏、轨迹追踪和联动处置","steps":["汇总物联网终端与事件态势","触发示波器01离开实验室围栏事件","回放示波器01历史轨迹并查看热力分布","生成物联网事件运营报告"]},
}

TRAJECTORIES = {
    "medical": [{"time":"08:02","x":12,"y":72,"area":"分诊台","name":"张三"},{"time":"08:18","x":29,"y":58,"area":"抢救室","name":"张三"},{"time":"08:54","x":51,"y":42,"area":"CT室","name":"张三"},{"time":"09:26","x":72,"y":30,"area":"介入室","name":"张三"}],
    "safety": [{"time":"07:44","x":9,"y":78,"area":"厂区东门","name":"张伟"},{"time":"08:03","x":26,"y":62,"area":"安全教育室","name":"张伟"},{"time":"08:46","x":48,"y":53,"area":"中控楼","name":"张伟"},{"time":"09:15","x":76,"y":27,"area":"一号装置区","name":"张伟"}],
    "building": [{"time":"08:10","x":12,"y":78,"area":"一楼大厅","name":"何磊"},{"time":"08:28","x":33,"y":61,"area":"5楼设备间","name":"何磊"},{"time":"09:02","x":56,"y":42,"area":"9楼办公区","name":"何磊"},{"time":"09:38","x":81,"y":24,"area":"屋面机房","name":"何磊"}],
    "eldercare": [{"time":"07:30","x":16,"y":74,"area":"203房","name":"李桂兰"},{"time":"08:05","x":32,"y":57,"area":"二楼餐厅","name":"李桂兰"},{"time":"08:52","x":58,"y":43,"area":"康复活动区","name":"李桂兰"},{"time":"09:35","x":78,"y":28,"area":"花园连廊","name":"李桂兰"}],
    "diagnostics": [{"time":"06:00","x":12,"y":70,"area":"振动2.8mm/s","name":"主引风机"},{"time":"07:00","x":34,"y":58,"area":"振动4.6mm/s","name":"主引风机"},{"time":"08:00","x":57,"y":39,"area":"振动7.3mm/s","name":"主引风机"},{"time":"09:00","x":82,"y":23,"area":"振动9.6mm/s","name":"主引风机"}],
    "iot": [{"time":"07:56","x":11,"y":76,"area":"研发中心入口","name":"示波器01"},{"time":"08:08","x":28,"y":61,"area":"算法实验室","name":"示波器01"},{"time":"08:59","x":55,"y":46,"area":"二楼公共走廊","name":"示波器01"},{"time":"09:31","x":82,"y":25,"area":"实验室围栏外","name":"示波器01"}],
}

TRAJECTORY_LAYOUTS = {
    "medical": {"title":"急诊中心一层","zones":[
        {"name":"分诊台","x":4,"y":58,"w":21,"h":30},{"name":"抢救室","x":27,"y":43,"w":22,"h":38},
        {"name":"CT室","x":51,"y":27,"w":20,"h":34},{"name":"介入室","x":73,"y":10,"w":23,"h":33},
        {"name":"观察区","x":51,"y":65,"w":45,"h":25},
    ]},
    "safety": {"title":"一厂区人员安全电子地图","zones":[
        {"name":"厂区东门","x":3,"y":61,"w":20,"h":29},{"name":"安全教育室","x":25,"y":47,"w":22,"h":32},
        {"name":"中控楼","x":48,"y":37,"w":20,"h":33},{"name":"一号装置区","x":70,"y":10,"w":27,"h":43,"kind":"risk"},
        {"name":"受限空间","x":48,"y":73,"w":22,"h":17,"kind":"fence"},
    ]},
    "building": {"title":"综合楼空间运营平面","zones":[
        {"name":"一楼大厅","x":4,"y":62,"w":21,"h":28},{"name":"5楼设备间","x":27,"y":46,"w":23,"h":35},
        {"name":"9楼办公区","x":52,"y":27,"w":20,"h":38},{"name":"屋面机房","x":74,"y":9,"w":22,"h":35},
        {"name":"会议区","x":52,"y":69,"w":44,"h":21},
    ]},
    "eldercare": {"title":"养老中心二层照护平面","zones":[
        {"name":"203房","x":5,"y":59,"w":21,"h":31},{"name":"二楼餐厅","x":28,"y":43,"w":23,"h":37},
        {"name":"康复活动区","x":53,"y":28,"w":20,"h":36},{"name":"花园连廊","x":75,"y":10,"w":21,"h":35},
        {"name":"护理站","x":53,"y":68,"w":43,"h":22},
    ]},
    "diagnostics": {"title":"主引风机状态演变图","zones":[
        {"name":"正常区","x":4,"y":58,"w":25,"h":32},{"name":"关注区","x":31,"y":43,"w":24,"h":37},
        {"name":"预警区","x":57,"y":25,"w":19,"h":40,"kind":"fence"},{"name":"报警区","x":78,"y":8,"w":18,"h":42,"kind":"risk"},
        {"name":"检修建议区","x":57,"y":69,"w":39,"h":21},
    ]},
    "iot": {"title":"研发中心物联网定位平面","zones":[
        {"name":"研发中心入口","x":4,"y":60,"w":21,"h":30},{"name":"算法实验室","x":27,"y":46,"w":22,"h":34},
        {"name":"二楼公共走廊","x":51,"y":31,"w":22,"h":34},{"name":"实验室围栏外","x":75,"y":8,"w":21,"h":43,"kind":"risk"},
        {"name":"硬件实验室","x":51,"y":69,"w":44,"h":21,"kind":"fence"},
    ]},
}

TRAJECTORY_WEIGHTS = {
    "medical": [3, 8, 5, 7], "safety": [2, 4, 6, 9], "building": [2, 5, 7, 4],
    "eldercare": [5, 7, 9, 4], "diagnostics": [2, 4, 7, 10], "iot": [2, 6, 5, 10],
}

ELDERCARE_GROUP_LAYOUT = {"title":"养老院全域老人活动分布","zones":[
    {"name":"居住房间","x":3,"y":12,"w":23,"h":76},
    {"name":"护理站","x":29,"y":10,"w":22,"h":28},
    {"name":"餐厅","x":29,"y":48,"w":22,"h":40},
    {"name":"康复活动区","x":54,"y":26,"w":19,"h":39},
    {"name":"花园连廊","x":76,"y":8,"w":21,"h":39},
    {"name":"照护中心A区","x":76,"y":57,"w":21,"h":31,"kind":"fence"},
]}

ELDERCARE_GROUP_TRAJECTORIES = [
    {"name":"李桂兰","color":"#55ead8","points":[
        {"time":"07:30","x":14,"y":72,"area":"203房","weight":5},{"time":"08:05","x":40,"y":63,"area":"餐厅","weight":7},
        {"time":"08:52","x":63,"y":43,"area":"康复活动区","weight":9},{"time":"09:35","x":85,"y":26,"area":"花园连廊","weight":4}]},
    {"name":"王建国","color":"#58a6ff","points":[
        {"time":"07:25","x":13,"y":25,"area":"306房","weight":6},{"time":"08:15","x":40,"y":25,"area":"护理站","weight":8},
        {"time":"09:02","x":63,"y":47,"area":"康复活动区","weight":5},{"time":"09:40","x":41,"y":61,"area":"餐厅","weight":4}]},
    {"name":"陈淑芬","color":"#b58cff","points":[
        {"time":"07:18","x":13,"y":45,"area":"108房","weight":4},{"time":"08:10","x":84,"y":29,"area":"花园连廊","weight":8},
        {"time":"09:00","x":64,"y":42,"area":"康复活动区","weight":10},{"time":"09:38","x":40,"y":64,"area":"餐厅","weight":3}]},
    {"name":"赵德明","color":"#ff6b82","points":[
        {"time":"07:40","x":85,"y":72,"area":"照护中心A区","weight":9},{"time":"08:20","x":41,"y":27,"area":"护理站","weight":7},
        {"time":"08:48","x":62,"y":51,"area":"康复活动区","weight":3},{"time":"09:28","x":84,"y":70,"area":"照护中心A区","weight":10}]},
    {"name":"周月琴","color":"#ffc85b","points":[
        {"time":"07:35","x":14,"y":82,"area":"218房","weight":6},{"time":"08:12","x":39,"y":68,"area":"餐厅","weight":9},
        {"time":"08:40","x":40,"y":30,"area":"护理站","weight":5},{"time":"08:56","x":38,"y":66,"area":"餐厅","weight":8}]},
]

GROUP_TRAJECTORY_SUBJECTS = {
    "medical": {
        "person": ("全部患者", "人", ["张三", "李敏", "王芳", "赵强", "陈洁"]),
        "asset": ("全部医疗设备", "台", ["输液泵12号", "呼吸机03", "除颤仪02", "监护仪08"]),
    },
    "safety": {
        "person": ("全部人员", "人", ["张伟", "王强", "李娜", "周建国", "陈晨"]),
        "asset": ("全部生产资产", "件", ["气体检测仪01", "应急箱02", "巡检终端05", "防爆对讲机03"]),
    },
    "building": {
        "person": ("全部楼宇人员", "人", ["何磊", "陈静", "王海", "刘洋", "访客V018"]),
        "asset": ("全部楼宇资产", "台", ["1号电梯", "巡更终端03", "移动投影仪06", "消防装备箱02"]),
    },
    "eldercare": {
        "asset": ("全部养老设备", "台", ["智能手表1001", "智能手表1002", "智能床垫0203", "床旁SOS-A06"]),
    },
    "diagnostics": {
        "asset": ("全部监测设备", "台", ["主引风机", "一号空压机", "二号循环泵", "10kV主变压器", "冷却塔风机"]),
    },
    "iot": {
        "person": ("全部定位人员", "人", ["陈晨", "刘洋", "王雪", "赵磊", "孙强"]),
        "asset": ("全部物联网资产", "件", ["示波器01", "频谱仪02", "移动工作站03", "电动叉车01", "AGV搬运车07"]),
    },
}

GROUP_TRACK_COLORS = ("#55ead8", "#58a6ff", "#b58cff", "#ff6b82", "#ffc85b", "#63e67d")
GROUP_TRACK_OFFSETS = (
    ((0,0),(0,0),(0,0),(0,0)),
    ((2,-11),(5,-8),(3,8),(-2,10)),
    ((-1,12),(4,10),(7,-5),(1,-9)),
    ((5,5),(-3,-12),(-5,11),(4,5)),
    ((-3,-7),(7,5),(-2,-12),(-5,12)),
    ((6,13),(-5,8),(6,6),(-7,-5)),
)


def _read(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def get_agent_configs(redact: bool = True) -> dict[str, dict[str, Any]]:
    with _LOCK:
        saved = _read(CONFIG_PATH, {})
        merged = {key: {**value, **saved.get(key, {})} for key, value in DEFAULT_CONFIGS.items()}
    if redact:
        for config in merged.values():
            secret = config.pop("authValue", "")
            config["authConfigured"] = bool(secret)
    return merged


def update_agent_config(scene: str, patch: dict[str, Any]) -> dict[str, Any]:
    if scene not in DEFAULT_CONFIGS:
        raise ValueError("未知智能体场景")
    allowed = {"name","enabled","sourceMode","baseUrl","authHeader","authValue","timeoutSeconds","endpoints"}
    clean = {key: value for key, value in patch.items() if key in allowed}
    if clean.get("sourceMode") not in {None, "mock", "real"}:
        raise ValueError("sourceMode 只能是 mock 或 real")
    if "baseUrl" in clean and clean["baseUrl"] and not str(clean["baseUrl"]).startswith(("http://", "https://")):
        raise ValueError("真实接口地址必须以 http:// 或 https:// 开头")
    with _LOCK:
        saved = _read(CONFIG_PATH, {})
        current = {**DEFAULT_CONFIGS[scene], **saved.get(scene, {})}
        if clean.get("authValue") == "••••••••":
            clean.pop("authValue")
        current.update(clean); current["updatedAt"] = datetime.now().isoformat(timespec="seconds")
        saved[scene] = current; _write(CONFIG_PATH, saved)
    return get_agent_configs()[scene]


def call_real_source(scene: str, tool_name: str, args: dict[str, Any]) -> str | None:
    """mock 返回 None 交给原工具；real 返回远端结果或明确配置错误。"""
    config = get_agent_configs(redact=False).get(scene, {})
    if config.get("sourceMode") != "real":
        return None
    endpoint = (config.get("endpoints") or {}).get(tool_name)
    base_url = str(config.get("baseUrl") or "").rstrip("/")
    if not base_url or not endpoint:
        return json.dumps({"source":"真实接口","ok":False,"error":f"{scene}/{tool_name} 尚未配置真实接口映射"}, ensure_ascii=False)
    spec = {"path": endpoint, "method": "POST"} if isinstance(endpoint, str) else endpoint
    url = base_url + "/" + str(spec.get("path", "")).lstrip("/")
    headers = {"Accept":"application/json"}
    if config.get("authValue"):
        headers[str(config.get("authHeader") or "Authorization")] = str(config["authValue"])
    try:
        with httpx.Client(timeout=float(config.get("timeoutSeconds") or 15), follow_redirects=False) as client:
            if str(spec.get("method", "POST")).upper() == "GET": response = client.get(url, params=args, headers=headers)
            else: response = client.request(str(spec.get("method", "POST")).upper(), url, json=args, headers=headers)
            response.raise_for_status()
            payload = response.json()
            return json.dumps({"source":"真实接口","endpoint":str(spec.get("path")),"data":payload}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"source":"真实接口","ok":False,"error":str(exc)[:500]}, ensure_ascii=False)


LOCAL_ONLY_TOOLS = {"create_data_table","create_chart","render_trajectory_heatmap","generate_schematic_image","format_concise_reply","format_executive_brief","format_alarm_disposal_card","format_positioning_report","format_shift_handover","query_demo_scenario_state","query_agent_directory"}


def source_aware_tool(scene: str, original):
    if original.name in LOCAL_ONLY_TOOLS:
        return original
    def invoke_proxy(**kwargs):
        remote = call_real_source(scene, original.name, kwargs)
        return remote if remote is not None else original.invoke(kwargs)
    return StructuredTool.from_function(name=original.name, description=original.description, func=invoke_proxy, args_schema=original.args_schema)


def list_demo_scenarios(scene: str = "") -> list[dict[str, Any]]:
    return [{"id": key, **value} for key, value in DEMO_SCENARIOS.items() if not scene or value["scene"] == scene]


def set_demo_state(scenario_id: str, step: int = 0) -> dict[str, Any]:
    if scenario_id not in DEMO_SCENARIOS:
        raise ValueError("未知演示场景")
    scenario = DEMO_SCENARIOS[scenario_id]
    state = {"active":True,"scenarioId":scenario_id,"scene":scenario["scene"],"step":max(0,min(step,len(scenario["steps"])-1)),"startedAt":datetime.now().isoformat(timespec="seconds")}
    _write(DEMO_PATH, state)
    return {**state, "scenario": scenario, "currentStep": scenario["steps"][state["step"]]}


def get_demo_state() -> dict[str, Any]:
    state = _read(DEMO_PATH, {"active":False})
    scenario = DEMO_SCENARIOS.get(state.get("scenarioId", ""))
    return {**state, "scenario": scenario, "currentStep": scenario["steps"][state.get("step",0)] if scenario and state.get("active") else ""}


def reset_demo_state() -> dict[str, Any]:
    state = {"active":False,"resetAt":datetime.now().isoformat(timespec="seconds")}; _write(DEMO_PATH,state); return state


@tool
def query_demo_scenario_state() -> str:
    """查询演示导演当前激活的业务场景、步骤和演示事件。"""
    return json.dumps(get_demo_state(), ensure_ascii=False)


@tool
def query_agent_directory() -> str:
    """查询全部领域智能体、能力和当前数据源模式，用于智能体总控分发。"""
    configs = get_agent_configs()
    return json.dumps({"count":len(SCENE_LABELS),"data":[{"scene":s,"name":n,"sourceMode":configs[s]["sourceMode"]} for s,n in SCENE_LABELS.items()]}, ensure_ascii=False)


def _looks_like_follow_up(text: str) -> bool:
    compact = re.sub(r"\s+", "", (text or "").lower())
    if not compact or len(compact) > 48:
        return False
    markers = (
        "他", "她", "它", "他们", "她们", "它们", "这个", "这些", "上述", "刚才", "前面",
        "该人员", "该患者", "该老人", "该设备", "同一个", "继续", "再查", "再看", "详细",
        "展开", "还有呢", "结果呢", "现在呢", "然后呢", "那", "怎么处理", "如何处置",
        "画成", "改成", "导出", "生成图表", "生成报告",
    )
    return any(marker in compact for marker in markers)


def route_supervisor_scene(question: str, fallback_scene: str = "") -> dict[str, Any]:
    """按领域强特征路由；无明确特征的追问沿用同一会话上次路由。"""
    text = (question or "").lower()
    strong = {
        "medical":("急症","急诊","急救","绿通","患者","病人","抢救室","分诊台","留观","院内","门诊号","腕带","医院","医护人员","医疗资产"),
        "safety":("人员安全","安全生产","作业票","工票","承包商","工业园区","生产园区","厂区","车间","受限空间","高危作业","特种作业","安全告警"),
        "building":("政企楼宇","楼宇运营","写字楼","办公楼","大楼","暖通","电梯","停车场","消防联动","楼宇能耗"),
        "eldercare":("养老院","养老机构","老人","长者","护理院","康养","离床"),
        "diagnostics":("故障诊断","设备诊断","波形","频谱","振动","剩余寿命","主引风机","预测维护"),
        "iot":("物联网平台","设备接入","物模型","网关","信标","下行任务","示波器"),
    }
    keywords = {
        "medical":("医疗","护士","医生","医护","医疗设备","高值设备","输液泵","呼吸机","ct","介入室","手术室"),
        "safety":("员工","考勤","门禁","在场人员","人员定位","人员轨迹","资产定位","越界","静止告警","劳保","巡检"),
        "building":("楼宇","建筑","空调","照明","机房","烟感","楼层","充电桩","给排水"),
        "eldercare":("养老","床位","照护","健康手表","护理","老人定位"),
        "diagnostics":("健康度","轴承","设备状态","故障","监测指标","温度趋势"),
        "iot":("物联网","终端","电子围栏","传感器","设备事件","拓扑"),
    }
    aliases = {
        "medical":("医脉", "医疗智能体"), "safety":("安域", "安全智能体"),
        "building":("筑境", "楼宇智能体"), "eldercare":("颐护", "养老智能体"),
        "diagnostics":("机鉴", "诊断智能体"), "iot":("万联", "物联网智能体"),
    }
    scores = {scene: 0 for scene in keywords}
    for scene in scores:
        scores[scene] += sum(6 for word in strong[scene] if word in text)
        scores[scene] += sum(2 for word in keywords[scene] if word in text)
        scores[scene] += sum(12 for word in aliases[scene] if word in text)
        scores[scene] += sum(10 for word in SUPERVISOR_ENTITY_HINTS[scene] if word.lower() in text)

    # 场所上下文用于处理“医院人员考勤”“急诊人员定位”等跨领域常用词。
    context_markers = {
        "medical": ("医院","院内","急症","急诊","急救","绿通","患者","病人","抢救室","分诊台"),
        "safety": ("工业园区","生产园区","厂区","车间","受限空间","作业票","承包商","安全生产"),
        "building": ("大楼","办公楼","写字楼","政企楼宇","楼宇"),
        "eldercare": ("养老院","养老机构","护理院","康养中心","老人","长者"),
    }
    for scene, markers in context_markers.items():
        if any(word in text for word in markers):
            scores[scene] += 8

    target = max(scores, key=scores.get)
    reason = "keyword"
    if scores[target] == 0:
        explicitly_unrelated = any(term in text for term in UNRELATED_TERMS)
        generic_business = any(term in text for term in GENERIC_BUSINESS_TERMS)
        if explicitly_unrelated and not _is_related_knowledge(text):
            target, reason = "", "unrelated"
        elif fallback_scene in SCENE_LABELS and (_looks_like_follow_up(text) or generic_business):
            target, reason = fallback_scene, "conversation"
        elif generic_business:
            target, reason = "safety", "business_default"
        else:
            target, reason = fallback_scene if fallback_scene in SCENE_LABELS else "safety", "needs_interpretation"
    matched = [] if not target else [word for word in strong[target] if word in text] + [word for word in keywords[target] if word in text] + [word for word in aliases[target] if word in text]
    confidence = .72 if reason == "conversation" else (.58 if reason == "business_default" else (0.0 if reason == "unrelated" else min(.99, .62 + scores[target] * .025)))
    return {"scene":target,"name":SCENE_LABELS.get(target, ""),"confidence":confidence,"scores":scores,"matched":matched,"reason":reason}


SUPERVISOR_ENTITY_HINTS = {
    "medical": ("张三", "李敏", "王芳", "赵强", "陈洁", "输液泵12号", "呼吸机03", "除颤仪02", "监护仪08"),
    "safety": ("张伟", "王强", "李娜", "周建国", "气体检测仪01", "应急箱02", "巡检终端05", "防爆对讲机03"),
    "building": ("何磊", "陈静", "王海", "访客v018", "1号电梯", "巡更终端03", "移动投影仪06", "消防装备箱02"),
    "eldercare": ("李桂兰", "王建国", "陈淑芬", "赵德明", "周月琴", "智能手表1001", "智能床垫0203", "床旁sos-a06"),
    "diagnostics": ("主引风机", "一号空压机", "二号循环泵", "10kv主变压器", "冷却塔风机"),
    "iot": ("示波器01", "频谱仪02", "移动工作站03", "电动叉车01", "agv搬运车07"),
}

GENERIC_BUSINESS_TERMS = (
    "人员", "员工", "资产", "设备", "位置", "在哪", "在哪里", "轨迹", "停留", "热力图", "地图",
    "告警", "报警", "异常", "状态", "在线", "离线", "考勤", "门禁", "围栏", "运营", "统计",
    "图表", "柱状图", "饼图", "折线图", "雷达图", "报告", "接口", "数据源", "实时", "历史",
)

COMMAND_META_TERMS = (
    "智能体列表", "有哪些智能体", "智能体能力", "总控能力", "演示状态", "你是谁", "能做什么",
    "有什么功能", "使用帮助", "怎么使用", "使用说明", "介绍一下", "数据来源", "接口说明",
    "支持哪些", "有哪些skill", "有哪些 skill", "技能列表",
)

SCENE_SCOPE_TERMS = {
    "medical": (
        "急症", "急诊", "急救", "绿通", "患者", "病人", "医院", "院内", "门诊", "分诊", "抢救",
        "医护", "医生", "护士", "护工", "腕带", "医疗", "输液泵", "呼吸机", "除颤仪", "监护仪",
        "ct室", "介入室", "手术室", "留观",
    ),
    "safety": (
        "人员安全", "安全生产", "园区", "厂区", "车间", "员工", "承包商", "访客", "作业票",
        "工作票", "操作票", "高危作业", "受限空间", "劳保", "巡检", "疲劳", "劳动强度",
        "生产资产", "定位卡", "机组", "电网", "变电站", "供热", "燃气", "能源", "预测维护",
    ),
    "building": (
        "楼宇", "大楼", "办公楼", "写字楼", "楼层", "暖通", "空调", "照明", "给排水", "水泵",
        "电梯", "停车", "车位", "充电桩", "消防", "烟感", "数据机房", "楼宇能耗", "楼宇资产",
    ),
    "eldercare": (
        "养老", "老人", "长者", "康养", "护理院", "床位", "护理站", "照护", "离床", "跌倒",
        "智能手表", "智能床垫", "健康指标", "心率", "睡眠", "房间",
    ),
    "diagnostics": (
        "设备诊断", "故障诊断", "状态监测", "振动", "波形", "频谱", "轴承", "健康度", "故障概率",
        "剩余寿命", "rul", "检修建议", "主引风机", "空压机", "循环泵", "变压器", "冷却塔",
    ),
    "iot": (
        "物联网", "物模型", "网关", "信标", "beacon", "传感器", "终端", "拓扑", "下行任务",
        "示波器", "频谱仪", "移动工作站", "叉车", "agv", "设备接入", "定位平台",
    ),
}

COMMON_OPERATION_TERMS = (
    "人员定位", "资产定位", "设备定位", "实时位置", "历史位置", "人员轨迹", "资产轨迹", "设备轨迹",
    "在哪里", "在哪", "当前区域",
    "热力图", "活动热区", "电子围栏", "越界", "考勤", "门禁", "在场人员", "停留时间",
    "告警", "报警", "在线率", "低电量", "区域分布", "运营态势", "运营报告", "一键报告",
    "柱状图", "条形图", "饼图", "折线图", "雷达图", "仪表盘", "原理图", "示意图", "架构图",
    "流程图", "平面图", "位置图", "3d地图", "数字孪生", "接口接入", "真实接口", "模拟接口",
)

UNRELATED_TERMS = (
    "天气预报", "今天天气", "明天天气", "股票", "股价", "基金", "比特币", "彩票", "菜谱", "做饭",
    "写代码", "python代码", "编程", "程序报错", "写作文", "写诗", "讲笑话", "讲故事", "翻译成", "电影", "电视剧",
    "游戏攻略", "星座", "八字", "数学题", "历史人物", "总统", "明星", "歌曲", "旅游攻略", "酒店推荐",
    "餐厅推荐", "手机推荐", "电脑推荐",
)

SCENE_SCOPE_SUMMARIES = {
    "medical": "医院急诊绿通、患者与医护定位、医疗资产及设备运营",
    "safety": "工业园区人员与资产定位、作业安全、考勤门禁、能源和预测维护",
    "building": "政企楼宇人员资产、机电能源、安防消防、停车电梯和运维",
    "eldercare": "养老机构老人定位、照护、床位、健康终端和养老告警",
    "diagnostics": "工业设备状态监测、振动频谱、故障研判和检修建议",
    "iot": "物联网终端、网关信标、人员资产定位、物模型、围栏和设备事件",
    "command": "平台智能体能力查询，以及医疗、安全、楼宇、养老、设备诊断和物联网业务分发",
}


def is_command_meta_request(question: str) -> bool:
    compact = re.sub(r"\s+", "", (question or "").lower())
    return any(term.replace(" ", "") in compact for term in COMMAND_META_TERMS) or any(
        term in compact for term in ("系统知识", "系统里", "系统相关", "平台功能", "知识库", "系统原理")
    )


def _is_related_knowledge(text: str) -> bool:
    domain_terms = tuple(term for terms in SCENE_SCOPE_TERMS.values() for term in terms)
    domain_terms += GENERIC_BUSINESS_TERMS + ("系统", "平台", "rfid", "uwb", "蓝牙", "定位", "知识库")
    explanations = ("什么是", "是什么", "什么意思", "为什么", "如何", "怎么", "原理", "区别", "知识", "解释", "介绍", "接入", "对接")
    return any(term in text for term in domain_terms) and any(term in text for term in explanations)


def assess_scene_relevance(question: str, scene: str, has_context: bool = False) -> dict[str, Any]:
    """在模型调用前判断是否属于当前智能体；明确无关内容直接阻断。"""
    text = re.sub(r"\s+", "", (question or "").lower())
    if not text:
        return {"relevant": False, "reason": "empty"}
    if scene == "command":
        route = route_supervisor_scene(text)
        return {"relevant": bool(is_command_meta_request(text) or route["scene"]), "reason": "command"}
    if scene not in SCENE_SCOPE_TERMS:
        return {"relevant": False, "reason": "unknown_scene"}
    if _is_related_knowledge(text):
        return {"relevant": True, "reason": "related_knowledge"}
    if any(term in text for term in UNRELATED_TERMS):
        return {"relevant": False, "reason": "explicitly_unrelated"}
    if is_command_meta_request(text):
        return {"relevant": True, "reason": "capability"}
    own_terms = SCENE_SCOPE_TERMS[scene]
    if any(term in text for term in own_terms):
        return {"relevant": True, "reason": "scene_keyword"}
    route = route_supervisor_scene(text)
    target = route.get("scene", "")
    if target and target != scene and route.get("scores", {}).get(target, 0) >= 6:
        return {"relevant": False, "reason": "other_scene", "target": target}
    if any(term in text for term in COMMON_OPERATION_TERMS):
        return {"relevant": True, "reason": "shared_capability"}
    if has_context and _looks_like_follow_up(text):
        return {"relevant": True, "reason": "conversation"}
    return {"relevant": True, "reason": "needs_interpretation"}


def scene_scope_refusal(scene: str) -> str:
    label = SCENE_LABELS.get(scene, "智枢 AI · 全域智能指挥中心" if scene == "command" else "当前智能体")
    scope = SCENE_SCOPE_SUMMARIES.get(scene, "当前配置的业务领域")
    return f"「{label}」可以帮助你查询{scope}，也可以解释相关业务知识、技术原理和系统用法。其他场景的实际数据请切换对应智能体或使用总控查询。"


def _densify_track(key_points: list[dict[str, Any]], subject: str, fallback_weights: list[int] | None = None) -> list[dict[str, Any]]:
    dense_points: list[dict[str, Any]] = []
    weights = fallback_weights or [int(point.get("weight", 4)) for point in key_points]
    for index, point in enumerate(key_points):
        weight = point.get("weight", weights[index] if index < len(weights) else 4)
        weighted = {**point, "name":subject, "weight":weight, "key":True}
        if not dense_points:
            dense_points.append(weighted)
            continue
        previous = key_points[index - 1]
        previous_weight = previous.get("weight", weights[index - 1] if index - 1 < len(weights) else 4)
        for step in range(1, 6):
            ratio = step / 6
            bend = (1 if index % 2 else -1) * (1 - abs(ratio - .5) * 2) * 2.2
            dense_points.append({
                "x":round(previous["x"] + (point["x"] - previous["x"]) * ratio, 2),
                "y":round(previous["y"] + (point["y"] - previous["y"]) * ratio + bend, 2),
                "weight":round(previous_weight + (weight - previous_weight) * ratio, 2),
                "area":point["area"], "name":subject, "key":False,
            })
        dense_points.append(weighted)
    return dense_points


def _eldercare_group_payload() -> dict[str, Any]:
    tracks = []
    all_points = []
    all_keys = []
    area_weights: dict[str, float] = {}
    for item in ELDERCARE_GROUP_TRAJECTORIES:
        keys = [{**point, "name":item["name"], "key":True} for point in item["points"]]
        dense = _densify_track(keys, item["name"])
        tracks.append({"name":item["name"], "color":item["color"], "keyPoints":keys, "points":dense})
        all_points.extend(dense); all_keys.extend(keys)
        for point in keys:
            area_weights[point["area"]] = area_weights.get(point["area"], 0) + float(point.get("weight", 1))
    hottest = max(area_weights, key=area_weights.get)
    return {
        "scene":"eldercare", "sceneName":SCENE_LABELS["eldercare"], "subject":"全部老人（5人）",
        "mode":"group", "subjectCount":len(tracks), "countUnit":"人", "layout":ELDERCARE_GROUP_LAYOUT,
        "tracks":tracks, "keyPoints":all_keys, "points":all_points,
        "heatmap":[{"x":p["x"],"y":p["y"],"weight":p["weight"],"area":p["area"],"name":p["name"]} for p in all_points],
        "summary":{"hottestArea":hottest,"keyNodes":len(all_keys),"samplePoints":len(all_points),"timeRange":"07:18—09:40","subjectCount":len(tracks),"countUnit":"人"},
        "durationSeconds":14, "source":"当前养老智能体全体老人轨迹模拟接口", "isSimulation":True,
    }


def _group_kind(scene: str, text: str) -> str:
    if scene == "diagnostics":
        return "asset"
    asset_words = ("资产", "设备", "终端", "仪器", "车辆", "装备", "机组")
    return "asset" if any(word in text for word in asset_words) else "person"


def _generic_group_payload(scene: str, kind: str) -> dict[str, Any] | None:
    spec = GROUP_TRAJECTORY_SUBJECTS.get(scene, {}).get(kind)
    base = TRAJECTORIES.get(scene, [])
    if not spec or not base:
        return None
    label, unit, names = spec
    base_weights = TRAJECTORY_WEIGHTS.get(scene, [4] * len(base))
    tracks, all_points, all_keys = [], [], []
    area_weights: dict[str, float] = {}
    for track_index, name in enumerate(names):
        offsets = GROUP_TRACK_OFFSETS[track_index % len(GROUP_TRACK_OFFSETS)]
        ordered = list(reversed(base)) if track_index % 2 else list(base)
        keys = []
        for point_index, point in enumerate(ordered):
            dx, dy = offsets[point_index % len(offsets)]
            weight_index = (point_index + track_index) % len(base_weights)
            item = {
                **point, "name":name,
                "x":max(5, min(95, point["x"] + dx)), "y":max(7, min(91, point["y"] + dy)),
                "weight":max(2, min(10, base_weights[weight_index] + (track_index % 3) - 1)), "key":True,
            }
            keys.append(item)
            area_weights[item["area"]] = area_weights.get(item["area"], 0) + float(item["weight"])
        dense = _densify_track(keys, name)
        tracks.append({"name":name,"color":GROUP_TRACK_COLORS[track_index % len(GROUP_TRACK_COLORS)],"keyPoints":keys,"points":dense})
        all_keys.extend(keys); all_points.extend(dense)
    hottest = max(area_weights, key=area_weights.get)
    return {
        "scene":scene, "sceneName":SCENE_LABELS.get(scene, scene), "subject":f"{label}（{len(names)}{unit}）",
        "mode":"group", "subjectCount":len(names), "countUnit":unit,
        "layout":TRAJECTORY_LAYOUTS.get(scene, {"title":"场景定位平面","zones":[]}), "tracks":tracks,
        "keyPoints":all_keys, "points":all_points,
        "heatmap":[{"x":p["x"],"y":p["y"],"weight":p["weight"],"area":p["area"],"name":p["name"]} for p in all_points],
        "summary":{"hottestArea":hottest,"keyNodes":len(all_keys),"samplePoints":len(all_points),"timeRange":"07:00—09:40","subjectCount":len(names),"countUnit":unit},
        "durationSeconds":14, "source":f"当前{SCENE_LABELS.get(scene, scene)}群体轨迹模拟接口", "isSimulation":True,
    }


def trajectory_payload(scene: str, keyword: str = "") -> dict[str, Any]:
    text = (keyword or "").strip()
    group_request = any(word in text for word in ("所有", "全部", "全体", "整体", "群体", "多人", "多设备"))
    if scene == "eldercare" and group_request and _group_kind(scene, text) == "person":
        return _eldercare_group_payload()
    if group_request:
        group_payload = _generic_group_payload(scene, _group_kind(scene, text))
        if group_payload:
            return group_payload
    key_points = [dict(point) for point in TRAJECTORIES.get(scene, [])]
    default_subject = key_points[0]["name"] if key_points else "定位对象"
    # 自然语言问题不能整体变成对象名；只识别演示数据中已知对象或短名称输入。
    subject = default_subject
    known_subjects = {items[0]["name"] for items in TRAJECTORIES.values() if items}
    for candidate in known_subjects:
        if candidate in text:
            subject = candidate
            break
    else:
        if 0 < len(text) <= 16 and not any(word in text for word in ("生成", "查看", "轨迹", "热力", "回放", "分布", "停留")):
            subject = text
    key_points = [{**point, "name": subject} for point in key_points]
    weights = TRAJECTORY_WEIGHTS.get(scene, [3] * len(key_points))
    dense_points = _densify_track(key_points, subject, weights)
    hottest_index = max(range(len(key_points)), key=lambda i: weights[i]) if key_points else 0
    hottest = key_points[hottest_index]["area"] if key_points else "--"
    return {
        "scene": scene, "sceneName": SCENE_LABELS.get(scene, scene), "subject": subject,
        "layout": TRAJECTORY_LAYOUTS.get(scene, {"title":"场景定位平面","zones":[]}),
        "keyPoints": key_points, "points": dense_points,
        "heatmap": [{"x":p["x"],"y":p["y"],"weight":p["weight"],"area":p["area"]} for p in dense_points],
        "summary": {"hottestArea":hottest,"keyNodes":len(key_points),"samplePoints":len(dense_points),"timeRange":f'{key_points[0]["time"]}—{key_points[-1]["time"]}' if key_points else "--"},
        "durationSeconds": 12, "source":"当前智能体场景轨迹模拟接口", "isSimulation": True,
    }


def make_trajectory_tool(scene: str) -> StructuredTool:
    """为每个领域智能体创建同名但数据场景隔离的热力图渲染工具。"""
    if scene not in TRAJECTORIES:
        raise ValueError("该场景不支持轨迹热力图")

    def render_trajectory_heatmap(subject: str = "", reason: str = "") -> str:
        """根据历史轨迹查询结果渲染轨迹回放与停留热力图。"""
        payload = trajectory_payload(scene, subject)
        payload["decisionReason"] = str(reason or "历史轨迹与停留分布适合空间可视化")[:120]
        return "__TRAJECTORY__" + json.dumps(payload, ensure_ascii=False)

    return StructuredTool.from_function(
        name="render_trajectory_heatmap",
        description=(
            "在已经查询历史位置后，智能判断并渲染当前对象的轨迹回放与停留热力图。"
            "适用于历史路径、区域停留、活动集中区、频繁出入、徘徊或越界移动；"
            "仅查询当前实时位置、设备状态或单个数值时不要调用。subject 传对象名称；"
            "群体问题必须原样传所有老人、全部人员或全部资产，不得替换成单个人。reason 说明调用依据。"
        ),
        func=render_trajectory_heatmap,
    )


REPORT_FIELD_LABELS = {
    "asOf":"数据时间", "dataSource":"数据来源", "count":"数量", "data":"明细", "total":"总数",
    "building":"楼宇", "floors":"楼层数", "todayEnergyKwh":"今日能耗（kWh）", "pue":"PUE",
    "solarPowerKw":"光伏功率（kW）", "availableParkingSpaces":"停车余位", "elevatorsNormal":"正常电梯",
    "visitorsOnSite":"在场访客", "activeAlarms":"活跃告警", "systems":"接入系统数", "activeCount":"未处理数量",
    "alarmId":"告警编号", "system":"所属系统", "device":"设备", "point":"监测点", "value":"当前值",
    "level":"等级", "time":"时间", "location":"位置", "handled":"已处理", "status":"状态",
    "online":"在线数", "offline":"离线数", "onlineRate":"在线率", "lowBattery":"低电量数",
    "patients":"患者数", "assets":"资产数", "employees":"人员数", "events":"事件数",
    "name":"名称", "area":"区域", "type":"类型", "priority":"优先级", "message":"说明",
}


def _report_label(key: Any) -> str:
    text = str(key)
    return html.escape(REPORT_FIELD_LABELS.get(text, text.replace("_", " ")))


def _report_value(value: Any) -> str:
    """把接口数据变成业务可读卡片/表格，不向用户展示 JSON 代码。"""
    if isinstance(value, dict):
        items = []
        for key, item in value.items():
            label = _report_label(key)
            if isinstance(item, (dict, list)):
                items.append(f"<div class='report-group'><h3>{label}</h3>{_report_value(item)}</div>")
            else:
                items.append(f"<div class='metric'><span>{label}</span><b>{html.escape(str(item))}</b></div>")
        return f"<div class='metrics'>{''.join(items)}</div>"
    if isinstance(value, list):
        if not value:
            return "<p class='muted'>暂无数据</p>"
        if all(isinstance(item, dict) for item in value):
            keys: list[str] = []
            for item in value[:20]:
                for key in item:
                    if key not in keys and not isinstance(item[key], (dict, list)):
                        keys.append(key)
            if keys:
                head = "".join(f"<th>{_report_label(key)}</th>" for key in keys)
                rows = "".join("<tr>" + "".join(f"<td>{html.escape(str(item.get(key,'')))}</td>" for key in keys) + "</tr>" for item in value[:30])
                return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>"
        return "<ul>" + "".join(f"<li>{_report_value(item)}</li>" for item in value[:30]) + "</ul>"
    text = html.escape(str(value or "暂无内容")).replace("\n", "<br>")
    return f"<p>{text}</p>"


def generate_report(scene: str, title: str, sections: list[dict[str, Any]]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{scene}-report-{stamp}.html"
    cards = []
    for section in sections:
        body = section.get("data", section.get("content", ""))
        cards.append(f"<section><h2>{html.escape(str(section.get('title','分析结果')))}</h2>{_report_value(body)}</section>")
    page = f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title><style>
*{{box-sizing:border-box}}body{{font-family:'Microsoft YaHei','PingFang SC',sans-serif;max-width:1120px;margin:0 auto;padding:36px;color:#173047;background:#eef5f7}}header{{padding:28px;border-radius:16px;background:linear-gradient(135deg,#073b55,#087b83);color:white;box-shadow:0 14px 32px #0b53602b}}h1{{margin:0 0 9px;font-size:28px}}header small{{color:#c9f7f1}}.actions{{display:flex;justify-content:flex-end;margin:16px 0}}button{{padding:10px 16px;border:0;border-radius:8px;background:#087b83;color:white;font-weight:700;cursor:pointer}}section{{margin:18px 0;padding:22px;border:1px solid #d6e5e9;border-radius:14px;background:white;box-shadow:0 8px 22px #2348580e}}h2{{margin:0 0 16px;color:#075b70;font-size:19px}}h3{{font-size:14px;color:#54727d}}.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:10px}}.metric{{display:flex;flex-direction:column;gap:7px;min-height:74px;padding:13px;border-left:3px solid #13a58f;border-radius:8px;background:#f2f8f8}}.metric span{{font-size:12px;color:#6c838b}}.metric b{{font-size:17px;color:#173047;word-break:break-word}}.report-group{{grid-column:1/-1}}.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:10px;border-bottom:1px solid #e2ecef;text-align:left}}th{{background:#e9f5f4;color:#146270}}tr:nth-child(even){{background:#f8fbfc}}.muted{{color:#80949b}}ul{{line-height:1.8}}@media print{{body{{padding:0;background:white}}.actions{{display:none}}header,section{{box-shadow:none;break-inside:avoid}}}}
</style></head><body><header><h1>{html.escape(title)}</h1><small>{SCENE_LABELS.get(scene,scene)} · 生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 演示数据</small></header><div class='actions'><button onclick='print()'>打印 / 保存为 PDF</button></div>{''.join(cards)}</body></html>"""
    path = REPORT_DIR / filename; path.write_text(page, encoding="utf-8"); return path
