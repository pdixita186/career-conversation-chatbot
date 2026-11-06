"""Saves unanswered questions and contact requests, and optionally sends a push notification."""

from __future__ import annotations

import json
import logging
import threading
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .config import settings

log = logging.getLogger(__name__)
_lock = threading.Lock()


def _append(filename: str, record: dict, data_dir: Path | None = None) -> dict:
    folder = data_dir or settings.data_dir
    folder.mkdir(parents=True, exist_ok=True)
    record = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
    with _lock, open(folder / filename, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def notify(message: str) -> bool:
    """Send a Pushover notification if it's configured. Never raises."""
    if not (settings.pushover_token and settings.pushover_user):
        return False
    body = urllib.parse.urlencode(
        {"token": settings.pushover_token, "user": settings.pushover_user, "message": message[:1000]}
    ).encode()
    try:
        with urllib.request.urlopen("https://api.pushover.net/1/messages.json", data=body, timeout=5) as r:
            return r.status == 200
    except Exception as exc:  # notification failure must never break the chat
        log.warning("Push notification failed: %s", exc)
        return False


def save_unknown_question(question: str, session_id: str) -> dict:
    record = _append("unknown_questions.jsonl", {"question": question, "session_id": session_id})
    notify(f"Unanswered question: {question}")
    return record


def save_contact(
    name: str, email: str, company: str = "", reason: str = "", note: str = "", session_id: str = "", via: str = "form"
) -> dict:
    record = _append(
        "contacts.jsonl",
        {"name": name, "email": email, "company": company, "reason": reason, "note": note,
         "session_id": session_id, "via": via},
    )
    who = f"{name} ({company})" if company else name
    notify(f"New contact: {who} <{email}> — {reason or 'no reason given'}")
    return record
