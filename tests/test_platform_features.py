import json

import platform_features as features
from agent import SCENE_TOOLS, prepare_grounded_image


def test_supervisor_routes_domain_questions():
    assert features.route_supervisor_scene("主引风机振动频谱异常")["scene"] == "diagnostics"
    assert features.route_supervisor_scene("养老院老人离床告警")["scene"] == "eldercare"
    assert features.route_supervisor_scene("研发中心网关和物模型事件")["scene"] == "iot"


def test_supervisor_distinguishes_emergency_care_and_industrial_safety():
    medical_questions = (
        "急症患者现在在哪个区域", "查询急诊护士人员定位", "医院医护人员今天的考勤",
        "抢救室病人的停留时间", "绿通患者腕带轨迹",
    )
    safety_questions = (
        "工业园区人员安全态势", "受限空间员工轨迹", "查询厂区承包商考勤",
        "今天高危作业票是否合规", "生产车间人员越界告警",
    )
    assert all(features.route_supervisor_scene(question)["scene"] == "medical" for question in medical_questions)
    assert all(features.route_supervisor_scene(question)["scene"] == "safety" for question in safety_questions)


def test_supervisor_routes_known_entities_and_generic_business_requests():
    assert features.route_supervisor_scene("张三现在在哪")["scene"] == "medical"
    assert features.route_supervisor_scene("张伟现在在哪")["scene"] == "safety"
    assert features.route_supervisor_scene("查看所有人员热力图")["scene"] == "safety"
    assert features.route_supervisor_scene("查询当前未处理告警")["scene"] == "safety"
    continued = features.route_supervisor_scene("生成当前智能体报告", fallback_scene="building")
    assert continued["scene"] == "building"
    assert continued["reason"] == "conversation"


def test_supervisor_follow_up_uses_previous_scene():
    route = features.route_supervisor_scene("那他的轨迹和停留时间呢", fallback_scene="medical")
    assert route["scene"] == "medical"
    assert route["reason"] == "conversation"


def test_supervisor_rejects_unrelated_questions_even_with_previous_scene():
    for question in ("今天天气怎么样", "帮我分析股票", "写一段Python代码"):
        route = features.route_supervisor_scene(question, fallback_scene="medical")
        assert route["scene"] == ""
        assert route["reason"] == "unrelated"


def test_related_knowledge_and_ambiguous_questions_are_not_blocked():
    for question in ("系统里相关知识", "什么是RFID", "UWB和蓝牙定位有什么区别", "如何编程对接系统接口", "为什么会这样", "你好"):
        assert features.assess_scene_relevance(question, "safety")["relevant"]
        assert features.route_supervisor_scene(question)["scene"]
    assert features.is_command_meta_request("系统里有哪些相关知识")
    assert features.assess_scene_relevance("什么是医院急诊绿通", "safety")["relevant"]
    assert not features.assess_scene_relevance("查询急诊患者现在在哪里", "safety")["relevant"]


def test_prompt_allows_knowledge_but_requires_tools_for_business_facts():
    from agent import STRICT_SCOPE_INSTRUCTION
    assert "通用知识" in STRICT_SCOPE_INSTRUCTION
    assert "禁止跨场景读取或编造数据" in STRICT_SCOPE_INSTRUCTION


def test_scene_scope_guard_rejects_unrelated_and_cross_scene_questions():
    assert features.assess_scene_relevance("今天天气怎么样", "medical")["relevant"] is False
    assert features.assess_scene_relevance("急诊患者现在在哪里", "safety")["relevant"] is False
    assert features.assess_scene_relevance("工业园区受限空间人员告警", "medical")["relevant"] is False
    assert features.assess_scene_relevance("张伟现在在哪里", "safety")["relevant"] is True
    assert features.assess_scene_relevance("输液泵12号设备轨迹", "medical")["relevant"] is True
    assert features.assess_scene_relevance("那他的停留时间呢", "medical", has_context=True)["relevant"] is True


def test_image_generation_is_grounded_by_the_selected_scene_tools():
    result = prepare_grounded_image("safety", "画人员定位、资产定位和考勤原理图")
    assert result["scene"] == "safety"
    assert result["sources"] == ["query_locations_realtime", "query_asset_locations_realtime", "query_attendances"]
    assert "Business API snapshot" in result["prompt"]
    assert "安域 AI" in result["prompt"]


def test_trajectory_and_demo_director(tmp_path, monkeypatch):
    monkeypatch.setattr(features, "DEMO_PATH", tmp_path / "demo.json")
    payload = features.trajectory_payload("iot", "示波器01")
    assert len(payload["keyPoints"]) == 4
    assert len(payload["points"]) > len(payload["keyPoints"])
    assert len(payload["heatmap"]) == len(payload["points"])
    assert payload["layout"]["zones"]
    assert payload["summary"]["hottestArea"] == "实验室围栏外"
    state = features.set_demo_state("iot-fence", 1)
    assert state["active"] is True
    assert state["step"] == 1
    assert features.reset_demo_state()["active"] is False


def test_each_domain_agent_has_isolated_trajectory_renderer():
    for scene in ("medical", "safety", "building", "eldercare", "diagnostics", "iot"):
        tools = {item.name:item for item in SCENE_TOOLS[scene]}
        assert "render_trajectory_heatmap" in tools
        raw = tools["render_trajectory_heatmap"].invoke({"subject":"测试对象", "reason":"历史停留分布"})
        assert raw.startswith("__TRAJECTORY__")
        payload = json.loads(raw[len("__TRAJECTORY__"):])
        assert payload["scene"] == scene
        assert payload["subject"] == "测试对象"
        assert payload["decisionReason"] == "历史停留分布"


def test_all_elderly_heatmap_is_aggregated_instead_of_single_resident():
    tool = {item.name:item for item in SCENE_TOOLS["eldercare"]}["render_trajectory_heatmap"]
    raw = tool.invoke({"subject":"所有老人", "reason":"查看全体活动分布"})
    payload = json.loads(raw[len("__TRAJECTORY__"):])
    assert payload["mode"] == "group"
    assert payload["subjectCount"] == 5
    assert payload["subject"] == "全部老人（5人）"
    assert {track["name"] for track in payload["tracks"]} == {"李桂兰", "王建国", "陈淑芬", "赵德明", "周月琴"}
    assert len(payload["points"]) == sum(len(track["points"]) for track in payload["tracks"])


def test_group_heatmaps_are_available_in_every_domain_agent():
    cases = {
        "medical":"所有患者", "safety":"全部人员", "building":"所有楼宇人员",
        "eldercare":"所有养老设备", "diagnostics":"全部设备", "iot":"全部资产",
    }
    for scene, subject in cases.items():
        tool = {item.name:item for item in SCENE_TOOLS[scene]}["render_trajectory_heatmap"]
        raw = tool.invoke({"subject":subject, "reason":"群体活动分布"})
        payload = json.loads(raw[len("__TRAJECTORY__"):])
        assert payload["scene"] == scene
        assert payload["mode"] == "group"
        assert payload["subjectCount"] >= 4
        assert len(payload["tracks"]) == payload["subjectCount"]
        assert len({track["name"] for track in payload["tracks"]}) == payload["subjectCount"]


def test_mock_real_source_switch_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(features, "CONFIG_PATH", tmp_path / "configs.json")
    features.update_agent_config("iot", {"sourceMode":"real", "baseUrl":"https://example.invalid", "endpoints":{}})
    tool = {item.name:item for item in SCENE_TOOLS["iot"]}["query_iot_terminals"]
    missing = json.loads(tool.invoke({}))
    assert "尚未配置真实接口映射" in missing["error"]
    features.update_agent_config("iot", {"sourceMode":"mock"})
    assert json.loads(tool.invoke({}))["count"] >= 30


def test_one_click_report_generates_printable_html(tmp_path, monkeypatch):
    monkeypatch.setattr(features, "REPORT_DIR", tmp_path)
    path = features.generate_report("iot", "测试报告", [{"title":"概览","data":{"terminals":36}}])
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "测试报告" in text
    assert "保存为 PDF" in text
    assert "<pre>" not in text
    assert "class='metric'" in text
