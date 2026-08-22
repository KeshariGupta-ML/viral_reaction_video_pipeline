from typing import Optional
from pydantic import BaseModel, Field

class RawComment(BaseModel):
    id: str
    author: str
    text: str
    likes: int = 0
    replies: int = 0
    avatar_url: Optional[str] = None

class CuratedComment(BaseModel):
    id: str
    author: str
    comment_text: str
    likes: str
    replies: str
    roast_narration: str
    sfx: Optional[str] = Field(default="vine_boom.mp3")
    meme_clip: Optional[str] = None
    avatar_url: Optional[str] = None