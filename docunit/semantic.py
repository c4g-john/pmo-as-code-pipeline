"""AI-graded semantic checks. These are ADVISORY — they never block a merge.

Each check asks a model to score one rubric criterion against the document and
return structured JSON: {score: 0..1, pass: bool, rationale: str}. Results are
cached by content hash so unchanged documents are not re-billed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .models import CheckResult, Document

DEFAULT_MODEL = os.environ.get("DOCUNIT_MODEL", "claude-sonnet-5")
CACHE_DIR = Path(os.environ.get("DOCUNIT_CACHE", ".docunit-cache"))

_SYSTEM = (
    "You are a meticulous document auditor. You are given one audit criterion "
    "and a business document. Judge only that criterion. Respond with a single "
    "JSON object and nothing else: "
    '{"score": <number 0..1>, "pass": <true|false>, "rationale": "<one or two '
    'sentences citing specifics from the document>"}.'
)


def _cache_key(model: str, prompt: str, content: str) -> str:
    h = hashlib.sha256()
    h.update(model.encode())
    h.update(b"\x00")
    h.update(prompt.encode())
    h.update(b"\x00")
    h.update(content.encode())
    return h.hexdigest()


def _cache_get(key: str) -> dict | None:
    f = CACHE_DIR / f"{key}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            return None
    return None


def _cache_put(key: str, value: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{key}.json").write_text(json.dumps(value))
    except OSError:
        pass  # caching is best-effort


def _grade(prompt: str, content: str, model: str) -> dict:
    """Call the Anthropic API and return the parsed JSON grade."""
    import anthropic  # imported lazily so structural-only runs need no dependency

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    message = client.messages.create(
        model=model,
        max_tokens=400,
        temperature=0,
        system=_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"AUDIT CRITERION:\n{prompt}\n\nDOCUMENT:\n{content}",
        }],
    )
    text = "".join(block.text for block in message.content
                   if getattr(block, "type", None) == "text").strip()
    # tolerate models that wrap JSON in prose or fences
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON in model response: {text[:120]!r}")
    return json.loads(text[start:end + 1])


def run_semantic(doc: Document, spec: dict, content: str) -> CheckResult:
    check_id = spec["id"]
    prompt = spec.get("prompt", "").strip()
    threshold = float(spec.get("pass_threshold", 0.7))
    model = spec.get("model", DEFAULT_MODEL)

    # Advisory checks are never blocking regardless of criteria config.
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return CheckResult(check_id, True, False,
                           "skipped — no ANTHROPIC_API_KEY (advisory only)",
                           kind="semantic", score=None)

    key = _cache_key(model, prompt, content)
    grade = _cache_get(key)
    if grade is None:
        try:
            grade = _grade(prompt, content, model)
            _cache_put(key, grade)
        except Exception as exc:
            return CheckResult(check_id, True, False,
                               f"advisory check unavailable: {exc}",
                               kind="semantic", score=None)

    score = float(grade.get("score", 0.0))
    passed = bool(grade.get("pass", score >= threshold))
    rationale = str(grade.get("rationale", "")).strip()
    return CheckResult(check_id, passed, False,
                       rationale or f"score {score:.2f} (threshold {threshold:.2f})",
                       kind="semantic", score=score)
