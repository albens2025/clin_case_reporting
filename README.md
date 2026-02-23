# WhatsApp AMIE + NEJM History Agent

This repository now includes a production-ready starter backend for collecting
structured clinical history over WhatsApp, inspired by AMIE-style interviewing
and guided by NEJM-like clinicopathologic case-discussion patterns.

The goal is **history collection and clinician handoff**, not diagnosis.

## What this agent does

- Accepts incoming WhatsApp messages via a Twilio webhook
- Maintains per-patient interview state in SQLite
- Progresses through a structured interview flow:
  - chief complaint
  - HPI
  - PMH
  - medications/allergies
  - family/social history
  - red flags
  - summary for handoff
- Uses a curated NEJM-style teaching-pattern library to ask higher-yield
  follow-up questions
- Escalates obvious emergency language with immediate safety messaging

## Project structure

- `app/main.py` — FastAPI app + Twilio webhook endpoint
- `app/interviewer.py` — AMIE-style interview logic and OpenAI integration
- `app/knowledge.py` — NEJM pattern retrieval utilities
- `app/store.py` — SQLite persistence for sessions and message transcripts
- `app/config.py` — environment-based settings
- `data/nejm_case_discussions.json` — curated case-discussion pattern library
- `tests/` — lightweight tests for retrieval and fallback conversation flow
- `index.html` — legacy static case-report checklist page (kept intact)

## Quick start

### 1) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure environment

```bash
cp .env.example .env
```

Required:

- `OPENAI_API_KEY` for model-backed questioning

Optional:

- `VERIFY_TWILIO_SIGNATURE=true` and `TWILIO_AUTH_TOKEN=...` for webhook auth

### 3) Run the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4) Connect Twilio WhatsApp Sandbox

In Twilio Console, set the incoming webhook for your WhatsApp number/sandbox to:

`https://<your-public-url>/webhooks/whatsapp/twilio`

For local development, you can use a tunnel provider (for example ngrok).

## API endpoints

- `GET /health` — service and knowledge status
- `POST /webhooks/whatsapp/twilio` — Twilio inbound message webhook
- `GET /sessions/{phone_number}` — inspect session state/transcript (debug)

## Important safeguards

- This agent should be used for **intake/history collection** only.
- It should not provide final diagnoses or treatment decisions.
- Route urgent/emergent symptoms to local emergency services.
- Store and process patient data according to your institution's privacy and
  compliance requirements (HIPAA/GDPR/etc.).

## About NEJM discussion content

The included dataset contains **synthetic teaching pearls** and discussion
patterns inspired by clinicopathologic case formats. It intentionally avoids
full-text copying. For real deployments, replace with your own licensed or
institution-approved summaries.
