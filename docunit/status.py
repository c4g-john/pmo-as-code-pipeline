"""Derive a project status view from the documents.

Nothing here is authored: every number comes from the actual files and the
traceability graph. This is "derived status over self-reported status" — the
page computes its own RAG from real signals rather than trusting a typed field.
"""
from __future__ import annotations

import json
from pathlib import Path

from .consistency import load_config
from .graph import build_graph
from .loader import load, load_criteria
from .structural import run_structural, _field_value

CRITERIA_DIR = Path("criteria")
SCHEMA_DIR = Path("schema")
DOCUMENTS_DIR = Path("documents")
APPROVED = {"approved", "baselined"}
_SEVERITY = {"low": 1, "medium": 2, "high": 3, "critical": 4}


# ── per-document validity (blocking structural checks only) ─────────────────
def _doc_passes(doc, id_index) -> bool:
    kind = doc.kind or ""
    cpath = CRITERIA_DIR / f"{kind}.criteria.yaml"
    if not cpath.is_file():
        return True
    criteria = load_criteria(cpath)
    schema_path = SCHEMA_DIR / f"{kind}.schema.json"
    schema = json.loads(schema_path.read_text()) if schema_path.is_file() else {}
    ctx = {
        "schema": schema,
        "required_sections": criteria.get("required_sections", []),
        "item_sections": criteria.get("item_sections", []),
        "steps_sections": criteria.get("steps_sections", []),
        "measurable_sections": criteria.get("measurable_sections", []),
        "id_index": id_index,
    }
    for spec in criteria.get("checks", []):
        if spec.get("type") == "structural":
            if run_structural(doc, spec, ctx).is_blocking_failure:
                return False
    return True


# ── signal extractors ───────────────────────────────────────────────────────
def _coverage(graph, config):
    out = []
    for rule in config.get("coverage", []):
        parent_prefix, relation = rule["parent"], rule["relation"]
        by_prefix = rule.get("by_prefix")
        parents = graph.by_prefix.get(parent_prefix, [])
        covered = [p for p in parents if graph.children(p.id, relation, by_prefix)]
        out.append({
            "label": rule.get("label", f"{parent_prefix} → {by_prefix}"),
            "covered": len(covered),
            "total": len(parents),
            "gaps": [p.id for p in parents if p not in covered],
        })
    return out


def _risks(graph):
    risks = []
    for item in graph.by_prefix.get("RISK", []):
        prob = (_field_value(item.text, "probability") or "").lower()
        impact = (_field_value(item.text, "impact") or "").lower()
        risks.append({
            "id": item.id,
            "probability": prob or "?",
            "impact": impact or "?",
            "owner": _field_value(item.text, "owner") or "?",
            "score": _SEVERITY.get(prob, 0) * _SEVERITY.get(impact, 0),
        })
    return sorted(risks, key=lambda r: -r["score"])


def _broken_references(graph):
    broken = []
    for item in graph.all_items():
        for relation, targets in item.links.items():
            for target in targets:
                if not graph.exists(target):
                    broken.append(f"{item.id} —{relation}→ {target}")
    return broken


def _latest_report(docs):
    reports = [d for d in docs if d.kind == "status-report"]
    if not reports:
        return None
    reports.sort(key=lambda d: str(d.frontmatter.get("period", "")), reverse=True)
    top = reports[0]
    return {
        "id": top.id,
        "period": str(top.frontmatter.get("period", "")),
        "rag": str(top.frontmatter.get("rag", "")).lower(),
    }


# ── the model + derived RAG ─────────────────────────────────────────────────
def build_status(documents_dir=DOCUMENTS_DIR) -> dict:
    docs = [load(p) for p in sorted(Path(documents_dir).rglob("*.md"))]
    graph = build_graph(documents_dir)
    config = load_config()

    id_index = {}
    for d in docs:
        id_index.setdefault(d.id, []).append(d.path)

    documents = [{
        "kind": d.kind,
        "id": d.id,
        "title": d.frontmatter.get("title", d.id),
        "status": str(d.frontmatter.get("status", "draft")),
        "passing": _doc_passes(d, id_index),
    } for d in docs]

    model = {
        "documents": documents,
        "counts": {
            "total": len(documents),
            "kinds": len({d["kind"] for d in documents}),
            "approved": sum(1 for d in documents if d["status"] in APPROVED),
            "failing": sum(1 for d in documents if not d["passing"]),
        },
        "coverage": _coverage(graph, config),
        "risks": _risks(graph),
        "broken_references": _broken_references(graph),
        "latest_report": _latest_report(docs),
    }
    model["rag"] = derive_rag(model)
    return model


def derive_rag(model) -> str:
    """Red = something is objectively broken. Amber = carrying risk or
    incompleteness. Green = clean."""
    approved_failing = any(not d["passing"] for d in model["documents"]
                           if d["status"] in APPROVED)
    if approved_failing or model["broken_references"]:
        return "red"
    coverage_gap = any(c["gaps"] for c in model["coverage"])
    reported = (model["latest_report"] or {}).get("rag")
    if coverage_gap or model["risks"] or reported in {"amber", "red"}:
        return "amber"
    return "green"


# ── renderers ───────────────────────────────────────────────────────────────
_EMOJI = {"green": "🟢", "amber": "🟠", "red": "🔴"}


def render_markdown(model, summary: bool = False) -> str:
    rag = model["rag"]
    c = model["counts"]
    heading = "## Project Status" if summary else "# Project Status"
    out = [f"{heading} — {_EMOJI[rag]} {rag.upper()}", ""]
    out.append(f"_Derived from {c['total']} documents across {c['kinds']} kinds "
               f"({c['approved']} approved). Generated by `docunit status` — do not edit._")
    out += ["", "## Signals", ""]

    for cov in model["coverage"]:
        pct = round(100 * cov["covered"] / cov["total"]) if cov["total"] else 100
        mark = "🟢" if not cov["gaps"] else "🟠"
        detail = f" — gaps: {', '.join(cov['gaps'])}" if cov["gaps"] else ""
        out.append(f"- {mark} **{cov['label']}**: {cov['covered']}/{cov['total']} ({pct}%){detail}")

    if model["broken_references"]:
        out.append(f"- 🔴 **Broken references**: {len(model['broken_references'])} "
                   f"({', '.join(model['broken_references'][:3])}…)")
    failing = [d["id"] for d in model["documents"] if not d["passing"]]
    if failing:
        out.append(f"- 🔴 **Documents failing audit**: {', '.join(failing)}")

    if model["risks"]:
        out.append(f"- 🟠 **Open risks**: {len(model['risks'])}")
        for r in model["risks"][:5]:
            out.append(f"    - `{r['id']}` — {r['probability']}/{r['impact']} · owner: {r['owner']}")

    lr = model["latest_report"]
    if lr:
        out.append(f"- ℹ️ Latest status report `{lr['id']}` ({lr['period']}) reported **{lr['rag']}**")

    if not summary:
        out += ["", "## Documents", "", "| Kind | ID | Status | Audit |", "|---|---|---|---|"]
        for d in sorted(model["documents"], key=lambda x: (x["kind"], x["id"])):
            out.append(f"| {d['kind']} | {d['id']} | {d['status']} | {'✓' if d['passing'] else '✗'} |")
    else:
        out += ["", f"<sub>Full inventory of {c['total']} documents in "
                    "[`STATUS.md`](../../blob/main/STATUS.md).</sub>"]
    return "\n".join(out) + "\n"


def render_json(model) -> str:
    return json.dumps(model, indent=2) + "\n"
