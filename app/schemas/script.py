from typing import List
from pydantic import BaseModel
from app.schemas.comment import CuratedComment

class VideoScript(BaseModel):
    hook_narration: str
    reactions: List[CuratedComment]
    outro_narration: str