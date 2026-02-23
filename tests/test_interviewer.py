from pathlib import Path

from app.config import Settings
from app.interviewer import AmieNejmInterviewer
from app.knowledge import NejmPatternLibrary
from app.models import InterviewState


def _settings() -> Settings:
    return Settings(
        openai_api_key="",
        openai_model="gpt-4.1-mini",
        database_path=Path("data/sessions.db").resolve(),
        nejm_patterns_path=Path("data/nejm_case_discussions.json").resolve(),
        verify_twilio_signature=False,
        twilio_auth_token="",
        max_context_messages=16,
        max_knowledge_snippets=3,
    )


def test_interviewer_progresses_without_llm() -> None:
    knowledge = NejmPatternLibrary.from_json_file(
        Path("data/nejm_case_discussions.json").resolve()
    )
    interviewer = AmieNejmInterviewer(settings=_settings(), knowledge=knowledge)
    state = InterviewState(phone_number="whatsapp:+10000000000")

    first = interviewer.generate_reply("Hi", state, history=[])
    assert "main problem" in first.lower()
    assert state.phase == "chief_complaint"

    second = interviewer.generate_reply("Chest discomfort", state, history=[])
    assert "when did this start" in second.lower()
    assert state.phase == "hpi"


def test_emergency_message_is_escalated() -> None:
    knowledge = NejmPatternLibrary(patterns=[])
    interviewer = AmieNejmInterviewer(settings=_settings(), knowledge=knowledge)
    state = InterviewState(phone_number="whatsapp:+10000000001")

    reply = interviewer.generate_reply("I have severe chest pain and can't breathe", state, [])
    assert "emergency" in reply.lower()
    assert state.urgency == "emergency"
