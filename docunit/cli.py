"""docunit command-line interface.

    docunit validate documents/charters/aurora.md
    docunit validate documents/**/*.md --junit out.xml --markdown comment.md

Exit code = number of BLOCKING (structural) failures. Advisory (AI) failures
never affect the exit code, so CI is gated only by deterministic checks.
"""
from __future__ import annotations

import argparse
import glob
import sys
from collections import defaultdict
from pathlib import Path

from . import report
from .loader import load, load_criteria
from .models import CheckResult
from .structural import run_structural
from .semantic import run_semantic

# repo layout
CRITERIA_DIR = Path("criteria")
SCHEMA_DIR = Path("schema")
DOCUMENTS_DIR = Path("documents")


def _build_id_index() -> dict[str, list[str]]:
    """Map document id -> [paths] across all documents/, for uniqueness checks."""
    index: dict[str, list[str]] = defaultdict(list)
    for path in DOCUMENTS_DIR.rglob("*.md"):
        try:
            doc = load(path)
        except ValueError:
            continue
        if doc.id:
            index[doc.id].append(str(path))
    return index


def _validate_one(path: str, id_index: dict) -> list[CheckResult]:
    doc = load(path)
    kind = doc.kind or "charter"
    criteria = load_criteria(CRITERIA_DIR / f"{kind}.criteria.yaml")
    schema_path = SCHEMA_DIR / f"{kind}.schema.json"
    import json
    schema = json.loads(schema_path.read_text())

    ctx = {
        "schema": schema,
        "required_sections": criteria.get("required_sections", []),
        "id_index": id_index,
    }
    content = Path(path).read_text(encoding="utf-8")

    results: list[CheckResult] = []
    for spec in criteria.get("checks", []):
        if spec.get("type") == "structural":
            results.append(run_structural(doc, spec, ctx))
        elif spec.get("type") == "semantic":
            results.append(run_semantic(doc, spec, content))
    return results


def _expand(paths: list[str]) -> list[str]:
    files: list[str] = []
    for p in paths:
        matched = glob.glob(p, recursive=True)
        files.extend(matched if matched else [p])
    # de-dupe, keep only markdown docs
    seen, out = set(), []
    for f in files:
        if f.endswith(".md") and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def cmd_validate(args: argparse.Namespace) -> int:
    files = _expand(args.paths)
    if not files:
        print("docunit: no markdown documents matched.", file=sys.stderr)
        return 0

    id_index = _build_id_index()
    results_by_doc: dict[str, list[CheckResult]] = {}
    for path in files:
        try:
            results_by_doc[path] = _validate_one(path, id_index)
        except FileNotFoundError as exc:
            print(f"docunit: {exc}", file=sys.stderr)
            return 2
        except ValueError as exc:  # malformed frontmatter → a real, blocking failure
            results_by_doc[path] = [CheckResult(
                "parse", False, True, str(exc), kind="structural")]

    print(report.console(results_by_doc))
    print("\n" + report.summary_line(results_by_doc))

    if args.junit:
        Path(args.junit).write_text(report.junit(results_by_doc))
    if args.markdown:
        Path(args.markdown).write_text(report.markdown(results_by_doc))

    return sum(1 for rs in results_by_doc.values()
               for r in rs if r.is_blocking_failure)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docunit",
                                     description="Unit testing for business documents.")
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="Validate documents against their criteria.")
    v.add_argument("paths", nargs="+", help="Markdown files or globs.")
    v.add_argument("--junit", help="Write a JUnit XML report to this path.")
    v.add_argument("--markdown", help="Write a PR-comment markdown report to this path.")
    v.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
