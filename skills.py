"""工业园区智能体 Skill 目录。"""
from __future__ import annotations
from typing import Any, Callable
from agent import TOOLS

GROUPS = {
    "回复格式": ["format_concise_reply", "format_executive_brief", "format_alarm_disposal_card", "format_positioning_report", "format_shift_handover"],
    "人员组织": ["query_employees", "query_contractor_staff", "query_contractors", "query_departments", "query_visitors", "summarize_employees"],
    "定位轨迹": ["query_locations_realtime", "query_locations_history", "query_region_enter_leave", "query_region_enter_leave_summary", "query_online_persons"],
    "资产定位": ["query_asset_locations_realtime", "query_asset_locations_history", "query_asset_region_enter_leave"],
    "作业票": ["list_work_tickets", "summarize_work_tickets", "list_work_ticket_compliance", "summarize_work_ticket_compliance", "trend_work_ticket_compliance", "group_work_ticket_compliance", "rank_work_ticket_compliance_rules", "get_work_ticket_compliance_detail", "get_work_ticket_process_analysis"],
    "报警": ["summarize_alarms", "analyze_alarms"],
    "设备硬件": ["query_devices", "summarize_devices", "query_card_bind_records"],
    "考勤排班": ["query_attendances", "query_schedules"], "门禁": ["query_access_records"],
    "承包商工时": ["query_work_ticket_workhour_person", "query_work_ticket_workhour_contractor"],
    "驻留强度": ["query_loitering_sessions", "query_abnormal_dwell_summary", "query_trajectory_distance", "query_work_intensity_summary", "query_workload_analysis"],
    "质检": ["query_inspection_list"], "辅助渲染": ["render_personnel_tree", "render_personnel_timeline", "show_factory_3d_map"],
    "能源生产": ["query_generation_units", "query_power_generation_realtime", "summarize_grid_load"],
    "输变配电": ["query_substations", "query_line_operations", "query_outage_events"],
    "供热燃气": ["query_heat_supply", "query_heat_network_alarms", "query_gas_supply"],
    "能源调度": ["query_dispatch_commands", "query_energy_consumption", "query_energy_safety_risks", "summarize_energy_kpis"],
    "预测性维护": ["query_predictive_monitoring_terminals", "summarize_predictive_monitoring_terminals", "query_equipment_health", "query_condition_monitoring", "predict_equipment_failures", "query_remaining_useful_life", "recommend_predictive_maintenance", "summarize_predictive_maintenance"],
}
TOOL_BY_NAME: dict[str, Callable[..., str]] = {tool.name: tool for tool in TOOLS}
SKILL_CATALOG: list[dict[str, Any]] = [
    {"id": name, "name": name, "kind": "tool", "group": group, "description": TOOL_BY_NAME[name].description}
    for group, names in GROUPS.items() for name in names if name in TOOL_BY_NAME
]
SKILL_CATALOG += [
    {"id": "create_data_table", "name": "表格生成", "kind": "tool", "group": "辅助渲染", "description": "将查询结果渲染为表格。"},
    {"id": "create_chart", "name": "图表生成", "kind": "tool", "group": "辅助渲染", "description": "将统计结果渲染为图表。"},
    {"id": "e2e_chat", "name": "对话端到端", "kind": "e2e", "group": "测试", "description": "检查工具选择与回答。"},
]

def skill_choices(include_e2e: bool = True) -> list[str]:
    rows = SKILL_CATALOG if include_e2e else [x for x in SKILL_CATALOG if x["kind"] != "e2e"]
    return [f"{x['id']}  ·  {x['name']}" for x in rows]

def parse_skill_choice(choice: str) -> str:
    return (choice or "").split("·", 1)[0].strip()
