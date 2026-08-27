import os
import json
import re
from pathlib import Path
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
            temperature=0.1  # Low temperature for strict adherence to formatting rules
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
        logger.info(f"🤖 [LLM Curation] Curating top {comment_count} comments (4-15 words)...")

        available_memes = self._get_available_memes()
        comments_payload = [c.dict() for c in raw_comments[:30]]

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an expert AI video editor selecting comments for high-retention reaction shorts.\n"
                "RULES:\n"
                "1. Filter out offensive, abusive, spam, or toxic comments.\n"
                "2. Pick the top {comment_count} funniest, most witty, or flirtatious comments (Priority: Hinglish/English/Hindi).\n"
                "3. CRITICAL LENGTH CONSTRAINT: Each selected comment MUST be between 4 and 15 words long. Ignore comments shorter than 4 words or longer than 15 words.\n"
                "4. Set 'hook_narration' (AUDIO ONLY) EXACTLY to: 'Pehle video dekho, fir iske comments padhte hain! Aur meri mehnat ke liye subscribe aur like thok ke jana!'\n"
                "5. Set 'hook_comment' (DYNAMIC BANNER ONLY) to a punchy 2-5 word curiosity/shock hook derived from the best comment (e.g., 'BRO THOUGHT HE WON 💀', 'WAIT FOR THE END 💀', 'HE REGRETTED THIS INSTANTLY').\n"
                "6. For each selected comment, 'roast_narration' MUST BE THE EXACT RAW COMMENT TEXT:\n"
                "   - DO NOT translate the text into Hindi.\n"
                "   - DO NOT rephrase, modify, rewrite, or summarize.\n"
                "   - DO NOT prefix with usernames or filler phrases like 'Ye bhai bol rahe hain'.\n"
                "   - Strip out emojis and excessive laughter tags (such as 'hahaha', 'lmao', 'rofl', '😂😂', '💀').\n"
                "7. Assign 'meme_clip' for each curated comment by picking the best matching filename from this exact list: {available_memes}. If the list is empty or none match, set to null.\n\n"
                "{format_instructions}"
            ),
            (
                "user",
                "Here are the scraped comments to evaluate:\n{comments_json}"
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