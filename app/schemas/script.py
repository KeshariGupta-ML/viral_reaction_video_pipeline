from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.comment import CuratedComment


class VideoScript(BaseModel):
    hook_narration: str = Field(
        default="Pehle video dekho, fir iske comments padhte hain! Aur meri mehnat ke liye subscribe aur like thok ke jana!",
        description="Spoken Hindi/Hinglish TTS intro audio narration",
    )
    reactions: List[CuratedComment] = Field(
        ...,
        description="List of selected curated comments with roast narrations",
    )
    outro_narration: Optional[str] = Field(
        default="Video pasand aayi toh like aur subscribe zaroor karna!",
        description="Outro closing call to action",
    )