"""Tests for the cross-document consistency engine."""
from pathlib import Path

from docunit.models import Item
from docunit.graph import Graph
from docunit.consistency import (
    load_config, run_consistency,
    check_referential_integrity, check_coverage,
    check_required_links, check_unique_item_ids,
)
from docunit import rtm
from docunit.graph import build_graph

ROOT = Path(__file__).resolve().parent.parent
CONFIG = load_config(ROOT / "consistency.yaml")


def mk(iid, prefix, links=None, status="approved"):
    return Item(iid, prefix, f"{iid} text", links or {}, "d.md", "k", status, "S")


def graph_of(*items):
    g = Graph()
    for it in items:
        g.add(it)
    return g


# ── referential integrity (always blocks) ──────────────────────────────────
def test_referential_integrity_ok():
    g = graph_of(mk("BR-001", "BR"), mk("PR-014", "PR", {"traces": ["BR-001"]}))
    assert check_referential_integrity(g).passed


def test_referential_integrity_broken_ref_caught():
    g = graph_of(mk("PR-014", "PR", {"traces": ["BR-999"]}))
    r = check_referential_integrity(g)
    assert not r.passed and "BR-999" in r.detail and r.blocking


# ── coverage (blocks only when approved) ────────────────────────────────────
def test_coverage_enforced_when_approved():
    g = graph_of(mk("BR-001", "BR", status="approved"))  # no covering PR
    assert not check_coverage(g, CONFIG).passed


def test_coverage_skipped_when_draft():
    g = graph_of(mk("BR-001", "BR", status="draft"))     # no covering PR, but draft
    assert check_coverage(g, CONFIG).passed


def test_coverage_satisfied():
    g = graph_of(mk("BR-001", "BR", status="approved"),
                 mk("PR-014", "PR", {"traces": ["BR-001"]}, status="approved"),
                 mk("AC-001", "AC", {"verifies": ["PR-014"]}, status="approved"),
                 mk("TC-001", "TC", {"tests": ["AC-001"]}, status="approved"))
    assert check_coverage(g, CONFIG).passed


# ── required links / orphans (blocks only when approved) ────────────────────
def test_orphan_blocks_when_approved():
    g = graph_of(mk("PR-014", "PR", status="approved"))  # no traces link
    assert not check_required_links(g, CONFIG).passed


def test_orphan_ok_when_draft():
    g = graph_of(mk("PR-014", "PR", status="draft"))
    assert check_required_links(g, CONFIG).passed


# ── uniqueness (always blocks) ──────────────────────────────────────────────
def test_duplicate_item_ids_caught():
    g = graph_of(mk("BR-001", "BR"), mk("BR-001", "BR"))
    r = check_unique_item_ids(g)
    assert not r.passed and "BR-001" in r.detail


# ── the real repo spine is fully consistent ─────────────────────────────────
def test_repo_consistency_has_no_blocking_failures():
    results = run_consistency(ROOT / "documents", ROOT / "consistency.yaml",
                              with_semantic=False)
    assert not any(r.is_blocking_failure for r in results)


def test_rtm_renders_full_chain():
    rows = rtm.build_rows(build_graph(ROOT / "documents"))
    by_br = {r["BR"]: r for r in rows}
    assert by_br["BR-001"]["PR"] == {"PR-014"}
    assert by_br["BR-001"]["TC"] == {"TC-001"}
    assert all(r["PR"] for r in rows)  # no uncovered business requirement
