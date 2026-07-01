"""Generate a Requirements Traceability Matrix from the item graph.

Derived, never authored: it walks BR → PR → FR/NFR → AC → TC and renders the
coverage as a table, so gaps are visible at a glance.
"""
from __future__ import annotations

import csv
import io


def _cell(ids: set[str]) -> str:
    return ", ".join(sorted(ids)) if ids else "—"


def build_rows(graph) -> list[dict]:
    rows: list[dict] = []
    for br in sorted(graph.by_prefix.get("BR", []), key=lambda i: i.id):
        prs = graph.children(br.id, "traces", "PR")
        fr_ids, ac_ids, tc_ids = set(), set(), set()
        for pr in prs:
            for src in graph.children(pr.id, "traces"):
                if src.prefix in {"FR", "NFR"}:
                    fr_ids.add(src.id)
            for ac in graph.children(pr.id, "verifies", "AC"):
                ac_ids.add(ac.id)
                for tc in graph.children(ac.id, "tests", "TC"):
                    tc_ids.add(tc.id)
        rows.append({
            "BR": br.id,
            "PR": {p.id for p in prs},
            "FR/NFR": fr_ids,
            "AC": ac_ids,
            "TC": tc_ids,
        })
    return rows


_COLS = ["BR", "PR", "FR/NFR", "AC", "TC"]
_HEADERS = ["Business Req", "Product Req", "Functional / NFR",
            "Acceptance Criteria", "Test Cases"]


def render_markdown(graph) -> str:
    rows = build_rows(graph)
    out = ["# Requirements Traceability Matrix", ""]
    out.append("| " + " | ".join(_HEADERS) + " |")
    out.append("|" + "|".join(["---"] * len(_HEADERS)) + "|")
    for r in rows:
        out.append("| " + " | ".join(
            [r["BR"]] + [_cell(r[c]) for c in _COLS[1:]]) + " |")
    uncovered = [r["BR"] for r in rows if not r["PR"]]
    out += ["",
            f"_{len(rows)} business requirement(s); "
            f"{len(uncovered)} with no product requirement"
            + (": " + ", ".join(uncovered) if uncovered else "") + "._"]
    return "\n".join(out) + "\n"


def render_csv(graph) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_HEADERS)
    for r in build_rows(graph):
        writer.writerow([r["BR"]] + [_cell(r[c]) for c in _COLS[1:]])
    return buf.getvalue()
