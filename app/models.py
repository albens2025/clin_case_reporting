from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


PHASES = [
    "introduction",
    "chief_complaint",
    "hpi",
    "pmh",
    "meds_allergies",
    "family_social",
    "ros_red_flags",
    "summary",
]


def utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class ConversationMessage:
    role: str
    content: str
    timestamp: str = field(default_factory=utcnow_iso)


@dataclass
class InterviewState:
    phone_number: str
    phase: str = "introduction"
    urgency: str = "routine"
    notes: dict[str, Any] = field(
        default_factory=lambda: {
            "chief_complaint": "",
            "hpi": "",
            "associated_symptoms": [],
            "pmh": "",
            "medications": "",
            "allergies": "",
            "family_history": "",
            "social_history": "",
            "red_flags": [],
            "patient_goals": "",
            "summary": "",
        }
    )

    def to_record(self) -> dict[str, Any]:
        return {
            "phone_number": self.phone_number,
            "phase": self.phase,
            "urgency": self.urgency,
            "notes": self.notes,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "InterviewState":
        notes = record.get("notes", {}) if record else {}
        state = cls(phone_number=record["phone_number"] if record else "")
        state.phase = record.get("phase", "introduction") if record else "introduction"
        state.urgency = record.get("urgency", "routine") if record else "routine"
        state.notes.update(notes)
        return state
