"""可选 Langfuse 运行监控；未配置凭据时自动关闭。"""
from __future__ import annotations
import os

def langfuse_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))

def callback_for(session_id: str = "", metadata: dict | None = None):
    if not langfuse_enabled(): return None
    try:
        from langfuse.langchain import CallbackHandler
        return CallbackHandler()
    except Exception:
        return None

def callbacks_config(session_id: str, metadata: dict | None = None) -> dict:
    handler = callback_for(session_id, metadata)
    config = {"configurable": {"thread_id": session_id}, "metadata": {"session_id": session_id, **(metadata or {})}}
    if handler: config["callbacks"] = [handler]
    return config
