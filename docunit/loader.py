"""Load and parse a business document into frontmatter + sections."""
from __future__ import annotations

import io
from pathlib import Path

import frontmatter
import yaml

from .models import Document, Section


def parse_sections(body: str) -> dict[str, Section]:
    """Split a markdown body into H2 (`## `) sections, preserving order."""
    sections: dict[str, Section] = {}
    current_title: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_title is not None:
            sections[current_title] = Section(
                title=current_title, body="\n".join(current_lines).strip()
            )

    for line in body.splitlines():
        if line.startswith("## "):
            flush()
            current_title = line[3:].strip()
            current_lines = []
        else:
            if current_title is not None:
                current_lines.append(line)
    flush()
    return sections


def load(path: str | Path) -> Document:
    """Parse a document file. Raises ValueError on malformed frontmatter."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    try:
        post = frontmatter.loads(text)
    except yaml.YAMLError as exc:  # malformed YAML frontmatter
        raise ValueError(f"{path}: invalid YAML frontmatter: {exc}") from exc

    return Document(
        path=str(path),
        frontmatter=dict(post.metadata),
        sections=parse_sections(post.content),
        raw_body=post.content,
    )


def load_criteria(path: str | Path) -> dict:
    """Load a criteria YAML file (e.g. criteria/charter.criteria.yaml)."""
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)
