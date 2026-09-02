"""国家级医疗急诊与医疗资产管理文件的轻量检索。"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


CATALOG_PATH = Path(__file__).resolve().parent / "knowledge_base" / "documents.json"


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def catalog_metadata() -> dict[str, str]:
    data = _catalog()
    return {"as_of": data["as_of"], "scope": data["scope"]}


def list_documents(category: str = "") -> list[dict[str, Any]]:
    category = (category or "").strip().lower()
    rows = [dict(item) for item in _catalog()["documents"]]
    if category in {"emergency", "asset"}:
        rows = [item for item in rows if item["category"] == category]
    return sorted(rows, key=lambda item: item["issued_at"], reverse=True)


def get_document(document_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in list_documents() if item["id"] == document_id),
        None,
    )


def _query_terms(query: str) -> list[str]:
    compact = re.sub(r"\s+", " ", (query or "").strip().lower())
    terms: list[str] = []
    for term in compact.split(" "):
        if not term:
            continue
        terms.append(term)
        # 中文搜索通常不输入空格；补充二字词片段，让“医疗设备维护台账”
        # 能匹配文件中的“医疗设备”“维护”和“台账”。
        for block in re.findall(r"[\u4e00-\u9fff]{4,}", term):
            terms.extend(block[index : index + 2] for index in range(len(block) - 1))
    return list(dict.fromkeys(terms))


def _score(document: dict[str, Any], terms: list[str]) -> int:
    title = document["title"].lower()
    keywords = " ".join(document["keywords"]).lower()
    key_points = " ".join(document["key_points"]).lower()
    summary = document["summary"].lower()
    score = 0
    for term in terms:
        score += 8 if term in title else 0
        score += 5 if term in keywords else 0
        score += 3 if term in key_points else 0
        score += 2 if term in summary else 0
    return score


def search_documents(
    query: str,
    category: str = "",
    limit: int = 5,
) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    if not terms:
        return list_documents(category)[: max(1, min(int(limit or 5), 50))]
    ranked = [
        (_score(document, terms), document)
        for document in list_documents(category)
    ]
    ranked = [(score, document) for score, document in ranked if score > 0]
    ranked.sort(key=lambda row: (row[0], row[1]["issued_at"]), reverse=True)
    size = max(1, min(int(limit or 5), 20))
    return [dict(document, relevance=score) for score, document in ranked[:size]]
