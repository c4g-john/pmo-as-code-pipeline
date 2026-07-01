"""Tests for item parsing and the cross-document graph."""
from pathlib import Path

from docunit.loader import ITEM_RE, parse_link_clause
from docunit.graph import build_graph

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "documents"


def test_parse_link_clause():
    assert parse_link_clause("traces: BR-001, BR-002; verifies: FR-3") == {
        "traces": ["BR-001", "BR-002"], "verifies": ["FR-3"]}


def test_parse_link_clause_empty():
    assert parse_link_clause("") == {}


def test_item_regex():
    m = ITEM_RE.match("**PR-014** (traces: BR-001): the flow shall be self-serve.")
    assert m and m.group("id") == "PR-014" and m.group("prefix") == "PR"
    assert m.group("text").startswith("the flow")


def test_item_regex_no_links():
    m = ITEM_RE.match("**BR-001**: the business shall reduce onboarding time.")
    assert m and m.group("id") == "BR-001" and m.group("links") is None


def test_build_graph_extracts_items():
    g = build_graph(DOCS)
    for iid in ("BR-001", "BR-002", "PR-014", "PR-015", "FR-101", "NFR-05",
                "AC-001", "AC-002", "TC-001", "TC-002"):
        assert g.exists(iid), f"missing {iid}"
    assert {i.id for i in g.by_prefix["PR"]} == {"PR-014", "PR-015"}


def test_build_graph_links_and_children():
    g = build_graph(DOCS)
    assert "BR-001" in g.canonical("PR-014").targets("traces")
    assert [c.id for c in g.children("BR-001", "traces", "PR")] == ["PR-014"]
    assert [c.id for c in g.children("AC-001", "tests", "TC")] == ["TC-001"]
