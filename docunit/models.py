"""Shared data types for docunit."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Section:
    """A single H2 section of a document body."""
    title: str
    body: str

    @property
    def list_items(self) -> list[str]:
        """Top-level markdown bullet items in this section, comments stripped."""
        items: list[str] = []
        for line in self.body.splitlines():
            stripped = line.strip()
            if stripped.startswith(("- ", "* ")):
                text = stripped[2:].strip()
                # drop HTML-comment-only placeholder bullets from the template
                if text.startswith("<!--") or not text:
                    continue
                items.append(text)
        return items

    @property
    def is_empty(self) -> bool:
        """A section counts as empty if it has no prose or list items once
        template HTML comments and whitespace are removed."""
        meaningful = []
        for line in self.body.splitlines():
            s = line.strip()
            if not s or s.startswith("<!--") and s.endswith("-->"):
                continue
            # strip inline comment fragments
            if s.startswith("<!--") or s.endswith("-->"):
                continue
            meaningful.append(s)
        return len("".join(meaningful).strip()) == 0


@dataclass
class Document:
    """A parsed business document: frontmatter + ordered body sections."""
    path: str
    frontmatter: dict
    sections: dict[str, Section] = field(default_factory=dict)
    raw_body: str = ""

    @property
    def id(self) -> Optional[str]:
        return self.frontmatter.get("id")

    @property
    def kind(self) -> Optional[str]:
        return self.frontmatter.get("kind")

    def section(self, title: str) -> Optional[Section]:
        return self.sections.get(title)


@dataclass
class CheckResult:
    """The outcome of one audit check against one document."""
    check_id: str
    passed: bool
    blocking: bool
    detail: str
    kind: str = "structural"           # structural | semantic
    score: Optional[float] = None      # semantic checks only, 0..1

    @property
    def is_blocking_failure(self) -> bool:
        return self.blocking and not self.passed
