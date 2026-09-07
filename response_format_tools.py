"""三个业务场景共用的无状态回复格式 Skill。"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

_SENSITIVE_KEYS = {
    "epc", "wristbandEpc", "relatedEpc", "rfid", "tag", "标签号",
    "x", "y", "longitude", "latitude", "password", "token", "apiKey",
}


def _text(value: Any) -> str:
    return str(value or "").strip().replace("\x00", "")


def _items(raw: str) -> list[Any]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        value = []
    if isinstance(value, dict):
        return [{"项目": key, "内容": item} for key, item in value.items()]
    return value[:30] if isinstance(value, list) else []


def _bullet_lines(items: list[Any], numbered: bool = False) -> list[str]:
    lines = []
    for index, item in enumerate(items, 1):
        prefix = f"{index}." if numbered else "-"
        if isinstance(item, dict):
            label = _text(item.get("label") or item.get("name") or item.get("项目") or item.get("action") or item.get("事项"))
            value = _text(item.get("value") or item.get("内容") or item.get("status") or item.get("说明") or item.get("owner"))
            content = f"**{label}**：{value}" if label and value else label or value or _text(item)
        else:
            content = _text(item)
        if content:
            lines.append(f"{prefix} {content}")
    return lines


def _table(rows: list[Any]) -> list[str]:
    records = [row for row in rows if isinstance(row, dict)]
    if not records:
        return _bullet_lines(rows)
    columns: list[str] = []
    for row in records:
        for key in row:
            if key not in columns and str(key) not in _SENSITIVE_KEYS:
                columns.append(str(key))
        if len(columns) >= 8:
            break
    columns = columns[:8]

    def cell(value: Any) -> str:
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        return _text(value).replace("|", "\\|").replace("\n", " ")

    return [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
        *("| " + " | ".join(cell(row.get(column, "")) for column in columns) + " |" for row in records),
    ]


def _section(lines: list[str], title: str, body: list[str]) -> None:
    if body:
        lines.extend(["", f"### {title}", "", *body])


@tool
def format_concise_reply(conclusion: str = "", facts_json: str = "[]", source: str = "") -> str:
    """生成简洁回复。完成业务查询后传入一句结论、关键事实 JSON 数组和真实数据来源；不得补造事实。"""
    lines = [_text(conclusion) or "暂无可确认的结论。"]
    _section(lines, "关键事实", _bullet_lines(_items(facts_json)))
    if _text(source):
        lines.extend(["", f"数据来源：{_text(source)}"])
    return "\n".join(lines)


@tool
def format_executive_brief(
    title: str = "运营摘要",
    conclusion: str = "",
    kpis_json: str = "[]",
    risks_json: str = "[]",
    actions_json: str = "[]",
    source: str = "",
) -> str:
    """生成供领导浏览的运营摘要。查询后传入结论、指标、风险和行动 JSON；突出决策信息，不得新增数据。"""
    lines = [f"## {_text(title) or '运营摘要'}", "", f"**结论：** {_text(conclusion) or '暂无可确认的结论。'}"]
    _section(lines, "关键指标", _table(_items(kpis_json)))
    _section(lines, "风险关注", _bullet_lines(_items(risks_json)))
    _section(lines, "建议行动", _bullet_lines(_items(actions_json), numbered=True))
    if _text(source):
        lines.extend(["", f"数据来源：{_text(source)}"])
    return "\n".join(lines)


@tool
def format_alarm_disposal_card(
    alarm: str = "",
    level: str = "",
    location: str = "",
    occurred_at: str = "",
    status: str = "",
    evidence_json: str = "[]",
    actions_json: str = "[]",
    owner: str = "",
    disclaimer: str = "",
) -> str:
    """生成告警处置卡。查询后传入告警、等级、地点、时间、状态、证据和处置动作；建议与已执行动作必须区分。"""
    lines = ["## 告警处置卡", "", f"**{_text(alarm) or '未命名告警'}**"]
    overview = [
        {"项目": "等级", "内容": level}, {"项目": "位置", "内容": location},
        {"项目": "发生时间", "内容": occurred_at}, {"项目": "状态", "内容": status},
        {"项目": "责任人", "内容": owner},
    ]
    _section(lines, "告警概况", _table([row for row in overview if _text(row["内容"])]))
    _section(lines, "数据证据", _bullet_lines(_items(evidence_json)))
    _section(lines, "处置步骤", _bullet_lines(_items(actions_json), numbered=True))
    if _text(disclaimer):
        lines.extend(["", f"> {_text(disclaimer)}"])
    return "\n".join(lines)


@tool
def format_positioning_report(
    subject: str = "",
    subject_type: str = "人员/资产",
    current_location: str = "",
    current_status: str = "",
    last_seen: str = "",
    timeline_json: str = "[]",
    anomalies_json: str = "[]",
    source: str = "",
) -> str:
    """生成人员或资产定位报告。查询后传入对象、当前位置、状态、最后上报时间、轨迹和异常；禁止传入原始坐标或标签号。"""
    lines = [f"## {_text(subject_type) or '对象'}定位报告", "", f"**对象：** {_text(subject) or '未指定'}"]
    overview = [
        {"项目": "当前位置", "内容": current_location},
        {"项目": "当前状态", "内容": current_status},
        {"项目": "最后上报", "内容": last_seen},
    ]
    _section(lines, "实时状态", _table([row for row in overview if _text(row["内容"])]))
    _section(lines, "轨迹与停留", _table(_items(timeline_json)))
    _section(lines, "异常关注", _bullet_lines(_items(anomalies_json)))
    if _text(source):
        lines.extend(["", f"数据来源：{_text(source)}"])
    return "\n".join(lines)


@tool
def format_shift_handover(
    shift: str = "本班次",
    summary: str = "",
    alarms_json: str = "[]",
    pending_json: str = "[]",
    followups_json: str = "[]",
    source: str = "",
) -> str:
    """生成值班交接班记录。查询后传入班次概况、告警、未结事项和下一班跟进项；不得把建议写成已完成。"""
    lines = [f"## {_text(shift) or '本班次'}交接班记录", "", f"**运行概况：** {_text(summary) or '暂无可确认的运行概况。'}"]
    _section(lines, "本班告警", _table(_items(alarms_json)))
    _section(lines, "未结事项", _table(_items(pending_json)))
    _section(lines, "下一班跟进", _bullet_lines(_items(followups_json), numbered=True))
    if _text(source):
        lines.extend(["", f"数据来源：{_text(source)}"])
    return "\n".join(lines)


RESPONSE_FORMAT_TOOLS = [
    format_concise_reply,
    format_executive_brief,
    format_alarm_disposal_card,
    format_positioning_report,
    format_shift_handover,
]
RESPONSE_FORMAT_TOOL_NAMES = {item.name for item in RESPONSE_FORMAT_TOOLS}

RESPONSE_FORMATS = {
    "auto": {"label": "自动格式", "tool": ""},
    "concise": {"label": "简洁答复", "tool": "format_concise_reply"},
    "executive": {"label": "领导摘要", "tool": "format_executive_brief"},
    "alarm": {"label": "告警处置单", "tool": "format_alarm_disposal_card"},
    "positioning": {"label": "定位分析报告", "tool": "format_positioning_report"},
    "handover": {"label": "交接班记录", "tool": "format_shift_handover"},
}


def normalize_response_format(value: str) -> str:
    value = (value or "auto").lower().strip()
    return value if value in RESPONSE_FORMATS else "auto"


def response_format_system_instruction(value: str) -> str:
    value = normalize_response_format(value)
    config = RESPONSE_FORMATS[value]
    if not config["tool"]:
        return ""
    return (
        f"\n\n本轮回复格式固定为“{config['label']}”。完成必要的业务数据查询后，必须调用 "
        f"{config['tool']}；格式 Skill 的参数只能来自本轮工具结果和用户原话。"
        "将格式 Skill 返回的 Markdown 原样作为最终回答，不得补充未经查询的数据。"
    )
