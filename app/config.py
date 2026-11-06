"""Settings read from environment variables, with safe defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so local runs work without an extra dependency.

    Real environment variables always win over values in the file.
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    content_dir: Path = field(default_factory=lambda: Path(os.getenv("CONTENT_DIR", ROOT / "content")))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", ROOT / "data")))
    static_dir: Path = ROOT / "static"

    model: str = field(default_factory=lambda: os.getenv("CHATBOT_MODEL", "claude-opus-5-5"))
    # Chat is latency-sensitive and the answers are short lookups, so low effort is the right default.
    effort: str = field(default_factory=lambda: os.getenv("CHATBOT_EFFORT", "low"))

    # Demo mode (scripted answers) when no API key is configured.
    demo_mode: bool = field(default_factory=lambda: not os.getenv("ANTHROPIC_API_KEY"))

    pushover_token: str = field(default_factory=lambda: os.getenv("PUSHOVER_TOKEN", ""))
    pushover_user: str = field(default_factory=lambda: os.getenv("PUSHOVER_USER", ""))

    # Abuse limits: a public chatbot spends your API budget on every message.
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "12")))
    max_message_chars: int = 1000
    max_turns_per_session: int = 30
    max_sessions: int = 500


settings = Settings()
