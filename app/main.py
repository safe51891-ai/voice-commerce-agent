"""FastAPI service: browser chat for testing, and Twilio phone webhooks for live calls."""
import os
from pathlib import Path
from xml.sax.saxutils import escape

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from twilio.request_validator import RequestValidator

from .agent import STORE_NAME, LLMError, make_openai_llm, run_turn
from .sessions import SessionStore
from .tools import LEADS

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="Northwind Voice Commerce Agent")
sessions = SessionStore()

GREETING = f"Thanks for calling {STORE_NAME}. I can help with products, order status, and current offers. How can I help?"
RETRY = "Sorry, I didn't catch that. Could you say it again?"
PHONE_FAILURE = "Sorry, we're having a technical problem. Please call back shortly. Goodbye."


def get_llm():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not set")
    return make_openai_llm(api_key)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=1000)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, str]:
    try:
        reply = run_turn(sessions.history(request.session_id), request.message, get_llm())
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"reply": reply}


@app.get("/api/leads")
def leads(request: Request) -> list[dict]:
    """Owner view of saved leads. Requires ADMIN_TOKEN; always refused when it is unset."""
    expected = os.getenv("ADMIN_TOKEN", "").strip()
    if not expected or request.headers.get("Authorization") != f"Bearer {expected}":
        raise HTTPException(status_code=403, detail="forbidden")
    return LEADS


# ---------- Twilio phone webhooks ----------

def _public_url(request: Request, path: str) -> str:
    base = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}{path}"


async def _verify_twilio(request: Request, path: str) -> None:
    """Reject requests not signed by Twilio. Enforced when TWILIO_AUTH_TOKEN is set."""
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not token:
        return
    form = dict(await request.form())
    signature = request.headers.get("X-Twilio-Signature", "")
    if not RequestValidator(token).validate(_public_url(request, path), form, signature):
        raise HTTPException(status_code=403, detail="invalid Twilio signature")


def _twiml(*parts: str) -> Response:
    body = "".join(parts)
    return Response(content=f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>', media_type="application/xml")


def _say(text: str) -> str:
    return f"<Say>{escape(text)}</Say>"


def _gather(action_url: str) -> str:
    return f'<Gather input="speech" action="{escape(action_url)}" method="POST" speechTimeout="auto" timeout="5"></Gather>'


@app.post("/twilio/voice")
async def twilio_voice(request: Request) -> Response:
    await _verify_twilio(request, "/twilio/voice")
    return _twiml(_say(GREETING), _gather(_public_url(request, "/twilio/turn")))


@app.post("/twilio/turn")
async def twilio_turn(request: Request, CallSid: str = Form(""), SpeechResult: str = Form("")) -> Response:
    await _verify_twilio(request, "/twilio/turn")
    turn_url = _public_url(request, "/twilio/turn")
    if not SpeechResult.strip():
        return _twiml(_say(RETRY), _gather(turn_url))
    try:
        reply = run_turn(sessions.history(CallSid or "unknown-call"), SpeechResult, get_llm())
    except (LLMError, HTTPException):
        return _twiml(_say(PHONE_FAILURE), "<Hangup/>")
    return _twiml(_say(reply), _gather(turn_url))
