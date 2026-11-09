# Northwind Voice Commerce Agent

A phone and chat assistant for an online outdoor-gear shop (synthetic store). It answers product and stock questions, checks order status, shares current promotions, makes recommendations, and captures marketing leads with the caller's consent.

- **Phone:** Twilio handles the call and speech-to-text. Each caller turn goes to the agent.
- **Brain:** the OpenAI chat API decides what to say and calls tools. Every product, price, order and promotion fact comes from a tool, never from the model's memory.
- **Browser test page:** type or use the mic in Chrome, so you can test without a phone.

## Privacy rules (enforced in code, not only in the prompt)

- Order details are returned only when the order number **and** the email match. Otherwise nothing about the order is revealed.
- A lead is saved only when `consent` is true. The model must ask first.
- `/api/leads` needs an `ADMIN_TOKEN`. It is refused when the token is unset.
- Tool data is never stored in conversation history, only the spoken text.

## Run it locally

```bash
cd voice-commerce-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="<your key>"
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and try:

- "Do you have a waterproof running shoe?"
- "What's on sale?"
- "Check order NW-1001 for amara.test@example.com"
- "Can you recommend a warm layer under $80?"
- "Sign me up for updates. My name is Ana, ana@example.com, I'm interested in running shoes." (The agent should ask for consent first.)

## Test it

```bash
python -m pytest -q   # 26 tests: tools, the agent loop, API, and Twilio endpoints
```

The tests use a fake model, so they don't call OpenAI or Twilio.

## Connect a phone number (Twilio)

1. Create a Twilio account and buy a phone number with voice capability.
2. Run the server locally, then expose it publicly, for example with ngrok:
   ```bash
   ngrok http 8000
   ```
3. Set `PUBLIC_BASE_URL` to the ngrok https address, and `TWILIO_AUTH_TOKEN` to your Twilio auth token, so Twilio requests are verified:
   ```bash
   export PUBLIC_BASE_URL="https://<your-ngrok-address>"
   export TWILIO_AUTH_TOKEN="<your Twilio auth token>"
   ```
4. In the Twilio console, open the phone number. Under Voice Configuration, set "A call comes in" to Webhook, `https://<your-ngrok-address>/twilio/voice`, HTTP POST.
5. Call the number.

Don't commit the Twilio token or OpenAI key. Keep them in your terminal or a local `.env` file, which `.gitignore` excludes.

## Known limits (v1)

- **Speech:** Twilio's built-in speech recognition and voice handle the phone audio. OpenAI does the reasoning. Switching to OpenAI's realtime speech is a later step.
- **Storage:** conversations and leads are in memory. They reset when the server restarts. Use a database before real customers call.
- **Data:** the catalog, orders and promotions are synthetic. Connect them to the real store system before use.
- **Live calls:** the Twilio signature check is in place, but I haven't tested against a real Twilio call. Test with a real call before relying on it.
- **Escalation:** there is no transfer to a human yet.

## Structure

```
app/
  agent.py      conversation loop and OpenAI calls
  tools.py      product, order, promotion and lead tools with privacy checks
  sessions.py   short conversation history per call
  main.py       chat API, leads API, Twilio webhooks
data/           synthetic catalog, orders, promotions
static/         browser test page
tests/          pytest suite
```
