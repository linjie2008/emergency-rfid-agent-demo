from response_format_tools import (
    RESPONSE_FORMAT_TOOL_NAMES,
    format_alarm_disposal_card,
    format_concise_reply,
    format_executive_brief,
    format_positioning_report,
    format_shift_handover,
    normalize_response_format,
    response_format_system_instruction,
)
from types import SimpleNamespace

from agent import _select_agent_tools, ask_stream, route_local_tools


def test_five_response_format_skills_are_registered():
    assert RESPONSE_FORMAT_TOOL_NAMES == {
        "format_concise_reply",
        "format_executive_brief",
        "format_alarm_disposal_card",
        "format_positioning_report",
        "format_shift_handover",
    }


def test_response_formats_render_markdown_from_supplied_data():
    concise = format_concise_reply.invoke({"conclusion": "在线 6 人", "facts_json": '[{"name":"承包商","value":"2人"}]'})
    executive = format_executive_brief.invoke({"conclusion": "总体平稳", "kpis_json": '[{"指标":"在线率","值":"98%"}]'})
    alarm = format_alarm_disposal_card.invoke({"alarm": "越界告警", "actions_json": '["通知监护人"]'})
    positioning = format_positioning_report.invoke({"subject": "张伟", "current_location": "一号装置区"})
    private_positioning = format_positioning_report.invoke({
        "subject": "张伟",
        "timeline_json": '[{"时间":"10:00","区域":"装置区","x":12,"y":8,"epc":"secret-tag"}]',
    })
    handover = format_shift_handover.invoke({"summary": "运行平稳", "pending_json": '[{"事项":"复核","状态":"待处理"}]'})
    assert "在线 6 人" in concise and "承包商" in concise
    assert "运营摘要" in executive and "98%" in executive
    assert "告警处置卡" in alarm and "通知监护人" in alarm
    assert "定位报告" in positioning and "一号装置区" in positioning
    assert "secret-tag" not in private_positioning and "| x |" not in private_positioning
    assert "交接班记录" in handover and "待处理" in handover


def test_response_format_selection_is_bounded_and_enforced():
    assert normalize_response_format("executive") == "executive"
    assert normalize_response_format("unknown") == "auto"
    assert response_format_system_instruction("auto") == ""
    assert "format_executive_brief" in response_format_system_instruction("executive")


def test_only_selected_response_format_tool_is_loaded():
    routed, _ = route_local_tools("查询实时人员位置", scene="safety")
    assert not (RESPONSE_FORMAT_TOOL_NAMES & set(routed))
    for provider in ("deepseek", "local"):
        tools = _select_agent_tools("safety", provider, routed, "executive")
        format_names = {item.name for item in tools} & RESPONSE_FORMAT_TOOL_NAMES
        assert format_names == {"format_executive_brief"}
        auto_tools = _select_agent_tools("safety", provider, routed, "auto")
        assert not ({item.name for item in auto_tools} & RESPONSE_FORMAT_TOOL_NAMES)


def test_format_tool_result_is_streamed_even_without_final_model_text():
    class FakeAgent:
        def stream(self, *_args, **_kwargs):
            message = SimpleNamespace(name="format_concise_reply", content="结论：运行正常")
            yield "updates", {"tools": {"messages": [message]}}

    events = list(ask_stream(FakeAgent(), "测试", thread_id="format-fallback"))
    assert {"type": "formatted", "text": "结论：运行正常"} in events
