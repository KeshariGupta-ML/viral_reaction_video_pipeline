import os
import uuid
from pathlib import Path
import edge_tts
import ffmpeg

from app.core.logger import logger
from config import settings


class TTSEngineService:
    def __init__(self, output_dir: Path = settings.TEMP_DIR):
        self.output_dir = output_dir
        # High-quality multilingual neural voice supporting Hinglish / Hindi / English
        self.default_voice = "en-IN-NeerjaNeural"  # or "hi-IN-SwaraNeural"

    async def generate_speech(self, text: str, voice: str = None) -> Path:
        """
        Converts input text (English/Hinglish) into an MP3 audio file using Edge TTS.
        """
        selected_voice = voice or self.default_voice
        file_id = str(uuid.uuid4())[:8]
        output_path = self.output_dir / f"tts_{file_id}.mp3"

        logger.info(f"🎙️ [TTS Engine] Synthesizing speech using voice '{selected_voice}': '{text[:30]}...'")

        communicate = edge_tts.Communicate(text, selected_voice)
        await communicate.save(str(output_path))

        logger.info(f"✅ [TTS Engine] Audio generated successfully at: {output_path}")
        return output_path

    def get_audio_duration(self, audio_path: Path) -> float:
        """
        Probes an audio file using ffmpeg/ffprobe to get its exact duration in seconds.
        """
        try:
            probe = ffmpeg.probe(str(audio_path))
            duration = float(probe["format"]["duration"])
            return duration
        except Exception as e:
            logger.error(f"❌ [TTS Engine] Failed to probe audio duration for {audio_path}: {str(e)}")
            return 3.0  # Fallback default duration


tts_service = TTSEngineService()