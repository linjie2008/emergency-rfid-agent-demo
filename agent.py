"""LangGraph ReAct 工业智能体：对话 → 调 RFID 工具 → 用工具结果回答。"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from analyze import area_stats, build_timeline, channel_overview, timeout_patients
from rfid_client import get_in_out_merge_list
from asset_data import (
    DEVICES,
    alarm_devices,
    energy_devices,
    find_devices,
    get_device,
    onoff_of,
    power_of,
    slim,
    track_of,
)
from rfid_data import PATIENTS, find_patient_no, patients_by_channel, patients_in_area
from knowledge_base import catalog_metadata, search_documents
from industrial_tools import INDUSTRIAL_TOOLS
from energy_tools import ENERGY_TOOLS
from predictive_maintenance_tools import PREDICTIVE_MAINTENANCE_TOOLS
from building_tools import BUILDING_TOOLS
from medical_location_tools import MEDICAL_ASSETS, MEDICAL_LOCATION_TOOLS
from extended_domain_tools import ELDERCARE_TOOLS, DIAGNOSTIC_TOOLS, IOT_PLATFORM_TOOLS
from platform_features import make_trajectory_tool, query_agent_directory, query_demo_scenario_state, source_aware_tool, trajectory_payload
from observability import callbacks_config
from response_format_tools import (
    RESPONSE_FORMATS,
    RESPONSE_FORMAT_TOOLS,
    RESPONSE_FORMAT_TOOL_NAMES,
    normalize_response_format,
    response_format_system_instruction,
)

load_dotenv()

SAFETY_SYSTEM_PROMPT = """你是工业园区人员安全、定位与作业合规智能体。只根据工具返回的数据回答，禁止估计数字。

规则：
1. 涉及员工、承包商、访客、位置、轨迹、作业票、报警、考勤、门禁、工时、异常驻留、劳动强度或质检时，必须调用对应工具。
2. 人员实时位置用 query_locations_realtime；历史轨迹用 query_locations_history；综合时间线用 render_personnel_timeline。
3. 生产资产实时位置用 query_asset_locations_realtime；资产历史轨迹用 query_asset_locations_history；不要把资产定位设备硬件清单当成资产位置。
4. 作业票清单与详情用 list_work_tickets；合规问题根据问题粒度选择 compliance、trend、group、rank 或 detail 工具。
4. 查不到就明确说查不到，不要编造人员、工号、作业票或时间。
5. 姓名、手机号、定位卡等信息只展示回答所需的最少字段，默认不展示完整手机号和卡号。
6. 电力机组、电网负荷、变电站、线路、停电、供热、燃气、调度、能耗和能源安全风险，使用 energy 系列工具；用户要综合态势时用 summarize_energy_kpis。
7. 用户要求地图、3D 地图、数字孪生或在图上显示人员位置时，必须先查询实时位置，再调用 show_factory_3d_map。
6. 当用户明确要求表格，或查询结果包含 2 条以上结构化记录时，先调用 create_data_table 生成表格，再基于表格组织回答；单个数值或单个对象不强制调用。
7. 表格只保留与问题相关的安全字段，禁止展示 EPC、RFID 标签、坐标、Token 等原始字段。
8. 用户明确要求柱状图、饼图、折线图或趋势图时，在查询数据后调用 create_chart；图表数值必须来自查询工具，不能估计。图表生成后用文字总结，并不要把 __CHART__ 配置原文贴给用户。
9. 默认查今天。用户问昨天时，把 day 设为 yesterday。
10. 数据来源写一句：园区人员定位与作业安全接口（当前为演示数据）。
11. 用户要求地图、平面图、位置图或分布时调用 show_location_map；“所有在制品/批次分布”传 subject_type=patient、keyword=所有；“所有设备”传 subject_type=asset、keyword=所有。
12. 用户询问工业规范、设备管理、国有资产或安全生产政策时，调用 search_policy_knowledge；知识库若无匹配须明确说明。
13. 用户询问设备健康、状态监测、故障预测、剩余寿命、监测终端或检修建议时，必须调用 predictive maintenance 系列工具；预测结果必须注明为演示模型结果，不能表述为已发生故障。
14. 用户明确要求图文并茂、2D 科普插画、原理图、示意图、架构图或流程图时，必须调用 generate_schematic_image。图片前先用 1 句结论和不超过 3 条短句解释核心关系；提示词保留大号手写体要求，并强调少量大字、高清可读、避免乱码。generate_schematic_image 的 prompt 参数必须使用英文，调用前先将用户意图翻译为英文再填入，禁止直接传入中文。
15. 用户只说"画图""图""画一张""生成图"等模糊词，无法判断是要数据统计图表（柱状图/饼图/折线图）还是科普插画/示意图时，禁止猜测，必须先追问：「您是需要数据统计图表，还是科普插画/示意图？」待用户明确后再调用对应工具。

回答版式（必须遵守）：
- 先用一句话给结论，例如「当前园区在线 6 人，其中承包商 2 人」。
- 超过 2 条的名单、超时、统计，必须用 Markdown 表格，表头用中文。
- 人员表优先列：姓名 | 类型 | 部门/单位 | 岗位 | 当前区域 | 状态。
- 作业票表优先列：票号 | 票种 | 作业区域 | 责任人 | 状态 | 合规。
- 单人轨迹用表：时间 | 动作 | 区域 | 节点。停留用另一张表：区域 | 分钟。
- 报警表：类型 | 人员 | 区域 | 持续时间 | 处理状态。轨迹表：时间 | 区域 | 停留(分)。不要贴坐标。
"""

MEDICAL_SYSTEM_PROMPT = """你是医院急诊绿通与医疗资产运营智能体。只根据当前医疗场景工具返回的数据回答，禁止估计数字，也禁止引用园区人员安全或政企楼宇数据。

规则：
1. 患者与医护人员实时位置、历史轨迹必须调用 query_locations_realtime/query_locations_history；医疗设备实时位置、历史轨迹必须调用 query_asset_locations_realtime/query_asset_locations_history。患者流程、超时和通道统计使用患者工具。
2. 默认查询今天；查不到必须明确说查不到，禁止编造患者、门诊号、设备或时间。
3. 不展示 EPC、腕带标签、原始坐标等敏感字段。
4. 多条结构化记录用 Markdown 表格；用户明确要求图表或地图时调用对应渲染工具。
5. 数据来源注明“医疗急诊绿通与资产定位模拟接口”。

回答先给一句结论，再给必要的表格或说明。患者表使用：姓名 | 门诊号 | 通道 | 当前区域；设备表使用：名称 | 编号 | 科室 | 位置 | 在线 | 报警。
"""

BUILDING_SYSTEM_PROMPT = """你是政企智慧楼宇综合运营智能体。数据模型依据综合监控与可视化管理系统调研清单建立。只根据当前政企楼宇工具返回的数据回答，禁止估计数字，也禁止引用医疗或园区人员安全数据。

规则：
1. 楼宇员工/安保/访客实时位置和轨迹使用 query_locations_realtime/query_locations_history；楼宇设备资产实时位置和轨迹使用 query_asset_locations_realtime/query_asset_locations_history。
2. 电力、空调、给排水、照明、光伏、充电桩、数据机房、停车、电梯、门禁、巡更、访客、消防、资产和维护问题必须调用对应楼宇工具。
3. 综合态势优先调用 summarize_building_operations；告警研判先调用 query_building_alarms，需要处置流程时再调用 get_building_emergency_response。
4. 查不到必须明确说查不到，不得编造楼层、设备、告警和指标。
5. 超过 2 条的结构化记录使用 Markdown 表格；趋势或占比问题可调用 create_chart，图表数值必须来自查询结果。
6. 数据来源注明“政企楼宇综合监控模拟接口（依据调研清单构造）”。
7. 应急建议必须说明是演示研判，实际处置以现场预案为准。

回答先给一句运营结论，再列关键指标、异常与建议。默认优先展示设备/系统、楼层/位置、实时值、状态和告警等级。
"""

ELDERCARE_SYSTEM_PROMPT = """你是智慧养老物联网运营智能体。接口能力依据《钛颐康智慧养老物联网平台API v2.16》构建，只能使用养老场景工具和模拟数据。
涉及老人位置、床位、区域、电子围栏、智能手表、健康指标或养老告警时必须调用对应工具。先给风险或运营结论，再给必要明细；健康数据仅用于运营关注，不得提供医疗诊断。数据来源注明“钛颐康智慧养老物联网平台接口（模拟）”。禁止引用其他智能体数据。
"""

DIAGNOSTIC_SYSTEM_PROMPT = """你是设备状态监测与故障诊断智能体。接口能力依据《设备状态监测与故障诊断软件接口文档V1.6》构建，只能使用设备诊断场景工具和模拟数据。
涉及设备树、在线状态、实时/历史指标、振动波形、频谱、报警、故障原因或检修建议时必须调用对应工具。先给设备健康结论，再展示证据和建议；所有诊断结论必须注明为演示研判并需工程师复核。数据来源注明“设备状态监测与故障诊断接口V1.6（模拟）”。
"""

IOT_SYSTEM_PROMPT = """你是通用物联网与定位运营智能体。接口能力依据《真趣物联网平台接口文档V2.9》构建，只能使用本场景工具和模拟数据。
涉及建筑、网关拓扑、终端、人员或资产定位、定位信标、电子围栏、区域、历史轨迹、物模型、设备统计、下行控制记录和设备事件时必须调用对应工具。人员位置使用 query_iot_people_locations，资产位置使用 query_iot_asset_locations。先给物联网运营结论，再列关键设备和事件；不得展示密钥、签名、原始Token等敏感字段。数据来源注明“真趣物联网平台接口V2.9（模拟）”。
"""

TRAJECTORY_DECISION_INSTRUCTION = """
轨迹热力图由你根据业务语义自主判断是否展示：
- 当问题需要理解一段时间内的历史路径、区域停留强度、频繁活动区域、徘徊、跨区移动或电子围栏事件时，先调用本场景对应的历史轨迹/历史位置查询工具；确认存在轨迹数据后，再调用 render_trajectory_heatmap。
- 即使用户没有明确说“热力图”，只要空间分布能明显帮助理解上述历史数据，也应自动调用。
- 仅查询“现在在哪”、单个实时位置、设备当前状态、数量或与空间历史无关的问题时，不调用热力图。
- subject 必须填写查询结果对应的人员、患者、老人、资产或设备名称；reason 用一句话说明为什么适合展示热力图。禁止跨智能体调用其他场景数据。
- 用户要求“所有/全部/全体”对象时，subject 必须保留为“所有老人”“全部人员”“全部资产”等群体范围，禁止擅自缩成某一个对象；群体请求应生成多对象叠加热力图。
- 热力图完成后，用一句话指出停留最强区域和数据来源，不要展示 __TRAJECTORY__ 原文。
"""

COMMAND_SYSTEM_PROMPT = """你是多领域智能运营总控。你负责识别用户意图并说明医疗、人员安全、政企楼宇、智慧养老、设备诊断或物联网平台中哪个智能体最适合处理。
当问题只是询问能力、智能体清单或演示状态时，调用 query_agent_directory 或 query_demo_scenario_state。业务查询由服务端自动路由到隔离的领域智能体，禁止编造跨领域数据。
"""

STRICT_SCOPE_INSTRUCTION = """
回答范围与数据规则（优先于前文笼统的“只根据工具回答”和“涉及某领域必须调用工具”要求）：
1. 可以回答系统功能、使用方法、业务概念、技术原理、接口接入、相关知识及方案建议；这些解释性问题可以使用通用知识，不要求先查询实时业务工具。跨领域的概念解释和比较也可以回答。
2. 只有查询具体人员、资产、告警、当前状态、数量、历史记录等实际业务事实时，才必须调用当前场景工具。禁止跨场景读取或编造数据；其他场景的实际查询应引导切换智能体或使用总控。
3. 区分“通用知识/建议”和“系统实际数据”。系统是否已实现某项功能需以已提供的能力说明或工具结果为依据，不能把通用方案描述成已实现功能。知识库没有命中时说明未检索到，可以继续提供通用解释，但不得编造文件、条款或来源。
4. 问题表达模糊、没有业务关键词或属于追问时，结合上下文理解，必要时追问，不要直接按无关问题拒答。问候时简短回应并介绍可以提供的帮助。
5. 对明确与系统及业务无关的请求简短引导回相关话题。不要因为出现“编程”“翻译”等词就拒绝系统接口开发或业务资料解释等相关请求。
"""


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


@tool
def search_policy_knowledge(query: str, category: str = "", limit: int = 5) -> str:
    """检索医疗急诊、资产管理、安全生产、能源运行和承包商制度知识库。

    query 使用自然语言关键词；category 可传 emergency、asset、safety、power、heat_gas、contractor
    或留空查询全部。结果包含文件名称、文号、发布机关、日期、管理要点和原文链接。
    """
    normalized = "" if category in {"", "all"} else category
    rows = search_documents(query=query, category=normalized, limit=max(1, min(limit, 10)))
    metadata = catalog_metadata()
    return _dumps(
        {
            "query": query,
            "category": normalized or "all",
            "count": len(rows),
            "as_of": metadata["as_of"],
            "notice": "摘要仅供管理参考，请以官方原文为准。",
            "data": rows,
        }
    )


@tool
def create_data_table(
    title: str = "",
    columns_json: str = "",
    rows_json: str = "",
) -> str:
    """把当前场景查询得到的结构化数据生成可直接展示的 Markdown 表格。

    用户明确要求表格，或查询结果包含多条人员、患者、设备、轨迹、统计数据时调用。
    columns_json 是列定义 JSON，例如 [{"key":"patientName","label":"姓名"}]；
    rows_json 是数据行 JSON 数组。不要展示 EPC、腕带标签、坐标等敏感字段。
    """
    hidden = {"epc", "wristbandEpc", "relatedEpc", "id", "sn", "x", "y", "password", "token", "apiKey"}

    def parse_json(raw: str, fallback):
        try:
            return json.loads(raw or "")
        except (TypeError, ValueError, json.JSONDecodeError):
            return fallback

    rows = parse_json(rows_json, [])
    columns = parse_json(columns_json, [])
    if not isinstance(rows, list):
        return "表格生成失败：rows_json 必须是 JSON 数组。"
    rows = [row for row in rows[:100] if isinstance(row, dict)]
    if not rows:
        return (f"### {title}\n\n暂无数据。" if title else "暂无数据。")

    normalized = []
    if isinstance(columns, dict):
        columns = [{"key": key, "label": label} for key, label in columns.items()]
    if isinstance(columns, list):
        for column in columns:
            if isinstance(column, str):
                normalized.append((column, column))
            elif isinstance(column, dict) and column.get("key"):
                normalized.append((str(column["key"]), str(column.get("label") or column["key"])))
    if not normalized:
        normalized = [(key, key) for key in rows[0].keys() if key not in hidden]
    normalized = [(key, label) for key, label in normalized if key not in hidden]
    if not normalized:
        return "表格生成失败：没有可展示的安全字段。"

    def cell(value):
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        return str(value).replace("|", "\\|").replace("\n", " ")

    head = "| " + " | ".join(label for _, label in normalized) + " |"
    sep = "| " + " | ".join("---" for _ in normalized) + " |"
    body = ["| " + " | ".join(cell(row.get(key, "")) for key, _ in normalized) + " |" for row in rows]
    prefix = f"### {title}\n\n" if title else ""
    return prefix + "\n".join([head, sep, *body])


@tool
def create_chart(
    chart_type: str = "bar",
    title: str = "",
    categories_json: str = "",
    series_json: str = "",
    data_json: str = "",
    unit: str = "",
) -> str:
    """根据当前场景查询结果生成 3D 风格柱状图、环形饼图、折线图、面积图、雷达图或仪表盘。

    chart_type 取值支持：
    - bar: 柱状图（对比分析）
    - line: 折线图（时序变化）
    - area: 面积流光图（机组负荷/能耗走势）
    - pie: 环形/饼图（占比分布）
    - radar: 雷达图（多维合规/风险评估）
    - gauge: 工业仪表盘（合规率/机组出力/负荷率百分比）

    柱状图、折线图、面积图和雷达图使用 categories_json 与 series_json；
    饼图使用 data_json，例如 [{"name":"受限空间","value":9}]；
    仪表盘使用 data_json，例如 [{"name":"作业票合规率","value":96.5,"max":100}]。
    只传入真实查询数据，不要估计数值。
    """
    def parse_json(raw: str, fallback):
        try:
            return json.loads(raw or "")
        except (TypeError, ValueError, json.JSONDecodeError):
            return fallback

    chart_type = (chart_type or "bar").lower().strip()
    if chart_type not in {"bar", "pie", "line", "area", "radar", "gauge"}:
        chart_type = "bar"
    title = str(title or "数据统计")[:80]
    unit = str(unit or "")[:20]
    categories = parse_json(categories_json, [])
    series = parse_json(series_json, [])
    data = parse_json(data_json, [])

    if chart_type in {"pie", "gauge"}:
        if not isinstance(data, list):
            return f"图表生成失败：{chart_type} data_json 必须是数组。"
        clean_data = []
        for item in data[:30]:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            try:
                value = float(item.get("value", 0))
            except (TypeError, ValueError):
                continue
            clean_item = {"name": str(item["name"])[:40], "value": value}
            if "max" in item:
                try:
                    clean_item["max"] = float(item["max"])
                except (TypeError, ValueError):
                    pass
            clean_data.append(clean_item)
        if not clean_data:
            return f"图表生成失败：{chart_type} 没有可展示的数据。"
        payload = {"type": chart_type, "title": title, "unit": unit, "visualStyle": "3d", "data": clean_data}
    else:
        if not isinstance(categories, list) or not isinstance(series, list):
            return "图表生成失败：categories_json 和 series_json 必须是数组。"
        clean_categories = [str(item)[:40] for item in categories[:30]]
        clean_series = []
        for item in series[:8]:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            values = []
            for value in (item.get("data") or [])[:30]:
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    values.append(0)
            if values:
                clean_series.append({"name": str(item["name"])[:40], "data": values})
        if not clean_categories or not clean_series:
            return "图表生成失败：没有可展示的分类或序列数据。"
        payload = {
            "type": chart_type,
            "title": title,
            "unit": unit,
            "visualStyle": "3d",
            "categories": clean_categories,
            "series": clean_series,
        }
    # 特殊前缀由 SSE 层识别，前端负责渲染；模型只需用文字解释图表结论。
    return "__CHART__" + _dumps(payload)


def _generate_with_gemini(prompt: str, aspect: str = "16:9") -> str:
    """调用 Google Gemini 图像生成模型，返回 __IMAGE__ 协议字符串。"""
    try:
        from google import genai as google_genai
        from google.genai import types as google_types
    except ImportError:
        return "__IMAGE__" + _dumps({"status": "failed", "error": "google-genai 未安装，请运行 pip install google-genai"})

    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        return "__IMAGE__" + _dumps({"status": "failed", "error": "未配置 GOOGLE_API_KEY，请在 .env 中填写"})

    model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-lite-image")
    aspect_hint = {"1:1": "square", "16:9": "landscape 16:9", "9:16": "portrait 9:16"}.get(aspect, "landscape 16:9")
    full_prompt = (
        f"{prompt}. Clean educational science illustration and technical schematic, "
        f"flat 2D vector illustration, {aspect_hint} composition, clear hierarchy, "
        "generous whitespace, simple modules and arrows, friendly rounded icons, "
        "limited navy teal and warm accent palette, large handwritten-style labels, "
        "very large readable lettering, few words, high contrast, centered labels, "
        "no tiny text, no dense paragraphs, no gibberish, no distorted characters, "
        "no photorealism, no clutter, no watermark."
    )
    try:
        client = google_genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config=google_types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        import time
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                ext = part.inline_data.mime_type.split("/")[-1].replace("jpeg", "jpg")
                outdir = Path("/home/administrator/comfyui_outputs")
                outdir.mkdir(parents=True, exist_ok=True)
                filename = f"Gemini_Schematic_{int(time.time())}.{ext}"
                dest = outdir / filename
                data = part.inline_data.data
                dest.write_bytes(data if isinstance(data, bytes) else bytes(data))
                return "__IMAGE__" + _dumps({"status": "success", "image_path": str(dest), "backend": "gemini", "model": model, "prompt": full_prompt})
        return "__IMAGE__" + _dumps({"status": "failed", "error": "Gemini 未返回图像内容"})
    except Exception as exc:
        return "__IMAGE__" + _dumps({"status": "failed", "error": str(exc), "backend": "gemini"})


@tool
def generate_schematic_image(prompt: str, style: str = "Kurzgesagt Style", aspect: str = "16:9", seed: int = 0) -> str:
    """生成简约的 2D 科普插画或原理图；适用于人员安全、定位、电子围栏、告警和考勤架构图。
    后端由环境变量 IMAGE_BACKEND 控制：comfyui（本地）| gemini（谷歌）| auto（优先本地，不可用时自动切换 Gemini）。
    """
    if not (prompt or "").strip():
        return "请提供要绘制的图片或原理图描述。"

    backend = os.getenv("IMAGE_BACKEND", "auto").lower().strip()

    # 判断 ComfyUI 脚本是否可用
    script = Path("/home/administrator/.codex/skills/comfyui-zimage-schematic/scripts/generate_schematic.py")
    if not script.exists():
        script = Path("/home/administrator/comfyui-zimage-schematic/scripts/generate_schematic.py")
    comfyui_available = script.exists()

    use_gemini = (
        backend == "gemini"
        or (backend == "auto" and not comfyui_available)
    )

    if use_gemini:
        return _generate_with_gemini(prompt, aspect)

    if not comfyui_available:
        return "__IMAGE__" + _dumps({"status": "failed", "error": "ComfyUI 脚本不存在且未配置 Gemini 后端"})

    cmd = ["python3", str(script), "--prompt", prompt, "--style", style or "Kurzgesagt Style", "--aspect", aspect or "16:9", "--output-dir", "/home/administrator/comfyui_outputs"]
    if seed and int(seed) > 0:
        cmd += ["--seed", str(int(seed))]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=720, check=False)
        raw = (proc.stdout or "").strip().splitlines()
        result = json.loads(raw[-1]) if raw else {"status": "failed", "error": proc.stderr[-500:]}
        # auto 模式：ComfyUI 失败（如服务未启动）时回退 Gemini
        if backend == "auto" and result.get("status") in ("server_unavailable", "failed", "submit_failed"):
            gemini_key = os.getenv("GOOGLE_API_KEY", "")
            if gemini_key:
                return _generate_with_gemini(prompt, aspect)
    except Exception as exc:
        if backend == "auto" and os.getenv("GOOGLE_API_KEY", ""):
            return _generate_with_gemini(prompt, aspect)
        return "__IMAGE__" + _dumps({"status": "failed", "error": str(exc)})
    return "__IMAGE__" + _dumps(result)


MAP_AREAS = [
    {"name": "来料检验区", "floor": "1F", "x": 5, "y": 9, "w": 20, "h": 25},
    {"name": "装配工位", "floor": "1F", "x": 28, "y": 9, "w": 28, "h": 25},
    {"name": "无损检测区", "floor": "1F", "x": 59, "y": 9, "w": 17, "h": 25},
    {"name": "尺寸检测区", "floor": "1F", "x": 79, "y": 9, "w": 16, "h": 25},
    {"name": "材料实验室", "floor": "1F", "x": 5, "y": 55, "w": 20, "h": 28},
    {"name": "质量复检区", "floor": "1F", "x": 28, "y": 55, "w": 28, "h": 28},
    {"name": "精加工区", "floor": "1F", "x": 59, "y": 55, "w": 17, "h": 28},
    {"name": "出库区", "floor": "1F", "x": 79, "y": 55, "w": 16, "h": 28},
    {"name": "总装区", "floor": "2F", "x": 5, "y": 9, "w": 43, "h": 32},
    {"name": "成品暂存区", "floor": "2F", "x": 52, "y": 9, "w": 43, "h": 32},
    {"name": "机加工车间", "floor": "2F", "x": 5, "y": 55, "w": 43, "h": 28},
    {"name": "质量隔离区", "floor": "2F", "x": 52, "y": 55, "w": 43, "h": 28},
    {"name": "返修工位", "floor": "3F", "x": 5, "y": 9, "w": 43, "h": 32},
    {"name": "通道（越界）", "floor": "3F", "x": 52, "y": 9, "w": 43, "h": 32},
    {"name": "焊接区", "floor": "3F", "x": 5, "y": 55, "w": 43, "h": 28},
    {"name": "能源中心", "floor": "3F", "x": 52, "y": 55, "w": 43, "h": 28},
    {"name": "涂装区", "floor": "4F", "x": 5, "y": 9, "w": 43, "h": 32},
    {"name": "备件库", "floor": "4F", "x": 52, "y": 9, "w": 43, "h": 32},
    {"name": "成品仓", "floor": "4F", "x": 5, "y": 55, "w": 90, "h": 28},
]


def _map_area(position: str, floor: str = "") -> dict[str, Any] | None:
    normalized = (position or "").strip()
    for area in MAP_AREAS:
        if (floor and area["floor"] != floor):
            continue
        if area["name"] in normalized or normalized in area["name"]:
            return area
    return None


@tool
def show_location_map(keyword: str = "所有", subject_type: str = "auto", day: str = "today") -> str:
    """在院内楼层平面图上显示一个或多个患者/设备的实时位置。

    keyword 可为姓名/门诊号/设备名称/编号，也可传“所有”显示全部；传区域名可筛选该区域。
    subject_type 取 auto / patient / asset；day 取 today / yesterday / all。
    用户要求地图、平面图、患者分布、设备分布、在图上显示时调用。不返回真实经纬度。
    """
    subject_type = (subject_type or "auto").lower().strip()
    keyword = (keyword or "所有").strip()
    payload: dict[str, Any] | None = None

    generic = keyword in {"", "所有", "全部", "所有患者", "全部患者", "患者", "患者分布", "所有设备", "全部设备", "设备", "设备分布"}
    area_filter = next((a["name"] for a in MAP_AREAS if a["name"] in keyword), "")

    if generic or area_filter:
        markers = []
        if subject_type in {"auto", "patient"} and "设备" not in keyword:
            for no, meta in PATIENTS.items():
                if day not in {"", "all"} and meta.get("day", "today") != day:
                    continue
                position = meta.get("currentLocation") or "未知"
                area = _map_area(position)
                if not area or (area_filter and area["name"] != area_filter):
                    continue
                markers.append({
                    "name": meta.get("name") or no, "identifier": no, "position": area["name"],
                    "floor": area["floor"], "subjectType": "患者", "status": "院内",
                })
        if subject_type == "asset" or (subject_type == "auto" and "设备" in keyword):
            for item in MEDICAL_ASSETS:
                area = _map_area(item.get("region") or "", item.get("floor") or "") or _map_area(item.get("region") or "")
                if not area or (area_filter and area["name"] != area_filter):
                    continue
                markers.append({
                    "name": item["asset"], "identifier": item["assetNo"], "position": area["name"],
                    "floor": area["floor"], "subjectType": "设备", "status": "在线" if item["online"] else "离线",
                    "alarm": item["alarm"],
                })
        if markers:
            kind = "设备" if all(m["subjectType"] == "设备" for m in markers) else "患者"
            scope = area_filter or ("今日" if day == "today" and kind == "患者" else "院内")
            floors = sorted({m["floor"] for m in markers})
            payload = {
                "title": f"{scope}{kind}实时分布",
                "subject": f"{len(markers)} 个{kind}", "subjectType": kind,
                "identifier": "实时聚合", "position": area_filter or "多区域",
                "floor": floors[0] if len(floors) == 1 else "多楼层", "status": "实时",
                "areas": [a for a in MAP_AREAS if a["floor"] in floors], "markers": markers,
            }

    if payload is None and subject_type in {"auto", "patient"}:
        no = find_patient_no(keyword)
        if no:
            journey = build_timeline((get_in_out_merge_list(hospital_no=no).get("data") or []))
            position = journey.get("currentLocation") or "未知"
            if position == "已离开":
                return "无法生成位置图：该患者已离开院内定位区域。"
            area = _map_area(position)
            if area:
                payload = {
                    "title": f"{journey.get('patientName') or keyword} · 实时位置",
                    "subject": journey.get("patientName") or keyword,
                    "subjectType": "患者",
                    "identifier": journey.get("hospitalNo") or no,
                    "position": position,
                    "floor": area["floor"],
                    "status": "院内",
                    "areas": [a for a in MAP_AREAS if a["floor"] == area["floor"]],
                    "markers": [{"name": journey.get("patientName") or keyword, "identifier": journey.get("hospitalNo") or no, "position": position, "floor": area["floor"], "subjectType": "患者", "status": "院内"}],
                }

    if payload is None and subject_type in {"auto", "asset"}:
        item = next((row for row in MEDICAL_ASSETS if keyword in {row["asset"], row["assetNo"]}), None)
        if item:
            area = _map_area(item.get("region") or "", item.get("floor") or "")
            if not area:
                area = _map_area(item.get("region") or "")
            if area:
                payload = {
                    "title": f"{item['asset']} · 实时位置",
                    "subject": item["asset"],
                    "subjectType": "设备",
                    "identifier": item["assetNo"],
                    "position": item["region"],
                    "floor": area["floor"],
                    "status": "在线" if item["online"] else "离线",
                    "alarm": item["alarm"],
                    "areas": [a for a in MAP_AREAS if a["floor"] == area["floor"]],
                    "markers": [{"name": item["asset"], "identifier": item["assetNo"], "position": area["name"], "floor": area["floor"], "subjectType": "设备", "status": "在线" if item["online"] else "离线", "alarm": item["alarm"]}],
                }

    if payload is None:
        return "无法生成位置图：未找到对象，或当前位置尚未配置院内平面图。"
    return "__MAP__" + _dumps(payload)


@tool
def list_patients(day: str = "today") -> str:
    """列出绿通患者（姓名、门诊号、腕带EPC、通道、当前区域）。
    day 取 today / yesterday / all，默认今天。
    """
    rows = []
    for no, meta in PATIENTS.items():
        if day not in ("all", "") and meta.get("day", "today") != day:
            continue
        rows.append({"hospitalNo": no, **meta})
    return _dumps({"count": len(rows), "day": day or "today", "data": rows})


@tool
def get_inout_records(
    hospital_no: str = "",
    epc: str = "",
    start_time: str = "",
    end_time: str = "",
) -> str:
    """查询患者 RFID 全量合并流转记录。对应接口 getInOutMergeList。
    hospital_no 可为门诊号或姓名；与 epc 至少传一个。
    start_time/end_time 格式 YYYY-MM-DD HH:MM:SS，必须成对出现。
    """
    no = find_patient_no(hospital_no) or hospital_no or None
    payload = get_in_out_merge_list(
        hospital_no=no,
        epc=epc or None,
        start_time=start_time or None,
        end_time=end_time or None,
    )
    data = payload.get("data") or []
    return _dumps(
        {
            "code": payload.get("code"),
            "message": payload.get("message") or payload.get("msg"),
            "count": len(data),
            "data": data,
        }
    )


@tool
def analyze_patient_journey(hospital_no: str = "", epc: str = "") -> str:
    """分析一名患者的绿通轨迹：当前区域、各节点停留分钟、事件时间线。
    hospital_no 可为门诊号或姓名，与 epc 至少传一个。
    """
    no = find_patient_no(hospital_no) or hospital_no or None
    payload = get_in_out_merge_list(hospital_no=no, epc=epc or None)
    events = payload.get("data") or []
    return _dumps(build_timeline(events))


@tool
def find_timeout_patients(threshold_minutes: float = 120) -> str:
    """查找当前仍在抢救室且停留超过阈值（默认120分钟）的患者。"""
    return _dumps(timeout_patients(threshold_minutes))


@tool
def summarize_area_stay(day: str = "today") -> str:
    """统计各区域停留时长（平均/最长），用于找瓶颈。day=today|yesterday|all。"""
    return _dumps(area_stats(day=day or "today"))


@tool
def list_patients_in_area(area_name: str) -> str:
    """按当前所在区域列出患者，例如 抢救室、CT室、介入室、分诊台、手术室。"""
    rows = patients_in_area(area_name)
    return _dumps({"area": area_name, "count": len(rows), "data": rows})


@tool
def list_patients_by_channel(channel: str, day: str = "today") -> str:
    """按通道列出患者。channel 如 胸痛绿通、卒中绿通、创伤绿通、孕产妇绿通、儿科绿通。"""
    rows = [
        row
        for row in patients_by_channel(channel)
        if day in ("all", "") or row.get("day", "today") == day
    ]
    return _dumps({"channel": channel, "day": day or "today", "count": len(rows), "data": rows})


@tool
def summarize_channels(day: str = "today") -> str:
    """按绿通类型汇总人数和当前分布。"""
    return _dumps(channel_overview(day=day or "today"))


@tool
def list_assets(keyword: str = "", dept: str = "", alarm: str = "", asset_type: str = "") -> str:
    """查询资产/设备列表。对应 GET /goods。
    keyword 为名称、编号、种类或 SN；dept 为科室；alarm 为 越界报警/离线报警/低电量报警/防拆报警；
    asset_type 为 定位 或 能效。
    """
    rows = [slim(d) for d in find_devices(keyword=keyword, dept=dept, alarm=alarm, asset_type=asset_type)]
    return _dumps({"count": len(rows), "data": rows})


@tool
def locate_asset(keyword: str) -> str:
    """查一台设备当前在哪。对应 GET /goods/{id} 与实时定位。
    keyword 为设备名称、编号或标签 SN，例如 输液泵12号、YP-012。
    """
    d = get_device(keyword)
    if not d:
        hits = find_devices(keyword=keyword)
        if not hits:
            return _dumps({"ok": False, "message": "未找到设备"})
        return _dumps({"ok": False, "message": "匹配到多台，请用编号", "candidates": [slim(x) for x in hits[:8]]})
    return _dumps({"ok": True, "data": slim(d)})


@tool
def list_asset_alarms() -> str:
    """当前有报警的设备：越界、防拆、离线、低电量。对应 /goods?alarmStatus=。"""
    rows = [slim(d) for d in alarm_devices()]
    return _dumps({"count": len(rows), "data": rows})


@tool
def analyze_energy(dept: str = "", status: str = "") -> str:
    """能效分析列表。对应 GET /getEnergyEfficiencyPage。
    dept 为科室；status 为 关机/待机/运行/闲置。含使用率、使用时长、开机次数。
    """
    rows = [slim(d) for d in energy_devices(dept=dept, status=status)]
    high = [r for r in rows if isinstance(r.get("useRate"), (int, float)) and r.get("useRate") and r["useRate"] >= 70]
    low = [r for r in rows if isinstance(r.get("useRate"), (int, float)) and r.get("useRate") is not None and r["useRate"] < 25]
    return _dumps({"count": len(rows), "highUseRate": high, "lowUseRate": low, "data": rows})


@tool
def get_asset_power(keyword: str) -> str:
    """某设备近几日耗电。对应 GET /electricQuantity/list。keyword 为名称或编号。"""
    payload = power_of(keyword)
    if not payload:
        return _dumps({"ok": False, "message": "未找到设备或无耗电数据"})
    extra = onoff_of(keyword)
    if extra:
        payload["onOff"] = extra.get("records") or []
    daily = payload["daily"]
    total = round(sum(x["electricQuantity"] for x in daily), 1) if daily else 0
    return _dumps({"ok": True, "total": total, **payload})


@tool
def get_asset_track(keyword: str) -> str:
    """查设备历史轨迹与离开存放位置记录。对应 GET /userPaths/{sn}、GET /move/record。
    返回已合并的停留段（区域、楼层、分钟），不含原始 x/y 坐标。keyword 为名称、编号或 SN。
    """
    payload = track_of(keyword)
    if not payload:
        return _dumps({"ok": False, "message": "未找到设备或无轨迹"})
    if not payload.get("stays"):
        return _dumps({"ok": False, "message": "该设备暂无轨迹历史", "device": payload.get("device")})
    return _dumps({"ok": True, **payload})


LEGACY_TOOLS = [
    search_policy_knowledge,
    create_data_table,
    create_chart,
    show_location_map,
    list_patients,
    list_patients_in_area,
    list_patients_by_channel,
    get_inout_records,
    analyze_patient_journey,
    find_timeout_patients,
    summarize_area_stay,
    summarize_channels,
    list_assets,
    locate_asset,
    list_asset_alarms,
    analyze_energy,
    get_asset_power,
    get_asset_track,
]

# 三个场景只共用无数据状态的渲染/格式工具；业务工具和数据源严格分组。
SAFETY_TOOLS = [create_data_table, create_chart, make_trajectory_tool("safety"), generate_schematic_image, *RESPONSE_FORMAT_TOOLS, *INDUSTRIAL_TOOLS, *ENERGY_TOOLS, *PREDICTIVE_MAINTENANCE_TOOLS]
_REPLACED_MEDICAL_ASSET_TOOLS = {"list_assets", "locate_asset", "list_asset_alarms", "analyze_energy", "get_asset_power", "get_asset_track"}
MEDICAL_TOOLS = [item for item in LEGACY_TOOLS if item.name not in _REPLACED_MEDICAL_ASSET_TOOLS] + [make_trajectory_tool("medical"), *RESPONSE_FORMAT_TOOLS, *MEDICAL_LOCATION_TOOLS]
BUILDING_AGENT_TOOLS = [create_data_table, create_chart, make_trajectory_tool("building"), *RESPONSE_FORMAT_TOOLS, *BUILDING_TOOLS]
ELDERCARE_AGENT_TOOLS = [create_data_table, create_chart, make_trajectory_tool("eldercare"), generate_schematic_image, *RESPONSE_FORMAT_TOOLS, *ELDERCARE_TOOLS]
DIAGNOSTIC_AGENT_TOOLS = [create_data_table, create_chart, make_trajectory_tool("diagnostics"), generate_schematic_image, *RESPONSE_FORMAT_TOOLS, *DIAGNOSTIC_TOOLS]
IOT_AGENT_TOOLS = [create_data_table, create_chart, make_trajectory_tool("iot"), generate_schematic_image, *RESPONSE_FORMAT_TOOLS, *IOT_PLATFORM_TOOLS]
COMMAND_AGENT_TOOLS = [create_data_table, create_chart, *RESPONSE_FORMAT_TOOLS, query_agent_directory, query_demo_scenario_state]
_BASE_SCENE_TOOLS = {
    "medical": MEDICAL_TOOLS,
    "safety": SAFETY_TOOLS,
    "building": BUILDING_AGENT_TOOLS,
    "eldercare": ELDERCARE_AGENT_TOOLS,
    "diagnostics": DIAGNOSTIC_AGENT_TOOLS,
    "iot": IOT_AGENT_TOOLS,
    "command": COMMAND_AGENT_TOOLS,
}
SCENE_TOOLS = {
    scene: [source_aware_tool(scene, item) for item in tools]
    for scene, tools in _BASE_SCENE_TOOLS.items()
}

IMAGE_GROUNDING_LABELS = {
    "medical": "医脉 AI · 急诊与医疗资产",
    "safety": "安域 AI · 人员安全",
    "building": "筑境 AI · 楼宇运营",
    "eldercare": "颐护 AI · 康养物联",
    "diagnostics": "机鉴 AI · 设备健康诊断",
    "iot": "万联 AI · 物联网运营",
}

IMAGE_GROUNDING_DEFAULTS = {
    "medical": [("summarize_channels", {"day": "today"}), ("list_asset_alarms", {})],
    "safety": [("summarize_employees", {"group_by": "department"}), ("summarize_alarms", {}), ("summarize_work_ticket_compliance", {})],
    "building": [("summarize_building_operations", {}), ("query_building_alarms", {"handled": "未处理"})],
    "eldercare": [("summarize_eldercare_operations", {}), ("query_eldercare_alarms", {"status": "未处理"})],
    "diagnostics": [("summarize_diagnostic_operations", {}), ("query_diagnostic_alarms", {"status": "全部"})],
    "iot": [("summarize_iot_operations", {}), ("summarize_iot_device_statistics", {"dimension": "building"}), ("query_iot_events", {"status": ""})],
}

IMAGE_GROUNDING_SPECIAL = {
    "medical": [
        (("人员", "医生", "护士", "医护", "定位"), [("query_locations_realtime", {})]),
        (("资产", "设备", "定位"), [("query_asset_locations_realtime", {})]),
        (("患者", "绿通", "急诊"), [("list_patients", {"day": "today"})]),
    ],
    "safety": [
        (("人员", "定位", "位置"), [("query_locations_realtime", {})]),
        (("资产", "装备", "定位"), [("query_asset_locations_realtime", {})]),
        (("考勤", "出勤"), [("query_attendances", {"date": "__today__"})]),
        (("作业票", "合规"), [("summarize_work_ticket_compliance", {})]),
    ],
    "building": [
        (("人员", "定位", "位置"), [("query_locations_realtime", {})]),
        (("资产", "设施", "设备定位"), [("query_asset_locations_realtime", {})]),
        (("能耗", "能源", "电力"), [("query_building_energy", {"days": 7})]),
        (("空调", "暖通"), [("query_hvac_status", {})]),
    ],
    "eldercare": [
        (("老人", "长者", "定位", "位置"), [("query_elderly_locations", {"keyword": "所有"})]),
        (("健康", "手表", "终端"), [("query_eldercare_health", {"keyword": "所有"})]),
        (("围栏",), [("query_eldercare_geofences", {})]),
    ],
    "diagnostics": [
        (("设备", "机组", "风机"), [("query_diagnostic_devices", {"keyword": "所有"})]),
        (("告警", "报警"), [("query_diagnostic_alarms", {"status": "全部"})]),
    ],
    "iot": [
        (("人员", "定位"), [("query_iot_people_locations", {"keyword": "所有"})]),
        (("资产", "定位"), [("query_iot_asset_locations", {"keyword": "所有"})]),
        (("围栏",), [("query_iot_geofences", {})]),
        (("网关", "拓扑"), [("query_iot_gateway_topology", {})]),
        (("终端", "设备"), [("query_iot_terminals", {"keyword": "所有", "status": "全部"})]),
    ],
}


def _compact_image_data(value: Any, depth: int = 0) -> Any:
    """限制送入生图模型的数据量，同时保留真实指标、对象名称和异常状态。"""
    if depth >= 4:
        return "[nested data omitted]" if isinstance(value, (dict, list)) else str(value)[:180]
    if isinstance(value, dict):
        sensitive = ("password", "secret", "token", "authorization", "authvalue", "mobile", "phone", "idcard", "身份证", "手机号")
        return {
            str(key): ("***" if any(mark in str(key).lower() for mark in sensitive) else _compact_image_data(item, depth + 1))
            for key, item in list(value.items())[:24]
        }
    if isinstance(value, list):
        return [_compact_image_data(item, depth + 1) for item in value[:10]]
    if isinstance(value, str):
        return value[:240]
    return value


def prepare_grounded_image(scene: str, request: str) -> dict[str, Any]:
    """先调用当前场景的隔离业务接口，再生成可供 ComfyUI/Gemini 使用的业务提示词。"""
    scene = scene if scene in IMAGE_GROUNDING_DEFAULTS else "safety"
    text = request or "生成业务原理图"
    planned: list[tuple[str, dict[str, Any]]] = []
    for keywords, tools in IMAGE_GROUNDING_SPECIAL.get(scene, []):
        if any(keyword in text for keyword in keywords):
            planned.extend(tools)
    planned.extend(IMAGE_GROUNDING_DEFAULTS[scene])

    selected: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for name, args in planned:
        if name in seen:
            continue
        seen.add(name)
        selected.append((name, {key: (date.today().isoformat() if value == "__today__" else value) for key, value in args.items()}))
        if len(selected) == 3:
            break

    available = {item.name: item for item in SCENE_TOOLS[scene]}
    snapshots: list[dict[str, Any]] = []
    for name, args in selected:
        tool_item = available.get(name)
        if tool_item is None:
            continue
        try:
            raw = tool_item.invoke(args)
            try:
                payload = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                payload = str(raw)[:1200]
            snapshots.append({"interface": name, "request": args, "response": _compact_image_data(payload)})
        except Exception as exc:
            snapshots.append({"interface": name, "request": args, "response": {"ok": False, "error": str(exc)[:300]}})

    snapshot_text = json.dumps(snapshots, ensure_ascii=False, separators=(",", ":"))[:9000]
    scene_label = IMAGE_GROUNDING_LABELS[scene]
    prompt = (
        f"Create a clean 16:9 business schematic for {scene_label}. "
        f"The user's requested subject is: {text}. "
        "The picture must be grounded in the current agent's isolated business API snapshot below. "
        "Use the actual object names, totals, locations, statuses and alarm values when they are present; do not invent data. "
        "Turn the data into one clear operational story with four to six connected modules, arrows, and two or three KPI callouts. "
        "Keep all visible wording in Simplified Chinese, use only a few very large handwritten-style labels, high contrast, "
        "ample whitespace, no tiny text, no dense table, no gibberish, no watermark. "
        f"Business API snapshot: {snapshot_text}"
    )
    return {
        "scene": scene,
        "sceneLabel": scene_label,
        "prompt": prompt,
        "sources": [item["interface"] for item in snapshots],
        "snapshotCount": len(snapshots),
    }
SCENE_PROMPTS = {
    "medical": MEDICAL_SYSTEM_PROMPT,
    "safety": SAFETY_SYSTEM_PROMPT,
    "building": BUILDING_SYSTEM_PROMPT,
    "eldercare": ELDERCARE_SYSTEM_PROMPT,
    "diagnostics": DIAGNOSTIC_SYSTEM_PROMPT,
    "iot": IOT_SYSTEM_PROMPT,
    "command": COMMAND_SYSTEM_PROMPT,
}
# 兼容既有导入；默认仍为人员安全场景。
TOOLS = SAFETY_TOOLS

LOCAL_TOOL_GROUPS = {
    "人员组织": {
        "keywords": ("员工", "人员档案", "工号", "姓名", "承包商", "访客", "部门", "岗位", "组织", "在册"),
        "tools": ("query_employees", "query_contractor_staff", "query_contractors", "query_departments", "query_visitors", "summarize_employees"),
    },
    "定位轨迹": {
        "keywords": ("位置", "定位", "在哪", "轨迹", "进出", "进入", "离开", "在线人数", "当前区域", "停留"),
        "tools": ("query_locations_realtime", "query_locations_history", "query_region_enter_leave", "query_region_enter_leave_summary", "query_online_persons", "render_trajectory_heatmap"),
    },
    "资产定位": {
        "keywords": ("资产定位", "资产位置", "设备位置", "设备在哪", "设备轨迹", "仪器位置", "装备位置"),
        "tools": ("query_asset_locations_realtime", "query_asset_locations_history", "query_asset_region_enter_leave", "render_trajectory_heatmap"),
    },
    "作业票": {
        "keywords": ("作业票", "工作票", "操作票", "合规", "违规规则", "票号", "流程时长", "有效工时", "承包商工时"),
        "tools": ("list_work_tickets", "summarize_work_tickets", "list_work_ticket_compliance", "summarize_work_ticket_compliance", "trend_work_ticket_compliance", "group_work_ticket_compliance", "rank_work_ticket_compliance_rules", "get_work_ticket_compliance_detail", "get_work_ticket_process_analysis", "query_work_ticket_workhour_person", "query_work_ticket_workhour_contractor"),
    },
    "人员报警": {
        "keywords": ("人员报警", "报警汇总", "报警明细", "连续报警", "处理时长", "越界报警", "静止报警"),
        "tools": ("summarize_alarms", "analyze_alarms"),
    },
    "定位设备": {
        "keywords": ("定位设备", "定位卡", "基站", "信标", "卡片", "绑定记录", "低电量", "设备在线率"),
        "tools": ("query_devices", "summarize_devices", "query_card_bind_records"),
    },
    "考勤门禁": {
        "keywords": ("考勤", "排班", "班次", "门禁", "门禁记录", "迟到", "早退"),
        "tools": ("query_attendances", "query_schedules", "query_access_records"),
    },
    "驻留强度": {
        "keywords": ("徘徊", "异常驻留", "行走距离", "工作强度", "劳动强度", "疲劳", "工作负荷"),
        "tools": ("query_loitering_sessions", "query_abnormal_dwell_summary", "query_trajectory_distance", "query_work_intensity_summary", "query_workload_analysis", "render_trajectory_heatmap"),
    },
    "质检": {
        "keywords": ("质检", "质量检查", "检查记录"),
        "tools": ("query_inspection_list",),
    },
    "辅助渲染": {
        "keywords": ("目录树", "人员树", "时间线", "地图", "平面图", "3d", "三维", "数字孪生", "原理图", "示意图", "架构图", "流程图", "画图", "图片", "插画", "图文并茂", "科普"),
        "tools": ("render_personnel_tree", "render_personnel_timeline", "show_factory_3d_map", "generate_schematic_image"),
    },
    "能源生产": {
        "keywords": ("机组", "发电", "出力", "装机", "煤耗", "可用率", "电网负荷", "新能源占比", "频率"),
        "tools": ("query_generation_units", "query_power_generation_realtime", "summarize_grid_load"),
    },
    "输变配电": {
        "keywords": ("变电站", "主变", "线路", "馈线", "停电", "输电", "配电", "负载率", "导线温升"),
        "tools": ("query_substations", "query_line_operations", "query_outage_events"),
    },
    "供热燃气": {
        "keywords": ("供热", "热网", "热负荷", "供温", "回温", "燃气", "天然气", "供气", "门站", "调压站", "加臭"),
        "tools": ("query_heat_supply", "query_heat_network_alarms", "query_gas_supply"),
    },
    "能源运营": {
        "keywords": ("调度指令", "能源调度", "能耗", "线损", "热损", "气损", "经营指标", "能源安全", "综合驾驶舱", "能源指标"),
        "tools": ("query_dispatch_commands", "query_energy_consumption", "query_energy_safety_risks", "summarize_energy_kpis"),
    },
    "预测性维护": {
        "keywords": ("预测性维护", "预测维护", "监测终端", "健康度", "健康评分", "状态监测", "故障预测", "故障概率", "剩余寿命", "rul", "维护建议", "检修建议", "振动趋势", "局放", "油色谱", "数据质量"),
        "tools": ("query_predictive_monitoring_terminals", "summarize_predictive_monitoring_terminals", "query_equipment_health", "query_condition_monitoring", "predict_equipment_failures", "query_remaining_useful_life", "recommend_predictive_maintenance", "summarize_predictive_maintenance"),
    },
}

DEFAULT_LOCAL_TOOLS = (
    "summarize_employees", "query_locations_realtime", "summarize_work_tickets",
    "query_asset_locations_realtime", "summarize_alarms", "summarize_energy_kpis", "summarize_predictive_maintenance",
)
MEDICAL_LOCAL_TOOL_GROUPS = {
    "人员定位": {
        "keywords": ("人员定位", "医护", "医生", "护士", "护工", "人员位置", "人员轨迹", "历史位置", "停留", "活动区域", "在哪里", "在哪"),
        "tools": ("query_locations_realtime", "query_locations_history", "query_region_enter_leave", "render_trajectory_heatmap"),
    },
    "患者绿通": {
        "keywords": ("患者", "绿通", "抢救室", "分诊", "ct", "介入", "通道", "停留", "超时"),
        "tools": ("list_patients", "list_patients_in_area", "list_patients_by_channel", "get_inout_records", "analyze_patient_journey", "find_timeout_patients", "summarize_area_stay", "summarize_channels", "render_trajectory_heatmap"),
    },
    "医疗资产": {
        "keywords": ("医疗设备", "资产", "输液泵", "呼吸机", "设备", "离线", "低电", "越界", "耗电", "能效", "使用率"),
        "tools": ("query_asset_locations_realtime", "query_asset_locations_history", "query_asset_region_enter_leave", "list_assets", "locate_asset", "list_asset_alarms", "analyze_energy", "get_asset_power", "get_asset_track", "render_trajectory_heatmap"),
    },
    "医疗地图": {
        "keywords": ("地图", "平面图", "位置图", "分布"),
        "tools": ("show_location_map", "list_patients", "list_assets"),
    },
    "政策知识": {
        "keywords": ("政策", "规范", "标准", "制度", "国有资产"),
        "tools": ("search_policy_knowledge",),
    },
}

BUILDING_LOCAL_TOOL_GROUPS = {
    "综合运营": {"keywords": ("综合", "总览", "整体", "驾驶舱", "运营态势"), "tools": ("summarize_building_operations",)},
    "人员资产定位": {"keywords": ("人员", "员工", "安保", "访客位置", "人员定位", "人员轨迹", "资产定位", "设备位置", "设备轨迹", "在哪", "停留", "活动区域"), "tools": ("query_locations_realtime", "query_locations_history", "query_region_enter_leave", "query_asset_locations_realtime", "query_asset_locations_history", "query_asset_region_enter_leave", "render_trajectory_heatmap")},
    "能源电力": {"keywords": ("电力", "电压", "电流", "功率", "谐波", "能耗", "用电", "pue", "eui"), "tools": ("query_building_power", "query_building_energy")},
    "空调水务照明": {"keywords": ("空调", "冷水", "冰水", "eer", "给水", "排水", "水泵", "液位", "照明", "照度", "调光"), "tools": ("query_hvac_status", "query_water_system", "query_lighting_status")},
    "绿色能源": {"keywords": ("光伏", "发电", "充电桩", "充电"), "tools": ("query_solar_generation", "query_charging_piles")},
    "机房设施": {"keywords": ("机房", "ups", "存储", "服务器", "防火墙", "cpu", "内存"), "tools": ("query_data_room",)},
    "交通安防": {"keywords": ("停车", "车位", "电梯", "门禁", "巡更", "访客", "安防"), "tools": ("query_parking_status", "query_elevator_status", "query_security_operations")},
    "消防应急": {"keywords": ("消防", "火警", "联动", "应急", "事故", "处置"), "tools": ("query_fire_linkage", "query_building_alarms", "get_building_emergency_response")},
    "告警运维": {"keywords": ("告警", "报警", "异常", "故障", "资产", "台账", "维护", "维保", "逾期"), "tools": ("query_building_alarms", "query_building_assets", "query_building_maintenance")},
}

ELDERCARE_LOCAL_TOOL_GROUPS = {
    "养老综合": {"keywords": ("综合", "总览", "养老", "运营态势", "床位"), "tools": ("summarize_eldercare_operations",)},
    "老人定位": {"keywords": ("老人", "长者", "位置", "定位", "在哪", "楼层", "房间", "轨迹", "停留", "活动区域"), "tools": ("query_elderly_locations", "render_trajectory_heatmap")},
    "养老告警": {"keywords": ("告警", "跌倒", "静止", "离床", "越界", "低电", "离线"), "tools": ("query_eldercare_alarms",)},
    "养老设备": {"keywords": ("手表", "床垫", "按钮", "设备", "终端"), "tools": ("query_eldercare_devices",)},
    "健康关注": {"keywords": ("心率", "步数", "睡眠", "健康"), "tools": ("query_eldercare_health",)},
    "养老围栏": {"keywords": ("围栏", "区域", "进出"), "tools": ("query_eldercare_geofences",)},
}

DIAGNOSTIC_LOCAL_TOOL_GROUPS = {
    "诊断综合": {"keywords": ("综合", "总览", "健康度", "设备态势"), "tools": ("summarize_diagnostic_operations",)},
    "设备状态": {"keywords": ("设备", "设备树", "在线", "状态", "详情"), "tools": ("query_diagnostic_devices",)},
    "实时指标": {"keywords": ("实时", "温度", "振动", "转速", "指标"), "tools": ("query_realtime_device_metrics",)},
    "历史趋势": {"keywords": ("历史", "趋势", "变化", "曲线", "状态轨迹", "异常热区"), "tools": ("query_history_device_metrics", "render_trajectory_heatmap")},
    "故障报警": {"keywords": ("报警", "故障", "异常", "原因"), "tools": ("query_diagnostic_alarms", "recommend_diagnostic_action")},
    "波形诊断": {"keywords": ("波形", "频谱", "倍频", "诊断"), "tools": ("analyze_device_waveform", "recommend_diagnostic_action")},
}

IOT_LOCAL_TOOL_GROUPS = {
    "物联综合": {"keywords": ("综合", "总览", "物联网", "态势"), "tools": ("summarize_iot_operations",)},
    "建筑终端": {"keywords": ("建筑", "终端", "设备", "在线", "通信", "低电量"), "tools": ("query_iot_buildings", "query_iot_terminals", "summarize_iot_device_statistics")},
    "人员资产定位": {"keywords": ("人员", "员工", "访客", "资产", "车辆", "工具", "位置", "在哪里", "在哪", "停留", "活动区域"), "tools": ("query_iot_people_locations", "query_iot_asset_locations", "query_iot_history", "render_trajectory_heatmap")},
    "网关信标": {"keywords": ("网关", "拓扑", "节点组", "信标", "beacon", "定位"), "tools": ("query_iot_gateway_topology", "query_iot_beacons")},
    "电子围栏": {"keywords": ("围栏", "区域", "进出"), "tools": ("query_iot_geofences", "query_iot_events")},
    "轨迹物模型": {"keywords": ("轨迹", "历史路径", "物模型", "实时数据", "历史数据"), "tools": ("query_iot_history", "query_iot_model_data", "render_trajectory_heatmap")},
    "设备事件": {"keywords": ("事件", "离线", "低电", "异常", "告警"), "tools": ("query_iot_events",)},
    "设备控制": {"keywords": ("控制", "下发", "重启", "亮度", "频率", "属性设置", "服务调用"), "tools": ("query_iot_downlink_tasks",)},
}

COMMAND_LOCAL_TOOL_GROUPS = {
    "智能体目录": {"keywords": ("能力", "智能体", "场景", "领域", "能做什么"), "tools": ("query_agent_directory",)},
    "演示状态": {"keywords": ("演示", "导演", "步骤", "场景状态"), "tools": ("query_demo_scenario_state",)},
}

SCENE_LOCAL_TOOL_GROUPS = {
    "medical": MEDICAL_LOCAL_TOOL_GROUPS,
    "safety": LOCAL_TOOL_GROUPS,
    "building": BUILDING_LOCAL_TOOL_GROUPS,
    "eldercare": ELDERCARE_LOCAL_TOOL_GROUPS,
    "diagnostics": DIAGNOSTIC_LOCAL_TOOL_GROUPS,
    "iot": IOT_LOCAL_TOOL_GROUPS,
    "command": COMMAND_LOCAL_TOOL_GROUPS,
}
SCENE_DEFAULT_LOCAL_TOOLS = {
    "medical": ("query_locations_realtime", "query_asset_locations_realtime", "list_patients", "summarize_channels", "list_asset_alarms"),
    "safety": DEFAULT_LOCAL_TOOLS,
    "building": ("summarize_building_operations", "query_locations_realtime", "query_asset_locations_realtime", "query_building_alarms"),
    "eldercare": ("summarize_eldercare_operations", "query_elderly_locations", "query_eldercare_alarms"),
    "diagnostics": ("summarize_diagnostic_operations", "query_diagnostic_devices", "query_diagnostic_alarms"),
    "iot": ("summarize_iot_operations", "query_iot_terminals", "query_iot_events"),
    "command": ("query_agent_directory", "query_demo_scenario_state"),
}
_ALL_TOOL_BY_NAME = {
    scene: {item.name: item for item in tools}
    for scene, tools in SCENE_TOOLS.items()
}
_TOOL_BY_NAME = _ALL_TOOL_BY_NAME["safety"]
AGENT_MEMORIES = {scene: MemorySaver() for scene in SCENE_TOOLS}
AGENT_MEMORY = AGENT_MEMORIES["safety"]


def route_local_tools(question: str, scene: str = "safety") -> tuple[list[str], list[str]]:
    """用轻量规则选择相关工具组；返回工具名和可展示的业务域名称。"""
    scene = scene if scene in SCENE_TOOLS else "safety"
    local_groups = SCENE_LOCAL_TOOL_GROUPS[scene]
    normalized = re.sub(r"\s+", "", (question or "").lower())
    groups = [name for name, config in local_groups.items() if any(word in normalized for word in config["keywords"])]
    if scene == "safety" and "辅助渲染" in groups and "定位轨迹" not in groups:
        groups.append("定位轨迹")
    if not groups:
        return ["create_data_table", "create_chart", *SCENE_DEFAULT_LOCAL_TOOLS[scene]], ["综合查询"]
    names = {"create_data_table", "create_chart"}
    for group in groups:
        names.update(local_groups[group]["tools"])
    return sorted(names), groups


TOOL_LABELS = {
    "search_policy_knowledge": "国家政策知识库",
    "create_data_table": "表格生成",
    "create_chart": "图表生成",
    "generate_schematic_image": "原理图生成",
    "render_trajectory_heatmap": "轨迹热力图",
    "show_location_map": "院内位置图",
    "list_patients": "患者名录",
    "list_patients_in_area": "区域在场",
    "list_patients_by_channel": "通道名录",
    "summarize_channels": "通道汇总",
    "get_inout_records": "进出记录",
    "analyze_patient_journey": "轨迹分析",
    "find_timeout_patients": "超时预警",
    "summarize_area_stay": "区域统计",
    "list_assets": "设备列表",
    "locate_asset": "设备定位",
    "list_asset_alarms": "设备报警",
    "analyze_energy": "能效分析",
    "get_asset_power": "耗电统计",
    "get_asset_track": "设备轨迹",
    "format_concise_reply": "简洁答复格式",
    "format_executive_brief": "领导摘要格式",
    "format_alarm_disposal_card": "告警处置单格式",
    "format_positioning_report": "定位分析报告格式",
    "format_shift_handover": "交接班记录格式",
}
TOOL_LABELS.update({tool.name: tool.name for tool in INDUSTRIAL_TOOLS})
TOOL_LABELS.update({tool.name: tool.name for tool in ENERGY_TOOLS})
TOOL_LABELS.update({tool.name: tool.name for tool in PREDICTIVE_MAINTENANCE_TOOLS})
TOOL_LABELS.update({tool.name: tool.name for tool in BUILDING_TOOLS})
TOOL_LABELS.update({tool.name: tool.name for tool in ELDERCARE_TOOLS})
TOOL_LABELS.update({tool.name: tool.name for tool in DIAGNOSTIC_TOOLS})
TOOL_LABELS.update({tool.name: tool.name for tool in IOT_PLATFORM_TOOLS})


def build_llm(provider: str = "deepseek", model: str = "") -> ChatOpenAI:
    # 云端偶发连接抖动或 429/5xx 时由 SDK 自动退避重试；90 秒也适配较慢的推理节点。
    provider = (provider or "deepseek").lower().strip()
    max_output_tokens = int(os.getenv("LOCAL_MODEL_MAX_OUTPUT_TOKENS", "800")) if provider == "local" else 800
    common = dict(temperature=0, timeout=90, max_retries=4, max_tokens=max_output_tokens, streaming=True, stream_usage=True)
    if provider == "local":
        return ChatOpenAI(
            model=model or os.getenv("LOCAL_MODEL", "qwen3.8-27b-local"),
            api_key=os.getenv("LOCAL_API_KEY", "local-no-key"),
            base_url=os.getenv("LOCAL_BASE_URL", "http://127.0.0.1:8080/v1"),
            **common,
        )
    if provider == "openrouter" and os.getenv("OPENROUTER_API_KEY"):
        return ChatOpenAI(
            model=model or os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3.1"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            default_headers={"HTTP-Referer": "http://localhost:7861", "X-Title": "Energy Spatial Intelligence Agent"},
            extra_body={"provider": {"allow_fallbacks": True}},
            **common,
        )
    if provider == "deepseek" and os.getenv("DEEPSEEK_API_KEY"):
        return ChatOpenAI(
            model=model or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            **common,
        )
    if os.getenv("OPENAI_API_KEY"):
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
            **common,
        )
    raise RuntimeError(
        "未配置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY。请复制 .env.example 为 .env 后填写。"
    )


def _select_agent_tools(scene: str, provider: str, local_tool_names: list[str] | None, response_format: str):
    """业务工具按场景/本地路由选择，回复格式只加载本轮指定的一个。"""
    response_format = normalize_response_format(response_format)
    selected_format_tool = RESPONSE_FORMATS[response_format]["tool"]
    if provider == "local":
        selected_names = set(local_tool_names or route_local_tools("", scene=scene)[0])
        selected_names.difference_update(RESPONSE_FORMAT_TOOL_NAMES)
        if selected_format_tool:
            selected_names.add(selected_format_tool)
        scene_tools = _ALL_TOOL_BY_NAME[scene]
        return [scene_tools[name] for name in selected_names if name in scene_tools]

    tools = [item for item in SCENE_TOOLS[scene] if item.name not in RESPONSE_FORMAT_TOOL_NAMES]
    if selected_format_tool:
        tools.append(_ALL_TOOL_BY_NAME[scene][selected_format_tool])
    return tools


def build_agent(provider: str = "deepseek", model: str = "", local_tool_names: list[str] | None = None, scene: str = "safety", response_format: str = "auto"):
    scene = scene if scene in SCENE_TOOLS else "safety"
    response_format = normalize_response_format(response_format)
    tools = _select_agent_tools(scene, provider, local_tool_names, response_format)
    return create_react_agent(
        build_llm(provider=provider, model=model),
        tools=tools,
        checkpointer=AGENT_MEMORIES[scene],
        prompt=SCENE_PROMPTS[scene] + STRICT_SCOPE_INSTRUCTION + (TRAJECTORY_DECISION_INSTRUCTION if scene != "command" else "") + "\n数据来源以工具返回的 source 字段为准：真实接口结果必须标注真实接口，模拟结果必须标注模拟数据。\n" + response_format_system_instruction(response_format),
        pre_model_hook=_local_pre_model_hook if provider == "local" else None,
    )


from langchain_core.messages import trim_messages, SystemMessage, HumanMessage, AIMessage, ToolMessage

def _approx_message_tokens(messages: list) -> int:
    """保守估算中英文消息 token，避免依赖远程 tokenizer。"""
    chars = 0
    for message in messages:
        content = getattr(message, "content", "")
        if isinstance(content, str):
            chars += len(content)
        else:
            chars += len(json.dumps(content, ensure_ascii=False, default=str))
        chars += 24
    return max(1, chars // 2)


def _local_pre_model_hook(state: dict) -> dict:
    """限制本地模型的对话历史，为系统提示、工具定义和回答预留上下文。"""
    messages = state.get("messages") or []
    try:
        trimmed = trim_messages(
            messages,
            max_tokens=int(os.getenv("LOCAL_HISTORY_TOKENS", "900")),
            strategy="last",
            token_counter=_approx_message_tokens,
            include_system=False,
            start_on="human",
            allow_partial=False,
        )
        return {"llm_input_messages": trimmed or messages[-1:]}
    except Exception:
        # 工具调用链不完整时，至少保留最新用户问题，避免再次溢出。
        latest_human = [item for item in reversed(messages) if isinstance(item, HumanMessage)]
        return {"llm_input_messages": latest_human[:1] or messages[-1:]}

def ask(agent, question: str, thread_id: str = "demo") -> str:
    result = agent.invoke(
        {"messages": [("user", question)]},
        config=callbacks_config(thread_id),
    )
    return result["messages"][-1].content


def ask_stream(agent, question: str, thread_id: str = "demo", metadata: dict | None = None):
    """产出 {type: status|token, text}，供网页边生成边显示。"""
    config = callbacks_config(thread_id, metadata)
    seen_tools: set[str] = set()
    usage_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0}
    for mode, data in agent.stream(
        {"messages": [("user", question)]},
        config=config,
        stream_mode=["messages", "updates"],
    ):
        if mode == "updates" and isinstance(data, dict):
            tools_update = data.get("tools")
            messages = []
            if isinstance(tools_update, dict):
                messages = tools_update.get("messages") or []
            for msg in messages:
                name = getattr(msg, "name", None)
                if name and name not in seen_tools:
                    seen_tools.add(name)
                    label = TOOL_LABELS.get(name, name)
                    yield {"type": "status", "text": f"正在查询「{label}」…"}
                    yield {"type": "tool", "name": name, "label": label, "phase": "calling"}
                elif name:
                    label = TOOL_LABELS.get(name, name)
                    yield {"type": "tool", "name": name, "label": label, "phase": "done"}
                content = getattr(msg, "content", "")
                if name in RESPONSE_FORMAT_TOOL_NAMES and isinstance(content, str) and content.strip():
                    # 有些兼容模型在格式工具返回后不再生成 Assistant 文本，先直接展示工具结果。
                    yield {"type": "formatted", "text": content}
                if name == "create_chart" and isinstance(content, str) and content.startswith("__CHART__"):
                    try:
                        chart = json.loads(content[len("__CHART__"):])
                        yield {"type": "chart", "chart": chart}
                    except json.JSONDecodeError:
                        yield {"type": "status", "text": "图表数据解析失败，已保留文字结果。"}
                if name == "render_trajectory_heatmap" and isinstance(content, str) and content.startswith("__TRAJECTORY__"):
                    try:
                        trajectory = json.loads(content[len("__TRAJECTORY__"):])
                        # 智能体决定是否画图；一旦决定画图，群体范围必须以用户原问题为准，
                        # 防止模型把“所有老人/全部资产”在工具参数中缩成某一个对象。
                        group_words = ("所有", "全部", "全体", "整体", "群体", "多人", "多设备")
                        scene = (metadata or {}).get("scene", "")
                        if scene and any(word in question for word in group_words):
                            scoped = trajectory_payload(scene, question)
                            if scoped.get("mode") == "group":
                                scoped["decisionReason"] = trajectory.get("decisionReason", "群体活动分布适合热力图展示")
                                trajectory = scoped
                        yield {"type": "trajectory", "trajectory": trajectory}
                    except json.JSONDecodeError:
                        yield {"type": "status", "text": "轨迹热力图解析失败，已保留文字结果。"}
                if name == "generate_schematic_image" and isinstance(content, str) and content.startswith("__IMAGE__"):
                    try:
                        image = json.loads(content[len("__IMAGE__"):])
                        yield {"type": "image", "image": image}
                    except json.JSONDecodeError:
                        yield {"type": "status", "text": "原理图结果解析失败。"}
                if name in {"show_location_map", "show_factory_3d_map"} and isinstance(content, str) and content.startswith("__MAP__"):
                    try:
                        location_map = json.loads(content[len("__MAP__"):])
                        yield {"type": "map", "map": location_map}
                    except json.JSONDecodeError:
                        yield {"type": "status", "text": "位置图数据解析失败，已保留文字结果。"}
            continue

        if mode != "messages":
            continue
        msg, meta = data if isinstance(data, tuple) else (data, {})
        node = (meta or {}).get("langgraph_node")
        if node and node != "agent":
            continue
        usage = getattr(msg, "usage_metadata", None) or {}
        if usage and any(usage.get(key) for key in ("input_tokens", "output_tokens", "total_tokens")):
            usage_total["input_tokens"] += int(usage.get("input_tokens") or 0)
            usage_total["output_tokens"] += int(usage.get("output_tokens") or 0)
            usage_total["total_tokens"] += int(usage.get("total_tokens") or 0)
            usage_total["calls"] += 1
        if getattr(msg, "tool_calls", None):
            for call in msg.tool_calls:
                name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
                if name and name not in seen_tools:
                    seen_tools.add(name)
                    label = TOOL_LABELS.get(name, name)
                    yield {"type": "status", "text": f"正在查询「{label}」…"}
                    yield {"type": "tool", "name": name, "label": label, "phase": "calling"}
            continue
        text = getattr(msg, "content", None)
        if isinstance(text, list):
            text = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in text
            )
        if text:
            yield {"type": "token", "text": text}
    if usage_total["total_tokens"]:
        yield {"type": "usage", "usage": usage_total}
