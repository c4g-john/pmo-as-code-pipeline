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
        parents = graph.by_type.get(parent_prefix, [])
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
    for item in graph.by_type.get("RISK", []):
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


_HTML_CSS = """
  :root { --bg:#0d1117; --panel:#161b22; --border:#30363d; --ink:#e6edf3;
          --muted:#8b949e; --ok:#2ea043; --amber:#d29922; --bad:#f85149; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
  main { max-width:860px; margin:0 auto; padding:40px 24px 64px; }
  header { display:flex; align-items:center; gap:16px; flex-wrap:wrap; margin-bottom:8px; }
  .rag { font-weight:700; font-size:13px; letter-spacing:.08em; color:#0d1117;
         padding:5px 12px; border-radius:999px; }
  h1 { font-size:26px; margin:0; }
  .meta { color:var(--muted); font-size:13px; margin:2px 0 30px; }
  section { margin-bottom:30px; }
  h2 { font-size:15px; text-transform:uppercase; letter-spacing:.05em;
       color:var(--muted); border-bottom:1px solid var(--border); padding-bottom:8px; }
  .sig { margin:12px 0; }
  .sig-h { display:flex; justify-content:space-between; font-size:14px; margin-bottom:5px; }
  .bar { height:8px; background:var(--border); border-radius:4px; overflow:hidden; }
  .bar-f { height:100%; background:var(--ok); border-radius:4px; }
  ul { padding-left:18px; } li { margin:4px 0; }
  code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:13px;
         background:#21262d; padding:1px 5px; border-radius:4px; }
  table { width:100%; border-collapse:collapse; font-size:13.5px; }
  th,td { text-align:left; padding:7px 10px; border-bottom:1px solid var(--border); }
  th { color:var(--muted); font-weight:600; }
  td.ok { color:var(--ok); } td.bad { color:var(--bad); font-weight:700; }
  footer { color:var(--muted); font-size:12px; margin-top:36px; border-top:1px solid var(--border); padding-top:14px; }
"""


def render_html(model) -> str:
    import datetime
    import html as _h
    rag = model["rag"]
    c = model["counts"]
    color = {"green": "var(--ok)", "amber": "var(--amber)", "red": "var(--bad)"}[rag]
    bar_color = {"green": "var(--ok)", "amber": "var(--amber)", "red": "var(--bad)"}[rag]
    esc = lambda s: _h.escape(str(s))

    coverage = "".join(
        f'<div class="sig"><div class="sig-h"><span>{esc(cov["label"])}</span>'
        f'<span>{cov["covered"]}/{cov["total"]}'
        + (f' · gaps: {esc(", ".join(cov["gaps"]))}' if cov["gaps"] else "")
        + '</span></div><div class="bar"><div class="bar-f" style="width:'
        f'{(100 * cov["covered"] // cov["total"]) if cov["total"] else 100}%'
        + (";background:var(--amber)" if cov["gaps"] else "") + '"></div></div></div>'
        for cov in model["coverage"])

    risks = "".join(
        f'<li><code>{esc(r["id"])}</code> — {esc(r["probability"])}/{esc(r["impact"])}'
        f' · owner {esc(r["owner"])}</li>' for r in model["risks"]) or "<li>None open.</li>"

    problems = ""
    if model["broken_references"]:
        problems += ("<section><h2>Broken references</h2><ul>"
                     + "".join(f"<li><code>{esc(b)}</code></li>" for b in model["broken_references"])
                     + "</ul></section>")
    failing = [d for d in model["documents"] if not d["passing"]]
    if failing:
        problems += ("<section><h2>Documents failing audit</h2><ul>"
                     + "".join(f'<li><code>{esc(d["id"])}</code></li>' for d in failing)
                     + "</ul></section>")

    rows = "".join(
        f'<tr><td>{esc(d["kind"])}</td><td><code>{esc(d["id"])}</code></td>'
        f'<td>{esc(d["status"])}</td>'
        f'<td class="{"ok" if d["passing"] else "bad"}">{"✓" if d["passing"] else "✗"}</td></tr>'
        for d in sorted(model["documents"], key=lambda x: (x["kind"], x["id"])))

    lr = model["latest_report"]
    report = (f'<code>{esc(lr["id"])}</code> ({esc(lr["period"])}) → reported <b>{esc(lr["rag"])}</b>'
              if lr else "None on record.")
    gen = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Project Status — {rag.upper()}</title>
<style>{_HTML_CSS}
  .bar-f {{ background:{bar_color}; }}</style></head>
<body><main>
  <header>
    <span class="rag" style="background:{color}">{rag.upper()}</span>
    <h1>Project Status</h1>
  </header>
  <p class="meta">Derived from {c['total']} documents · {c['kinds']} kinds ·
    {c['approved']} approved · generated {gen}. Do not edit — regenerated from the documents.</p>
  <section><h2>Traceability coverage</h2>{coverage}</section>
  {problems}
  <section><h2>Open risks ({len(model['risks'])})</h2><ul>{risks}</ul></section>
  <section><h2>Latest status report</h2><p>{report}</p></section>
  <section><h2>Documents ({c['total']})</h2>
    <table><thead><tr><th>Kind</th><th>ID</th><th>Status</th><th>Audit</th></tr></thead>
    <tbody>{rows}</tbody></table></section>
  <footer>Generated by <code>docunit status</code> from the documents in this repository.</footer>
</main></body></html>
"""
