import json
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.schemas.comment import RawComment
from app.schemas.script import VideoScript
from app.core.logger import logger
from config import settings


class CommentCurationService:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.7,
        )

    def curate_and_generate_script(
        self,
        raw_comments: List[RawComment],
        comment_count: int = 3
    ) -> VideoScript:
        logger.info(f"🤖 [LLM Curation] Processing {len(raw_comments)} comments using {settings.GEMINI_MODEL}...")

        comments_data = [
            {
                "id": c.id,
                "author": c.author,
                "text": c.text,
                "likes": c.likes,
                "replies": c.replies
            }
            for c in raw_comments
        ]

        parser = JsonOutputParser(pydantic_object=VideoScript)

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a viral YouTube Shorts/Reels scriptwriter. "
                "1. Pick the top {comment_count} funniest comments.\n"
                "2. Set 'hook_narration' EXACTLY to: 'Pehle ye video dekho, fir iske comments padhte hain! Aur meri mehnat ke liye subscribe aur like thok ke jaiyega!'\n"
                "3. For each selected comment, write a funny and roasted Hinglish narration that reads the comment (e.g. 'Ye bhai bol rahe hain... bhai kya bol diya! 💀').\n\n"
                "{format_instructions}"
            ),
            (
                "user",
                "Here are the scraped comments:\n{comments_json}"
            )
        ])

        chain = prompt | self.llm | parser

        try:
            result = chain.invoke({
                "comment_count": comment_count,
                "comments_json": json.dumps(comments_data, indent=2),
                "format_instructions": parser.get_format_instructions()
            })

            script = VideoScript(**result)
            # Guarantee the exact hook
            script.hook_narration = "Pehle ye video dekho, feer iske comments padhte hain! Aur meri mehnat ke liye subscribe aur like thok ke jaiyega!"
            return script

        except Exception as e:
            logger.error(f"❌ [LLM Curation] Error: {str(e)}")
            raise e


curation_service = CommentCurationService()