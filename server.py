"""轻量网页：无 Gradio CDN / WebSocket，回答走 SSE 流式输出。"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from agent import SCENE_TOOLS, TOOL_LABELS, ask_stream, build_agent, route_local_tools, generate_schematic_image, prepare_grounded_image
from building_tools import BUILDING_TOOL_BY_NAME
from knowledge_base import catalog_metadata, get_document, list_documents, search_documents
from skill_test import format_report, run_skill_tests
from observability import langfuse_enabled
from system_metrics import system_metrics
from local_model_manager import local_model_manager
from public_access import public_demo_guard
from response_format_tools import normalize_response_format
from platform_features import (
    LOCAL_ONLY_TOOLS, REPORT_DIR, generate_report, get_agent_configs, get_demo_state, list_demo_scenarios,
    assess_scene_relevance, is_command_meta_request, reset_demo_state, route_supervisor_scene,
    scene_scope_refusal, set_demo_state, trajectory_payload,
    update_agent_config,
)
from predictive_maintenance_tools import (
    predict_equipment_failures,
    query_condition_monitoring,
    query_equipment_health,
    query_predictive_monitoring_terminals,
    query_remaining_useful_life,
    recommend_predictive_maintenance,
    summarize_predictive_maintenance,
    summarize_predictive_monitoring_terminals,
)

ROOT = Path(__file__).resolve().parent
TELEGRAM_VISUAL_DIR = ROOT / "runtime" / "telegram_visuals"
TELEGRAM_HEALTH_PATH = ROOT / "runtime" / "telegram_health.json"
try:
    agent = build_agent("deepseek", scene="safety")
    agent_error = ""
except RuntimeError as exc:
    # 未配置模型密钥时仍可启动前端与 Skill 测试，便于先完成现场部署。
    agent = None
    agent_error = str(exc)
app = FastAPI(title="多场景智能运营中心")
app.middleware("http")(public_demo_guard)


class ChatIn(BaseModel):
    message: str
    session_id: str = "web"
    scene: str = "safety"
    provider: str = "deepseek"
    model: str = ""
    response_format: str = "auto"
    image_backend: str = "auto"


class TestIn(BaseModel):
    skill_id: str = ""
    include_e2e: bool = False
    scene: str = "safety"


class ToolCallIn(BaseModel):
    args: dict = Field(default_factory=dict)


class AgentConfigIn(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    sourceMode: str | None = None
    baseUrl: str | None = None
    authHeader: str | None = None
    authValue: str | None = None
    timeoutSeconds: int | None = None
    endpoints: dict | None = None


class DemoIn(BaseModel):
    scenario_id: str
    step: int = 0


class ReportIn(BaseModel):
    scene: str
    title: str = ""


def _require_local_admin(request: Request) -> None:
    host = request.client.host if request.client else ""
    if request.headers.get("cf-ray") or host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="配置修改仅允许在本机操作")


@app.get("/")
def index():
    return FileResponse(
        ROOT / "static" / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/assets/{filename}")
def static_asset(filename: str):
    """提供前端品牌图片等静态资源，且只允许访问 assets 目录内的文件。"""
    safe_name = Path(filename).name
    path = ROOT / "static" / "assets" / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="静态资源不存在")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/telegram-visuals/{token}")
def telegram_visual_payload(token: str):
    """供本机无头浏览器读取一次性可视化任务；随机令牌避免访问其他文件。"""
    if len(token) != 32 or any(char not in "0123456789abcdef" for char in token):
        raise HTTPException(status_code=404, detail="可视化任务不存在")
    path = TELEGRAM_VISUAL_DIR / f"{token}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="可视化任务不存在")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="可视化任务无效") from exc


@app.get("/api/generated-images/{filename}")
def generated_image(filename: str):
    """只允许读取 ComfyUI 输出目录内的 PNG，供原理图事件在网页展示。"""
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(status_code=404, detail="image not found")
    path = Path("/home/administrator/comfyui_outputs") / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="image not found")
    return FileResponse(path)


def is_diagram_request(text: str) -> bool:
    """自动识别用户是否想生成原理图/流程图/示意图/画图。"""
    if not text:
        return False
    t = text.lower()
    if any(k in t for k in ("原理图", "示意图", "架构图", "流程图", "插画", "拓扑图", "设计图", "结构图", "系统图", "框图", "示意")):
        return True
    if any(k in t for k in ("图文并茂", "画图", "生成图", "生图", "作图", "绘图", "画一张", "画一个", "画幅", "做一张图", "生成图片", "出张图", "画张图", "画个图")):
        return True
    import re
    if re.search(r"(画|绘制|生成|做|出|来)[一两1-9个张幅套份首]*.*(图|图片|插图|架构|流程|拓扑)", t):
        return True
    return False


def is_trajectory_request(text: str) -> bool:
    """轨迹热力图属于场景内置可视化，不应被通用生图规则截获。"""
    t = (text or "").lower()
    return "轨迹" in t or any(word in t for word in ("热力图", "停留热区", "活动热区", "热力分布"))


def is_chart_request(text: str) -> bool:
    t = (text or "").lower()
    return any(word in t for word in ("图表", "柱状图", "条形图", "饼图", "环形图", "折线图", "趋势图", "面积图", "雷达图", "仪表盘"))


def is_report_request(text: str) -> bool:
    t = (text or "").lower()
    return "报告" in t and any(word in t for word in ("生成", "一键", "制作", "导出", "出一份", "做一份"))


@app.post("/api/chat")
def chat(body: ChatIn):
    def events():
        trajectory_request = is_trajectory_request(body.message)
        report_request = is_report_request(body.message)
        diagram_request = is_diagram_request(body.message) and not trajectory_request and not report_request and not is_chart_request(body.message)
        requested_scene = body.scene.lower().strip()
        scene = requested_scene
        if scene == "command" and not is_command_meta_request(body.message):
            route_key = str(body.session_id or "web")
            route = route_supervisor_scene(body.message, SUPERVISOR_SESSION_ROUTES.get(route_key, ""))
            if not route["scene"]:
                yield f"data: {json.dumps({'type': 'formatted', 'text': scene_scope_refusal('command')}, ensure_ascii=False)}\n\n"
                yield "data: {\"type\": \"done\"}\n\n"
                return
            scene = route["scene"]
            SUPERVISOR_SESSION_ROUTES[route_key] = scene
            yield f"data: {json.dumps({'type': 'status', 'text': f'智能体总控已路由至「{route["name"]}」'}, ensure_ascii=False)}\n\n"
        if diagram_request and scene not in SCENE_TOOLS:
            scene = "safety"
        if scene not in SCENE_TOOLS:
            yield f"data: {json.dumps({'type': 'error', 'text': '未知智能体场景'}, ensure_ascii=False)}\n\n"
            yield "data: {\"type\": \"done\"}\n\n"
            return
        isolated_session_id = f"{requested_scene}:{scene}:{body.session_id}"
        scope_key = (scene, isolated_session_id)
        scope = assess_scene_relevance(body.message, scene, scope_key in SCENE_SESSION_CONTEXTS)
        if not scope["relevant"]:
            yield f"data: {json.dumps({'type': 'formatted', 'text': scene_scope_refusal(scene)}, ensure_ascii=False)}\n\n"
            yield "data: {\"type\": \"done\"}\n\n"
            return
        SCENE_SESSION_CONTEXTS.add(scope_key)
        if report_request:
            try:
                report = _build_scene_report(scene)
                yield f"data: {json.dumps({'type':'formatted','text':f'已生成 **{report["title"]}**，报告内容来自当前智能体的隔离数据接口。'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type':'report','report':report}, ensure_ascii=False)}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'type':'error','text':f'报告生成失败：{exc}'}, ensure_ascii=False)}\n\n"
            yield "data: {\"type\": \"done\"}\n\n"
            return
        if diagram_request:
            backend = (body.image_backend or "auto").lower().strip()
            backend_label = {"gemini": "Gemini 云端", "comfyui": "本地 ComfyUI", "auto": "自动"}.get(backend, "自动")
            yield f"data: {json.dumps({'type': 'status', 'text': '正在读取当前智能体的业务数据…'}, ensure_ascii=False)}\n\n"
            import os as _os
            _prev = _os.environ.get("IMAGE_BACKEND")
            _os.environ["IMAGE_BACKEND"] = backend
            try:
                grounded = prepare_grounded_image(scene, body.message)
                source_text = "、".join(grounded["sources"]) or "当前业务接口"
                for source in grounded["sources"]:
                    yield f"data: {json.dumps({'type': 'tool', 'name': source, 'label': TOOL_LABELS.get(source, source), 'phase': 'done'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'status', 'text': f'已读取 {source_text}，正在生成原理图（{backend_label}）…'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'tool', 'name': 'generate_schematic_image', 'label': '业务数据原理图生成', 'phase': 'calling'}, ensure_ascii=False)}\n\n"
                raw_image = generate_schematic_image.invoke({"prompt": grounded["prompt"], "style": "Blueprint", "aspect": "16:9", "seed": 0})
                yield f"data: {json.dumps({'type': 'tool', 'name': 'generate_schematic_image', 'label': '业务数据原理图生成', 'phase': 'done'}, ensure_ascii=False)}\n\n"
                if isinstance(raw_image, str) and raw_image.startswith("__IMAGE__"):
                    image_payload = json.loads(raw_image[len("__IMAGE__"):])
                    image_payload["scene"] = scene
                    image_payload["scene_label"] = grounded["sceneLabel"]
                    image_payload["grounding_sources"] = grounded["sources"]
                    yield f"data: {json.dumps({'type': 'image', 'image': image_payload}, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'text': str(raw_image)[:800]}, ensure_ascii=False)}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'type': 'error', 'text': f'原理图生成失败：{exc}'}, ensure_ascii=False)}\n\n"
            finally:
                if _prev is None:
                    _os.environ.pop("IMAGE_BACKEND", None)
                else:
                    _os.environ["IMAGE_BACKEND"] = _prev
            yield "data: {\"type\": \"done\"}\n\n"
            return
        local_tool_names = None
        if body.provider.lower().strip() == "local":
            yield f"data: {json.dumps({'type': 'status', 'text': '正在按需启动本地 Qwen3.8-27B…'}, ensure_ascii=False)}\n\n"
            if not local_model_manager.ensure_ready():
                detail = local_model_manager.as_dict().get("error") or "本地模型启动失败"
                yield f"data: {json.dumps({'type': 'error', 'text': detail}, ensure_ascii=False)}\n\n"
                yield "data: {\"type\": \"done\"}\n\n"
                return
            local_tool_names, route_groups = route_local_tools(body.message, scene=scene)
            route_key = (scene, isolated_session_id)
            if route_groups == ["综合查询"] and route_key in LOCAL_SESSION_ROUTES:
                local_tool_names, route_groups = LOCAL_SESSION_ROUTES[route_key]
            else:
                LOCAL_SESSION_ROUTES[route_key] = (local_tool_names, route_groups)
            domain_text = " + ".join(route_groups)
            domain_count = max(0, len(local_tool_names) - 2)
            yield f"data: {json.dumps({'type': 'status', 'text': f'本地工具路由：{domain_text}（{domain_count} 个业务接口）'}, ensure_ascii=False)}\n\n"
        selected_agent = get_agent(scene, body.provider, body.model, local_tool_names, body.response_format)
        if selected_agent is None:
            yield f"data: {json.dumps({'type': 'error', 'text': agent_error}, ensure_ascii=False)}\n\n"
            yield "data: {\"type\": \"done\"}\n\n"
            return
        try:
            for ev in ask_stream(selected_agent, body.message.strip(), thread_id=isolated_session_id, metadata={"provider": body.provider, "model": body.model, "scene": scene, "app": "multi-scene-intelligence"}):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'text': str(exc)}, ensure_ascii=False)}\n\n"
        if body.provider.lower().strip() == "local":
            local_model_manager.touch()
        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "agentReady": agent is not None, "mode": "multi-scene-intelligence", "scenes": list(SCENE_TOOLS), "langfuse": langfuse_enabled(), "providers": model_options()}


@app.get("/api/integrations/telegram/status")
def telegram_status():
    """综合 systemd 进程与独立探活心跳，绝不返回 Token 或代理配置。"""
    configured = bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip())
    if not configured:
        return {"integration": "telegram", "configured": False, "online": False, "status": "unconfigured"}
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "personnel-safety-telegram.service"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        service_state = result.stdout.strip() or "unknown"
        active = result.returncode == 0 and service_state == "active"
        health = {}
        heartbeat_age = None
        try:
            health = json.loads(TELEGRAM_HEALTH_PATH.read_text(encoding="utf-8"))
            heartbeat_age = max(0, int(time.time() - TELEGRAM_HEALTH_PATH.stat().st_mtime))
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        heartbeat_limit = max(90, int(health.get("watchdogIntervalSeconds") or 30) * 3)
        fresh = heartbeat_age is not None and heartbeat_age <= heartbeat_limit
        health_status = str(health.get("status") or "starting")
        online = active and fresh and health_status == "online"
        status = "online" if online else ("degraded" if active else "offline")
        return {
            "integration": "telegram",
            "configured": True,
            "online": online,
            "status": status,
            "serviceState": service_state,
            "healthState": health_status,
            "heartbeatAgeSeconds": heartbeat_age,
            "lastSuccessAt": health.get("lastSuccessAt", ""),
            "consecutiveFailures": int(health.get("consecutiveFailures") or 0),
        }
    except (OSError, subprocess.SubprocessError):
        return {"integration": "telegram", "configured": True, "online": False, "status": "unknown"}


MODEL_OPTIONS = {
    "deepseek": ["deepseek-v4-flash", "deepseek-v4-flash-vision-exp"],
    "local": ["qwen3.8-27b-local"],
    "openrouter": [
        "deepseek/deepseek-chat-v3.1",
        "openai/gpt-5.6-sol",
        "openai/gpt-5.6-terra",
        "openai/gpt-5.6-luna",
        "openai/gpt-5.5",
        "openai/gpt-5.4-mini",
        "anthropic/claude-opus-5",
        "anthropic/claude-sonnet-5",
        "anthropic/claude-fable-5.1",
        "anthropic/claude-sonnet-4.6",
        "anthropic/claude-haiku-4.5",
        "google/gemini-3.7-flash",
        "google/gemini-3.5-flash",
        "google/gemini-3.1-pro-preview",
        "deepseek/deepseek-v4-pro-0813",
        "deepseek/deepseek-v4-flash-0731",
        "deepseek/deepseek-v3.2",
        "deepseek/deepseek-r1",
        "qwen/qwen3.8-max",
        "qwen/qwen3.8-flash",
        "qwen/qwen3.8-27b",
        "qwen/qwen3.7-plus",
        "qwen/qwen3-max-thinking",
        "moonshotai/kimi-k3",
        "moonshotai/kimi-k2.6",
        "z-ai/glm-5.3",
        "z-ai/glm-5.3-flash",
        "meta-llama/llama-4-maverick",
        "meta-llama/llama-3.3-70b-instruct",
    ],
}
AGENT_CACHE = {("safety", "deepseek", "deepseek-v4-flash", "auto"): agent} if agent is not None else {}
LOCAL_SESSION_ROUTES: dict[tuple[str, str], tuple[list[str], list[str]]] = {}
SUPERVISOR_SESSION_ROUTES: dict[str, str] = {}
SCENE_SESSION_CONTEXTS: set[tuple[str, str]] = set()


def model_options():
    return [
        {"id": provider, "models": models, "configured": provider == "local" or bool(__import__("os").getenv(f"{provider.upper()}_API_KEY"))}
        for provider, models in MODEL_OPTIONS.items()
    ]


def get_agent(scene: str, provider: str, model: str, local_tool_names: list[str] | None = None, response_format: str = "auto"):
    if scene not in SCENE_TOOLS:
        return None
    provider = (provider or "deepseek").lower().strip()
    allowed = MODEL_OPTIONS.get(provider)
    if not allowed:
        return None
    model = model if model in allowed else allowed[0]
    response_format = normalize_response_format(response_format)
    key = (scene, provider, model, response_format, tuple(sorted(local_tool_names or []))) if provider == "local" else (scene, provider, model, response_format)
    if key not in AGENT_CACHE:
        try:
            AGENT_CACHE[key] = build_agent(provider, model, local_tool_names=local_tool_names, scene=scene, response_format=response_format)
        except RuntimeError:
            return None
    return AGENT_CACHE[key]


SCENE_METADATA = {
    "medical": {
        "id": "medical", "name": "医脉 AI · 急诊与医疗资产智控中心", "shortName": "医脉 AI · 医疗",
        "description": "面向医院急诊与设备运营，快速查询患者流转、医护与资产位置、超时预警和设备状态。",
        "capabilities": ["人员与患者定位", "急诊绿通流程", "医疗资产定位", "停留超时预警", "设备能效分析"],
        "dataNamespace": "medical", "theme": "mint",
    },
    "safety": {
        "id": "safety", "name": "安域 AI · 人员安全智控中心", "shortName": "安域 AI · 安全",
        "description": "面向工业园区安全运营，融合人员与资产定位、考勤门禁、作业票、报警和能源设备数据。",
        "capabilities": ["人员与资产定位", "考勤门禁", "作业票合规", "人员安全报警", "能源与预测维护"],
        "dataNamespace": "safety", "theme": "industrial",
    },
    "building": {
        "id": "building", "name": "筑境 AI · 楼宇运营智控中心", "shortName": "筑境 AI · 楼宇",
        "description": "面向政企楼宇综合运营，统一查询人员资产位置、机电能源、安防消防、告警和维保信息。",
        "capabilities": ["人员与资产定位", "能源与空调", "安防与消防", "停车与电梯", "告警与维保"],
        "dataNamespace": "building", "theme": "command",
    },
    "eldercare": {
        "id": "eldercare", "name": "颐护 AI · 康养物联智控中心", "shortName": "颐护 AI · 养老",
        "description": "依据钛颐康平台接口，统一查询老人位置、床位、围栏、健康终端和养老告警。",
        "capabilities": ["老人实时定位", "床位与区域", "电子围栏", "健康终端", "养老告警"],
        "dataNamespace": "eldercare", "theme": "mint",
    },
    "diagnostics": {
        "id": "diagnostics", "name": "机鉴 AI · 设备健康诊断中心", "shortName": "机鉴 AI · 诊断",
        "description": "依据STD V1.6接口，查询设备树、实时历史指标、波形频谱、报警和诊断建议。",
        "capabilities": ["设备树", "实时指标", "历史趋势", "波形频谱", "故障诊断"],
        "dataNamespace": "diagnostics", "theme": "industrial",
    },
    "iot": {
        "id": "iot", "name": "万联 AI · 物联网运营中心", "shortName": "万联 AI · 物联网",
        "description": "依据真趣物联网V2.9接口，管理园区建筑、人员资产定位、网关信标、电子围栏、物模型、事件与控制记录。",
        "capabilities": ["人员与资产定位", "网关与终端", "定位信标", "电子围栏", "物模型与控制", "事件运营"],
        "dataNamespace": "iot", "theme": "command",
    },
    "command": {
        "id": "command", "name": "智枢 AI · 全域智能指挥中心", "shortName": "智枢 AI 总控",
        "description": "自动识别业务问题并路由到医疗、安全、楼宇、养老、设备诊断或物联网智能体。",
        "capabilities": ["意图识别", "智能路由", "场景目录", "跨领域入口", "数据隔离"],
        "dataNamespace": "command", "theme": "cyber",
    },
}


@app.get("/api/scenes")
def scenes():
    configs = get_agent_configs()
    data = []
    for scene, metadata in SCENE_METADATA.items():
        config = configs.get(scene, {})
        data.append({**metadata, "name": config.get("name") or metadata["name"], "sourceMode": config.get("sourceMode", "router" if scene == "command" else "mock"), "enabled": config.get("enabled", True)})
    return {"default": "safety", "data": data}


def _scene_tool_guide(scene: str) -> dict:
    tools = SCENE_TOOLS.get(scene, [])
    remote_tools = [item for item in tools if item.name not in LOCAL_ONLY_TOOLS]
    tool_specs = []
    for item in remote_tools:
        try:
            input_schema = item.args_schema.model_json_schema() if item.args_schema else {"type": "object", "properties": {}}
        except (AttributeError, TypeError):
            input_schema = {"type": "object", "properties": {}}
        tool_specs.append({"name": item.name, "description": item.description, "inputSchema": input_schema})
    return {
        "toolCount": len(tools),
        "remoteToolCount": len(remote_tools),
        "tools": [item.name for item in tools],
        "toolSpecs": tool_specs,
    }


@app.get("/api/interface-guides")
def public_interface_guides():
    """公开只读的客户接口规范，不包含 Base URL、凭据或运行配置。"""
    return {"data": [
        {"scene": scene, "name": SCENE_METADATA[scene]["name"], **_scene_tool_guide(scene)}
        for scene in SCENE_TOOLS if scene != "command"
    ]}


@app.get("/api/admin/agent-configs")
def agent_configs(request: Request):
    _require_local_admin(request)
    configs = get_agent_configs()
    return {"data": [{**config, **_scene_tool_guide(scene)} for scene, config in configs.items()]}


@app.put("/api/admin/agent-configs/{scene}")
def save_agent_config(scene: str, body: AgentConfigIn, request: Request):
    _require_local_admin(request)
    try:
        return update_agent_config(scene, body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/scenarios")
def demo_scenarios(scene: str = ""):
    return {"data":list_demo_scenarios(scene),"state":get_demo_state()}


@app.post("/api/demo/start")
def demo_start(body: DemoIn, request: Request):
    _require_local_admin(request)
    try:
        return set_demo_state(body.scenario_id, body.step)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/next")
def demo_next(request: Request):
    _require_local_admin(request)
    state = get_demo_state()
    if not state.get("active"):
        raise HTTPException(status_code=409, detail="尚未启动演示场景")
    return set_demo_state(state["scenarioId"], int(state.get("step",0))+1)


@app.post("/api/demo/reset")
def demo_reset(request: Request):
    _require_local_admin(request)
    return reset_demo_state()


@app.get("/api/visualizations/{scene}/trajectory")
def visualization_trajectory(scene: str, keyword: str = ""):
    if scene not in SCENE_METADATA or scene == "command":
        raise HTTPException(status_code=404, detail="未知轨迹场景")
    return trajectory_payload(scene, keyword)


@app.get("/api/router")
def route_agent(question: str):
    return route_supervisor_scene(question)


REPORT_TOOLS = {
    "medical": ("summarize_channels","summarize_area_stay","list_asset_alarms"),
    "safety": ("summarize_employees","summarize_alarms","summarize_energy_kpis"),
    "building": ("summarize_building_operations","query_building_alarms"),
    "eldercare": ("summarize_eldercare_operations","query_eldercare_alarms"),
    "diagnostics": ("summarize_diagnostic_operations","query_diagnostic_alarms"),
    "iot": ("summarize_iot_operations","summarize_iot_device_statistics","query_iot_events"),
}
REPORT_LABELS = {
    "summarize_channels":"急诊绿通概览", "summarize_area_stay":"区域停留分析", "list_asset_alarms":"医疗设备告警",
    "summarize_employees":"人员运营概览", "summarize_alarms":"安全告警概览", "summarize_energy_kpis":"能源运营指标",
    "summarize_building_operations":"楼宇综合态势", "query_building_alarms":"楼宇告警",
    "summarize_eldercare_operations":"养老运营态势", "query_eldercare_alarms":"养老照护告警",
    "summarize_diagnostic_operations":"设备健康态势", "query_diagnostic_alarms":"设备故障告警",
    "summarize_iot_operations":"物联网综合态势", "summarize_iot_device_statistics":"终端分布统计", "query_iot_events":"物联网事件",
}


def _build_scene_report(scene: str, title: str = "") -> dict:
    tools = {item.name:item for item in SCENE_TOOLS[scene]}
    sections = []
    for name in REPORT_TOOLS[scene]:
        try:
            raw = tools[name].invoke({})
            try:
                data = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                data = raw
            sections.append({"title":REPORT_LABELS.get(name,name),"data":data})
        except Exception as exc:
            sections.append({"title":REPORT_LABELS.get(name,name),"content":f"生成失败：{exc}"})
    report_title = title.strip() or f"{SCENE_METADATA[scene]['name']}运营报告"
    path = generate_report(scene, report_title, sections)
    return {
        "scene":scene, "title":report_title, "generatedAt":time.strftime("%Y-%m-%d %H:%M:%S"),
        "source":"当前智能体隔离接口", "sections":sections, "sectionCount":len(sections),
        "downloadUrl":f"/api/reports/{path.name}",
    }


@app.post("/api/reports/generate")
def report_generate(body: ReportIn, request: Request):
    scene = body.scene.lower().strip()
    if scene not in REPORT_TOOLS:
        raise HTTPException(status_code=404, detail="该场景暂不支持报告")
    report = _build_scene_report(scene, body.title)
    return {"status":"success", **report}


@app.get("/api/reports/{filename}")
def report_download(filename: str):
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name.endswith(".html"):
        raise HTTPException(status_code=404, detail="报告不存在")
    path = REPORT_DIR / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="报告不存在")
    return FileResponse(path, media_type="text/html")


@app.get("/api/scenes/{scene}/tools")
def scene_tools(scene: str):
    if scene not in SCENE_TOOLS:
        raise HTTPException(status_code=404, detail="未知智能体场景")
    return {
        "scene": scene,
        "count": len(SCENE_TOOLS[scene]),
        "data": [{"name": item.name, "description": item.description} for item in SCENE_TOOLS[scene]],
    }


@app.post("/api/scenes/{scene}/tools/{tool_name}")
def call_scene_tool(scene: str, tool_name: str, body: ToolCallIn):
    if scene not in SCENE_TOOLS:
        raise HTTPException(status_code=404, detail="未知智能体场景")
    tools = {item.name: item for item in SCENE_TOOLS[scene]}
    if tool_name not in tools:
        raise HTTPException(status_code=404, detail=f"{tool_name} 不属于 {scene} 场景")
    try:
        raw = tools[tool_name].invoke(body.args or {})
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {"output": raw}
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _scene_positioning_json(scene: str, tool_name: str, args: dict):
    if scene not in SCENE_TOOLS:
        raise HTTPException(status_code=404, detail="未知智能体场景")
    tools = {item.name: item for item in SCENE_TOOLS[scene]}
    tool = tools.get(tool_name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"{scene} 场景未配置 {tool_name}")
    return json.loads(tool.invoke(args))


@app.get("/api/scenes/{scene}/positioning/persons/realtime")
def scene_person_locations(scene: str, keyword: str = "", region: str = "", person_type: str = ""):
    return _scene_positioning_json(scene, "query_locations_realtime", {"keyword": keyword, "region": region, "person_type": person_type})


@app.get("/api/scenes/{scene}/positioning/persons/history")
def scene_person_history(scene: str, person: str, start_time: str = "", end_time: str = ""):
    return _scene_positioning_json(scene, "query_locations_history", {"person": person, "start_time": start_time, "end_time": end_time})


@app.get("/api/scenes/{scene}/positioning/persons/region-events")
def scene_person_region_events(scene: str, person: str, region: str = ""):
    return _scene_positioning_json(scene, "query_region_enter_leave", {"person": person, "region": region})


@app.get("/api/scenes/{scene}/positioning/assets/realtime")
def scene_asset_locations(scene: str, keyword: str = "", region: str = "", asset_type: str = ""):
    return _scene_positioning_json(scene, "query_asset_locations_realtime", {"keyword": keyword, "region": region, "asset_type": asset_type})


@app.get("/api/scenes/{scene}/positioning/assets/history")
def scene_asset_history(scene: str, asset: str, start_time: str = "", end_time: str = ""):
    return _scene_positioning_json(scene, "query_asset_locations_history", {"asset": asset, "start_time": start_time, "end_time": end_time})


@app.get("/api/scenes/{scene}/positioning/assets/region-events")
def scene_asset_region_events(scene: str, asset: str, region: str = ""):
    return _scene_positioning_json(scene, "query_asset_region_enter_leave", {"asset": asset, "region": region})


@app.get("/api/models")
def models():
    return {"providers": model_options(), "default": {"provider": "deepseek", "model": "deepseek-v4-flash"}}


@app.get("/api/system-metrics")
def metrics():
    return system_metrics()


def _tool_json(tool, args: dict):
    return json.loads(tool.invoke(args))


def _building_json(tool_name: str, args: dict | None = None):
    return _tool_json(BUILDING_TOOL_BY_NAME[tool_name], args or {})


@app.get("/api/scenes/building/overview")
def building_overview():
    return _building_json("summarize_building_operations")


@app.get("/api/scenes/building/power")
def building_power(floor: str = "", category: str = "", status: str = ""):
    return _building_json("query_building_power", {"floor": floor, "category": category, "status": status})


@app.get("/api/scenes/building/energy")
def building_energy(days: int = 7):
    return _building_json("query_building_energy", {"days": days})


@app.get("/api/scenes/building/hvac")
def building_hvac(floor: str = "", status: str = ""):
    return _building_json("query_hvac_status", {"floor": floor, "status": status})


@app.get("/api/scenes/building/water")
def building_water(system_type: str = "", status: str = ""):
    return _building_json("query_water_system", {"system_type": system_type, "status": status})


@app.get("/api/scenes/building/lighting")
def building_lighting(floor: str = "", mode: str = ""):
    return _building_json("query_lighting_status", {"floor": floor, "mode": mode})


@app.get("/api/scenes/building/solar")
def building_solar(status: str = ""):
    return _building_json("query_solar_generation", {"status": status})


@app.get("/api/scenes/building/charging-piles")
def building_charging_piles(status: str = "", location: str = ""):
    return _building_json("query_charging_piles", {"status": status, "location": location})


@app.get("/api/scenes/building/data-room")
def building_data_room(device_type: str = "", status: str = ""):
    return _building_json("query_data_room", {"device_type": device_type, "status": status})


@app.get("/api/scenes/building/parking")
def building_parking(floor: str = "", status: str = ""):
    return _building_json("query_parking_status", {"floor": floor, "status": status})


@app.get("/api/scenes/building/elevators")
def building_elevators(status: str = "", group: str = ""):
    return _building_json("query_elevator_status", {"status": status, "group": group})


@app.get("/api/scenes/building/security")
def building_security(system: str = "全部", status: str = ""):
    return _building_json("query_security_operations", {"system": system, "status": status})


@app.get("/api/scenes/building/fire-linkage")
def building_fire_linkage(floor: str = "", status: str = ""):
    return _building_json("query_fire_linkage", {"floor": floor, "status": status})


@app.get("/api/scenes/building/alarms")
def building_alarms(system: str = "", level: str = "", handled: str = ""):
    return _building_json("query_building_alarms", {"system": system, "level": level, "handled": handled})


@app.get("/api/scenes/building/assets")
def building_assets(system: str = "", keyword: str = "", status: str = ""):
    return _building_json("query_building_assets", {"system": system, "keyword": keyword, "status": status})


@app.get("/api/scenes/building/maintenance")
def building_maintenance(system: str = "", due_status: str = ""):
    return _building_json("query_building_maintenance", {"system": system, "due_status": due_status})


@app.get("/api/scenes/building/emergency/{alarm_id}")
def building_emergency(alarm_id: str):
    return _building_json("get_building_emergency_response", {"alarm_id": alarm_id})


@app.get("/api/predictive-maintenance/terminals")
def predictive_terminals(keyword: str = "", terminal_type: str = "", online_status: str = ""):
    return _tool_json(query_predictive_monitoring_terminals, {"keyword": keyword, "terminal_type": terminal_type, "online_status": online_status})


@app.get("/api/predictive-maintenance/terminals/summary")
def predictive_terminal_summary(site: str = ""):
    return _tool_json(summarize_predictive_monitoring_terminals, {"site": site})


@app.get("/api/predictive-maintenance/health")
def predictive_health(keyword: str = "", asset_type: str = "", risk_level: str = ""):
    return _tool_json(query_equipment_health, {"keyword": keyword, "asset_type": asset_type, "risk_level": risk_level})


@app.get("/api/predictive-maintenance/condition")
def predictive_condition(asset_id: str = "", keyword: str = "", metric: str = "", hours: int = 24):
    return _tool_json(query_condition_monitoring, {"asset_id": asset_id, "keyword": keyword, "metric": metric, "hours": hours})


@app.get("/api/predictive-maintenance/predictions")
def predictive_failures(keyword: str = "", horizon_days: int = 30, min_probability_pct: float = 35):
    return _tool_json(predict_equipment_failures, {"keyword": keyword, "horizon_days": horizon_days, "min_probability_pct": min_probability_pct})


@app.get("/api/predictive-maintenance/rul")
def predictive_rul(keyword: str = "", max_days: int = 365):
    return _tool_json(query_remaining_useful_life, {"keyword": keyword, "max_days": max_days})


@app.get("/api/predictive-maintenance/maintenance-plan")
def predictive_plan(keyword: str = "", priority: str = ""):
    return _tool_json(recommend_predictive_maintenance, {"keyword": keyword, "priority": priority})


@app.get("/api/predictive-maintenance/summary")
def predictive_summary(site: str = ""):
    return _tool_json(summarize_predictive_maintenance, {"site": site})


@app.get("/api/local-model/status")
def local_model_status():
    return local_model_manager.as_dict()


@app.post("/api/local-model/start")
def local_model_start():
    started = local_model_manager.start(wait=False)
    return {"accepted": started, **local_model_manager.as_dict()}


@app.post("/api/local-model/stop")
def local_model_stop():
    local_model_manager.stop()
    return local_model_manager.as_dict()


@app.post("/api/skill-tests")
def skill_tests(body: TestIn):
    scene = body.scene.lower().strip()
    if scene not in SCENE_TOOLS:
        raise HTTPException(status_code=404, detail="未知智能体场景")
    if scene != "safety":
        return _run_scene_tool_tests(scene, body.skill_id)
    skill_id = body.skill_id or None
    report = run_skill_tests(
        skill_id=skill_id,
        include_e2e=body.include_e2e or skill_id == "e2e_chat",
        agent=agent if (body.include_e2e or skill_id == "e2e_chat") else None,
    )
    report["detail"] = format_report(report)
    return report


SCENE_TEST_ARGS = {
    "medical": {
        "search_policy_knowledge": {"query": "医疗设备管理"},
        "list_patients_in_area": {"area_name": "抢救室"},
        "list_patients_by_channel": {"channel": "胸痛绿通"},
        "get_inout_records": {"hospital_no": "张三"},
        "analyze_patient_journey": {"hospital_no": "张三"},
        "query_locations_realtime": {"keyword": "林医生"},
        "query_locations_history": {"person": "张三"},
        "query_region_enter_leave": {"person": "张三"},
        "query_asset_locations_realtime": {"keyword": "输液泵12号"},
        "query_asset_locations_history": {"asset": "输液泵12号"},
        "query_asset_region_enter_leave": {"asset": "输液泵12号"},
        "locate_asset": {"keyword": "输液泵12号"},
        "get_asset_power": {"keyword": "输液泵12号"},
        "get_asset_track": {"keyword": "输液泵12号"},
    },
    "building": {
        "query_locations_realtime": {"keyword": "何磊"},
        "query_locations_history": {"person": "何磊"},
        "query_region_enter_leave": {"person": "何磊"},
        "query_asset_locations_realtime": {"keyword": "AHU-01"},
        "query_asset_locations_history": {"asset": "AHU-01"},
        "query_asset_region_enter_leave": {"asset": "AHU-01"},
        "get_building_emergency_response": {"alarm_id": "BLD-A006"},
    },
    "eldercare": {
        "generate_schematic_image": {"prompt": "智慧养老定位、围栏与告警原理图"},
    },
    "diagnostics": {
        "generate_schematic_image": {"prompt": "设备状态监测与故障诊断原理图"},
        "query_realtime_device_metrics": {"keyword": "主引风机"},
        "query_history_device_metrics": {"keyword": "主引风机"},
        "analyze_device_waveform": {"keyword": "主引风机"},
        "recommend_diagnostic_action": {"keyword": "主引风机"},
    },
    "iot": {
        "generate_schematic_image": {"prompt": "物联网终端、定位信标与电子围栏原理图"},
        "query_iot_history": {"keyword": "资产定位标签101"},
        "query_iot_model_data": {"keyword": "资产定位标签101"},
        "query_iot_people_locations": {"keyword": "陈晨"},
        "query_iot_asset_locations": {"keyword": "示波器01"},
    },
}


def _run_scene_tool_tests(scene: str, skill_id: str = ""):
    tools = [item for item in SCENE_TOOLS[scene] if not skill_id or item.name == skill_id]
    results = []
    for item in tools:
        started = time.perf_counter()
        errors = []
        output = ""
        try:
            # 图片生成会占用 ComfyUI/GPU，接口冒烟测试只验证工具已注册，避免测试页误触发重任务。
            if item.name == "generate_schematic_image":
                output = json.dumps({"status": "registered", "note": "图片生成接口已注册，未在冒烟测试中执行"}, ensure_ascii=False)
            else:
                output = item.invoke(SCENE_TEST_ARGS.get(scene, {}).get(item.name, {}))
            if not isinstance(output, str) or not output.strip():
                errors.append("返回内容为空")
        except Exception as exc:
            errors.append(f"调用失败: {exc}")
        results.append({
            "id": f"{scene}.{item.name}.smoke", "skill_id": item.name,
            "title": f"{item.name} · {scene} 场景隔离测试", "kind": "tool",
            "ok": not errors, "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "errors": errors, "output": output[:4000], "tools": [item.name] if not errors else [],
        })
    passed = sum(row["ok"] for row in results)
    report = {"scene": scene, "total": len(results), "passed": passed, "failed": len(results) - passed, "results": results}
    report["detail"] = "\n".join(f"[{'PASS' if row['ok'] else 'FAIL'}] {row['skill_id']}" + (f"：{'；'.join(row['errors'])}" if row["errors"] else "") for row in results)
    return report


@app.get("/api/knowledge")
def knowledge_list(query: str = "", category: str = "", limit: int = 20):
    rows = (
        search_documents(query, category=category, limit=limit)
        if query.strip()
        else list_documents(category)[: max(1, min(limit, 50))]
    )
    all_rows = list_documents()
    metadata = catalog_metadata()
    return {
        "count": len(rows),
        "data": rows,
        "stats": {
            "total": len(all_rows),
            **{
                category: sum(row["category"] == category for row in all_rows)
                for category in {row["category"] for row in all_rows}
            },
        },
        **metadata,
    }


@app.get("/api/knowledge/{document_id}")
def knowledge_document(document_id: str):
    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="未找到该国家文件")
    return document


def serve(host: str = "0.0.0.0", port: int = 7861) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")
