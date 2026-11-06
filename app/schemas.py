"""Request/response shapes shared by the API and the chat engines."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, field_validator

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SESSION_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(value.strip()))


@dataclass
class ChatResult:
    reply: str
    sources: list[str] = field(default_factory=list)
    question_logged: bool = False
    contact_saved: bool = False


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1)

    @field_validator("session_id")
    @classmethod
    def _session(cls, v: str) -> str:
        if not SESSION_RE.match(v):
            raise ValueError("session_id must be 8–64 letters, digits or hyphens")
        return v

    @field_validator("message")
    @classmethod
    def _message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message is empty")
        return v


class ChatResponse(BaseModel):
    reply: str
    sources: list[str]
    question_logged: bool
    contact_saved: bool
    mode: str


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=200)
    company: str = Field(default="", max_length=120)
    reason: str = Field(default="", max_length=120)
    session_id: str = Field(default="", max_length=64)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Enter your name.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        if not is_valid_email(v):
            raise ValueError("Enter a valid email, like you@company.com.")
        return v.strip()
