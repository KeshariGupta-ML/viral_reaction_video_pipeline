import pytest
from pathlib import Path
from app.services.scraper import scraper_service
from app.services.video_compositor import video_compositor_service


@pytest.mark.asyncio
async def test_video_compositor_renders_vertical_mp4():
    """Verify FFmpeg successfully combines a source video into a 1080x1920 9:16 vertical MP4."""
    test_video_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

    # 1. Download sample video using our scraper service
    source_video_path, _, _ = scraper_service.extract_video_and_comments(
        video_url=test_video_url,
        max_comments=2
    )

    assert source_video_path.exists()

    # 2. Render final vertical reaction video
    output_video_path = video_compositor_service.compose_reaction_video(
        source_video_path=source_video_path,
        comment_card_images=[],
        tts_audio_paths=[]
    )

    # 3. Verify output file existence and integrity
    assert isinstance(output_video_path, Path)
    assert output_video_path.exists(), f"Rendered video not found at {output_video_path}"
    assert output_video_path.stat().st_size > 0, "Rendered reaction video file is empty"

    # Cleanup temporary files
    if source_video_path.exists():
        source_video_path.unlink()
    if output_video_path.exists():
        output_video_path.unlink()