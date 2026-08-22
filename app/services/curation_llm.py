import os
from pathlib import Path
import json
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
            temperature=0.3  # Lower temperature for strict prompt adherence
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
                "You are an AI video editor formatting YouTube Shorts reaction videos.\n"
                "RULES:\n"
                "1. Filter out offensive or toxic comments.\n"
                "2. Pick the top {comment_count} funniest comments.\n"
                "3. Set 'hook_narration' EXACTLY to: 'Pehle ye video dekho, fir iske comments padhte hain! Aur subscribe like thok ke jaiyega!'\n"
                "4. For each selected comment, 'roast_narration' MUST BE ONLY the comment text translated/spoken clearly in natural Hindi/Hinglish. DO NOT say the username, DO NOT add intro phrases like 'Ye bhai bol rahe hain', and DO NOT add self-reactions. ONLY read the comment text cleanly.\n"
                "5. Assign 'meme_clip' for each reaction by picking the best matching filename from this exact list: {available_memes}. If list is empty, set to null.\n\n"
                "{format_instructions}"
            ),
            (
                "user",
                "Here are the comments:\n{comments_json}"
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