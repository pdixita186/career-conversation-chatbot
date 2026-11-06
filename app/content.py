"""Loads the candidate's profile and documents from the content folder."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import settings

DOC_SUFFIXES = {".md", ".txt"}


@dataclass(frozen=True)
class Document:
    name: str
    text: str


@lru_cache(maxsize=1)
def load_profile(content_dir: Path | None = None) -> dict:
    path = (content_dir or settings.content_dir) / "profile.json"
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_documents(content_dir: Path | None = None) -> tuple[Document, ...]:
    """All documents, sorted by name so the system prompt is byte-identical between
    requests (required for prompt caching to hit)."""
    folder = (content_dir or settings.content_dir) / "documents"
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in DOC_SUFFIXES)
    return tuple(Document(p.name, p.read_text(encoding="utf-8").strip()) for p in files)


@lru_cache(maxsize=1)
def load_demo_answers(content_dir: Path | None = None) -> dict:
    path = (content_dir or settings.content_dir) / "demo-answers.json"
    if not path.is_file():
        return {"answers": [], "contact_keywords": []}
    return json.loads(path.read_text(encoding="utf-8"))
