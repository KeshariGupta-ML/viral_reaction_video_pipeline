<<<<<<< HEAD
from typing import Optional, Union
from pydantic import BaseModel, Field, field_validator

=======
from typing import Optional
from pydantic import BaseModel, Field
>>>>>>> origin/main

class RawComment(BaseModel):
    id: str
    author: str
    text: str
<<<<<<< HEAD
    likes: Union[str, int] = "0"
    replies: Union[str, int] = "0"
    avatar_url: Optional[str] = None

    @field_validator("likes", "replies", mode="before")
    @classmethod
    def coerce_to_string(cls, v):
        if v is None:
            return "0"
        return str(v)


=======
    likes: int = 0
    replies: int = 0
    avatar_url: Optional[str] = None

>>>>>>> origin/main
class CuratedComment(BaseModel):
    id: str
    author: str
    comment_text: str
<<<<<<< HEAD
    likes: Union[str, int] = "0"
    replies: Union[str, int] = "0"
    roast_narration: str
    sfx: Optional[str] = Field(default="vine_boom.mp3")
    meme_clip: Optional[str] = None
    avatar_url: Optional[str] = None

    @field_validator("likes", "replies", mode="before")
    @classmethod
    def coerce_to_string(cls, v):
        if v is None:
            return "0"
        return str(v)
=======
    likes: str
    replies: str
    roast_narration: str
    sfx: Optional[str] = Field(default="vine_boom.mp3")
    meme_clip: Optional[str] = None
    avatar_url: Optional[str] = None
>>>>>>> origin/main
