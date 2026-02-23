from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Environment-driven settings for the WhatsApp history agent."""

    openai_api_key: str
    openai_model: str
    database_path: Path
    nejm_patterns_path: Path
    verify_twilio_signature: bool
    twilio_auth_token: str
    max_context_messages: int
    max_knowledge_snippets: int


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def load_settings() -> Settings:
    workspace_root = Path(__file__).resolve().parent.parent

    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
    database_path = Path(
        os.getenv("DATABASE_PATH", str(workspace_root / "data" / "sessions.db"))
    )
    nejm_patterns_path = Path(
        os.getenv(
            "NEJM_PATTERNS_PATH",
            str(workspace_root / "data" / "nejm_case_discussions.json"),
        )
    )

    return Settings(
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        database_path=database_path,
        nejm_patterns_path=nejm_patterns_path,
        verify_twilio_signature=_as_bool(
            os.getenv("VERIFY_TWILIO_SIGNATURE"), default=False
        ),
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", "").strip(),
        max_context_messages=int(os.getenv("MAX_CONTEXT_MESSAGES", "16")),
        max_knowledge_snippets=int(os.getenv("MAX_KNOWLEDGE_SNIPPETS", "3")),
    )
