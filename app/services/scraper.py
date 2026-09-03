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
        return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:12]

    def _cleanup_other_cached_videos(self, current_hash: str):
        try:
            for item in self.cache_dir.iterdir():
                if not item.name.startswith(current_hash):
                    if item.is_file() or item.is_symlink():
                        item.unlink(missing_ok=True)
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
            logger.info(f"🧹 [Scraper Cache] Cleaned up previous video cache in {self.cache_dir}")
        except Exception as e:
            logger.warning(f"⚠️ [Scraper Cache] Could not purge old video cache: {str(e)}")

    def extract_video_and_comments(
            self,
            video_url: str,
            max_comments: int = 30
    ) -> Tuple[Path, List[RawComment], Dict[str, Any]]:
        url_hash = self._get_url_hash(video_url)
        cached_video_pattern = list(self.cache_dir.glob(f"{url_hash}_video.*"))
        cached_meta_path = self.cache_dir / f"{url_hash}_metadata.json"

        # 1. Skip download only if existing cached file is NOT low res
        if cached_video_pattern and cached_video_pattern[0].exists() and cached_meta_path.exists():
            cached_video_path = cached_video_pattern[0]
            with open(cached_meta_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)

            # If the cached file is at least 720p, reuse it. Otherwise, force redownload.
            if cached_data.get("metadata", {}).get("height", 0) >= 720:
                logger.info(f"⚡ [Scraper Cache] Reusing high-res cached video: {cached_video_path.name}")
                raw_comments = [RawComment(**c) for c in cached_data.get("comments", [])]
                return cached_video_path, raw_comments, cached_data.get("metadata", {})
            else:
                logger.info(f"🗑️ [Scraper Cache] Existing cache is low-res (360p). Deleting and redownloading...")
                cached_video_path.unlink(missing_ok=True)
                cached_meta_path.unlink(missing_ok=True)

        # 2. Cleanup other videos
        self._cleanup_other_cached_videos(current_hash=url_hash)

        # 3. Locate FFmpeg binary
        ffmpeg_exe = shutil.which(
            "ffmpeg") or r"C:\Users\dg\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.EXE"
        ffmpeg_bin_dir = str(Path(ffmpeg_exe).parent)

        output_template = str(self.cache_dir / f"{url_hash}_video.%(ext)s")

        ydl_opts = {
            # Force 1080p/720p video + best audio (explicitly 137+140 fallback)
            "format": "137+140/bestvideo[height>=720]+bestaudio/bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "ffmpeg_location": ffmpeg_bin_dir,
            "outtmpl": output_template,
            "getcomments": True,
            "max_comments": max_comments,
            "quiet": False,
            "no_warnings": False,
        }

        logger.info(f"📥 [Scraper Service] Downloading 1080p stream for: {video_url}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)

        video_path = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
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
            "uploader": info.get("uploader"),
            "width": info.get("width"),
            "height": info.get("height")
        }

        cache_payload = {
            "source_url": video_url,
            "metadata": metadata,
            "comments": [c.dict() for c in raw_comments]
        }
        with open(cached_meta_path, "w", encoding="utf-8") as f:
            json.dump(cache_payload, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Downloaded {metadata.get('width')}x{metadata.get('height')} at: {video_path}")
        return video_path, raw_comments, metadata


scraper_service = ScraperService()