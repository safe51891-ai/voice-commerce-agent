import json

from app.agent import FALLBACK_REPLY, MAX_TOOL_STEPS, run_turn


def tool_call(call_id: str, name: str, arguments: dict) -> dict:
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def scripted(*messages: dict):
    """A fake model that returns the given assistant messages in order."""
    queue = list(messages)
    seen: list[list[dict]] = []

    def llm(messages_sent, tools):
        seen.append(messages_sent)
        return queue.pop(0)

    llm.seen = seen
    return llm


def test_plain_answer_without_tools():
    history: list[dict] = []
    reply = run_turn(history, "hello", scripted({"role": "assistant", "content": "Hi there!"}))
    assert reply == "Hi there!"
    assert history == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]


def test_tool_result_is_fed_back_and_only_text_is_stored():
    history: list[dict] = []
    llm = scripted(
        {"role": "assistant", "content": None, "tool_calls": [tool_call("c1", "get_promotions", {})]},
        {"role": "assistant", "content": "We have WINTER15, 15% off outerwear."},
    )
    reply = run_turn(history, "any deals?", llm)
    assert reply == "We have WINTER15, 15% off outerwear."
    tool_messages = [m for m in llm.seen[1] if m["role"] == "tool"]
    assert tool_messages and "WINTER15" in tool_messages[0]["content"]
    assert all(m["role"] in ("user", "assistant") for m in history)


def test_unknown_tool_returns_error_instead_of_crashing():
    llm = scripted(
        {"role": "assistant", "content": None, "tool_calls": [tool_call("c1", "delete_everything", {})]},
        {"role": "assistant", "content": "Sorry, I can't do that."},
    )
    assert run_turn([], "do it", llm) == "Sorry, I can't do that."
    tool_message = next(m for m in llm.seen[1] if m["role"] == "tool")
    assert "unknown tool" in tool_message["content"]


def test_bad_arguments_return_error_instead_of_crashing():
    llm = scripted(
        {"role": "assistant", "content": None, "tool_calls": [tool_call("c1", "get_order_status", {"order_id": "NW-1001"})]},
        {"role": "assistant", "content": "I need your email too."},
    )
    assert run_turn([], "where is my order", llm) == "I need your email too."
    tool_message = next(m for m in llm.seen[1] if m["role"] == "tool")
    assert "invalid arguments" in tool_message["content"]


def test_endless_tool_calls_stop_with_fallback():
    looping = {"role": "assistant", "content": None, "tool_calls": [tool_call("c", "get_promotions", {})]}
    llm = scripted(*([looping] * MAX_TOOL_STEPS))
    assert run_turn([], "loop", llm) == FALLBACK_REPLY


def test_order_lookup_end_to_end_hides_details_on_wrong_email():
    llm = scripted(
        {"role": "assistant", "content": None, "tool_calls": [
            tool_call("c1", "get_order_status", {"order_id": "NW-1001", "email": "wrong@example.com"})]},
        {"role": "assistant", "content": "I could not verify that order and email."},
    )
    run_turn([], "status of NW-1001", llm)
    tool_message = next(m for m in llm.seen[1] if m["role"] == "tool")
    assert "shipped" not in tool_message["content"]
