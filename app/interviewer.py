from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from .config import Settings
from .knowledge import NejmPatternLibrary
from .models import ConversationMessage, InterviewState, PHASES

logger = logging.getLogger(__name__)

LIST_NOTE_KEYS = {"associated_symptoms", "red_flags"}


class AmieNejmInterviewer:
    """
    AMIE-style history-taking engine that can be guided by NEJM case patterns.

    The model is instructed to:
    - ask one concise question at a time
    - gather structured history
    - keep differential questions broad and non-diagnostic
    - escalate emergencies immediately
    """

    def __init__(self, settings: Settings, knowledge: NejmPatternLibrary):
        self.settings = settings
        self.knowledge = knowledge
        self.client = (
            OpenAI(api_key=settings.openai_api_key)
            if settings.openai_api_key
            else None
        )

    def generate_reply(
        self,
        user_text: str,
        state: InterviewState,
        history: list[ConversationMessage],
    ) -> str:
        if self._looks_emergent(user_text):
            state.urgency = "emergency"
            state.notes["red_flags"] = sorted(
                set(state.notes.get("red_flags", [])) | {"possible emergency symptom"}
            )
            return (
                "Thanks for sharing this. Some symptoms you mentioned might be urgent. "
                "If there is severe chest pain, trouble breathing, weakness on one side, "
                "fainting, confusion, or heavy bleeding, please call local emergency "
                "services now. I can continue collecting history after you are safe."
            )

        if state.phase == "introduction":
            state.phase = "chief_complaint"
            return (
                "Hi, I am your clinical history assistant. I will ask focused questions "
                "to collect your history for a clinician. I cannot diagnose or replace "
                "emergency care. What is the main problem bothering you today?"
            )

        retrieved = self.knowledge.retrieve(
            user_text=user_text,
            notes=state.notes,
            limit=self.settings.max_knowledge_snippets,
        )

        if self.client is not None:
            try:
                response = self._generate_with_llm(
                    user_text=user_text,
                    state=state,
                    history=history,
                    retrieved_snippets=[pattern.render_snippet() for pattern in retrieved],
                )
                self._apply_structured_updates(state, response)
                return str(response.get("reply_to_patient", "")).strip()
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.exception("LLM generation failed, using fallback: %s", exc)

        return self._fallback_reply(user_text=user_text, state=state)

    def _generate_with_llm(
        self,
        user_text: str,
        state: InterviewState,
        history: list[ConversationMessage],
        retrieved_snippets: list[str],
    ) -> dict[str, Any]:
        assert self.client is not None

        system_prompt = (
            "You are an AMIE-inspired clinical history-taking assistant over WhatsApp. "
            "Your role is to gather a complete, structured history before handoff to a "
            "human clinician.\n\n"
            "Rules:\n"
            "1) Ask one concise high-yield question per turn.\n"
            "2) Use patient language; keep tone empathetic and clear.\n"
            "3) Do not provide diagnosis or treatment plans.\n"
            "4) Watch for emergencies. If symptoms suggest emergency, clearly instruct "
            "the patient to call emergency services immediately.\n"
            "5) Use the provided NEJM-style case discussion pearls as heuristics for "
            "which clarifying question to ask next.\n"
            "6) Maintain interview progression: chief complaint -> HPI -> PMH -> "
            "medications/allergies -> family/social history -> red flags -> summary.\n"
            "7) Keep the patient reply under 550 characters.\n\n"
            "Return strict JSON with keys:\n"
            "- reply_to_patient (string)\n"
            "- next_phase (one of: introduction, chief_complaint, hpi, pmh, "
            "meds_allergies, family_social, ros_red_flags, summary)\n"
            "- urgency (routine|urgent|emergency)\n"
            "- updated_notes (object with any subset of keys: chief_complaint, hpi, "
            "associated_symptoms, pmh, medications, allergies, family_history, "
            "social_history, red_flags, patient_goals, summary)\n"
        )

        # Keep prompt content compact to reduce latency and token cost.
        history_payload = [
            {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp}
            for msg in history[-self.settings.max_context_messages :]
        ]

        user_payload = {
            "incoming_message": user_text,
            "current_phase": state.phase,
            "current_urgency": state.urgency,
            "notes_so_far": state.notes,
            "recent_conversation": history_payload,
            "nejm_case_discussion_pearls": retrieved_snippets,
        }

        completion = self.client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=True),
                },
            ],
        )
        content = completion.choices[0].message.content or "{}"
        return json.loads(content)

    def _apply_structured_updates(
        self, state: InterviewState, llm_response: dict[str, Any]
    ) -> None:
        next_phase = str(llm_response.get("next_phase", state.phase)).strip()
        if next_phase in PHASES:
            state.phase = next_phase

        urgency = str(llm_response.get("urgency", state.urgency)).strip().lower()
        if urgency in {"routine", "urgent", "emergency"}:
            state.urgency = urgency

        updates = llm_response.get("updated_notes", {})
        if not isinstance(updates, dict):
            return

        for key, value in updates.items():
            if key not in state.notes:
                continue

            if key in LIST_NOTE_KEYS:
                merged = list(state.notes.get(key, []))
                if isinstance(value, list):
                    merged.extend(str(v) for v in value if str(v).strip())
                elif isinstance(value, str) and value.strip():
                    merged.append(value.strip())
                state.notes[key] = sorted(set(merged))
                continue

            if isinstance(value, str):
                candidate = value.strip()
                if candidate:
                    existing = str(state.notes.get(key, "")).strip()
                    state.notes[key] = candidate if not existing else f"{existing}; {candidate}"

    def _fallback_reply(self, user_text: str, state: InterviewState) -> str:
        self._capture_fallback_note(user_text, state)

        if state.phase == "chief_complaint":
            state.phase = "hpi"
            return (
                "Thanks. When did this start, and how has it changed over time "
                "(better, worse, or unchanged)?"
            )
        if state.phase == "hpi":
            state.phase = "pmh"
            return (
                "Any important past medical conditions, surgeries, or hospitalizations?"
            )
        if state.phase == "pmh":
            state.phase = "meds_allergies"
            return "What medications do you take, and do you have any drug allergies?"
        if state.phase == "meds_allergies":
            state.phase = "family_social"
            return (
                "Any relevant family history, and could you share smoking, alcohol, "
                "or substance use?"
            )
        if state.phase == "family_social":
            state.phase = "ros_red_flags"
            return (
                "Any red-flag symptoms like chest pain, breathing trouble, fainting, "
                "high fever, weakness, or severe bleeding?"
            )
        if state.phase == "ros_red_flags":
            state.phase = "summary"
            summary = self._build_summary(state.notes)
            state.notes["summary"] = summary
            return (
                f"Thanks. Here is a draft history summary for clinician handoff: {summary} "
                "Is this accurate, or would you like to add anything?"
            )

        summary = self._build_summary(state.notes)
        state.notes["summary"] = summary
        return (
            f"Updated summary: {summary} "
            "If this is complete, I can mark your intake as ready for clinician review."
        )

    def _capture_fallback_note(self, user_text: str, state: InterviewState) -> None:
        text = user_text.strip()
        if not text:
            return
        if state.phase == "chief_complaint":
            state.notes["chief_complaint"] = text
        elif state.phase == "hpi":
            current = str(state.notes.get("hpi", "")).strip()
            state.notes["hpi"] = text if not current else f"{current}; {text}"
        elif state.phase == "pmh":
            state.notes["pmh"] = text
        elif state.phase == "meds_allergies":
            # Split simple medication/allergy statements when possible.
            lowered = text.lower()
            if "allerg" in lowered:
                state.notes["allergies"] = text
            else:
                state.notes["medications"] = text
        elif state.phase == "family_social":
            state.notes["social_history"] = text
        elif state.phase == "ros_red_flags":
            flags = list(state.notes.get("red_flags", []))
            flags.append(text)
            state.notes["red_flags"] = sorted(set(flags))
        elif state.phase == "summary":
            current = str(state.notes.get("summary", "")).strip()
            state.notes["summary"] = text if not current else f"{current}; {text}"

    @staticmethod
    def _looks_emergent(text: str) -> bool:
        lowered = text.lower()
        emergency_terms = [
            "severe chest pain",
            "can't breathe",
            "cannot breathe",
            "trouble breathing",
            "shortness of breath at rest",
            "one-sided weakness",
            "slurred speech",
            "passed out",
            "fainted",
            "uncontrolled bleeding",
            "suicidal",
            "overdose",
        ]
        return any(term in lowered for term in emergency_terms)

    @staticmethod
    def _build_summary(notes: dict[str, Any]) -> str:
        parts: list[str] = []
        if notes.get("chief_complaint"):
            parts.append(f"Chief concern: {notes['chief_complaint']}.")
        if notes.get("hpi"):
            parts.append(f"HPI: {notes['hpi']}.")
        if notes.get("pmh"):
            parts.append(f"Past history: {notes['pmh']}.")
        if notes.get("medications"):
            parts.append(f"Medications: {notes['medications']}.")
        if notes.get("allergies"):
            parts.append(f"Allergies: {notes['allergies']}.")
        if notes.get("family_history"):
            parts.append(f"Family history: {notes['family_history']}.")
        if notes.get("social_history"):
            parts.append(f"Social history: {notes['social_history']}.")
        red_flags = notes.get("red_flags", [])
        if red_flags:
            parts.append(f"Red flags noted: {', '.join(red_flags)}.")
        if not parts:
            return "History is still incomplete."
        return " ".join(parts)
