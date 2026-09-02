"""轻量网页：无 Gradio CDN / WebSocket，回答走 SSE 流式输出。"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from agent import ask_stream, build_agent
from knowledge_base import catalog_metadata, get_document, list_documents, search_documents
from skill_test import format_report, run_skill_tests

ROOT = Path(__file__).resolve().parent
agent = build_agent()
app = FastAPI(title="急诊绿通 RFID Demo")


class ChatIn(BaseModel):
    message: str
    session_id: str = "web"


class TestIn(BaseModel):
    skill_id: str = ""
    include_e2e: bool = False


@app.get("/")
def index():
    return FileResponse(
        ROOT / "static" / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.post("/api/chat")
def chat(body: ChatIn):
    def events():
        try:
            for ev in ask_stream(agent, body.message.strip(), thread_id=body.session_id):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'text': str(exc)}, ensure_ascii=False)}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/skill-tests")
def skill_tests(body: TestIn):
    skill_id = body.skill_id or None
    report = run_skill_tests(
        skill_id=skill_id,
        include_e2e=body.include_e2e or skill_id == "e2e_chat",
        agent=agent if (body.include_e2e or skill_id == "e2e_chat") else None,
    )
    report["detail"] = format_report(report)
    return report


@app.get("/api/knowledge")
def knowledge_list(query: str = "", category: str = "", limit: int = 20):
    rows = (
        search_documents(query, category=category, limit=limit)
        if query.strip()
        else list_documents(category)[: max(1, min(limit, 50))]
    )
    all_rows = list_documents()
    metadata = catalog_metadata()
    return {
        "count": len(rows),
        "data": rows,
        "stats": {
            "emergency": sum(row["category"] == "emergency" for row in all_rows),
            "asset": sum(row["category"] == "asset" for row in all_rows),
        },
        **metadata,
    }


@app.get("/api/knowledge/{document_id}")
def knowledge_document(document_id: str):
    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="未找到该国家文件")
    return document


def serve(host: str = "0.0.0.0", port: int = 7861) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")
