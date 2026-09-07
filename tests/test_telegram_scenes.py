import asyncio
from types import SimpleNamespace

import telegram_bot


def test_telegram_scenes_and_supervisor_are_available():
    assert set(telegram_bot.SCENE_SHORTCUTS) == {
        "medical", "safety", "building", "eldercare", "diagnostics", "iot", "command"
    }
    keyboard = telegram_bot.scene_keyboard("medical")
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == [
        "scene:medical", "scene:safety", "scene:building",
        "scene:eldercare", "scene:diagnostics", "scene:iot", "scene:command",
    ]


def test_new_telegram_conversations_start_in_auto_route_mode():
    context = SimpleNamespace(user_data={})
    scene, provider, model = telegram_bot._selection(context)
    assert scene == "command"
    assert (provider, model) == ("deepseek", "deepseek-v4-flash")


def test_each_scene_has_four_quick_actions():
    for scene, actions in telegram_bot.QUICK_ACTIONS.items():
        assert len(actions) == 4
        assert len({key for key, _, _ in actions}) == 4
        keyboard = telegram_bot.control_keyboard(scene, "deepseek", "deepseek-v4-flash")
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        assert sum(value.startswith("quick:") for value in callbacks) == 4
        assert "action:status" in callbacks
        assert "action:new" in callbacks


def test_telegram_agent_cache_and_builder_are_scene_scoped(monkeypatch):
    calls = []

    def fake_build(provider, model, **kwargs):
        calls.append((provider, model, kwargs))
        return SimpleNamespace(scene=kwargs["scene"])

    monkeypatch.setattr(telegram_bot, "build_agent", fake_build)
    telegram_bot.AGENTS.clear()
    medical = telegram_bot.get_agent("medical", "deepseek", "demo")
    building = telegram_bot.get_agent("building", "deepseek", "demo")
    assert medical.scene == "medical"
    assert building.scene == "building"
    assert len(calls) == 2


def test_scene_aliases_cover_chinese_names():
    assert telegram_bot.SCENE_ALIASES["医疗"] == "medical"
    assert telegram_bot.SCENE_ALIASES["人员安全"] == "safety"
    assert telegram_bot.SCENE_ALIASES["政企楼宇"] == "building"
    assert telegram_bot.SCENE_ALIASES["智慧养老"] == "eldercare"
    assert telegram_bot.SCENE_ALIASES["设备诊断"] == "diagnostics"
    assert telegram_bot.SCENE_ALIASES["物联网"] == "iot"
    assert telegram_bot.SCENE_ALIASES["智能体总控"] == "command"


def test_new_conversation_id_changes_only_current_scene_thread():
    data = {"conversation:safety": "new123", "conversation:medical": "med456"}
    assert telegram_bot._thread_id(7, "safety", data) == "telegram-7-safety-new123"
    assert telegram_bot._thread_id(7, "medical", data) == "telegram-7-medical-med456"


def test_telegram_local_model_uses_lifecycle_manager(monkeypatch):
    calls = []
    manager = SimpleNamespace(
        ensure_ready=lambda: calls.append("ensure") or True,
        touch=lambda: calls.append("touch"),
        as_dict=lambda: {"error": ""},
    )
    monkeypatch.setattr(telegram_bot, "local_model_manager", manager)
    ready, detail = asyncio.run(telegram_bot.ensure_local_model_ready())
    assert ready is True and detail == ""
    assert calls == ["ensure", "touch"]
