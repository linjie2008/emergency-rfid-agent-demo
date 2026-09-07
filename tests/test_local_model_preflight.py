from local_model_manager import LocalModelManager


def test_preflight_releases_managed_resources_before_model_start():
    manager = LocalModelManager()
    manager._terminate_orphan_models = lambda: [101, 102]
    manager._comfyui_release = lambda: {"ok": True, "status": "released"}
    manager._trim_python_memory = lambda: True

    assert manager.release_resources_before_start() is True
    assert manager.last_cleanup["ok"] is True
    assert manager.last_cleanup["orphanModelPids"] == [101, 102]
    assert manager.last_cleanup["comfyui"]["status"] == "released"
    assert manager.last_cleanup["pythonHeapTrimmed"] is True


def test_preflight_does_not_start_when_comfyui_is_busy_in_strict_mode():
    manager = LocalModelManager()
    manager._terminate_orphan_models = lambda: []
    manager._comfyui_release = lambda: {"ok": False, "status": "busy", "detail": "ComfyUI 正在执行任务"}
    manager._trim_python_memory = lambda: True

    assert manager.release_resources_before_start() is False
    assert manager.last_cleanup["comfyui"]["status"] == "busy"
    assert manager.error == "ComfyUI 正在执行任务"
