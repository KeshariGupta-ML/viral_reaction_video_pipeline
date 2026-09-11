import os
import uuid
import re
import shutil
import asyncio
from pathlib import Path
from typing import Optional
import edge_tts
import ffmpeg

from app.core.logger import logger
from config import settings


class TTSEngineService:
    def __init__(self, output_dir: Path = settings.TEMP_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Edge-TTS Hindi Voice
        self.default_voice = getattr(settings, "EDGE_TTS_VOICE", "hi-IN-SwaraNeural")

        # Pre-cached static hook audio path
        self.static_hook_path = Path(settings.ASSETS_DIR) / "audio" / "static_hook.mp3"

        # Map common Romanized Hinglish words to exact Devanagari phonetics
        self.phonetic_map = {
            r'\bfir\b': 'फिर',
            r'\bphir\b': 'फिर',
            r'\bpehle\b': 'पहले',
            r'\bdekho\b': 'देखो',
            r'\bpadhte\b': 'पढ़ते',
            r'\bhain\b': 'हैं',
            r'\bhain!\b': 'हैं!',
            r'\bye\b': 'ये',
            r'\byeh\b': 'यह',
            r'\biske\b': 'इसके',
            r'\bthok\b': 'ठोक',
            r'\bke\b': 'के',
            r'\bjaiyega\b': 'जाइएगा',
            r'\bchaliye\b': 'चलिए',
            r'\bshuru\b': 'शुरू',
            r'\bkarte\b': 'करते',
            r'\baap\b': 'आप',
            r'\bkya\b': 'क्या',
            r'\bkaisi\b': 'कैसी',
            r'\bkaise\b': 'कैसे',
            r'\bhaha\b': 'हाहा',
            r'\bhahaha\b': 'हाहाहा',
        }

    def _is_valid_audio(self, path: Path) -> bool:
        """Check if audio file exists and has actual data (> 1KB)."""
        return path.exists() and path.stat().st_size > 1024

    def _clean_text_for_speech(self, text: str) -> str:
        """Removes emojis, applies phonetic replacements, and ensures pure pronunciation."""
        # 1. Apply Hinglish -> Devanagari word mappings
        for pattern, replacement in self.phonetic_map.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # 2. Clean out unpronounceable symbols and emojis
        clean = re.sub(r'[#*_`💀😂🤣🔥✨👇❤️💬@/\\|]', '', text)

        # 3. Collapse extra whitespace
        return re.sub(r'\s+', ' ', clean).strip()

    def get_audio_duration(self, audio_path: Path | str) -> float:
        """Extracts audio duration in seconds using ffprobe."""
        try:
            probe = ffmpeg.probe(str(audio_path))
            return float(probe["format"]["duration"])
        except Exception as e:
            logger.warning(f"⚠️ [TTS Duration] Could not probe {audio_path}: {e}")
            return 4.0

    async def synthesize(
            self,
            text: str,
            output_path: Optional[str | Path] = None,
            output_filename: Optional[str] = None,
            voice: Optional[str] = None,
            rate: str = "+6%",
            pitch: str = "+2Hz",
            **kwargs
    ) -> Path:
        """Synthesizes speech using Edge-TTS with phonetic normalization."""
        # Handle either output_path or output_filename
        if output_path:
            target_path = Path(output_path)
        elif output_filename:
            target_path = self.output_dir / output_filename
        else:
            target_path = self.output_dir / f"tts_{str(uuid.uuid4())[:8]}.mp3"

        target_path.parent.mkdir(parents=True, exist_ok=True)

        chosen_voice = voice or kwargs.get("voice_id") or self.default_voice
        cleaned_text = self._clean_text_for_speech(text)
        logger.info(f"🎙️ [Edge-TTS] Synthesizing: '{cleaned_text}' with voice {chosen_voice}")

        communicate = edge_tts.Communicate(
            text=cleaned_text,
            voice=chosen_voice,
            rate=rate,
            pitch=pitch
        )
        await communicate.save(str(target_path))

        if not self._is_valid_audio(target_path):
            raise RuntimeError(f"Edge-TTS failed to create audio file at: {target_path}")

        return target_path

    # Alias for backwards compatibility with generate_speech
    async def generate_speech(self, *args, **kwargs) -> Path:
        return await self.synthesize(*args, **kwargs)

    async def get_hook_audio(
            self,
            output_path: Optional[str | Path] = None,
            output_filename: Optional[str] = None,
            hook_text: Optional[str] = None
    ) -> Path:
        """
        Fetches hook audio. If static_hook.mp3 is already cached, it copies it directly.
        Otherwise, synthesizes it once, caches it, and copies it to destination.
        """
        if output_path:
            destination_path = Path(output_path)
        elif output_filename:
            destination_path = self.output_dir / output_filename
        else:
            destination_path = self.output_dir / f"hook_{str(uuid.uuid4())[:8]}.mp3"

        destination_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Use static pre-cached hook if available and valid
        if self._is_valid_audio(self.static_hook_path):
            logger.info(f"⚡ [TTS Hook] Static hook found at {self.static_hook_path}. Skipping generation.")
            await asyncio.to_thread(shutil.copyfile, self.static_hook_path, destination_path)
            return destination_path

        # 2. Hook file missing or invalid: generate once and cache it
        logger.warning(f"⚠️ [TTS Hook] Static hook missing at {self.static_hook_path}. Generating new cache...")
        self.static_hook_path.parent.mkdir(parents=True, exist_ok=True)

        default_hook = "पहले वीडियो देखो, फिर इसके कमेंट्स पढ़ते हैं! और सब्सक्राइब और लाइक जरूर करना।"
        text_to_use = hook_text or default_hook

        # Synthesize directly to the static hook path
        await self.synthesize(
            text=text_to_use,
            output_path=self.static_hook_path
        )

        # Copy cached hook to the target destination
        await asyncio.to_thread(shutil.copyfile, self.static_hook_path, destination_path)
        return destination_path


# Export instance (also aliased for any legacy imports)
tts_service = TTSEngineService()