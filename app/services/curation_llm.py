import os
from pathlib import Path
import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from app.schemas.script import VideoScript
from app.core.logger import logger
from config import settings


class CurationLLMService:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.1  # Low temperature for strict adherence without hallucinated translations
        )
        self.parser = PydanticOutputParser(pydantic_object=VideoScript)

    def _get_available_memes(self) -> list:
        if settings.MEMES_DIR.exists():
            return [
                f.name for f in settings.MEMES_DIR.glob("*.*")
                if f.suffix.lower() in [".mp4", ".mov", ".webm", ".mkv"]
                and "chaliye" not in f.stem.lower()
            ]
        return []

    def curate_and_generate_script(self, raw_comments: list, comment_count: int = 3) -> VideoScript:
        logger.info(f"🤖 [LLM Curation] Curating top {comment_count} comments...")

        available_memes = self._get_available_memes()
        comments_payload = [c.dict() for c in raw_comments[:25]]

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an AI video editor selecting comments for reaction shorts.\n"
                "RULES:\n"
                "1. Pick the top {comment_count} most flirtatious, humorous, or witty comments (priority: Hinglish/English/Hindi).\n"
                "2. Set 'hook_narration' EXACTLY to: 'Pehle video dekho, fir iske comments padhte hain! Aur meri mehnat ke liye subscribe aur like thok ke jana!'\n"
                "3. For each selected comment, 'roast_narration' MUST BE THE EXACT, RAW COMMENT TEXT but lenght of comments between 4 to 15 words.\n"
                "   - DO NOT translate the comment.\n"
                "   - DO NOT convert English words to Hindi.\n"
                "   - DO NOT rephrase, modify.\n"
                "   - DO NOT add usernames or conversational phrases like 'Ye bhai bol rahe hain'.\n"
                "   - Simply copy the exact comment text as 'roast_narration', stripping out emojis and repeated laugh words (like 'hahaha', 'lmao', 'rofl', '😂😂').\n"
                "4. Assign 'meme_clip' for each reaction by picking the best matching filename from this exact list: {available_memes}. If list is empty, set to null.\n\n"
                "{format_instructions}"
            ),
            (
                "user",
                "Here are the scraped comments:\n{comments_json}"
            )
        ])

        chain = prompt | self.llm | self.parser
        return chain.invoke({
            "comment_count": comment_count,
            "available_memes": json.dumps(available_memes),
            "comments_json": json.dumps(comments_payload),
            "format_instructions": self.parser.get_format_instructions()
        })


curation_service = CurationLLMService()