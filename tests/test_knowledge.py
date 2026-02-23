from pathlib import Path

from app.knowledge import NejmPatternLibrary


def test_retrieve_matches_chest_pain_pattern() -> None:
    library = NejmPatternLibrary.from_json_file(
        Path("data/nejm_case_discussions.json").resolve()
    )
    assert library.patterns

    results = library.retrieve(
        user_text="I have severe chest pain and sweating",
        notes={"chief_complaint": "chest pressure"},
        limit=2,
    )
    assert results
    assert "chest pain" in results[0].complaint.lower()
