from __future__ import annotations

import logging
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from .config import load_settings
from .interviewer import AmieNejmInterviewer
from .knowledge import NejmPatternLibrary
from .store import SessionStore

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = load_settings()
store = SessionStore(settings.database_path)
knowledge = NejmPatternLibrary.from_json_file(settings.nejm_patterns_path)
interviewer = AmieNejmInterviewer(settings=settings, knowledge=knowledge)

app = FastAPI(
    title="WhatsApp AMIE + NEJM History Agent",
    version="0.1.0",
    description="Collects structured medical history over WhatsApp for clinician handoff.",
)


def _validate_twilio_signature(request: Request, form_data: dict[str, Any]) -> None:
    if not settings.verify_twilio_signature:
        return
    if not settings.twilio_auth_token:
        raise HTTPException(
            status_code=500,
            detail="TWILIO_AUTH_TOKEN is required when signature verification is enabled.",
        )

    signature = request.headers.get("X-Twilio-Signature", "")
    validator = RequestValidator(settings.twilio_auth_token)
    valid = validator.validate(str(request.url), form_data, signature)
    if not valid:
        raise HTTPException(status_code=403, detail="Invalid Twilio signature.")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "model": settings.openai_model,
            "knowledge_patterns_loaded": len(knowledge.patterns),
        }
    )


@app.get("/sessions/{phone_number}")
async def get_session(phone_number: str) -> JSONResponse:
    state = store.get_or_create_state(phone_number)
    history = [msg.__dict__ for msg in store.recent_messages(phone_number, limit=50)]
    return JSONResponse({"state": state.to_record(), "messages": history})


@app.post("/webhooks/whatsapp/twilio")
async def twilio_whatsapp_webhook(request: Request) -> PlainTextResponse:
    form = await request.form()
    form_data = {key: str(value) for key, value in form.items()}
    _validate_twilio_signature(request, form_data)

    from_number = str(form_data.get("From", "")).strip()
    incoming_text = str(form_data.get("Body", "")).strip()

    if not from_number:
        raise HTTPException(status_code=400, detail="Missing 'From' in webhook payload.")

    if not incoming_text:
        response = MessagingResponse()
        response.message(
            "I did not receive any text. Please send your symptoms or main concern."
        )
        return PlainTextResponse(str(response), media_type="application/xml")

    state = store.get_or_create_state(from_number)
    store.append_message(from_number, "user", incoming_text)
    history = store.recent_messages(from_number, limit=settings.max_context_messages)

    reply = interviewer.generate_reply(incoming_text, state, history)
    if not reply.strip():
        reply = (
            "Thanks. I am still collecting your history. Could you tell me more about "
            "the symptom that concerns you most?"
        )

    store.append_message(from_number, "assistant", reply)
    store.save_state(state)

    twiml = MessagingResponse()
    twiml.message(reply)
    return PlainTextResponse(str(twiml), media_type="application/xml")
