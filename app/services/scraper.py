import os
import json
import hashlib
import shutil
from pathlib import Path
from typing import Tuple, List, Dict, Any
import yt_dlp

from app.core.logger import logger
from app.schemas.comment import RawComment
from config import settings


class ScraperService:
    def __init__(self, cache_dir: Path = settings.VIDEOS_DIR, temp_dir: Path = settings.TEMP_DIR):
        self.cache_dir = cache_dir
        self.temp_dir = temp_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_url_hash(self, url: str) -> str:
        """Generates a stable 12-char SHA-256 hash from the video URL."""
        return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:12]

    def _cleanup_other_cached_videos(self, current_hash: str):
        """Purges any previously cached videos/metadata that don't match the current URL hash."""
        try:
            for item in self.cache_dir.iterdir():
                # If the file belongs to an older/different video, delete it
                if not item.name.startswith(current_hash):
                    if item.is_file() or item.is_symlink():
                        item.unlink(missing_ok=True)
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
            logger.info(f"🧹 [Scraper Cache] Cleaned up previous video cache in {self.cache_dir}")
        except Exception as e:
            logger.warning(f"⚠️ [Scraper Cache] Could not fully purge old video cache: {str(e)}")

    def extract_video_and_comments(
            self,
            video_url: str,
            max_comments: int = 30
    ) -> Tuple[Path, List[RawComment], Dict[str, Any]]:
        url_hash = self._get_url_hash(video_url)
        cached_video_pattern = list(self.cache_dir.glob(f"{url_hash}_video.*"))
        cached_meta_path = self.cache_dir / f"{url_hash}_metadata.json"

        # ----------------------------------------------------
        # 1. Same Video URL: Skip Download & Reuse Cache
        # ----------------------------------------------------
        if cached_video_pattern and cached_video_pattern[0].exists() and cached_meta_path.exists():
            cached_video_path = cached_video_pattern[0]
            logger.info(f"⚡ [Scraper Cache] Same URL detected! Reusing cached video: {cached_video_path.name}")

            with open(cached_meta_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)

            raw_comments = [RawComment(**c) for c in cached_data.get("comments", [])]
            metadata = cached_data.get("metadata", {})
            return cached_video_path, raw_comments, metadata

        # ----------------------------------------------------
        # 2. Different Video URL: Clean Previous Cache First
        # ----------------------------------------------------
        logger.info(f"🔄 [Scraper Cache] New video URL requested. Cleaning previous video files...")
        self._cleanup_other_cached_videos(current_hash=url_hash)

        # ----------------------------------------------------
        # 3. Download New Video & Extract Comments
        # ----------------------------------------------------
        output_template = str(self.cache_dir / f"{url_hash}_video.%(ext)s")

        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": output_template,
            "getcomments": True,
            "max_comments": max_comments,
            "quiet": True,
            "no_warnings": True,
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

        logger.info(f"📥 [Scraper Service] Downloading new video from: {video_url}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)

        video_path = Path(ydl.prepare_filename(info))
        if not video_path.exists():
            for f in self.cache_dir.glob(f"{url_hash}_video.*"):
                if f.suffix in [".mp4", ".mkv", ".webm"]:
                    video_path = f
                    break

        # Parse comments
        raw_comments = []
        raw_entries = info.get("comments") or []
        for c in raw_entries[:max_comments]:
            raw_comments.append(
                RawComment(
                    id=str(c.get("id") or ""),
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

        # Save metadata and comments cache for this URL
        cache_payload = {
            "source_url": video_url,
            "metadata": metadata,
            "comments": [c.dict() for c in raw_comments]
        }
        with open(cached_meta_path, "w", encoding="utf-8") as f:
            json.dump(cache_payload, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ [Scraper Service] Cached video & {len(raw_comments)} comments at: {self.cache_dir}")
        return video_path, raw_comments, metadata


scraper_service = ScraperService()