import os
import json
import random
import re
from pathlib import Path
from typing import List, Optional, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from app.schemas.script import VideoScript
from app.schemas.comment import CuratedComment
from app.core.logger import logger
from config import settings


class CurationLLMService:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.7  # Diverse, realistic comedic humor
        )
        self.parser = PydanticOutputParser(pydantic_object=VideoScript)

    def _get_available_memes(self) -> list:
        if hasattr(settings, "MEMES_DIR") and settings.MEMES_DIR.exists():
            return [
                f.name for f in settings.MEMES_DIR.glob("*.*")
                if f.suffix.lower() in [".mp4", ".mov", ".webm", ".mkv"]
                and "chaliye" not in f.stem.lower()
            ]
        return []

    def _sanitize_text(self, text: str) -> str:
        """Collapses 3+ repeating identical characters/emojis to 1 to prevent model loops."""
        if not text:
            return ""
        return re.sub(r'(.)\1{2,}', r'\1', text).strip()

    def curate_and_generate_script(
        self,
        raw_comments: Optional[list] = None,
        comment_count: int = 3,
        title: str = "Viral Video",
        description: str = "",
        **kwargs: Any
    ) -> VideoScript:
        """
        Primary generation method.
        Accepts raw_comments (for backward compatibility) and/or title/description.
        """
        # If title wasn't passed directly, check kwargs or extract from first raw comment
        clean_title = self._sanitize_text(title or kwargs.get("video_title", "Viral Video"))
        clean_desc = self._sanitize_text(description[:300])

        logger.info(f"🤖 [LLM Service] Generating {comment_count} comments & script for: '{clean_title[:35]}...'")

        available_memes = self._get_available_memes()

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an expert comedic writer and video editor creating YouTube Shorts reaction videos.\n\n"
                "GOAL:\n"
                "Generate {comment_count} realistic, high-engagement viewer comments reacting directly to the video context, then build the voiceover script.\n\n"
                "STRICT RULES:\n"
                "1. INVENT REALISTIC VIEWER COMMENTS:\n"
                "   - Create believable user handles (e.g. '@roast_master99', '@gamer_kabir', '@toxic_vibes').\n"
                "   - Write funny, sarcastic, or brutal comments reacting to the video topic.\n"
                "   - Language Priority: Hinglish (Hindi in Roman script) or conversational English.\n"
                "   - WORD COUNT: Strictly between 4 and 15 words per comment.\n"
                "   - Assign realistic like counts formatted as strings (e.g. '14.2K', '3.8K') and replies ('120', '45').\n"
                "   - NO EMOJI SPAM: Maximum 1 emoji per comment. Never repeat emojis.\n\n"
                "2. HOOK AUDIO ('hook_narration'):\n"
                "   - EXACT STRING: 'Pehle video dekho, fir iske comments padhte hain! Aur meri mehnat ke liye subscribe aur like thok ke jana!'\n\n"
                "3. VOICE NARRATION ('roast_narration'):\n"
                "   - Exact spoken comment text without emojis or username prefixes.\n\n"
                "4. MEME CLIP ('meme_clip'):\n"
                "   - Pick the best match from this list: {available_memes}. If none match, use null.\n\n"
                "{format_instructions}"
            ),
            (
                "user",
                "Video Title: {title}\n"
                "Video Description: {description}"
            )
        ])

        chain = prompt | self.llm | self.parser

        try:
            script: VideoScript = chain.invoke({
                "comment_count": comment_count,
                "title": clean_title,
                "description": clean_desc,
                "available_memes": json.dumps(available_memes),
                "format_instructions": self.parser.get_format_instructions()
            })
            return script

        except Exception as e:
            logger.warning(f"⚠️ [LLM Fallback] Parsing failed ({e}). Returning validated emergency script.")
            fallback_reactions = [
                CuratedComment(
                    id="gen_1",
                    author="@sarcastic_bro",
                    comment_text="Bro forgot to turn on his brain today 💀",
                    likes="12.5K",
                    replies="84",
                    roast_narration="Bro forgot to turn on his brain today",
                    meme_clip=available_memes[0] if available_memes else None
                ),
                CuratedComment(
                    id="gen_2",
                    author="@desiroaster",
                    comment_text="Confidence level 100 but IQ level minus zero 😭",
                    likes="8.2K",
                    replies="42",
                    roast_narration="Confidence level 100 but IQ level minus zero",
                    meme_clip=None
                )
            ][:comment_count]

            return VideoScript(
                hook_narration="Pehle video dekho, fir iske comments padhte hain! Aur meri mehnat ke liye subscribe aur like thok ke jana!",
                reactions=fallback_reactions
            )

    # Alias so both generate_comments_and_script and curate_and_generate_script work
    generate_comments_and_script = curate_and_generate_script


curation_service = CurationLLMService()