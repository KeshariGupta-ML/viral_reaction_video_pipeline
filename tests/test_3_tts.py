import pytest
from pathlib import Path
from app.services.tts_engine import tts_service


@pytest.mark.asyncio
async def test_tts_audio_generation_and_duration():
    """Verify Edge TTS generates an audio file and ffprobe reads its duration."""
    test_text = "Pehle ye clip dekho, fir comments padhte hain!"

    audio_path = await tts_service.generate_speech(test_text)

    # 1. Check file existence
    assert isinstance(audio_path, Path)
    assert audio_path.exists(), f"TTS audio file not found at {audio_path}"
    assert audio_path.stat().st_size > 0, "TTS audio file is empty"

    # 2. Check duration probe
    duration = tts_service.get_audio_duration(audio_path)
    assert isinstance(duration, float)
    assert duration > 0.0, "Audio duration should be greater than 0 seconds"

    # Cleanup
    if audio_path.exists():
        audio_path.unlink()