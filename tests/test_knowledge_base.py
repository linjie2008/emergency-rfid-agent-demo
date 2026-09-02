from knowledge_base import get_document, list_documents, search_documents


def test_catalog_contains_current_national_emergency_and_asset_documents():
    documents = list_documents()

    assert len(documents) >= 10
    assert {doc["category"] for doc in documents} == {"emergency", "asset"}
    assert any(doc["issued_at"].startswith("2026-") for doc in documents)
    assert all(doc["level"] == "国家级" for doc in documents)
    assert all(doc["status"] == "现行" for doc in documents)


def test_every_document_has_traceable_official_source_and_management_points():
    allowed_hosts = ("nhc.gov.cn", "samr.gov.cn", "gov.cn", "mof.gov.cn")

    for document in list_documents():
        assert document["source_url"].startswith("https://")
        assert any(host in document["source_url"] for host in allowed_hosts)
        assert document["issuer"]
        assert document["issued_at"]
        assert len(document["key_points"]) >= 2
        assert document["summary"]


def test_search_emergency_green_channel_finds_emergency_quality_documents():
    results = search_documents("急诊 绿色通道 预检分诊", category="emergency")

    assert results
    assert all(item["category"] == "emergency" for item in results)
    assert any("急诊" in item["title"] for item in results)
    assert any("绿色通道" in "".join(item["key_points"]) for item in results)


def test_search_asset_maintenance_finds_lifecycle_rules():
    results = search_documents("医学装备 维护 维修 台账", category="asset")

    assert results
    assert all(item["category"] == "asset" for item in results)
    assert any("维护" in "".join(item["key_points"]) for item in results)
    assert any("台账" in (item["summary"] + "".join(item["key_points"])) for item in results)


def test_search_accepts_natural_chinese_phrase_without_spaces():
    results = search_documents("医疗设备维护台账", category="asset")

    assert results
    assert any("维护" in "".join(item["key_points"]) for item in results)


def test_get_document_returns_full_record_and_unknown_id_returns_none():
    result = get_document("emergency-quality-indicators-2024")

    assert result["document_no"] == "国卫办医政函〔2024〕150号"
    assert get_document("missing-document") is None


def test_list_documents_filters_category_and_sorts_newest_first():
    documents = list_documents(category="emergency")

    assert documents
    assert all(doc["category"] == "emergency" for doc in documents)
    assert [doc["issued_at"] for doc in documents] == sorted(
        [doc["issued_at"] for doc in documents], reverse=True
    )


def test_agent_exposes_policy_knowledge_search_tool():
    from agent import TOOL_LABELS, TOOLS, search_policy_knowledge

    payload = search_policy_knowledge.invoke(
        {"query": "医学装备 维护 台账", "category": "asset", "limit": 3}
    )

    assert "医学装备" in payload
    assert "source_url" in payload
    assert "search_policy_knowledge" in {item.name for item in TOOLS}
    assert TOOL_LABELS["search_policy_knowledge"] == "国家政策知识库"
