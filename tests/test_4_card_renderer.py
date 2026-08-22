import pytest
from pathlib import Path
from app.services.card_renderer import card_renderer_service

def test_card_renderer_generates_png():
    """Verify Playwright isolated process renders comment card HTML to a transparent PNG snapshot."""
    card_path = card_renderer_service.render_comment_card_to_image(
        author="@viral_king",
        comment_text="Bro thought he was the main character 💀",
        likes="45K",
        replies="320"
    )

    assert isinstance(card_path, Path)
    assert card_path.exists(), f"Card image not found at {card_path}"
    assert card_path.stat().st_size > 0, "Rendered card image file is empty"

    if card_path.exists():
        card_path.unlink()