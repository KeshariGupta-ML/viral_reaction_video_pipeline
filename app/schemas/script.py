from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from app.schemas.comment import CuratedComment


class VideoScript(BaseModel):
    hook_narration: str = Field(
        default="Pehle video dekho, fir iske comments padhte hain! Aur meri mehnat ke liye subscribe aur like thok ke jana!",
        description="Spoken Hindi/Hinglish TTS intro audio narration",
    )
    hook_text: str = Field(
        default="WAIT FOR THE END 💀",
        description="Punchy 2-5 word curiosity headline for thumbnail multi-color hook text and intro badges",
    )
    reactions: List[CuratedComment] = Field(
        ...,
        description="List of selected curated comments with roast narrations",
    )
    outro_narration: Optional[str] = Field(
        default="Video pasand aayi toh like aur subscribe zaroor karna!",
        description="Outro closing call to action",
    )

    @field_validator("hook_text", mode="before")
    @classmethod
    def ensure_valid_hook_text(cls, v):
        if not v or str(v).strip().lower() in ["none", "null", ""]:
            return "WAIT FOR THE END 💀"
        return str(v).strip()