"""Scripted chat engine used when no API key is configured.

Lets you run and demo the full UI without paying for API calls. It does not use Claude.
"""

from __future__ import annotations

from . import storage
from .content import load_demo_answers, load_profile
from .schemas import ChatResult


class DemoChat:
    def __init__(self) -> None:
        self.data = load_demo_answers()
        self.first = load_profile().get("first_name", "the candidate")

    def chat(self, session_id: str, text: str) -> ChatResult:
        q = text.lower()
        if any(k in q for k in self.data.get("contact_keywords", [])):
            return ChatResult(reply=f"Happy to connect you. Leave your details and {self.first} will reply personally.")
        for item in self.data.get("answers", []):
            if any(k in q for k in item["keywords"]):
                return ChatResult(reply=item["reply"], sources=item.get("sources", []))
        storage.save_unknown_question(text[:500], session_id)
        return ChatResult(
            reply=f"I don't have that in {self.first}'s notes, so I won't guess. I've saved your question and "
            f"{self.first} will answer it personally.",
            question_logged=True,
        )
