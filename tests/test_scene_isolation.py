import json
from pathlib import Path

from fastapi import HTTPException

from agent import SCENE_TOOLS, route_local_tools
from building_tools import query_building_alarms, summarize_building_operations
from rfid_data import PATIENTS
from server import TestIn, ToolCallIn, app, call_scene_tool, skill_tests


SHARED_CONTRACTS = {
    "create_data_table", "create_chart", "render_trajectory_heatmap",
    "format_concise_reply", "format_executive_brief", "format_alarm_disposal_card",
    "format_positioning_report", "format_shift_handover",
    "query_locations_realtime", "query_locations_history", "query_region_enter_leave",
    "query_asset_locations_realtime", "query_asset_locations_history", "query_asset_region_enter_leave",
}


def _names(scene):
    return {tool.name for tool in SCENE_TOOLS[scene]}


def test_business_tool_sets_are_isolated_between_original_scenes():
    assert _names("medical") & _names("safety") == SHARED_CONTRACTS
    assert _names("medical") & _names("building") == SHARED_CONTRACTS
    assert _names("safety") & _names("building") == SHARED_CONTRACTS
    for name in SHARED_CONTRACTS - {
        "create_data_table", "create_chart", "render_trajectory_heatmap", "format_concise_reply", "format_executive_brief",
        "format_alarm_disposal_card", "format_positioning_report", "format_shift_handover",
    }:
        tools = [{item.name: item for item in SCENE_TOOLS[scene]}[name] for scene in ("medical", "safety", "building")]
        assert len({id(item) for item in tools}) == 3


def test_new_domain_tool_sets_are_independent():
    shared_renderers = {
        "create_data_table", "create_chart", "render_trajectory_heatmap", "generate_schematic_image",
        "format_concise_reply", "format_executive_brief", "format_alarm_disposal_card",
        "format_positioning_report", "format_shift_handover",
    }
    new_scenes = ("eldercare", "diagnostics", "iot")
    for index, scene in enumerate(new_scenes):
        for other in new_scenes[index + 1:]:
            assert _names(scene) & _names(other) == shared_renderers

    assert "query_elderly_locations" in _names("eldercare")
    assert "query_realtime_device_metrics" in _names("diagnostics")
    assert "query_iot_terminals" in _names("iot")
    assert "query_iot_terminals" not in _names("eldercare") | _names("diagnostics")


def test_iot_demo_dataset_is_large_enough_for_sales_demo():
    tools = {item.name: item for item in SCENE_TOOLS["iot"]}
    overview = json.loads(tools["summarize_iot_operations"].invoke({}))
    people = json.loads(tools["query_iot_people_locations"].invoke({"keyword": "所有"}))
    assets = json.loads(tools["query_iot_asset_locations"].invoke({"keyword": "所有"}))
    events = json.loads(tools["query_iot_events"].invoke({}))
    assert overview["buildings"] >= 6
    assert overview["terminals"] >= 30
    assert overview["beacons"] >= 15
    assert overview["geofences"] >= 10
    assert people["count"] >= 8
    assert assets["count"] >= 10
    assert events["count"] >= 15


def test_local_router_only_returns_tools_from_selected_scene():
    cases = {
        "medical": "今天抢救室有哪些患者",
        "safety": "查询王强今天的考勤和门禁",
        "building": "9楼消防和空调有哪些告警",
        "eldercare": "查询李桂兰的位置和健康手表状态",
        "diagnostics": "分析主引风机的振动和故障告警",
        "iot": "查询研发中心定位终端和围栏事件",
    }
    for scene, question in cases.items():
        routed, _ = route_local_tools(question, scene=scene)
        assert set(routed) <= _names(scene)
        assert not any(name.startswith("format_") for name in routed)


def test_medical_scene_keeps_medical_patient_data():
    names = {row["name"] for row in PATIENTS.values()}
    assert {"张三", "李四", "王五"} <= names
    assert not any("生产批次" in name for name in names)


def test_building_scene_has_independent_operational_data():
    overview = json.loads(summarize_building_operations.invoke({}))
    alarms = json.loads(query_building_alarms.invoke({"handled": "false"}))
    assert overview["systems"] == 19
    assert overview["building"] == "总部大楼"
    assert alarms["count"] >= 1
    assert all(row["alarmId"].startswith("BLD-") for row in alarms["data"])


def test_three_scenes_have_distinct_person_and_asset_location_data():
    expected = {
        "medical": ("林医生", "输液泵12号", "输液泵12号"),
        "safety": ("张伟", "便携式气体检测仪01", "便携式气体检测仪01"),
        "building": ("何磊", "AHU-01", "1F空调机组"),
    }
    for scene, (person, asset_query, asset_name) in expected.items():
        tools = {item.name: item for item in SCENE_TOOLS[scene]}
        people = json.loads(tools["query_locations_realtime"].invoke({"keyword": person}))
        assets = json.loads(tools["query_asset_locations_realtime"].invoke({"keyword": asset_query}))
        assert people["count"] == 1
        assert assets["count"] == 1
        assert people["data"][0]["person"] == person
        assert assets["data"][0]["asset"] == asset_name


def test_scene_scoped_api_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/scenes" in paths
    assert "/api/scenes/{scene}/tools" in paths
    assert "/api/scenes/{scene}/tools/{tool_name}" in paths
    assert "/api/scenes/building/overview" in paths
    assert "/api/scenes/building/alarms" in paths
    assert "/api/scenes/{scene}/positioning/persons/realtime" in paths
    assert "/api/scenes/{scene}/positioning/assets/history" in paths
    assert "/api/admin/agent-configs/{scene}" in paths
    assert "/api/demo/start" in paths
    assert "/api/visualizations/{scene}/trajectory" in paths
    assert "/api/reports/generate" in paths
    assert "/api/router" in paths
    assert "/api/interface-guides" in paths


def test_cross_scene_tool_call_is_rejected():
    try:
        call_scene_tool("medical", "summarize_building_operations", ToolCallIn())
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("楼宇工具不应能通过医疗场景调用")


def test_frontend_sends_scene_and_has_platform_feature_entries():
    html = (Path(__file__).parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert "scene-medical" in html
    assert "scene-safety" in html
    assert "scene-building" in html
    assert "scene-eldercare" in html
    assert "scene-diagnostics" in html
    assert "scene-iot" in html
    assert "scene-command" in html
    assert 'id="tab-config"' in html
    assert 'id="tab-demo"' in html
    assert 'id="tab-trajectory"' not in html
    assert 'id="tab-report"' not in html
    assert "renderTrajectories" in html
    assert "renderReports" in html
    assert 'ev.type === "trajectory"' in html
    assert 'ev.type === "report"' in html
    assert "scene: currentScene" in html
    assert 'id="responseFormat"' in html
    assert "response_format:" in html
    assert "agent-welcome-label" in html
    assert "智能体介绍" in html
    assert "config.abilities.map" in html
    assert "从左侧打开当前智能体的历史记录" not in html
    assert "人员与患者定位" in html
    assert "作业票合规" in html
    assert "安防与消防" in html
    assert "老人实时定位" in html
    assert "波形频谱" in html
    assert "物模型与控制" in html
    assert 'id="telegramStatus"' in html
    assert "/api/integrations/telegram/status" in html
    assert 'id="interfaceGuideDialog"' in html
    assert "openInterfaceGuide()" in html
    assert 'id="interfaceGuideShell"' not in html
    assert "grounding_sources" in html
    assert "chat.scene || \"safety\"" in html
    assert "loadSceneSkills()" in html
    assert "document.getElementById(\"tab-test\").hidden = false" in html


def test_non_safety_scene_skill_smoke_tests_are_available():
    for scene in ("medical", "building", "eldercare", "diagnostics", "iot"):
        report = skill_tests(TestIn(scene=scene))
        assert report["total"] == len(SCENE_TOOLS[scene])
        assert report["failed"] == 0
