import pytest
from pathlib import Path
from app.services.scraper import scraper_service
from app.schemas.comment import RawComment

# Use your target YouTube Short URL
TEST_VIDEO_URL = "https://www.youtube.com/shorts/LtU_3Ep6qLE"


def test_scraper_downloads_video_and_extracts_comments():
    """Verify video downloading, metadata parsing, and comment extraction."""
    video_path, comments, metadata = scraper_service.extract_video_and_comments(
        video_url=TEST_VIDEO_URL,
        max_comments=10
    )

    # 1. Video existence check
    assert isinstance(video_path, Path)
    assert video_path.exists(), f"Downloaded file not found at {video_path}"
    assert video_path.stat().st_size > 0, "Downloaded video file is empty"

    # 2. Metadata verification (Matches LtU_3Ep6qLE)
    assert metadata["id"] == "LtU_3Ep6qLE"
    assert metadata["duration"] > 0

    # 3. Comments parsing validation
    assert isinstance(comments, list)
    assert len(comments) > 0, "No comments were scraped"

    first_comment = comments[0]
    assert isinstance(first_comment, RawComment)
    assert first_comment.author != ""
    assert len(first_comment.text) > 0
    assert first_comment.likes >= 0

    # Cleanup temporary test video
    if video_path.exists():
        video_path.unlink()