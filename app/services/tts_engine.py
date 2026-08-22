import os
import uuid
import re
from pathlib import Path
from typing import Optional
import edge_tts
import ffmpeg

from app.core.logger import logger
from config import settings


class TTSEngineService:
    def __init__(self, output_dir: Path = settings.TEMP_DIR):
        self.output_dir = output_dir
        self.default_voice = "hi-IN-SwaraNeural"

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

    def _clean_text_for_speech(self, text: str) -> str:
        """Removes emojis, applies phonetic replacements, and ensures pure pronunciation."""
        # 1. Apply Hinglish -> Devanagari word mappings
        for pattern, replacement in self.phonetic_map.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # 2. Clean out unpronounceable symbols and emojis
        clean = re.sub(r'[#*_`💀😂🤣🔥✨👇❤️💬@/\\|]', '', text)

        # 3. Collapse extra whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def get_audio_duration(self, audio_path: Path) -> float:
        try:
            probe = ffmpeg.probe(str(audio_path))
            return float(probe["format"]["duration"])
        except Exception as e:
            logger.warning(f"⚠️ [TTS Duration] Could not probe {audio_path}: {e}")
            return 4.0

    async def generate_speech(
            self,
            text: str,
            voice: Optional[str] = None,
            rate: str = "+6%",
            pitch: str = "+2Hz",
            output_filename: Optional[str] = None
    ) -> Path:
        """Synthesizes realistic, expressive female voiceover with corrected Hindi phonetics."""
        chosen_voice = voice or self.default_voice
        filename = output_filename or f"tts_{str(uuid.uuid4())[:8]}.mp3"
        output_path = self.output_dir / filename

        cleaned_text = self._clean_text_for_speech(text)
        logger.info(f"🎙️ [TTS Engine] Pronunciation normalized: '{cleaned_text}'")

        communicate = edge_tts.Communicate(
            text=cleaned_text,
            voice=chosen_voice,
            rate=rate,
            pitch=pitch
        )

        await communicate.save(str(output_path))

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"TTS Engine failed to create audio file at: {output_path}")

        return output_path


tts_service = TTSEngineService()