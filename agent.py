"""LangGraph ReAct 智能体：对话 → 调 RFID 工具 → 用工具结果回答。"""

from __future__ import annotations

import json
import os
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

load_dotenv()

SYSTEM_PROMPT = """你是医院急诊绿通 + 资产定位能效助手。只根据工具返回的数据回答，禁止估计数字。

规则：
1. 凡是涉及患者位置、轨迹、停留时长、超时、统计，必须先调工具，禁止估计数字。
2. 分域：问患者/绿通/抢救室/分诊/CT轨迹 → 用患者工具；问设备/资产/输液泵/呼吸机/在哪台设备/离线/低电/越界/能耗/耗电/使用率/轨迹/去过哪 → 用资产工具。
3. 用户说患者姓名时用患者查询工具；问某区域有哪些患者用 list_patients_in_area，不要逐个分析。
4. 查不到就说查不到，不要编患者、设备或时间。
5. 患者当前仍停留的区域，分钟数是「进入该区域至今」。
6. 当用户明确要求表格，或查询结果包含 2 条以上结构化记录时，先调用 create_data_table 生成表格，再基于表格组织回答；单个数值或单个对象不强制调用。
7. 表格只保留与问题相关的安全字段，禁止展示 EPC、腕带标签、坐标、Token 等原始字段。
8. 用户明确要求柱状图、饼图、折线图或趋势图时，在查询数据后调用 create_chart；图表数值必须来自查询工具，不能估计。图表生成后用文字总结，并不要把 __CHART__ 配置原文贴给用户。
9. 默认查今天。用户问昨天时，把 day 设为 yesterday。
10. 数据来源写一句：绿通 RFID 或 资产定位/能效接口。
11. 用户要求地图、平面图、位置图或“直观显示位置”时，调用 show_location_map；“所有患者/患者分布”传 subject_type=patient、keyword=所有，“所有设备/设备分布”传 subject_type=asset、keyword=所有；不要在正文中输出地图配置或坐标。
12. 用户询问国家政策、规范、标准、急诊管理制度、医疗设备或国有资产管理要求时，必须调用 search_policy_knowledge。回答中注明文件名称、文号、发布机关、发布日期和官方原文链接；知识库摘要仅供管理参考，不替代正式文件或法律意见。

回答版式（必须遵守）：
- 先用一句话给结论，例如「今天胸痛绿通共 9 人」。
- 超过 2 条的名单、超时、统计，必须用 Markdown 表格，表头用中文。
- 患者表列只要：姓名 | 门诊号 | 通道 | 当前区域。不要贴 EPC，不要贴 JSON 原文，不要用代码块包表格。
- 人多时按当前区域分组，用小标题，如「### 抢救室（7人）」，每组一张表。
- 单人轨迹用表：时间 | 动作 | 区域 | 节点。停留用另一张表：区域 | 分钟。
- 统计表：区域 | 人数 | 平均(分) | 最长(分)。超时表：姓名 | 门诊号 | 已停留(分) | 进入时间。
- 设备表列：名称 | 编号 | 科室 | 位置 | 在线 | 报警。能效表加：状态 | 使用率。轨迹表：时间 | 区域 | 楼层 | 停留(分)。不要贴坐标 x/y、不要贴 JSON。
"""


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


@tool
def search_policy_knowledge(query: str, category: str = "", limit: int = 5) -> str:
    """检索国家级医疗急诊与医疗资产管理政策知识库。

    query 使用自然语言关键词；category 可传 emergency（医疗急诊）、asset（资产管理）
    或留空查询全部。结果包含文件名称、文号、发布机关、日期、管理要点和官方原文链接。
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
    """把查询得到的结构化数据生成可直接展示的 Markdown 表格。

    用户明确要求表格，或查询结果包含多条患者、设备、轨迹、统计数据时调用。
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
    """根据查询结果生成柱状图、饼图或折线图配置。

    chart_type 取 bar / pie / line；柱状图和折线图使用 categories_json 与 series_json，
    饼图使用 data_json，例如 [{"name":"胸痛绿通","value":9}]。
    只传入已由查询工具返回的数据，不要估计或编造数值。
    """
    def parse_json(raw: str, fallback):
        try:
            return json.loads(raw or "")
        except (TypeError, ValueError, json.JSONDecodeError):
            return fallback

    chart_type = (chart_type or "bar").lower().strip()
    if chart_type not in {"bar", "pie", "line"}:
        chart_type = "bar"
    title = str(title or "数据统计")[:80]
    unit = str(unit or "")[:20]
    categories = parse_json(categories_json, [])
    series = parse_json(series_json, [])
    data = parse_json(data_json, [])

    if chart_type == "pie":
        if not isinstance(data, list):
            return "图表生成失败：饼图 data_json 必须是数组。"
        clean_data = []
        for item in data[:30]:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            try:
                value = float(item.get("value", 0))
            except (TypeError, ValueError):
                continue
            clean_data.append({"name": str(item["name"])[:40], "value": value})
        if not clean_data:
            return "图表生成失败：饼图没有可展示的数据。"
        payload = {"type": chart_type, "title": title, "unit": unit, "data": clean_data}
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
            "categories": clean_categories,
            "series": clean_series,
        }
    # 特殊前缀由 SSE 层识别，前端负责渲染；模型只需用文字解释图表结论。
    return "__CHART__" + _dumps(payload)


MAP_AREAS = [
    {"name": "分诊台", "floor": "1F", "x": 5, "y": 9, "w": 20, "h": 25},
    {"name": "抢救室", "floor": "1F", "x": 28, "y": 9, "w": 28, "h": 25},
    {"name": "CT室", "floor": "1F", "x": 59, "y": 9, "w": 17, "h": 25},
    {"name": "DR室", "floor": "1F", "x": 79, "y": 9, "w": 16, "h": 25},
    {"name": "检验科", "floor": "1F", "x": 5, "y": 55, "w": 20, "h": 28},
    {"name": "观察室", "floor": "1F", "x": 28, "y": 55, "w": 28, "h": 28},
    {"name": "介入室", "floor": "1F", "x": 59, "y": 55, "w": 17, "h": 28},
    {"name": "收费处", "floor": "1F", "x": 79, "y": 55, "w": 16, "h": 28},
    {"name": "EICU", "floor": "2F", "x": 5, "y": 9, "w": 43, "h": 32},
    {"name": "卒中单元", "floor": "2F", "x": 52, "y": 9, "w": 43, "h": 32},
    {"name": "超声1室", "floor": "2F", "x": 5, "y": 55, "w": 43, "h": 28},
    {"name": "ICU", "floor": "2F", "x": 52, "y": 55, "w": 43, "h": 28},
    {"name": "手术室", "floor": "3F", "x": 5, "y": 9, "w": 43, "h": 32},
    {"name": "走廊（越界）", "floor": "3F", "x": 52, "y": 9, "w": 43, "h": 32},
    {"name": "产科", "floor": "3F", "x": 5, "y": 55, "w": 43, "h": 28},
    {"name": "产科监护区", "floor": "3F", "x": 52, "y": 55, "w": 43, "h": 28},
    {"name": "儿科急诊", "floor": "4F", "x": 5, "y": 9, "w": 43, "h": 32},
    {"name": "NICU", "floor": "4F", "x": 52, "y": 9, "w": 43, "h": 32},
    {"name": "病房", "floor": "4F", "x": 5, "y": 55, "w": 90, "h": 28},
]


def _map_area(position: str, floor: str = "") -> dict[str, Any] | None:
    normalized = (position or "").replace("急诊", "").strip()
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
            for device in DEVICES:
                item = slim(device)
                area = _map_area(item.get("position") or "", item.get("floor") or "") or _map_area(item.get("position") or "")
                if not area or (area_filter and area["name"] != area_filter):
                    continue
                markers.append({
                    "name": item["name"], "identifier": item["number"], "position": area["name"],
                    "floor": area["floor"], "subjectType": "设备", "status": item["online"],
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
        device = get_device(keyword)
        if device:
            item = slim(device)
            area = _map_area(item.get("position") or "", item.get("floor") or "")
            if not area:
                area = _map_area(item.get("position") or "")
            if area:
                payload = {
                    "title": f"{item['name']} · 实时位置",
                    "subject": item["name"],
                    "subjectType": "设备",
                    "identifier": item["number"],
                    "position": item["position"],
                    "floor": area["floor"],
                    "status": item["online"],
                    "alarm": item["alarm"],
                    "areas": [a for a in MAP_AREAS if a["floor"] == area["floor"]],
                    "markers": [{"name": item["name"], "identifier": item["number"], "position": area["name"], "floor": area["floor"], "subjectType": "设备", "status": item["online"], "alarm": item["alarm"]}],
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


TOOLS = [
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


TOOL_LABELS = {
    "search_policy_knowledge": "国家政策知识库",
    "create_data_table": "表格生成",
    "create_chart": "图表生成",
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
}


def build_llm() -> ChatOpenAI:
    common = dict(temperature=0, timeout=40, max_tokens=800, streaming=True)
    if os.getenv("DEEPSEEK_API_KEY"):
        return ChatOpenAI(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
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


def build_agent():
    return create_react_agent(
        build_llm(),
        tools=TOOLS,
        checkpointer=MemorySaver(),
        prompt=SYSTEM_PROMPT,
    )


def ask(agent, question: str, thread_id: str = "demo") -> str:
    result = agent.invoke(
        {"messages": [("user", question)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].content


def ask_stream(agent, question: str, thread_id: str = "demo"):
    """产出 {type: status|token, text}，供网页边生成边显示。"""
    config = {"configurable": {"thread_id": thread_id}}
    seen_tools: set[str] = set()
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
                if name == "create_chart" and isinstance(content, str) and content.startswith("__CHART__"):
                    try:
                        chart = json.loads(content[len("__CHART__"):])
                        yield {"type": "chart", "chart": chart}
                    except json.JSONDecodeError:
                        yield {"type": "status", "text": "图表数据解析失败，已保留文字结果。"}
                if name == "show_location_map" and isinstance(content, str) and content.startswith("__MAP__"):
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
