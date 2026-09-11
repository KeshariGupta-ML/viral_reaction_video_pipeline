import os
import shutil
import asyncio
from pathlib import Path
import edge_tts
from elevenlabs.client import ElevenLabs
from config import settings
from app.core.logger import logger

class ElevenlabTTSEngine:
    def __init__(self):
        self.api_key = getattr(settings, "ELEVENLABS_API_KEY", None)
        self.client = ElevenLabs(api_key=self.api_key) if self.api_key else None
        self.default_voice_id = getattr(settings, "ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
        # Absolute path to assets/audio/static_hook.mp3
        self.static_hook_path = settings.ASSETS_DIR / "audio" / "static_hook.mp3"
        self.fallback_voice = "hi-IN-SwaraNeural"
    def _is_valid_audio(self, path: Path) -> bool:
        """Check if file exists and has actual data (greater than 1KB)."""
        return path.exists() and path.stat().st_size > 1024

    def _get_hook_audio_sync(self, output_path: Path, hook_text: str = None) -> str:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Use static pre-rendered hook if valid
        if self._is_valid_audio(self.static_hook_path):
            logger.info(f"Using valid static hook audio from {self.static_hook_path}")
            shutil.copyfile(self.static_hook_path, output_path)
            return str(output_path)

        # 2. Generate and cache if missing or corrupted
        default_hook = "पहले वीडियो देखो, फिर इसके कमेंट्स पढ़ते हैं! और सब्सक्राइब और लाइक जरूर करना।"
        text_to_use = hook_text or default_hook
        logger.warning("Static hook file missing or empty. Generating clean hook...")
        self._synthesize_sync(text_to_use, self.static_hook_path)
        shutil.copyfile(self.static_hook_path, output_path)
        return str(output_path)

    def _synthesize_sync(self, text: str, output_path: Path, voice_id: str = None) -> str:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        target_voice = voice_id or self.default_voice_id

        if not self.client:
            return self._edge_tts_sync(text, output_path)

        try:
            audio_generator = self.client.text_to_speech.convert(
                voice_id=target_voice,
                text=text,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128"
            )

            with open(output_path, "wb") as f:
                for chunk in audio_generator:
                    f.write(chunk)

            if not self._is_valid_audio(output_path):
                raise RuntimeError("ElevenLabs wrote 0 bytes to file.")

            return str(output_path)
        except Exception as e:
            logger.warning(f"ElevenLabs synthesis failed: {e}. Falling back to Edge-TTS...")
            return self._edge_tts_sync(text, output_path)

    def _edge_tts_sync(self, text: str, output_path: Path) -> str:
        async def _run():
            communicate = edge_tts.Communicate(text, self.fallback_voice)
            await communicate.save(str(output_path))
        asyncio.run(_run())
        return str(output_path)

    async def get_hook_audio(self, output_path: str | Path, hook_text: str = None) -> str:
        return await asyncio.to_thread(self._get_hook_audio_sync, Path(output_path), hook_text)

    async def synthesize(self, text: str, output_path: str | Path, voice_id: str = None) -> str:
        return await asyncio.to_thread(self._synthesize_sync, text, Path(output_path), voice_id)


tts_service = ElevenlabTTSEngine()