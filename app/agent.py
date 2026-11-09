"""The conversation loop: the model reasons, tools act, and every answer is grounded in tool results."""
import json
import os
from typing import Callable

import httpx

from .tools import DISPATCH, TOOL_SCHEMAS

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MAX_TOOL_STEPS = 4
STORE_NAME = "Northwind Outfitters"

SYSTEM_PROMPT = f"""You are the phone and chat assistant for {STORE_NAME}, an outdoor clothing and gear shop.
You help with products, stock, order status, current promotions, and recommendations.
Rules:
- Use the tools for every product, price, stock, order or promotion fact. Never guess or invent them.
- For order status you need BOTH the order number and the email used to order. Ask for whatever is missing.
- Only mention promotions the get_promotions tool returns.
- Save a lead only if the caller clearly agrees to be contacted. Ask first, then call save_lead with consent true.
- Keep replies short and spoken-friendly: one or two sentences, no lists, no links, no emojis.
- If you cannot help, say so and offer to have the team follow up by email."""

FALLBACK_REPLY = "Sorry, I'm having trouble right now. Please try again in a few minutes."

LLM = Callable[[list[dict], list[dict]], dict]


class LLMError(RuntimeError):
    """The model call failed."""


def _execute(call: dict) -> str:
    name = call.get("function", {}).get("name", "")
    function = DISPATCH.get(name)
    if function is None:
        return json.dumps({"error": f"unknown tool {name}"})
    try:
        arguments = json.loads(call["function"].get("arguments") or "{}")
        result = function(**arguments)
    except (TypeError, ValueError, KeyError):
        return json.dumps({"error": "invalid arguments"})
    return json.dumps(result)


def run_turn(history: list[dict], user_text: str, llm: LLM) -> str:
    """Answer one caller turn. `history` keeps only user and assistant text, never tool data."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": user_text}]
    reply = FALLBACK_REPLY
    for _ in range(MAX_TOOL_STEPS):
        message = llm(messages, TOOL_SCHEMAS)
        calls = message.get("tool_calls") or []
        if not calls:
            reply = (message.get("content") or "").strip() or FALLBACK_REPLY
            break
        messages.append(message)
        for call in calls:
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": _execute(call)})
    history.extend([{"role": "user", "content": user_text}, {"role": "assistant", "content": reply}])
    return reply


def make_openai_llm(api_key: str, model: str | None = None, transport: httpx.BaseTransport | None = None) -> LLM:
    model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def llm(messages: list[dict], tools: list[dict]) -> dict:
        body = {"model": model, "messages": messages, "tools": tools, "temperature": 0.2}
        try:
            with httpx.Client(timeout=30, transport=transport) as client:
                response = client.post(OPENAI_URL, headers={"Authorization": f"Bearer {api_key}"}, json=body)
        except httpx.HTTPError as exc:
            raise LLMError(f"could not reach the OpenAI API: {exc.__class__.__name__}") from exc
        if response.status_code >= 400:
            raise LLMError(f"OpenAI API returned HTTP {response.status_code}")
        try:
            return response.json()["choices"][0]["message"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError("OpenAI API returned an unexpected response") from exc

    return llm
