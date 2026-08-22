import os
import uuid
from pathlib import Path
from typing import List, Tuple
import yt_dlp

from app.schemas.comment import RawComment
from app.core.logger import logger
from config import settings


class VideoScraperService:
    def __init__(self, download_dir: Path = settings.TEMP_DIR):
        self.download_dir = download_dir

    def _progress_hook(self, d: dict):
        """Logs live download progress."""
        if d.get("status") == "downloading":
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            percent = (downloaded / total_bytes * 100) if total_bytes > 0 else 0
            speed = d.get("speed", 0) or 0
            speed_mb = speed / (1024 * 1024)
            eta = d.get("eta", 0)
            logger.info(f"⏳ Downloading: {percent:.1f}% | Speed: {speed_mb:.2f} MB/s | ETA: {eta}s")
        elif d.get("status") == "finished":
            logger.info("✅ Video stream download complete. Processing final file...")

    def extract_video_and_comments(
        self,
        video_url: str,
        max_comments: int = 30
    ) -> Tuple[Path, List[RawComment], dict]:
        """
        Downloads the source video and extracts top comments with real-time logging.
        """
        job_id = str(uuid.uuid4())[:8]
        out_template = str(self.download_dir / f"{job_id}_source.%(ext)s")

        logger.info(f"🚀 [Job {job_id}] Starting ingestion for URL: {video_url}")

        ydl_opts = {
            "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
            "outtmpl": out_template,
            "getcomments": True,
            # Add user-agent headers to avoid 403 Forbidden blocks from YouTube
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            },
            "extractor_args": {
                "youtube": {
                    "max_comments": [str(max_comments), "all", "0", "0"]
                }
            },
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._progress_hook],
        }
        try:
            logger.info(f"🔍 [Job {job_id}] Fetching video metadata and comments...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)

            ext = info.get("ext", "mp4")
            downloaded_video_path = self.download_dir / f"{job_id}_source.{ext}"

            metadata = {
                "id": info.get("id"),
                "title": info.get("title"),
                "duration": info.get("duration", 0),
                "width": info.get("width"),
                "height": info.get("height"),
            }
            logger.info(f"🎬 Video metadata captured: '{metadata['title']}' ({metadata['duration']}s)")

            # Parse comments
            raw_comments: List[RawComment] = []
            extracted_comments = info.get("comments") or []
            logger.info(f"💬 Found {len(extracted_comments)} raw comment items. Normalizing top {max_comments}...")

            for idx, c in enumerate(extracted_comments[:max_comments]):
                text = c.get("text", "").strip()
                if not text:
                    continue

                raw_comments.append(
                    RawComment(
                        id=str(c.get("id", f"comment_{idx}")),
                        author=c.get("author", f"User_{idx}"),
                        text=text,
                        likes=int(c.get("like_count") or 0),
                        replies=int(c.get("reply_count") or 0),
                        avatar_url=c.get("author_thumbnail"),
                    )
                )

            # Sort descending by like count
            raw_comments.sort(key=lambda x: x.likes, reverse=True)
            logger.info(f"✨ Successfully parsed and ranked {len(raw_comments)} comments.")

            return downloaded_video_path, raw_comments, metadata

        except Exception as e:
            logger.error(f"❌ Ingestion failed for {video_url}: {str(e)}")
            raise e


scraper_service = VideoScraperService()