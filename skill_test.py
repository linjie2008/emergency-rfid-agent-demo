"""Skill 测试运行器：工具单测不调大模型；e2e 才走对话。"""

from __future__ import annotations

import json
import time
from typing import Any

from skills import SKILL_CATALOG, TOOL_BY_NAME

TOOL_CASES: list[dict[str, Any]] = [
    {
        "id": "search_policy_knowledge.asset",
        "skill_id": "search_policy_knowledge",
        "title": "检索医学装备维护与台账国家文件",
        "args": {"query": "医学装备 维护 台账", "category": "asset", "limit": 3},
        "contains": ["医学装备", "维护", "source_url", "官方原文"],
        "json_subset": {"category": "asset"},
    },
    {
        "id": "show_location_map.patient",
        "skill_id": "show_location_map",
        "title": "在平面图显示张三位于介入室",
        "args": {"keyword": "张三", "subject_type": "patient"},
        "contains": ["__MAP__", "张三", "介入室", "1F"],
        "json_subset": None,
    },
    {
        "id": "show_location_map.asset",
        "skill_id": "show_location_map",
        "title": "在平面图显示输液泵12号",
        "args": {"keyword": "输液泵12号", "subject_type": "asset"},
        "contains": ["__MAP__", "输液泵12号", "抢救室", "YP-012"],
        "json_subset": None,
    },
    {
        "id": "show_location_map.all_patients",
        "skill_id": "show_location_map",
        "title": "在平面图聚合显示所有患者",
        "args": {"keyword": "所有患者", "subject_type": "patient"},
        "contains": ["__MAP__", "markers", "今日患者实时分布", "张三", "李四", "王五"],
        "json_subset": None,
    },
    {
        "id": "show_location_map.area_patients",
        "skill_id": "show_location_map",
        "title": "在平面图显示抢救室患者",
        "args": {"keyword": "抢救室所有患者", "subject_type": "patient"},
        "contains": ["__MAP__", "抢救室患者实时分布", "王五"],
        "json_subset": None,
    },
    {
        "id": "show_location_map.all_assets",
        "skill_id": "show_location_map",
        "title": "在多楼层平面图聚合显示所有设备",
        "args": {"keyword": "所有设备", "subject_type": "asset"},
        "contains": ["__MAP__", "院内设备实时分布", "输液泵12号", "呼吸机3号", "markers"],
        "json_subset": None,
    },
    {
        "id": "list_patients.five",
        "skill_id": "list_patients",
        "title": "能列出核心样例患者",
        "args": {},
        "contains": ["张三", "李四", "王五", "MZ20260608001"],
        "json_subset": None,
    },
    {
        "id": "get_inout_records.zhangsan",
        "skill_id": "get_inout_records",
        "title": "按姓名查出张三进出记录",
        "args": {"hospital_no": "张三"},
        "contains": ["E200001234560001", "抢救室", "介入室"],
        "json_subset": {"code": 200},
    },
    {
        "id": "get_inout_records.epc",
        "skill_id": "get_inout_records",
        "title": "按腕带 EPC 查询",
        "args": {"epc": "E200001234560001"},
        "contains": ["张三", "MZ20260608001"],
        "json_subset": None,
    },
    {
        "id": "get_inout_records.empty",
        "skill_id": "get_inout_records",
        "title": "不传门诊号和 EPC 应返回空数组",
        "args": {},
        "contains": [],
        "json_subset": {"count": 0},
    },
    {
        "id": "analyze_patient_journey.zhangsan",
        "skill_id": "analyze_patient_journey",
        "title": "张三当前在介入室",
        "args": {"hospital_no": "张三"},
        "contains": ["介入室"],
        "json_subset": {"ok": True, "hospitalNo": "MZ20260608001", "currentLocation": "介入室"},
    },
    {
        "id": "analyze_patient_journey.chenqi",
        "skill_id": "analyze_patient_journey",
        "title": "陈七已离开",
        "args": {"hospital_no": "陈七"},
        "contains": ["已离开"],
        "json_subset": {"ok": True, "currentLocation": "已离开"},
    },
    {
        "id": "find_timeout_patients.wangwu",
        "skill_id": "find_timeout_patients",
        "title": "王五抢救室超时",
        "args": {"threshold_minutes": 120},
        "contains": ["王五", "抢救室"],
        "json_subset": None,
    },
    {
        "id": "summarize_area_stay.rescue",
        "skill_id": "summarize_area_stay",
        "title": "统计结果含抢救室",
        "args": {},
        "contains": ["抢救室", "分诊台"],
        "json_subset": None,
    },
    {
        "id": "list_patients_in_area.rescue",
        "skill_id": "list_patients_in_area",
        "title": "抢救室在场含王五",
        "args": {"area_name": "抢救室"},
        "contains": ["王五", "抢救室"],
        "json_subset": None,
    },
    {
        "id": "list_patients_by_channel.chest",
        "skill_id": "list_patients_by_channel",
        "title": "胸痛绿通含张三",
        "args": {"channel": "胸痛绿通"},
        "contains": ["张三", "胸痛绿通"],
        "json_subset": None,
    },
    {
        "id": "summarize_channels.types",
        "skill_id": "summarize_channels",
        "title": "通道汇总含胸痛和卒中",
        "args": {},
        "contains": ["胸痛绿通", "卒中绿通", "创伤绿通"],
        "json_subset": None,
    },
    {
        "id": "list_assets.pump",
        "skill_id": "list_assets",
        "title": "能查到输液泵",
        "args": {"keyword": "输液泵"},
        "contains": ["输液泵12号", "YP-012"],
        "json_subset": None,
    },
    {
        "id": "locate_asset.pump",
        "skill_id": "locate_asset",
        "title": "输液泵12号在抢救室",
        "args": {"keyword": "输液泵12号"},
        "contains": ["抢救室", "YP-012"],
        "json_subset": {"ok": True},
    },
    {
        "id": "list_asset_alarms.any",
        "skill_id": "list_asset_alarms",
        "title": "报警名单含离线或越界",
        "args": {},
        "contains": ["离线"],
        "json_subset": None,
    },
    {
        "id": "analyze_energy.ob",
        "skill_id": "analyze_energy",
        "title": "能效分析含妇产科一体机",
        "args": {},
        "contains": ["妇产科心电监测一体机", "useRate"],
        "json_subset": None,
    },
    {
        "id": "get_asset_power.y04",
        "skill_id": "get_asset_power",
        "title": "Y04 有耗电数据",
        "args": {"keyword": "Y04"},
        "contains": ["electricQuantity"],
        "json_subset": {"ok": True},
    },
    {
        "id": "get_asset_track.pump",
        "skill_id": "get_asset_track",
        "title": "输液泵12号轨迹含CT室",
        "args": {"keyword": "输液泵12号"},
        "contains": ["CT室", "抢救"],
        "json_subset": {"ok": True},
    },
]

E2E_CASES: list[dict[str, Any]] = [
    {
        "id": "e2e.zhangsan_where",
        "skill_id": "e2e_chat",
        "title": "问张三在哪，应提到介入室和门诊号",
        "question": "张三现在在哪个区域？",
        "expect_tools": ["analyze_patient_journey", "get_inout_records", "list_patients"],
        "contains": ["介入室", "MZ20260608001"],
    },
    {
        "id": "e2e.timeout",
        "skill_id": "e2e_chat",
        "title": "问抢救室超时，应提到王五",
        "question": "今天谁在抢救室待太久了？",
        "expect_tools": ["find_timeout_patients", "analyze_patient_journey"],
        "contains": ["王五", "抢救室"],
    },
]


def _as_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


def _subset_ok(actual: Any, expected: Any) -> bool:
    if expected is None:
        return True
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(k in actual and _subset_ok(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        return all(any(_subset_ok(item, exp) for item in actual) for exp in expected)
    return actual == expected


def _invoke_tool(skill_id: str, args: dict[str, Any]) -> str:
    tool = TOOL_BY_NAME[skill_id]
    return tool.invoke(args or {})


def _collect_tool_names(messages: list[Any]) -> list[str]:
    names: list[str] = []
    for msg in messages:
        for call in getattr(msg, "tool_calls", None) or []:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name:
                names.append(name)
        name = getattr(msg, "name", None)
        if getattr(msg, "type", None) == "tool" and name:
            names.append(name)
    # 保序去重
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def run_tool_case(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    errors: list[str] = []
    output = ""
    try:
        output = _invoke_tool(case["skill_id"], case.get("args") or {})
    except Exception as exc:
        errors.append(f"调用失败: {exc}")

    for token in case.get("contains") or []:
        if token not in output:
            errors.append(f"缺少文本: {token}")

    parsed = _as_json(output)
    expected_subset = case.get("json_subset")
    if expected_subset is not None:
        if parsed is None:
            errors.append("返回不是合法 JSON")
        elif not _subset_ok(parsed, expected_subset):
            errors.append(f"JSON 不含 {json.dumps(expected_subset, ensure_ascii=False)}")

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "id": case["id"],
        "skill_id": case["skill_id"],
        "title": case["title"],
        "kind": "tool",
        "ok": not errors,
        "elapsed_ms": elapsed_ms,
        "errors": errors,
        "output": output[:4000],
        "tools": [case["skill_id"]] if not errors else [],
    }


def run_e2e_case(case: dict[str, Any], agent) -> dict[str, Any]:
    started = time.perf_counter()
    errors: list[str] = []
    output = ""
    tools: list[str] = []
    try:
        thread_id = f"skill-test-{case['id']}"
        result = agent.invoke(
            {"messages": [("user", case["question"])]},
            config={"configurable": {"thread_id": thread_id}},
        )
        messages = result.get("messages") or []
        output = messages[-1].content if messages else ""
        tools = _collect_tool_names(messages)
    except Exception as exc:
        errors.append(f"对话失败: {exc}")

    expect_tools = case.get("expect_tools") or []
    if expect_tools and tools and not any(t in tools for t in expect_tools):
        errors.append(f"未调用预期 Skill，实际: {tools or '无'}")
    if expect_tools and not tools:
        errors.append("没有调用任何 Skill")

    for token in case.get("contains") or []:
        if token not in (output or ""):
            errors.append(f"回答缺少: {token}")

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "id": case["id"],
        "skill_id": case["skill_id"],
        "title": case["title"],
        "kind": "e2e",
        "ok": not errors,
        "elapsed_ms": elapsed_ms,
        "errors": errors,
        "output": (output or "")[:4000],
        "tools": tools,
        "question": case.get("question"),
    }


def run_skill_tests(
    skill_id: str | None = None,
    include_e2e: bool = False,
    agent=None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    tool_cases = TOOL_CASES
    e2e_cases = E2E_CASES
    if skill_id and skill_id != "all":
        tool_cases = [c for c in TOOL_CASES if c["skill_id"] == skill_id]
        e2e_cases = [c for c in E2E_CASES if c["skill_id"] == skill_id]
        if skill_id != "e2e_chat":
            e2e_cases = []
        if skill_id == "e2e_chat":
            tool_cases = []
            include_e2e = True

    for case in tool_cases:
        results.append(run_tool_case(case))

    if include_e2e:
        if agent is None:
            from agent import build_agent

            agent = build_agent()
        for case in e2e_cases:
            results.append(run_e2e_case(case, agent))

    passed = sum(1 for r in results if r["ok"])
    failed = len(results) - passed
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
        "catalog": SKILL_CATALOG,
    }


def format_report(report: dict[str, Any]) -> str:
    lines = [
        f"Skill 测试  {report['passed']}/{report['total']} 通过"
        + (f"，失败 {report['failed']}" if report["failed"] else ""),
        "",
    ]
    for row in report["results"]:
        flag = "PASS" if row["ok"] else "FAIL"
        lines.append(f"[{flag}] {row['skill_id']} · {row['title']}  ({row['elapsed_ms']} ms)")
        if row.get("tools"):
            lines.append(f"      调用: {', '.join(row['tools'])}")
        for err in row.get("errors") or []:
            lines.append(f"      - {err}")
        if not row["ok"] and row.get("output"):
            preview = row["output"].replace("\n", " ")[:180]
            lines.append(f"      输出: {preview}")
    return "\n".join(lines)


def results_table(report: dict[str, Any]) -> list[list[str]]:
    table = []
    for row in report["results"]:
        table.append(
            [
                "通过" if row["ok"] else "失败",
                row["skill_id"],
                row["title"],
                str(row["elapsed_ms"]),
                ", ".join(row.get("tools") or []) or "-",
                "；".join(row.get("errors") or []) or "OK",
            ]
        )
    return table
