# Career Conversation Chatbot

An AI assistant that sits on my portfolio site and answers recruiters' questions about my experience, skills and projects. You get the answers a first screening call would give, without waiting for one.

> **Project status: working prototype, not yet deployed.** The app runs end to end: a FastAPI backend, Claude answering from my documents, and the chat interface. It still uses **sample content** (a fictional candidate) and isn't hosted publicly yet. See the [roadmap](#roadmap).

![Chat screen: the assistant answers a question about past experience and admits when it doesn't know something](docs/screenshots/chat.png)

## The problem it solves

Recruiters spend a few minutes on each candidate. A resume can't answer follow-up questions like *"What did they actually own on that project?"* or *"Are they open to remote work?"*. This chatbot answers those questions on the spot, using only my real resume and project notes. When it doesn't know something, it says so and passes the question to me.

## How it works

1. **The visitor asks a question** in the chat, or picks a suggested one.
2. **Claude answers from my documents only** (resume, project notes, career goals) and the reply shows which document it came from.
3. **If the answer isn't in the documents, it doesn't guess.** Claude calls a `record_unknown_question` tool, the question is saved, and I get a notification so I can answer it personally.
4. **Visitors can leave their contact details**, through the form or just by typing them in the chat (a `record_contact` tool). I get notified either way.

The rule against guessing is deliberate. A chatbot that makes up a salary figure or a skill does more damage to a candidate than having no chatbot at all.

## Screens

| Welcome | Contact capture | Profile on mobile |
|---|---|---|
| ![Welcome screen](docs/screenshots/welcome.png) | ![Contact form inside the chat](docs/screenshots/contact.png) | ![Profile drawer on a phone](docs/screenshots/mobile-profile.png) |

## Run it locally

You need Python 3.10 or newer.

```bash
git clone https://github.com/pdixita186/career-conversation-chatbot.git
```

```bash
cd career-conversation-chatbot
```

```bash
pip install -r requirements.txt
```

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000.

**Without an API key the app runs in demo mode**, with scripted answers, so you can try the whole interface for free. To get real answers from Claude, copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. Unanswered questions and contact requests are saved to `data/` as JSON Lines files.

Run the tests (no API key or network needed):

```bash
pip install -r requirements-dev.txt
```

```bash
pytest
```

## Make it about you

All the personal content is in `content/`, so you can change it without touching the code:

| File | What it controls |
|---|---|
| `content/profile.json` | Name, headline, summary, experience timeline, skills, links, suggested questions |
| `content/documents/*.md` | What Claude is allowed to answer from. Add or remove files freely. |
| `content/demo-answers.json` | Scripted replies for demo mode only |

Set `"is_sample": false` in `profile.json` once the content is real, and the "Sample content" label disappears.

## Tech stack

| Part | Technology |
|---|---|
| Interface | HTML, CSS and vanilla JavaScript, with no build step |
| Backend | Python, FastAPI |
| AI | Claude via the Anthropic Python SDK, with tool use for logging questions and contacts |
| Cost control | Prompt caching on the documents, low reasoning effort for quick replies, per-visitor rate limit |
| Notifications | Optional Pushover push notifications |

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | none (demo mode) | Claude API key |
| `PUSHOVER_TOKEN`, `PUSHOVER_USER` | none | Push notifications for new questions and contacts |
| `CHATBOT_MODEL` | `claude-opus-5-5` | Claude model |
| `CHATBOT_EFFORT` | `low` | Reasoning effort (`low` keeps replies fast and cheap) |
| `RATE_LIMIT_PER_MINUTE` | `12` | Messages per visitor IP per minute |
| `DATA_DIR` | `data` | Where questions and contacts are saved |

## Roadmap

- [x] Clickable UI mockup
- [x] FastAPI backend with Claude answering from documents
- [x] "Don't guess" behavior: unknown questions are logged
- [x] Contact capture through the form and through the chat
- [x] Demo mode, rate limiting and automated tests
- [ ] Replace the sample content with my real resume and project notes
- [ ] Deploy publicly (e.g. Hugging Face Spaces or Render) and link it from my portfolio
- [ ] Move saved questions and contacts from local files to a database, so they survive redeploys
- [ ] Measure how many questions get answered vs. passed to me, and fill the gaps

## Known limitations

- Conversations are stored in server memory. A restart clears them, and running several server instances would split them.
- Saved questions and contacts are local files. On hosts with temporary disks they disappear on redeploy, so a database is needed before going public.
- The rate limiter is per server instance and keyed on IP address. It's enough to stop casual abuse, not a determined attacker.

## Project structure

```
career-conversation-chatbot/
├── app/
│   ├── main.py          # FastAPI routes, rate limiting
│   ├── llm.py           # Claude conversation engine and tools
│   ├── demo.py          # Scripted engine used without an API key
│   ├── content.py       # Loads profile and documents
│   ├── storage.py       # Saves questions/contacts, sends notifications
│   ├── schemas.py       # Request/response validation
│   └── config.py        # Settings from environment variables
├── content/             # Everything personal: profile + documents
├── static/              # Chat interface (index.html, app.js, styles.css)
├── tests/               # pytest suite (no network needed)
├── mockup/              # Original single-file clickable mockup
└── docs/screenshots/    # Images used in this README
```

## Author

Built by [@pdixita186](https://github.com/pdixita186).
