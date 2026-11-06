"""FastAPI app: serves the chat UI and the JSON API it calls."""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import storage
from .config import settings
from .content import load_profile
from .schemas import ChatRequest, ChatResponse, ContactRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("career-chat")


class RateLimiter:
    """Sliding one-minute window per client IP. In-memory, single process."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            return True


def create_app(engine=None, rate_limit_per_minute: int | None = None) -> FastAPI:
    """Build the app. Tests pass their own engine; otherwise pick Claude or demo mode."""
    if engine is None:
        if settings.demo_mode:
            from .demo import DemoChat
            engine = DemoChat()
            log.info("No ANTHROPIC_API_KEY set: running in DEMO mode with scripted answers.")
        else:
            from .llm import ClaudeChat
            engine = ClaudeChat()
            log.info("Running with Claude model %s", settings.model)
    mode = "demo" if engine.__class__.__name__ == "DemoChat" else "live"

    app = FastAPI(title="Career Conversation Chatbot", docs_url=None, redoc_url=None)
    limiter = RateLimiter(rate_limit_per_minute or settings.rate_limit_per_minute)

    def client_key(request: Request) -> str:
        # Behind a proxy (e.g. Hugging Face Spaces) the visitor's IP is the first X-Forwarded-For entry.
        fwd = request.headers.get("x-forwarded-for", "")
        return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "mode": mode}

    @app.get("/api/profile")
    def profile() -> dict:
        return {**load_profile(), "mode": mode}

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest, request: Request) -> ChatResponse:
        if len(body.message) > settings.max_message_chars:
            raise HTTPException(413, f"Keep questions under {settings.max_message_chars} characters.")
        if not limiter.allow(client_key(request)):
            raise HTTPException(429, "You're sending messages quickly. Wait a minute and try again.")
        from .llm import ChatUnavailable  # imported here so demo mode never needs the SDK configured

        try:
            # The SDK call is blocking; run it off the event loop.
            result = await run_in_threadpool(engine.chat, body.session_id, body.message)
        except ChatUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        return ChatResponse(mode=mode, **result.__dict__)

    @app.post("/api/contact")
    def contact(body: ContactRequest, request: Request) -> dict:
        if not limiter.allow(client_key(request)):
            raise HTTPException(429, "Too many requests. Wait a minute and try again.")
        storage.save_contact(body.name, body.email, body.company, body.reason, session_id=body.session_id)
        return {"ok": True}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(settings.static_dir / "index.html")

    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    return app


app = create_app()
