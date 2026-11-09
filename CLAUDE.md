# CLAUDE.md

Guidance for working in this repo. See `README.md` for the product overview and Twilio setup.

## What this is

Northwind Outfitters voice/chat agent (FastAPI). Twilio handles phone audio and speech-to-text; OpenAI chat completions decide replies and call tools. All catalog, order, and promotion facts come from tools reading `data/*.json`. The data is synthetic.

## Commands

```bash
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="..."        # required for real model calls
uvicorn app.main:app --reload      # browser test page at http://127.0.0.1:8000
python -m pytest -q                # full suite (see known issue below)
```

Tests use a scripted fake model; they never call OpenAI or Twilio.

## Layout

- `app/agent.py`: `run_turn` loop (max 4 tool steps), system prompt, `make_openai_llm` (httpx, 30s timeout). Raises `LLMError` on failure.
- `app/tools.py`: tool implementations, `TOOL_SCHEMAS` (OpenAI function schemas), and `DISPATCH` (name → function). Add a tool in all three places.
- `app/sessions.py`: in-memory history per session/call, capped at 20 messages.
- `app/main.py`: `/` (test page), `/api/chat`, `/api/leads` (admin), `/twilio/voice`, `/twilio/turn`.
- `app/data.py`: loads JSON from `data/`.
- `static/index.html`: browser test UI.
- `tests/`: `test_agent.py`, `test_tools.py`, `test_api.py`.

## Rules that are enforced in code (keep them enforced in code)

- Order details are returned only when order number AND email both match (`get_order_status`).
- Leads are saved only when `consent` is true and the email is valid (`save_lead`).
- `/api/leads` requires `Authorization: Bearer $ADMIN_TOKEN` and is refused when the token is unset.
- Twilio signature is verified when `TWILIO_AUTH_TOKEN` is set. Don't remove the check.
- Conversation history stores only user and assistant text, never tool results.
- The system prompt tells the model to use tools for every fact and to keep replies short with no lists, links, or emojis. Replies are spoken, so keep that format.

## Conventions

- Tool functions return plain dicts that are JSON-serialized by `_execute`. Bad arguments produce `{"error": "invalid arguments"}`, not an exception.
- Never send real customer data or real API keys in code, tests, or fixtures. Use `.test` / `example` domains like the existing data.
- Secrets go in the shell environment or a local `.env` (git-ignored). Never commit them.

## Known issues

- `tests/test_api.py` fails at collection: FastAPI `Form` needs `python-multipart`, which is missing from `requirements.txt`. Add it (and install it into `.venv`) before running the full suite. Without it, `pytest --ignore tests/test_api.py` runs the other 16 tests, which pass.
- Leads and sessions are in memory and reset on restart. Don't rely on them for persistence.
- No human escalation path yet.
