"""Telegram bot adapter for the multi-scene intelligent operations agents.

Run with TELEGRAM_BOT_TOKEN set in .env. The bot uses the same provider/model
configuration as the web application and supports agent and model switching.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import secrets
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import NetworkError, TimedOut
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from agent import ask_stream, build_agent, route_local_tools, generate_schematic_image, prepare_grounded_image
from local_model_manager import local_model_manager
from platform_features import (
    assess_scene_relevance, is_command_meta_request, route_supervisor_scene,
    scene_scope_refusal, trajectory_payload,
)
from telegram_visuals import render_visual_event

load_dotenv()
AGENTS: dict[tuple, object] = {}
LOGGER = logging.getLogger("personnel-safety-telegram")
TELEGRAM_HEALTH_PATH = Path(__file__).resolve().parent / "runtime" / "telegram_health.json"
WATCHDOG_INTERVAL_SECONDS = max(15, int(os.getenv("TELEGRAM_WATCHDOG_INTERVAL", "30")))
WATCHDOG_FAILURE_LIMIT = max(3, int(os.getenv("TELEGRAM_WATCHDOG_FAILURE_LIMIT", "5")))
POLLING_FAILURE_LIMIT = max(5, int(os.getenv("TELEGRAM_POLLING_FAILURE_LIMIT", "8")))
POLLING_FAILURE_WINDOW = max(60, int(os.getenv("TELEGRAM_POLLING_FAILURE_WINDOW", "180")))
_POLLING_ERROR_TIMES: list[float] = []
_POLLING_ERROR_LOCK = threading.Lock()
SAFETY_PPT_PATH = Path(__file__).resolve().parent / "docs" / "人员安全智能运营中心-工业产品销售培训.pptx"
MEDICAL_PPT_PATH = Path(__file__).resolve().parent / "docs" / "智慧医院急诊绿通与医疗资产智能运营中心-销售培训.pptx"
THREE_AGENT_PPT_PATH = Path(__file__).resolve().parent / "docs" / "三智能体智能运营中心-售前销售培训.pptx"
PPT_PATH = SAFETY_PPT_PATH
MODEL_SHORTCUTS = {
    "local": ("local", "qwen3.8-27b-local", "🖥️ 本地 Qwen3.8-27B"),
    "ds": ("deepseek", "deepseek-v4-flash", "⚡ DeepSeek V4 Flash"),
    "vision": ("deepseek", "deepseek-v4-flash-vision-exp", "👁️ DeepSeek Vision"),
    "or_ds": ("openrouter", "deepseek/deepseek-v3.2", "🌐 OR · DeepSeek V3.2"),
    "or_qwen": ("openrouter", "qwen/qwen3.8-27b", "🌐 OR · Qwen3.8-27B"),
    "or_gpt": ("openrouter", "openai/gpt-5.4-mini", "🌐 OR · GPT-5.4 mini"),
}
SCENE_SHORTCUTS = {
    "medical": {
        "label": "🏥 医脉 AI · 医疗",
        "title": "医脉 AI · 急诊与医疗资产智控中心",
        "description": "患者与医护定位、急诊绿通、医疗资产、超时预警和设备能效",
    },
    "safety": {
        "label": "🦺 安域 AI · 安全",
        "title": "安域 AI · 人员安全智控中心",
        "description": "人员与资产定位、考勤门禁、作业票合规、安全报警和预测维护",
    },
    "building": {
        "label": "🏢 筑境 AI · 楼宇",
        "title": "筑境 AI · 楼宇运营智控中心",
        "description": "人员与资产定位、能源空调、安防消防、停车电梯、告警和维保",
    },
    "eldercare": {
        "label": "👵 颐护 AI · 养老", "title": "颐护 AI · 康养物联智控中心",
        "description": "老人定位、床位区域、电子围栏、健康终端和养老告警",
    },
    "diagnostics": {
        "label": "🛠️ 机鉴 AI · 诊断", "title": "机鉴 AI · 设备健康诊断中心",
        "description": "设备树、实时历史指标、波形频谱、报警和诊断建议",
    },
    "iot": {
        "label": "📡 万联 AI · 物联网", "title": "万联 AI · 物联网运营中心",
        "description": "建筑终端、定位信标、电子围栏、轨迹、物模型和事件",
    },
    "command": {
        "label": "🧭 智枢 AI 总控", "title": "智枢 AI · 全域智能指挥中心",
        "description": "识别问题所属领域并自动路由到对应智能体",
    },
}
SCENE_ALIASES = {
    "medical": "medical", "医疗": "medical", "医脉": "medical", "医脉ai": "medical",
    "safety": "safety", "安全": "safety", "人员安全": "safety", "安域": "safety", "安域ai": "safety",
    "building": "building", "楼宇": "building", "政企楼宇": "building", "筑境": "building", "筑境ai": "building",
    "eldercare": "eldercare", "养老": "eldercare", "智慧养老": "eldercare", "颐护": "eldercare", "颐护ai": "eldercare",
    "diagnostics": "diagnostics", "诊断": "diagnostics", "设备诊断": "diagnostics", "机鉴": "diagnostics", "机鉴ai": "diagnostics",
    "iot": "iot", "物联网": "iot", "物联网平台": "iot", "万联": "iot", "万联ai": "iot",
    "command": "command", "总控": "command", "智能体总控": "command", "智枢": "command", "智枢ai": "command",
}
IMAGE_BACKEND_LABELS = {
    "auto": "🔄 自动（优先本地，失败切 Gemini）",
    "gemini": "☁️ Gemini 云端",
    "comfyui": "🖥️ 本地 ComfyUI",
}


def is_diagram_request(text: str) -> bool:
    """自动识别用户是否想生成原理图/流程图/示意图/画图。"""
    if not text:
        return False
    t = text.lower()
    if any(k in t for k in ("原理图", "示意图", "架构图", "流程图", "插画", "拓扑图", "设计图", "结构图", "系统图", "框图", "示意")):
        return True
    if any(k in t for k in ("图文并茂", "画图", "生成图", "生图", "作图", "绘图", "画一张", "画一个", "画幅", "做一张图", "生成图片", "出张图", "画张图", "画个图")):
        return True
    if re.search(r"(画|绘制|生成|做|出|来)[一两1-9个张幅套份首]*.*(图|图片|插图|架构|流程|拓扑)", t):
        return True
    return False


def is_trajectory_request(text: str) -> bool:
    value = (text or "").lower()
    return "轨迹" in value or any(word in value for word in ("热力图", "停留热区", "活动热区", "热力分布"))


def is_visualization_request(text: str) -> bool:
    value = (text or "").lower()
    return is_trajectory_request(value) or any(word in value for word in ("图表", "柱状图", "饼图", "环形图", "折线图", "趋势图", "雷达图", "仪表盘", "位置图", "地图", "平面图"))
QUICK_ACTIONS = {
    "medical": [
        ("people", "📍 人员定位", "查询当前急诊医生、护士和护工的实时位置"),
        ("patients", "🚑 今日绿通", "汇总今天各类绿通患者人数和当前分布"),
        ("assets", "🩺 设备定位", "查询当前医疗设备的实时位置和状态"),
        ("alarms", "⚠️ 设备告警", "列出当前有报警的医疗设备"),
    ],
    "safety": [
        ("people", "📍 人员定位", "当前园区在线人员有多少，分别在哪里？"),
        ("assets", "🧰 资产定位", "查询当前生产资产和应急装备的实时位置"),
        ("tickets", "📋 作业票", "今天各类作业票数量、状态和合规情况"),
        ("alarms", "⚠️ 安全报警", "当前有哪些未处理人员安全报警？"),
    ],
    "building": [
        ("overview", "📊 综合态势", "汇总总部大楼当前综合运营态势"),
        ("position", "📍 人员资产", "查询当前楼宇人员和设施资产的实时位置"),
        ("energy", "⚡ 能源空调", "汇总当前楼宇能耗、电力和空调运行情况"),
        ("alarms", "🚨 楼宇告警", "列出楼宇所有未处理告警并给出处置优先级"),
    ],
    "eldercare": [
        ("overview", "📊 养老态势", "汇总当前养老机构人员、床位、设备和告警态势"),
        ("location", "📍 老人定位", "查询所有老人当前所在区域和在线状态"),
        ("alarms", "🚨 养老告警", "当前有哪些未处理养老告警，谁需要优先关注？"),
        ("devices", "⌚ 健康终端", "查询智能健康手表和床位设备状态"),
    ],
    "diagnostics": [
        ("overview", "📊 诊断态势", "汇总所有设备健康度、在线率和故障报警"),
        ("devices", "⚙️ 设备状态", "列出当前预警、报警和离线设备"),
        ("metrics", "📈 实时指标", "查询主引风机实时温度、振动和转速"),
        ("fault", "🔬 波形诊断", "分析主引风机振动波形和频谱并给出建议"),
    ],
    "iot": [
        ("overview", "📊 物联态势", "汇总建筑、终端、信标、围栏和事件态势"),
        ("terminals", "📡 终端状态", "按建筑统计网关和终端的通信、定位与电量状态"),
        ("position", "📍 人员资产", "查询园区人员、访客、资产和车辆的实时位置"),
        ("fence", "🛡️ 电子围栏", "查询电子围栏、区域和当前围栏事件"),
    ],
    "command": [
        ("medical", "🏥 医疗问题", "今天抢救室有哪些超时患者？"),
        ("safety", "🦺 安全问题", "当前受限空间有哪些人员安全告警？"),
        ("building", "🏢 楼宇问题", "总部大楼有哪些未处理消防和空调告警？"),
        ("iot", "📡 物联问题", "研发中心有哪些离线终端和围栏事件？"),
    ],
}


def model_keyboard(active_provider: str = "", active_model: str = "") -> InlineKeyboardMarkup:
    def button(key: str) -> InlineKeyboardButton:
        provider, model, label = MODEL_SHORTCUTS[key]
        selected = "✅ " if (provider, model) == (active_provider, active_model) else ""
        return InlineKeyboardButton(selected + label, callback_data=f"model:{key}")
    return InlineKeyboardMarkup([
        [button("local"), button("ds")],
        [button("vision"), button("or_ds")],
        [button("or_qwen"), button("or_gpt")],
    ])


def scene_keyboard(active_scene: str = "command") -> InlineKeyboardMarkup:
    buttons = []
    for scene, config in SCENE_SHORTCUTS.items():
        selected = "✅ " if scene == active_scene else ""
        buttons.append(InlineKeyboardButton(selected + config["label"], callback_data=f"scene:{scene}"))
    return InlineKeyboardMarkup([buttons[:3], buttons[3:]])


def control_keyboard(active_scene: str, active_provider: str, active_model: str) -> InlineKeyboardMarkup:
    scene_rows = list(scene_keyboard(active_scene).inline_keyboard)
    actions = QUICK_ACTIONS[active_scene]
    quick_rows = [
        [InlineKeyboardButton(label, callback_data=f"quick:{key}") for key, label, _ in actions[index:index + 2]]
        for index in range(0, len(actions), 2)
    ]
    model_rows = list(model_keyboard(active_provider, active_model).inline_keyboard)
    utility_row = [
        InlineKeyboardButton("📊 当前状态", callback_data="action:status"),
        InlineKeyboardButton("🆕 新建会话", callback_data="action:new"),
    ]
    return InlineKeyboardMarkup([*scene_rows, *quick_rows, *model_rows, utility_row])


async def reply_with_retry(message, text: str, **kwargs) -> None:
    """完整发送回答；超过 Telegram 单条上限时按段落拆分，并对每段重试。"""
    raw = str(text or "")
    chunks: list[str] = []
    while len(raw) > 3900:
        cut = raw.rfind("\n", 0, 3900)
        if cut < 1200:
            cut = raw.rfind("。", 0, 3900)
        if cut < 1200:
            cut = 3900
        chunks.append(raw[:cut].rstrip())
        raw = raw[cut:].lstrip()
    if raw or not chunks:
        chunks.append(raw)
    for chunk in chunks:
        for attempt, delay in enumerate((0, 1, 2, 4), start=1):
            if delay:
                await asyncio.sleep(delay)
            try:
                await message.reply_text(chunk, **kwargs)
                break
            except (NetworkError, TimedOut) as exc:
                if attempt == 4:
                    raise
                LOGGER.warning("Telegram send retry %s/4: %s", attempt, exc)


async def photo_with_retry(message, path: Path, caption: str) -> None:
    for attempt, delay in enumerate((0, 1, 2, 4), start=1):
        if delay:
            await asyncio.sleep(delay)
        try:
            with path.open("rb") as photo:
                await message.reply_photo(photo=photo, caption=caption, read_timeout=60, write_timeout=60)
            return
        except (NetworkError, TimedOut) as exc:
            if attempt == 4:
                raise
            LOGGER.warning("Telegram visual retry %s/4: %s", attempt, exc)


def xhs_format(text: str) -> str:
    """转换为适合 Telegram 阅读的格式，但不截断模型回答。"""
    raw = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    raw = re.sub(r"```.*?```", "", raw, flags=re.S)
    raw = re.sub(r"\|.*\|", "", raw)
    raw = re.sub(r"^\s*[-|:]+\s*$", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"[*#>`]", "", raw)
    lines = [re.sub(r"\s+", " ", line).strip(" -") for line in raw.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return "ℹ️ 暂无可用结论"
    icons = ("📍", "⚠️", "✅", "📊", "🔧", "💡")
    body = "\n".join(f"{icons[i % len(icons)]} {line}" for i, line in enumerate(lines))
    return html.escape(body)


def get_agent(scene: str, provider: str, model: str, local_tool_names: list[str] | None = None):
    scene = scene if scene in SCENE_SHORTCUTS else "safety"
    key = (scene, provider, model, tuple(sorted(local_tool_names or [])))
    if key not in AGENTS:
        AGENTS[key] = build_agent(provider, model, local_tool_names=local_tool_names, scene=scene)
    return AGENTS[key]


def _selection(context: ContextTypes.DEFAULT_TYPE) -> tuple[str, str, str]:
    return (
        context.user_data.get("scene", "command"),
        context.user_data.get("provider", "deepseek"),
        context.user_data.get("model", "deepseek-v4-flash"),
    )


def _scene_summary(scene: str) -> str:
    config = SCENE_SHORTCUTS[scene]
    return f"{config['label']} {config['title']}\n{config['description']}"


def _thread_id(user_id: int, scene: str, user_data: dict) -> str:
    conversation = user_data.get(f"conversation:{scene}", "default")
    return f"telegram-{user_id}-{scene}-{conversation}"


async def ensure_local_model_ready() -> tuple[bool, str]:
    """复用网页端生命周期管理：释放资源、启动模型并等待健康检查通过。"""
    ready = await asyncio.to_thread(local_model_manager.ensure_ready)
    if ready:
        local_model_manager.touch()
        return True, ""
    state = local_model_manager.as_dict()
    return False, state.get("error") or "本地模型启动失败，请稍后重试"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    scene, provider, model = _selection(context)
    await reply_with_retry(update.message,
        "多场景智能运营中心已连接。\n\n"
        f"当前智能体：{_scene_summary(scene)}\n\n"
        "点击下方按钮切换智能体或模型，然后直接发送问题。",
        reply_markup=control_keyboard(scene, provider, model),
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    scene, provider, model = _selection(context)
    await reply_with_retry(
        update.message,
        "⚡ 快捷操作\n\n" + _scene_summary(scene) + "\n\n请选择业务查询、智能体或模型。",
        reply_markup=control_keyboard(scene, provider, model),
    )


async def _send_ppt_file(message, path: Path, caption: str, reply_markup=None) -> None:
    if not path.is_file():
        await reply_with_retry(message, "⚠️ 所选 PPT 文件尚未生成，请联系管理员。")
        return
    for attempt, delay in enumerate((0, 1, 2, 4), start=1):
        if delay:
            await asyncio.sleep(delay)
        try:
            with path.open("rb") as document:
                await message.reply_document(
                    document=document,
                    filename=path.name,
                    caption=caption,
                    reply_markup=reply_markup,
                    read_timeout=60,
                    write_timeout=60,
                )
            return
        except (NetworkError, TimedOut) as exc:
            if attempt == 4:
                raise
            LOGGER.warning("Telegram PPT retry %s/4: %s", attempt, exc)


async def send_ppt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """默认发送最新三智能体培训 PPT，并提供其他专题 PPT 下载按钮。"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 三智能体售前销售培训PPT (25页)", callback_data="ppt:three-agents")],
        [InlineKeyboardButton("🏥 智慧医院急诊与资产销售PPT (14页)", callback_data="ppt:medical")],
        [InlineKeyboardButton("🦺 人员安全智能运营中心销售PPT (22页)", callback_data="ppt:safety")],
    ])
    await _send_ppt_file(
        update.message,
        THREE_AGENT_PPT_PATH,
        "📎 三智能体智能运营中心｜售前与销售培训（25页）\n包含工作原理、销售架构、三场景话术、演示脚本和真实软件截图。",
        reply_markup=keyboard,
    )


async def select_ppt_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理内联按钮切换下载指定 PPT。"""
    query = update.callback_query
    await query.answer("正在发送对应 PPT…")
    target = query.data.split(":", 1)[-1]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 三智能体售前销售培训PPT (25页)", callback_data="ppt:three-agents")],
        [InlineKeyboardButton("🏥 智慧医院急诊与资产销售PPT (14页)", callback_data="ppt:medical")],
        [InlineKeyboardButton("🦺 人员安全智能运营中心销售PPT (22页)", callback_data="ppt:safety")],
    ])
    if target == "three-agents":
        await _send_ppt_file(
            query.message,
            THREE_AGENT_PPT_PATH,
            "📎 三智能体智能运营中心｜售前与销售培训（25页）\n包含工作原理、销售架构、三场景话术、演示脚本和真实软件截图。",
            reply_markup=keyboard,
        )
    elif target == "medical":
        await _send_ppt_file(
            query.message,
            MEDICAL_PPT_PATH,
            "📎 智慧医院急诊绿通与高价值资产｜销售培训（14页）\n包含五大中心时空质控达标与高价值设备盘点降本实战指南。",
            reply_markup=keyboard,
        )
    else:
        await _send_ppt_file(
            query.message,
            SAFETY_PPT_PATH,
            "📎 人员安全智能运营中心｜工业产品销售培训（22页）\n包含工业现场安全、作业合规与设备健康实战指南。",
            reply_markup=keyboard,
        )


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands([
        BotCommand("start", "打开多场景智能运营中心"),
        BotCommand("menu", "打开快捷操作菜单"),
        BotCommand("agents", "切换领域智能体与总控"),
        BotCommand("models", "查看可用模型"),
        BotCommand("local", "一键切换并启动本地模型"),
        BotCommand("status", "查看当前智能体和模型状态"),
        BotCommand("new", "新建独立对话"),
        BotCommand("ppt", "获取产品销售培训PPT"),
        BotCommand("help", "查看使用帮助"),
        BotCommand("imgbackend", "切换画图后端（本地/Gemini/自动）"),
    ])


def _write_telegram_health(status: str, **extra) -> None:
    """写入不含 Token 的原子化健康状态，供网页端读取。"""
    TELEGRAM_HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "pid": os.getpid(),
        "checkedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "watchdogIntervalSeconds": WATCHDOG_INTERVAL_SECONDS,
        "restartThreshold": WATCHDOG_FAILURE_LIMIT,
        **extra,
    }
    tmp = TELEGRAM_HEALTH_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(TELEGRAM_HEALTH_PATH)


def _telegram_api_reachable(token: str, proxy_url: str) -> bool:
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else {}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/getMe",
        headers={"User-Agent": "zhishu-telegram-watchdog/1.0"},
    )
    with opener.open(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
        return response.status == 200 and payload.get("ok") is True


def _telegram_watchdog_loop(token: str, proxy_url: str) -> None:
    failures = 0
    last_success = ""
    while True:
        try:
            if not _telegram_api_reachable(token, proxy_url):
                raise ConnectionError("telegram_api_not_ready")
            failures = 0
            last_success = datetime.now().astimezone().isoformat(timespec="seconds")
            _write_telegram_health("online", consecutiveFailures=0, lastSuccessAt=last_success)
        except Exception as exc:
            failures += 1
            status = "restarting" if failures >= WATCHDOG_FAILURE_LIMIT else "degraded"
            _write_telegram_health(
                status,
                consecutiveFailures=failures,
                lastSuccessAt=last_success,
                errorType=type(exc).__name__,
            )
            LOGGER.warning(
                "Telegram watchdog check failed (%s/%s): %s",
                failures, WATCHDOG_FAILURE_LIMIT, type(exc).__name__,
            )
            if failures >= WATCHDOG_FAILURE_LIMIT:
                LOGGER.error("Telegram watchdog is restarting the service after consecutive failures")
                os._exit(75)
        time.sleep(WATCHDOG_INTERVAL_SECONDS)


def _start_telegram_watchdog(token: str, proxy_url: str) -> None:
    _write_telegram_health("starting", consecutiveFailures=0, lastSuccessAt="")
    threading.Thread(
        target=_telegram_watchdog_loop,
        args=(token, proxy_url),
        name="telegram-connectivity-watchdog",
        daemon=True,
    ).start()


async def models(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    scene, provider, model = _selection(context)
    await reply_with_retry(update.message,
        "🤖 请选择模型\n\n"
        f"当前智能体：{SCENE_SHORTCUTS[scene]['title']}\n"
        "本地模型适合敏感数据和快速接口查询；云端模型适合复杂分析。",
        reply_markup=model_keyboard(provider, model),
    )


async def agents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    scene, provider, model = _selection(context)
    await reply_with_retry(
        update.message,
        "🤖 请选择要对话的智能体\n\n" + _scene_summary(scene),
        reply_markup=control_keyboard(scene, provider, model),
    )


async def select_scene_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    scene = (query.data or "").split(":", 1)[-1]
    if scene not in SCENE_SHORTCUTS:
        await query.edit_message_text("⚠️ 智能体选项已失效，请重新发送 /agents。")
        return
    context.user_data["scene"] = scene
    if scene != "command":
        context.user_data["last_routed_scene"] = scene
    context.user_data.pop(f"local_route:{scene}", None)
    _, provider, model = _selection(context)
    await query.edit_message_text(
        "✅ 已切换智能体\n\n" + _scene_summary(scene) + "\n\n现在可以直接发送问题。",
        reply_markup=control_keyboard(scene, provider, model),
    )


async def set_scene(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await agents(update, context)
        return
    value = "".join(context.args).lower()
    scene = SCENE_ALIASES.get(value)
    if scene is None:
        await reply_with_retry(update.message, "格式：/agent medical|safety|building|eldercare|diagnostics|iot|command，或输入 医疗、人员安全、政企楼宇、智慧养老、设备诊断、物联网、总控。")
        return
    context.user_data["scene"] = scene
    if scene != "command":
        context.user_data["last_routed_scene"] = scene
    context.user_data.pop(f"local_route:{scene}", None)
    _, provider, model = _selection(context)
    await reply_with_retry(
        update.message,
        "✅ 已切换智能体\n\n" + _scene_summary(scene),
        reply_markup=control_keyboard(scene, provider, model),
    )


async def select_model_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    key = (query.data or "").split(":", 1)[-1]
    selected = MODEL_SHORTCUTS.get(key)
    if selected is None:
        await query.edit_message_text("⚠️ 模型选项已失效，请重新发送 /models。")
        return
    provider, model, label = selected
    context.user_data["provider"] = provider
    context.user_data["model"] = model
    scene = context.user_data.get("scene", "command")
    context.user_data.pop(f"local_route:{scene}", None)
    if provider == "local":
        if not local_model_manager.check_health():
            await query.edit_message_text(
                "🧹 正在释放内存和显存并启动本地 Qwen3.8-27B，请稍候…"
            )
        ready, detail = await ensure_local_model_ready()
        if not ready:
            await query.edit_message_text(
                f"⚠️ 本地模型启动失败\n\n原因：{detail}",
                reply_markup=control_keyboard(scene, provider, model),
            )
            return
    await query.edit_message_text(
        f"✅ 已切换模型\n\n当前智能体：{SCENE_SHORTCUTS[scene]['title']}\n{label}"
        + (" · 已启动" if provider == "local" else "")
        + "\n\n现在可以直接发送问题。",
        reply_markup=control_keyboard(scene, provider, model),
    )


async def set_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or "/" not in context.args[0]:
        await reply_with_retry(update.message, "格式：/model provider/model，例如 /model openrouter/qwen/qwen3.8-27b")
        return
    provider, model = context.args[0].split("/", 1)
    provider = provider.lower()
    context.user_data["provider"] = provider
    context.user_data["model"] = model
    if provider == "local":
        await reply_with_retry(update.message, "🧹 正在释放内存和显存并启动本地模型，请稍候…")
        ready, detail = await ensure_local_model_ready()
        if not ready:
            await reply_with_retry(update.message, f"⚠️ 本地模型启动失败\n🔧 原因：{detail}")
            return
    await reply_with_retry(update.message, f"已切换：{provider}/{model}" + ("，本地模型已启动" if provider == "local" else ""))


async def use_local_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["provider"] = "local"
    context.user_data["model"] = "qwen3.8-27b-local"
    await reply_with_retry(update.message, "🧹 正在释放内存和显存并启动本地模型，请稍候…")
    ready, detail = await ensure_local_model_ready()
    if not ready:
        await reply_with_retry(update.message, f"⚠️ 本地模型启动失败\n🔧 原因：{detail}")
        return
    scene, provider, model = _selection(context)
    await reply_with_retry(
        update.message,
        f"✅ 本地模型已启动\n当前智能体：{SCENE_SHORTCUTS[scene]['title']}",
        reply_markup=control_keyboard(scene, provider, model),
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    scene, provider, model = _selection(context)
    state = await asyncio.to_thread(local_model_manager.as_dict)
    local_status = {
        "online": "在线", "offline": "休眠", "starting": "启动中", "cleaning": "正在释放资源",
        "stopping": "停止中", "error": "异常",
    }.get(state.get("status"), state.get("status", "未知"))
    await reply_with_retry(
        update.message,
        f"📊 当前状态\n\n"
        f"智能体：{SCENE_SHORTCUTS[scene]['title']}\n"
        f"模型：{provider}/{model}\n"
        f"本地 Qwen3.8-27B：{local_status}",
        reply_markup=control_keyboard(scene, provider, model),
    )


async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    scene, provider, model = _selection(context)
    context.user_data[f"conversation:{scene}"] = secrets.token_hex(4)
    context.user_data.pop(f"local_route:{scene}", None)
    if scene == "command":
        context.user_data.pop("last_routed_scene", None)
    await reply_with_retry(
        update.message,
        f"🆕 已新建独立对话\n当前智能体：{SCENE_SHORTCUTS[scene]['title']}",
        reply_markup=control_keyboard(scene, provider, model),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply_with_retry(
        update.message,
        "ℹ️ 使用帮助\n\n"
        "/menu 快捷操作菜单\n"
        "/agents 切换智能体\n"
        "/models 切换云端模型\n"
        "/local 启动本地模型\n"
        "/status 查看当前状态\n"
        "/new 清空上下文并新建对话\n\n"
        "也可以直接发送自然语言问题。",
    )


async def _answer_question(message, user_id: int, user_data: dict, text: str) -> None:
    scene = user_data.get("scene", "command")
    requested_scene = scene
    if scene == "command" and not is_command_meta_request(text):
        route = route_supervisor_scene(text, user_data.get("last_routed_scene", ""))
        if not route["scene"]:
            await reply_with_retry(message, scene_scope_refusal("command"))
            return
        scene = route["scene"]
        user_data["last_routed_scene"] = scene
        await reply_with_retry(message, f"🧭 智能体总控已路由至：{route['name']}")
    conversation_id = user_data.get(f"conversation:{requested_scene}", "default")
    scope_key = f"scope_context:{requested_scene}:{scene}:{conversation_id}"
    scope = assess_scene_relevance(text, scene, bool(user_data.get(scope_key)))
    if not scope["relevant"]:
        await reply_with_retry(message, scene_scope_refusal(scene))
        return
    user_data[scope_key] = True
    provider = user_data.get("provider", "deepseek")
    model = user_data.get("model", "deepseek-v4-flash")
    await message.chat.send_action(ChatAction.TYPING)
    # 图片原理图请求自动识别，支持任意场景与各种口语表达
    if is_diagram_request(text) and not is_visualization_request(text):
        _img_backend = user_data.get("image_backend", os.getenv("IMAGE_BACKEND", "auto"))
        _backend_label = IMAGE_BACKEND_LABELS.get(_img_backend, _img_backend)
        await reply_with_retry(message, "📡 正在读取当前子智能体的业务数据…")
        _prev_backend = os.environ.get("IMAGE_BACKEND")
        os.environ["IMAGE_BACKEND"] = _img_backend
        try:
            grounded = await asyncio.to_thread(prepare_grounded_image, scene, text)
            source_text = "、".join(grounded["sources"]) or "当前业务接口"
            await reply_with_retry(message, f"🎨 已读取 {source_text}，正在生成原理图（{_backend_label}）…")
            raw = await asyncio.to_thread(generate_schematic_image.invoke, {"prompt": grounded["prompt"], "style": "Blueprint", "aspect": "16:9", "seed": 0})
        finally:
            if _prev_backend is None:
                os.environ.pop("IMAGE_BACKEND", None)
            else:
                os.environ["IMAGE_BACKEND"] = _prev_backend
        if isinstance(raw, str) and raw.startswith("__IMAGE__"):
            try:
                result = json.loads(raw[len("__IMAGE__"):])
            except json.JSONDecodeError:
                result = {"status": "failed", "error": "结果解析失败"}
            image_path = result.get("image_path")
            if result.get("status") == "success" and image_path and Path(image_path).is_file():
                scene_label = SCENE_SHORTCUTS.get(scene, {}).get("label", "系统")
                with Path(image_path).open("rb") as photo:
                    source_text = "、".join(grounded["sources"]) or "当前业务接口"
                    await message.reply_photo(photo=photo, caption=f"✅ {scene_label}原理图已生成\n数据依据：{source_text}\n文字已按大号手写体和防乱码策略处理。")
            else:
                await reply_with_retry(message, f"⚠️ 原理图生成失败：{result.get('error') or result.get('status', '未知错误')}")
        else:
            await reply_with_retry(message, str(raw)[:800])
        return
    local_tool_names = None
    if provider == "local":
        if not local_model_manager.check_health():
            await reply_with_retry(message, "🧹 本地模型已休眠，正在释放资源并重新启动，请稍候…")
        ready, detail = await ensure_local_model_ready()
        if not ready:
            await reply_with_retry(message, f"⚠️ 本地模型启动失败\n🔧 原因：{detail}")
            return
        local_tool_names, groups = route_local_tools(text, scene=scene)
        route_key = f"local_route:{scene}"
        if groups == ["综合查询"] and user_data.get(route_key):
            local_tool_names, groups = user_data[route_key]
        else:
            user_data[route_key] = (local_tool_names, groups)
    if is_visualization_request(text):
        await reply_with_retry(message, "📊 正在读取业务数据并渲染电报图片…")
    def collect_stream_events():
        events = list(ask_stream(
            get_agent(scene, provider, model, local_tool_names),
            text,
            thread_id=f"telegram-{user_id}-{requested_scene}-{scene}-{user_data.get(f'conversation:{requested_scene}', 'default')}",
            metadata={"provider": provider, "model": model, "scene": scene, "app": "telegram"},
        ))
        visual_events = [event for event in events if event.get("type") in {"chart", "trajectory", "map", "image"}]
        if is_trajectory_request(text) and not any(event.get("type") == "trajectory" for event in visual_events):
            fallback = trajectory_payload(scene, text)
            fallback["decisionReason"] = "用户明确要求热力图，电报端自动补充场景可视化"
            visual_events.append({"type": "trajectory", "trajectory": fallback})
        outputs = []
        for event in visual_events[:3]:
            try:
                if event.get("type") == "image":
                    path = Path(str((event.get("image") or {}).get("image_path") or ""))
                else:
                    path = render_visual_event(event, scene)
                if path and path.is_file():
                    outputs.append((event.get("type"), path))
            except Exception:
                LOGGER.exception("Telegram visual rendering failed")
        return events, outputs
    try:
        stream_events, visual_outputs = await asyncio.wait_for(
            asyncio.to_thread(collect_stream_events),
            timeout=210,
        )
    except asyncio.TimeoutError:
        await reply_with_retry(message, "⚠️ 模型响应超时，请重新发送问题，或用 /models 切换模型后重试。")
        return
    if provider == "local":
        local_model_manager.touch()
    tokens = "".join(str(event.get("text") or "") for event in stream_events if event.get("type") == "token").strip()
    formatted = "\n\n".join(str(event.get("text") or "") for event in stream_events if event.get("type") == "formatted").strip()
    answer = tokens or formatted or "已完成查询，结果见下方图片。"
    await reply_with_retry(message, xhs_format(answer), parse_mode="HTML")

    labels = {"chart": "业务数据图表", "trajectory": "轨迹与停留热力图", "map": "实时位置图", "image": "业务原理图"}
    for kind, rendered in visual_outputs:
        await photo_with_retry(message, rendered, f"✅ {SCENE_SHORTCUTS[scene]['label']} · {labels.get(kind, '可视化')}")


async def select_quick_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("正在查询…")
    scene = context.user_data.get("scene", "command")
    key = (query.data or "").split(":", 1)[-1]
    question = next((question for action, _, question in QUICK_ACTIONS[scene] if action == key), "")
    if not question:
        await reply_with_retry(query.message, "⚠️ 快捷操作已失效，请重新发送 /menu。")
        return
    try:
        await _answer_question(query.message, update.effective_user.id, context.user_data, question)
    except Exception as exc:
        LOGGER.exception("Telegram quick action failed")
        await reply_with_retry(query.message, f"⚠️ 暂时无法完成请求，请稍后重试。\n🔧 原因：{str(exc)[:160]}")


async def select_utility_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = (query.data or "").split(":", 1)[-1]
    proxy_update = SimpleNamespace(message=query.message)
    if action == "status":
        await status(proxy_update, context)
    elif action == "new":
        await new_chat(proxy_update, context)


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await _answer_question(update.message, update.effective_user.id, context.user_data, update.message.text)
    except Exception as exc:
        LOGGER.exception("Telegram chat failed")
        await reply_with_retry(update.message, f"⚠️ 暂时无法完成请求，请稍后重试。\n🔧 原因：{str(exc)[:160]}")


def imgbackend_keyboard(active: str = "auto") -> InlineKeyboardMarkup:
    buttons = []
    for key, label in IMAGE_BACKEND_LABELS.items():
        selected = "✅ " if key == active else ""
        buttons.append([InlineKeyboardButton(selected + label, callback_data=f"imgbackend:{key}")])
    return InlineKeyboardMarkup(buttons)


async def imgbackend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """显示画图后端选择菜单。"""
    user_data = context.user_data
    current = user_data.get("image_backend", os.getenv("IMAGE_BACKEND", "auto"))
    await update.message.reply_text(
        f"🖼️ 当前画图后端：**{IMAGE_BACKEND_LABELS.get(current, current)}**\n\n请选择：",
        parse_mode="Markdown",
        reply_markup=imgbackend_keyboard(current),
    )


async def select_imgbackend_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理画图后端内联按钮回调。"""
    query = update.callback_query
    await query.answer()
    backend = query.data.split(":", 1)[1]
    if backend not in IMAGE_BACKEND_LABELS:
        return
    context.user_data["image_backend"] = backend
    label = IMAGE_BACKEND_LABELS[backend]
    await query.edit_message_text(
        f"✅ 画图后端已切换为：**{label}**",
        parse_mode="Markdown",
        reply_markup=imgbackend_keyboard(backend),
    )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """网络错误过密时主动退出，交给 systemd 建立全新的连接池。"""
    LOGGER.warning("Telegram polling error detected: %s", type(context.error).__name__)
    if not isinstance(context.error, (NetworkError, TimedOut)):
        return
    now = time.monotonic()
    with _POLLING_ERROR_LOCK:
        _POLLING_ERROR_TIMES[:] = [stamp for stamp in _POLLING_ERROR_TIMES if now - stamp <= POLLING_FAILURE_WINDOW]
        _POLLING_ERROR_TIMES.append(now)
        failure_count = len(_POLLING_ERROR_TIMES)
    if failure_count >= POLLING_FAILURE_LIMIT:
        _write_telegram_health(
            "restarting",
            consecutiveFailures=failure_count,
            lastSuccessAt="",
            errorType=type(context.error).__name__,
            restartReason="polling_error_burst",
        )
        LOGGER.error("Telegram polling error threshold reached; restarting service")
        os._exit(75)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("请在 .env 中设置 TELEGRAM_BOT_TOKEN")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # Telegram 请求 URL 含 Bot token，禁止第三方 HTTP 客户端输出访问日志。
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    proxy_url = os.getenv("TELEGRAM_PROXY", os.getenv("HTTPS_PROXY", "")).strip()
    builder = (
        Application.builder()
        .token(token)
        .connect_timeout(20)
        .read_timeout(45)
        .write_timeout(30)
        .pool_timeout(20)
        .connection_pool_size(12)
        .get_updates_connect_timeout(20)
        .get_updates_read_timeout(45)
        .get_updates_write_timeout(30)
        .get_updates_pool_timeout(20)
        .get_updates_connection_pool_size(4)
        .concurrent_updates(4)
        .post_init(post_init)
    )
    if proxy_url:
        builder = builder.proxy(proxy_url).get_updates_proxy(proxy_url)
    _start_telegram_watchdog(token, proxy_url)
    app = builder.build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("agents", agents))
    app.add_handler(CommandHandler("agent", set_scene))
    app.add_handler(CommandHandler("scene", set_scene))
    app.add_handler(CommandHandler("models", models))
    app.add_handler(CommandHandler("model", set_model))
    app.add_handler(CommandHandler("local", use_local_model))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("new", new_chat))
    app.add_handler(CommandHandler("ppt", send_ppt))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("imgbackend", imgbackend))
    app.add_handler(CallbackQueryHandler(select_model_button, pattern=r"^model:"))
    app.add_handler(CallbackQueryHandler(select_imgbackend_button, pattern=r"^imgbackend:"))
    app.add_handler(CallbackQueryHandler(select_ppt_button, pattern=r"^ppt:"))
    app.add_handler(CallbackQueryHandler(select_scene_button, pattern=r"^scene:"))
    app.add_handler(CallbackQueryHandler(select_quick_action, pattern=r"^quick:"))
    app.add_handler(CallbackQueryHandler(select_utility_action, pattern=r"^action:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_error_handler(on_error)
    try:
        app.run_polling(
            poll_interval=0.8,
            timeout=25,
            bootstrap_retries=-1,
            allowed_updates=Update.ALL_TYPES,
        )
    finally:
        _write_telegram_health("offline", consecutiveFailures=0, lastSuccessAt="")


if __name__ == "__main__":
    main()
