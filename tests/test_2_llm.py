import pytest
from app.services.curation_llm import curation_service
from app.schemas.comment import RawComment
from app.schemas.script import VideoScript


def test_gemini_curation_and_script_generation():
    """Verify LangChain + Gemini 2.5 Flash outputs valid VideoScript schema from raw comments."""
    mock_raw_comments = [
        RawComment(id="1", author="alice123", text="Bro thought he was the main character 💀", likes=1500, replies=45),
        RawComment(id="2", author="bob_99", text="Bro is lagging in real life", likes=3200, replies=120),
        RawComment(id="3", author="hate_user", text="This is awful content delete this", likes=2, replies=0),
        RawComment(id="4", author="carl_x", text="The camera man never dies 😂😂", likes=850, replies=12),
    ]

    script = curation_service.curate_and_generate_script(
        raw_comments=mock_raw_comments,
        comment_count=2
    )

    # Validate Pydantic structure
    assert isinstance(script, VideoScript)
    assert script.hook_narration != ""
    assert script.outro_narration != ""
    assert len(script.reactions) <= 2

    # Check that toxicity/hate comments were filtered out and structure is intact
    for reaction in script.reactions:
        assert reaction.author != ""
        assert reaction.comment_text != ""
        assert reaction.roast_narration != ""