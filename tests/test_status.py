"""Tests for the derived project-status view."""
import os
from pathlib import Path

from docunit import status as S

ROOT = Path(__file__).resolve().parent.parent


def _cd_root():
    os.chdir(ROOT)  # build_status reads criteria/ and consistency.yaml relatively


# ── the model derives from the real repo ────────────────────────────────────
def test_build_status_from_repo():
    _cd_root()
    m = S.build_status(ROOT / "documents")
    assert m["counts"]["total"] >= 20
    assert m["counts"]["kinds"] >= 15
    # the onboarding spine is fully covered
    assert all(not c["gaps"] for c in m["coverage"])
    # the risk register contributes open risks
    assert any(r["id"] == "RISK-001" for r in m["risks"])
    assert m["rag"] in {"green", "amber", "red"}


def test_repo_rag_is_amber_due_to_open_risks():
    _cd_root()
    m = S.build_status(ROOT / "documents")
    # nothing is broken (no failing approved docs, no dangling links), but the
    # register carries open risks → amber, not green.
    assert m["counts"]["failing"] == 0
    assert not m["broken_references"]
    assert m["risks"]
    assert m["rag"] == "amber"


# ── derive_rag logic ────────────────────────────────────────────────────────
def _model(**over):
    base = {"documents": [], "coverage": [], "risks": [],
            "broken_references": [], "latest_report": None}
    base.update(over)
    return base


def test_rag_red_on_broken_references():
    assert S.derive_rag(_model(broken_references=["PR-1 —traces→ BR-9"])) == "red"


def test_rag_red_on_failing_approved_doc():
    m = _model(documents=[{"status": "approved", "passing": False}])
    assert S.derive_rag(m) == "red"


def test_rag_amber_on_open_risk():
    assert S.derive_rag(_model(risks=[{"id": "RISK-1", "score": 4}])) == "amber"


def test_rag_amber_on_coverage_gap():
    assert S.derive_rag(_model(coverage=[{"gaps": ["BR-002"]}])) == "amber"


def test_rag_green_when_clean():
    m = _model(documents=[{"status": "approved", "passing": True}],
               coverage=[{"gaps": []}])
    assert S.derive_rag(m) == "green"


# ── renderers produce sane output ───────────────────────────────────────────
def test_render_html_is_self_contained():
    _cd_root()
    out = S.render_html(S.build_status(ROOT / "documents"))
    assert out.startswith("<!doctype html>")
    assert "AMBER" in out and "RISK-001" in out
    assert "http://" not in out and "https://" not in out  # no external deps


def test_render_json_roundtrips():
    import json
    _cd_root()
    data = json.loads(S.render_json(S.build_status(ROOT / "documents")))
    assert data["rag"] == "amber" and data["counts"]["total"] >= 20
