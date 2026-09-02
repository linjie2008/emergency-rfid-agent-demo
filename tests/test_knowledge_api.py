from server import knowledge_document, knowledge_list


def test_knowledge_list_returns_filtered_search_results():
    response = knowledge_list(query="急诊 绿色通道", category="emergency", limit=3)

    assert response["count"] >= 1
    assert len(response["data"]) <= 3
    assert all(item["category"] == "emergency" for item in response["data"])


def test_knowledge_list_without_query_returns_catalog_stats():
    response = knowledge_list(query="", category="", limit=20)

    assert response["count"] >= 10
    assert response["stats"]["emergency"] >= 1
    assert response["stats"]["asset"] >= 1
    assert response["as_of"] == "2026-08-28"


def test_knowledge_document_returns_selected_document():
    response = knowledge_document("emergency-quality-indicators-2024")

    assert response["id"] == "emergency-quality-indicators-2024"
    assert response["source_url"].startswith("https://www.nhc.gov.cn/")
