import os
import uuid
from pathlib import Path
from typing import Tuple, List, Dict, Any
import yt_dlp

from app.core.logger import logger
from app.schemas.comment import RawComment
from config import settings


class ScraperService:
    def __init__(self, temp_dir: Path = settings.TEMP_DIR):
        self.temp_dir = temp_dir

    def extract_video_and_comments(
            self,
            video_url: str,
            max_comments: int = 30
    ) -> Tuple[Path, List[RawComment], Dict[str, Any]]:
        job_prefix = str(uuid.uuid4())[:8]
        output_template = str(self.temp_dir / f"{job_prefix}_video.%(ext)s")

        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": output_template,
            "getcomments": True,
            "max_comments": max_comments,
            "quiet": True,
            "no_warnings": True,
            # Spoof official client to bypass bot detection checks
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "web_creator"],
                }
            },
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
        }

        logger.info(f"📥 [Scraper Service] Downloading video & comments from: {video_url}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)

        video_path = Path(ydl.prepare_filename(info))

        # Ensure mp4 extension matches
        if not video_path.exists():
            for f in self.temp_dir.glob(f"{job_prefix}_video.*"):
                if f.suffix in [".mp4", ".mkv", ".webm"]:
                    video_path = f
                    break

        # Parse comments
        raw_comments = []
        raw_entries = info.get("comments") or []
        for c in raw_entries[:max_comments]:
            raw_comments.append(
                RawComment(
                    id=str(c.get("id") or uuid.uuid4()),
                    author=str(c.get("author") or "Anonymous"),
                    text=str(c.get("text") or ""),
                    likes=str(c.get("like_count") or "0"),
                    replies=str(c.get("reply_count") or "0"),
                    avatar_url=c.get("author_thumbnail")
                )
            )

        metadata = {
            "title": info.get("title"),
            "duration": info.get("duration"),
            "views": info.get("view_count"),
            "uploader": info.get("uploader")
        }

        logger.info(
            f"✅ [Scraper Service] Downloaded video ({video_path.name}) and extracted {len(raw_comments)} comments.")
        return video_path, raw_comments, metadata


scraper_service = ScraperService()