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
            temperature=0.7  # Balanced comedic humor
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
        return re.sub(r'(.)\1{2,}', r'\1', str(text)).strip()

    def _format_raw_comments(self, raw_comments: Optional[list]) -> str:
        """Serializes raw comments into clean JSON or provides fallback prompt instructions."""
        if not raw_comments:
            return "No raw comments provided. Invent realistic, high-engagement viewer comments reacting to the video."

        clean_pool = []
        for c in raw_comments[:25]:
            if hasattr(c, "model_dump"):
                data = c.model_dump()
            elif hasattr(c, "dict"):
                data = c.dict()
            elif isinstance(c, dict):
                data = c
            else:
                data = {"text": str(c)}

            # Sanitize comment text to prevent repetitive loops
            if "text" in data:
                data["text"] = self._sanitize_text(data["text"])
            elif "comment_text" in data:
                data["comment_text"] = self._sanitize_text(data["comment_text"])

            clean_pool.append(data)

        return json.dumps(clean_pool, ensure_ascii=False, indent=2)

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
        Accepts raw_comments and/or title/description to generate high-retention reactions.
        """
        clean_title = self._sanitize_text(title or kwargs.get("video_title", "Viral Video"))
        clean_desc = self._sanitize_text(description[:300])
        formatted_comments = self._format_raw_comments(raw_comments)
        available_memes = self._get_available_memes()

        logger.info(f"🤖 [LLM Service] Curating/generating {comment_count} reactions for: '{clean_title[:35]}...'")

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an expert social media scriptwriter and editor for YouTube Shorts reaction videos.\n\n"
                "GOAL:\n"
                "Pick {comment_count} standout viewer comments from {raw_comments} that are funny, simp, dramatic,adult 18+ "
                "or relatable. Then TWEAK them slightly so they sound punchy, viral, and entertaining on screen.\n\n"
                "CORE RULE: TWEAK & POLISH\n"
                "- KEEP THE ORIGINAL INTENT: If the comment is simp/compliment, make it a funny, dramatic compliment. "
                "If it's about an outfit or look, make it a witty, catchy observation.\n\n"
                "TWEAKING GUIDELINES:\n"
                "1. Fix broken grammar / weird typing into smooth, readable Hinglish.\n"
                "2. Sharpen the punchline so viewers instantly smile.\n"
                "3. Remove emoji spam (limit to exactly 1 suitable emoji for display).\n"
                "4. Examples of Tweaking (Original -> Tweaked):\n"
                "   * 'Sona chandi aapke aage phika hay maydam ❤❤❤' -> 'Sona chandi sab phika hai madam aapke aage ✨'\n"
                "   * 'Apki saree aur blouse ki fitting jordar h' -> 'Designer ko 21 topon ki salami milni chahiye 🔥'\n"
                "   * 'Sona Chandi bahut mahange hue aur bade ho gaye' -> 'Gold rate se bhi tez madam ka glow badh raha hai 📈'\n\n"
                "AUDIO & SCRIPT RULES:\n"
                "1. 'hook_text': An attention-grabbing, ultra-punchy 3 to 5 word curiosity headline for the thumbnail & intro.\n"
                "   - SELECT directly from the best raw comment and tweak it slightly to make it viral/funny.\n"
                "   - SCRIPT REQUIREMENT: Keep it strictly in HINDI (written in Devanagari script, e.g. 'भाई, क्या बवाल डांस है!' ya 'ये क्या देख लिया 💀').\n"
                "   - Word limit: Strictly 3 to 5 words. Do not make it long.\n" "- 'hook_narration': EXACT STRING: 'Pehle video dekho, fir iske comments padhte hain! Aur meri mehnat ke liye subscribe aur like thok ke jana!'\n"
                "- 'voice_narration': Cleaned spoken version of 'tweaked_display_text' for natural TTS delivery (reads the comment directly without meta-commentary; excludes emojis, hashtags, and symbols; formatted in conversational Hinglish).\n"
                "- 'meme_clip': Pick the best matching reaction clip from: {available_memes}. If none fit, output null.\n\n"
                "{format_instructions}",
            ),
            (
                "user",
                "Video Title: {title}\n"
                "Video Description: {description}\n"
                "Raw Comments Pool:\n"
                "{raw_comments}",
            ),
        ])

        chain = prompt | self.llm | self.parser

        try:
            script: VideoScript = chain.invoke({
                "comment_count": comment_count,
                "title": clean_title,
                "description": clean_desc,
                "raw_comments": formatted_comments,
                "available_memes": json.dumps(available_memes),
                "format_instructions": self.parser.get_format_instructions()
            })
            return script

        except Exception as e:
            logger.warning(f"⚠️ [LLM Fallback] Parsing failed ({e}). Returning validated emergency script.")
            default_pool = [
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
                ),
                CuratedComment(
                    id="gen_3",
                    author="@backbencher_vibes",
                    comment_text="Madam ka glow dekh ke mera router bhi restart ho gaya 🔥",
                    likes="6.1K",
                    replies="19",
                    roast_narration="Madam ka glow dekh ke mera router bhi restart ho gaya",
                    meme_clip=None
                )
            ]

            return VideoScript(
                hook_narration="Pehle video dekho, fir iske comments padhte hain! Aur meri mehnat ke liye subscribe aur like thok ke jana!",
                reactions=default_pool[:comment_count]
            )

    # Alias for pipeline compatibility
    generate_comments_and_script = curate_and_generate_script


curation_service = CurationLLMService()
