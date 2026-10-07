import os
import shutil
import subprocess
import urllib.parse
import uuid
from pathlib import Path
from typing import List, Optional

import ffmpeg
from google import genai
from google.genai import types
import httpx

from app.core.logger import logger
from app.services.video_compositor import video_compositor_service
from config import settings


class ThumbnailGeneratorService:

    def __init__(
        self,
        temp_dir: Path = settings.TEMP_DIR,
        output_dir: Path = settings.OUTPUT_DIR,
    ):
        self.temp_dir = temp_dir
        self.output_dir = output_dir

        api_key = getattr(
            settings, "GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY")
        )
        self.client = genai.Client(api_key=api_key) if api_key else None

    def create_thumbnail_prompt(self, title: str, description: str = "") -> str:
        """Formulates an optimized 9:16 high-CTR prompt for open-source FLUX."""
        fallback_prompt = (
            f"Hyper-expressive YouTube Shorts thumbnail, dramatic facial reaction, "
            f"bold neon vibrant lighting, cinematic contrast, 9:16 vertical poster, "
            f"topic: {title[:80]}"
        )

        if not self.client:
            return fallback_prompt

        system_instruction = (
            "You are an expert thumbnail designer for YouTube Shorts. "
            "Write a concise image generation prompt (max 45 words) describing an irresistible, "
            "cinematic, vertical 9:16 reaction thumbnail image matching the video topic. "
            "Include visual hook details: exaggerated emotion, dynamic lighting, high contrast. "
            "Output ONLY the raw prompt without quotes or markdown."
        )

        try:
            response = self.client.models.generate_content(
                model=getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash"),
                contents=[f"Title: {title}\nDescription: {description[:200]}"],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction, temperature=0.7
                ),
            )
            refined_prompt = response.text.strip().replace("\n", " ")
            return refined_prompt if refined_prompt else fallback_prompt
        except Exception as e:
            logger.warning(f"⚠️ [Thumbnail] Prompt formulation fallback: {e}")
            return fallback_prompt

    def generate_image_pollinations(
        self,
        prompt: str,
        output_path: Path,
        width: int = 1080,
        height: int = 1920,
    ) -> Path:
        """Generates 9:16 vertical thumbnail via Pollinations.ai (FLUX engine)."""
        encoded_prompt = urllib.parse.quote(prompt)
        seed = int(uuid.uuid4().int % 1_000_000)

        url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={width}&height={height}&model=flux&nologo=true&seed={seed}"
        )

        logger.info(
            "🎨 [Thumbnail] Requesting 9:16 FLUX image from Pollinations..."
        )

        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            output_path.write_bytes(response.content)

        logger.info(
            f"✅ [Thumbnail] Generated thumbnail image: {output_path.name}"
        )
        return output_path

    def get_keyframe_from_compositor(self, video_path: Path) -> Path:
        """
        Uses video_compositor_service to extract candidate keyframes
        and selects the middle frame (around 50% mark).
        """
        candidate_frames = (
            video_compositor_service.extract_candidate_keyframes(
                video_path=video_path, output_dir=self.temp_dir, count=3
            )
        )

        if candidate_frames:
            # Pick the middle frame (50% mark) to avoid intro/outro cards
            selected_frame = candidate_frames[len(candidate_frames) // 2]
            logger.info(
                f"📸 [Thumbnail] Selected keyframe from video compositor: {selected_frame.name}"
            )
            return selected_frame

        # Fallback if keyframe extraction returned empty list
        fallback_frame = (
            self.temp_dir / f"fallback_frame_{uuid.uuid4().hex[:6]}.jpg"
        )
        (
            ffmpeg.input(str(video_path), ss=2.0)
            .filter("scale", 1080, 1920, force_original_aspect_ratio="increase")
            .filter("crop", 1080, 1920)
            .output(str(fallback_frame), vframes=1)
            .run(overwrite_output=True, quiet=True)
        )
        return fallback_frame

    def prepend_thumbnail_as_frame_zero(
        self,
        video_path: Path,
        thumbnail_path: Path,
        output_video_path: Path,
        freeze_duration: float = 0.30,
    ) -> Path:
        """
        Injects thumbnail as the first 0.3s of the video stream.
        Forces YouTube & Instagram scrapers to select it as the default display image.
        """
        logger.info(
            f"🎞️ [Thumbnail] Prepending {freeze_duration}s Frame-0 thumbnail to"
            " video..."
        )

        filter_complex = (
            f"[0:v]scale=1080:1920,fps=30,format=yuv420p,setpts=PTS-STARTPTS[v_thumb]; "
            f"[1:v]scale=1080:1920,fps=30,format=yuv420p,setpts=PTS-STARTPTS[v_main]; "
            f"[v_thumb][v_main]concat=n=2:v=1:a=0[outv]; "
            f"aevalsrc=0:d={freeze_duration}:s=44100:c=stereo[silence]; "
            f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo[a_main]; "
            f"[silence][a_main]concat=n=2:v=0:a=1[outa]"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-t",
            str(freeze_duration),
            "-i",
            str(thumbnail_path),
            "-i",
            str(video_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[outv]",
            "-map",
            "[outa]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_video_path),
        ]
        subprocess.run(
            cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return output_video_path

    def embed_container_cover(
        self,
        video_path: Path,
        thumbnail_path: Path,
        output_video_path: Path,
    ) -> Path:
        """Embeds thumbnail into MP4 container metadata for Google Drive and file explorers."""
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(thumbnail_path),
            "-map",
            "0",
            "-map",
            "1",
            "-c",
            "copy",
            "-disposition:v:1",
            "attached_pic",
            str(output_video_path),
        ]
        subprocess.run(
            cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return output_video_path

    def generate_and_attach(
        self,
        video_path: Path,
        title: str,
        description: str = "",
        output_video_path: Optional[Path] = None,
    ) -> Path:
        target_output = output_video_path or video_path
        saved_thumb_file = self.output_dir / f"{video_path.stem}_thumb.jpg"
        temp_thumb: Optional[Path] = None

        thumbnail_mode = settings.THUMBNAIL

        # 1. Decide source thumbnail based on settings
        if thumbnail_mode != "AI_GENERATED":
            logger.info(
                "📸 [Thumbnail] Using video keyframe extraction mode"
                f" ({thumbnail_mode})..."
            )
            temp_thumb = self.get_keyframe_from_compositor(video_path)
        else:
            temp_thumb = (
                self.temp_dir / f"thumb_pollinations_{uuid.uuid4().hex[:6]}.jpg"
            )
            try:
                prompt = self.create_thumbnail_prompt(
                    title=title, description=description
                )
                self.generate_image_pollinations(
                    prompt=prompt, output_path=temp_thumb
                )
            except Exception as e:
                logger.warning(
                    f"⚠️ [Thumbnail] Pollinations generation failed ({e}),"
                    " falling back to compositor keyframe."
                )
                temp_thumb = self.get_keyframe_from_compositor(video_path)

        # # 2. Save a permanent copy to output directory (for n8n cover_url parameter)
        # if temp_thumb and temp_thumb.exists():
        #     shutil.copy(temp_thumb, saved_thumb_file)

        # 3. Prepend thumbnail as Frame 0 into video stream (for YouTube Shorts & Instagram default covers)
        video_with_frame0 = self.temp_dir / f"f0_{uuid.uuid4().hex[:6]}.mp4"
        self.prepend_thumbnail_as_frame_zero(
            video_path=video_path,
            thumbnail_path=temp_thumb,
            output_video_path=video_with_frame0,
            freeze_duration=0.30,
        )

        # 4. Attach container cover art (for Google Drive & local file explorers)
        final_staged = self.temp_dir / f"final_{uuid.uuid4().hex[:6]}.mp4"
        self.embed_container_cover(
            video_path=video_with_frame0,
            thumbnail_path=temp_thumb,
            output_video_path=final_staged,
        )

        final_staged.replace(target_output)

        # Cleanup scratch video file
        if video_with_frame0.exists():
            video_with_frame0.unlink(missing_ok=True)

        logger.info(
            "✨ [Thumbnail] Video updated with default thumbnail:"
            f" {target_output.name}"
        )
        return target_output


thumbnail_service = ThumbnailGeneratorService()