from pathlib import Path


HTML = (Path(__file__).parents[1] / "static" / "index.html").read_text(encoding="utf-8")


def test_page_has_searchable_national_document_knowledge_tab():
    assert 'id="tab-kb"' in HTML
    assert 'id="kb"' in HTML
    assert 'id="kbQuery"' in HTML
    assert 'id="kbCategory"' in HTML
    assert 'id="kbResults"' in HTML
    assert 'fetch("/api/knowledge?' in HTML


def test_page_explains_scope_and_official_source_links():
    assert "医疗急诊" in HTML
    assert "资产管理" in HTML
    assert "国家级" in HTML
    assert "官方原文" in HTML
