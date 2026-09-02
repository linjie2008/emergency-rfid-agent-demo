"""把智能体能力收成可测试的 Skill。"""

from __future__ import annotations

from typing import Any, Callable

from agent import TOOLS

SKILL_CATALOG: list[dict[str, Any]] = [
    {
        "id": "search_policy_knowledge",
        "name": "国家政策知识库",
        "kind": "tool",
        "description": "检索医疗急诊与医疗资产管理国家文件、要点及官方原文。",
    },
    {
        "id": "show_location_map",
        "name": "院内位置图",
        "kind": "tool",
        "description": "把患者或设备当前位置显示在院内楼层平面图上。",
    },
    {
        "id": "list_patients",
        "name": "患者名录",
        "kind": "tool",
        "description": "列出绿通患者姓名、门诊号、腕带 EPC、通道、当前区域。",
    },
    {
        "id": "list_patients_in_area",
        "name": "区域在场",
        "kind": "tool",
        "description": "按当前区域列出患者，如抢救室、CT室、介入室。",
    },
    {
        "id": "list_patients_by_channel",
        "name": "通道名录",
        "kind": "tool",
        "description": "按胸痛/卒中/创伤等绿通类型列出患者。",
    },
    {
        "id": "summarize_channels",
        "name": "通道汇总",
        "kind": "tool",
        "description": "按绿通类型汇总人数和所在区域分布。",
    },
    {
        "id": "get_inout_records",
        "name": "进出记录查询",
        "kind": "tool",
        "description": "对应 getInOutMergeList，按门诊号/姓名/EPC 查 RFID 流转。",
    },
    {
        "id": "analyze_patient_journey",
        "name": "轨迹分析",
        "kind": "tool",
        "description": "根据进出记录计算当前区域、停留分钟、时间线。",
    },
    {
        "id": "find_timeout_patients",
        "name": "超时预警",
        "kind": "tool",
        "description": "查找仍在抢救室且停留超过阈值的患者。",
    },
    {
        "id": "summarize_area_stay",
        "name": "区域停留统计",
        "kind": "tool",
        "description": "各区域平均/最长停留，用于找瓶颈。",
    },
    {
        "id": "list_assets",
        "name": "设备列表",
        "kind": "tool",
        "description": "按名称/科室/报警查询资产设备，对应 GET /goods。",
    },
    {
        "id": "locate_asset",
        "name": "设备定位",
        "kind": "tool",
        "description": "查一台设备当前科室和位置。",
    },
    {
        "id": "list_asset_alarms",
        "name": "设备报警",
        "kind": "tool",
        "description": "越界、离线、低电量、防拆设备。",
    },
    {
        "id": "analyze_energy",
        "name": "能效分析",
        "kind": "tool",
        "description": "使用率、运行/待机/关机，对应 getEnergyEfficiencyPage。",
    },
    {
        "id": "get_asset_power",
        "name": "耗电统计",
        "kind": "tool",
        "description": "单设备近日耗电，对应 electricQuantity/list。",
    },
    {
        "id": "get_asset_track",
        "name": "设备轨迹",
        "kind": "tool",
        "description": "设备停留段和离开存放位置记录，对应 userPaths、move/record。",
    },
    {
        "id": "e2e_chat",
        "name": "对话端到端",
        "kind": "e2e",
        "description": "真实问一句，检查是否调用正确 Skill，回答是否含关键数字。",
    },
]

TOOL_BY_NAME: dict[str, Callable[..., str]] = {t.name: t for t in TOOLS}


def skill_choices(include_e2e: bool = True) -> list[str]:
    rows = SKILL_CATALOG if include_e2e else [s for s in SKILL_CATALOG if s["kind"] != "e2e"]
    return [f"{s['id']}  ·  {s['name']}" for s in rows]


def parse_skill_choice(choice: str) -> str:
    return (choice or "").split("·", 1)[0].strip()
