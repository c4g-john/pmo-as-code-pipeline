"""Deterministic structural checks. These are reliable and BLOCKING."""
from __future__ import annotations

import datetime as dt
import re
from typing import Callable

from jsonschema import Draft7Validator, FormatChecker

from .models import CheckResult, Document

# ── measurability heuristic ────────────────────────────────────────────────
# A success criterion is "measurable" if it contains a number AND either a
# comparator or a unit/symbol/date — enough to make pass/fail unambiguous.
_NUMBER = re.compile(r"\d")
_COMPARATOR = re.compile(
    r"[<>]=?|\b(?:below|under|above|over|at least|at most|no more than|"
    r"no less than|fewer than|more than|greater than|less than|within|by|"
    r"reach|reduce|increase|decrease|drop|rise|cut|from|to)\b",
    re.IGNORECASE,
)
_UNIT_OR_SYMBOL = re.compile(
    r"%|[$€£]|/\s*\d|\d{4}-\d{2}-\d{2}|"
    r"\b(?:hours?|hrs?|days?|weeks?|months?|minutes?|mins?|seconds?|secs?|"
    r"USD|EUR|GBP|k|m|bn|pts?|points?|x)\b",
    re.IGNORECASE,
)


def _is_measurable(text: str) -> bool:
    if not _NUMBER.search(text):
        return False
    return bool(_COMPARATOR.search(text) or _UNIT_OR_SYMBOL.search(text))


def _field_value(item: str, field: str) -> str | None:
    """Return the text after `field:` (up to a sentence/clause break), or None.

    Stops at a semicolon or a period that ends a clause (period + space, or
    period at end) so dotted handles like ``alex.kim`` are not truncated.
    """
    m = re.search(rf"{field}\s*:\s*(.+?)(?:;|\.\s|\.$|$)", item, re.IGNORECASE)
    if not m:
        return None
    val = m.group(1).strip()
    return val if len(val) >= 2 else None


def _jsonify(value):
    """Convert YAML date/datetime objects to ISO strings so a JSON Schema with
    `type: string, format: date` validates correctly."""
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonify(v) for v in value]
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def _as_date(value) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


# ── individual checks ──────────────────────────────────────────────────────
def check_frontmatter_schema(doc: Document, ctx: dict) -> tuple[bool, str]:
    schema = ctx["schema"]
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(_jsonify(doc.frontmatter)), key=str)
    if not errors:
        return True, "Frontmatter is valid against the charter schema."
    msgs = "; ".join(f"{'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}"
                     for e in errors)
    return False, f"Frontmatter schema errors: {msgs}"


def check_required_sections(doc: Document, ctx: dict) -> tuple[bool, str]:
    required = ctx["required_sections"]
    missing = [s for s in required if s not in doc.sections]
    empty = [s for s in required if s in doc.sections and doc.sections[s].is_empty]
    problems = []
    if missing:
        problems.append(f"missing: {', '.join(missing)}")
    if empty:
        problems.append(f"empty: {', '.join(empty)}")
    if problems:
        return False, "Required sections — " + "; ".join(problems)
    return True, f"All {len(required)} required sections present and non-empty."


def check_measurable_success_criteria(doc: Document, ctx: dict) -> tuple[bool, str]:
    section = doc.section("Success Criteria")
    if section is None:
        return False, "No Success Criteria section."
    items = section.list_items
    if not items:
        return False, "Success Criteria has no bulleted criteria."
    unmeasurable = [it for it in items if not _is_measurable(it)]
    if unmeasurable:
        preview = "; ".join(f'“{u[:60]}”' for u in unmeasurable)
        return False, f"{len(unmeasurable)}/{len(items)} criteria lack a measurable threshold: {preview}"
    return True, f"All {len(items)} success criteria state a measurable threshold."


def check_risks_owner_mitigation(doc: Document, ctx: dict) -> tuple[bool, str]:
    section = doc.section("Risks")
    if section is None:
        return False, "No Risks section."
    items = section.list_items
    if not items:
        return False, "Risks has no bulleted risks."
    bad = []
    for it in items:
        if _field_value(it, "owner") is None or _field_value(it, "mitigation") is None:
            bad.append(it)
    if bad:
        preview = "; ".join(f'“{b[:60]}”' for b in bad)
        return False, f"{len(bad)}/{len(items)} risks miss an Owner and/or Mitigation: {preview}"
    return True, f"All {len(items)} risks name an owner and a mitigation."


def check_dates_consistent(doc: Document, ctx: dict) -> tuple[bool, str]:
    dates = doc.frontmatter.get("dates") or {}
    created = _as_date(dates.get("created"))
    target = _as_date(dates.get("target"))
    if created is None or target is None:
        return False, "dates.created and dates.target must be valid ISO dates."
    if target < created:
        return False, f"target ({target}) is before created ({created})."
    return True, f"Dates consistent (created {created} → target {target})."


def check_unique_id(doc: Document, ctx: dict) -> tuple[bool, str]:
    if not doc.id:
        return False, "Document has no id."
    others = [p for p in ctx.get("id_index", {}).get(doc.id, []) if p != doc.path]
    if others:
        return False, f"id '{doc.id}' also used by: {', '.join(others)}"
    return True, f"id '{doc.id}' is unique."


CHECKS: dict[str, Callable[[Document, dict], tuple[bool, str]]] = {
    "frontmatter-schema": check_frontmatter_schema,
    "required-sections": check_required_sections,
    "measurable-success-criteria": check_measurable_success_criteria,
    "risks-have-owner-and-mitigation": check_risks_owner_mitigation,
    "dates-consistent": check_dates_consistent,
    "unique-id": check_unique_id,
}


def run_structural(doc: Document, spec: dict, ctx: dict) -> CheckResult:
    """Run one structural check described by a criteria `spec` dict."""
    check_id = spec["id"]
    fn = CHECKS.get(check_id)
    blocking = bool(spec.get("blocking", True))
    if fn is None:
        return CheckResult(check_id, False, blocking,
                           f"Unknown structural check '{check_id}'.", kind="structural")
    try:
        passed, detail = fn(doc, ctx)
    except Exception as exc:  # a check crash is a failure, never a silent pass
        return CheckResult(check_id, False, blocking,
                           f"Check errored: {exc}", kind="structural")
    return CheckResult(check_id, passed, blocking, detail, kind="structural")
