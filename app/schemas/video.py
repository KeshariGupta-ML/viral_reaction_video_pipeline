from enum import Enum
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, HttpUrl
from app.schemas.script import VideoScript

class JobStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    CURATING = "curating"
    SYNTHESIZING = "synthesizing"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"

class VideoJobRequest(BaseModel):
    video_url: HttpUrl
    voice_style: str = "hinglish_energetic"
    comment_count: int = 3

class VideoJob(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    source_url: str
    source_video_path: Optional[Path] = None
    script: Optional[VideoScript] = None
    rendered_video_path: Optional[Path] = None
    error_message: Optional[str] = None