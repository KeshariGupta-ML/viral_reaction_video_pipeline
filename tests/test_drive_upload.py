import json
import pytest
from pathlib import Path
from config import settings
from app.services.gdrive_uploader import gdrive_service


@pytest.mark.asyncio
async def test_upload_output_mp4_and_videos_json():
    job_id = "a8cac06f"

    # 1. Output MP4 file
    test_video_path = settings.OUTPUT_DIR / f"reaction_{job_id}.mp4"
    assert test_video_path.exists(), f"MP4 file missing at {test_video_path}"

    # 2. Raw JSON in storage/videos/
    test_json_path = settings.VIDEOS_DIR / f"{job_id}.json"
    if not test_json_path.exists():
        dummy_data = {
            "job_id": job_id,
            "source_type": "raw_video_data",
            "storage_location": "storage/videos",
            "video_file": f"reaction_{job_id}.mp4"
        }
        with open(test_json_path, "w", encoding="utf-8") as f:
            json.dump(dummy_data, f, indent=2)

    assert test_json_path.exists(), f"JSON file missing at {test_json_path}"

    # Upload MP4
    video_response = await gdrive_service.upload_file(
        file_path=test_video_path,
        mime_type="video/mp4",
        custom_filename=f"reaction_{job_id}.mp4"
    )
    assert video_response is not None and "id" in video_response
    print(f"\n✅ Output MP4 uploaded: {video_response.get('webViewLink')}")

    # Upload JSON from storage/videos
    json_response = await gdrive_service.upload_file(
        file_path=test_json_path,
        mime_type="application/json",
        custom_filename=f"metadata_{job_id}.json"
    )
    assert json_response is not None and "id" in json_response
    print(f"✅ Videos JSON uploaded : {json_response.get('webViewLink')}")