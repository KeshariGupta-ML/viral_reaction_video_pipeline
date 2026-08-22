import os
import shutil
import asyncio
from pathlib import Path
from typing import Dict, Any

from app.core.logger import logger
from app.schemas.video import JobStatus, VideoJob
from app.services.scraper import scraper_service
from app.services.curation_llm import curation_service
from app.services.tts_engine import tts_service
from app.services.card_renderer import card_renderer_service
from app.services.video_compositor import video_compositor_service
from config import settings


class PipelineOrchestrator:
    def __init__(self):
        self.jobs: Dict[str, VideoJob] = {}

    def _cleanup_temp_dir(self):
        """Removes all files in the temp folder to prevent disk bloating on new video runs."""
        try:
            temp_path = settings.TEMP_DIR
            if temp_path.exists():
                for item in temp_path.iterdir():
                    if item.is_file() or item.is_symlink():
                        item.unlink(missing_ok=True)
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                logger.info(f"🧹 [Pipeline Cleanup] Cleared temporary files from {temp_path}")
            else:
                temp_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"⚠️ [Pipeline Cleanup] Could not completely clean temp folder: {str(e)}")

    def create_job(self, job_id: str, video_url: str) -> VideoJob:
        """Immediately registers job in memory so polling endpoints do not return 404."""
        job = VideoJob(job_id=job_id, status=JobStatus.QUEUED, source_url=video_url)
        self.jobs[job_id] = job
        return job

    async def run_pipeline(self, job_id: str, video_url: str, comment_count: int = 2) -> VideoJob:
        # 0. Clean temporary directory at start of new generation
        self._cleanup_temp_dir()

        job = self.jobs.get(job_id) or VideoJob(job_id=job_id, status=JobStatus.DOWNLOADING, source_url=video_url)
        job.status = JobStatus.DOWNLOADING
        self.jobs[job_id] = job

        try:
            # Step 1: Ingestion & Scraping
            logger.info(f"🚀 [Pipeline {job_id}] Step 1/5: Scraping video and comments...")
            video_path, raw_comments, metadata = scraper_service.extract_video_and_comments(
                video_url=video_url,
                max_comments=30
            )
            job.source_video_path = video_path

            # Step 2: AI Curation & Script Generation (Gemini 2.5 Flash)
            job.status = JobStatus.CURATING
            logger.info(f"🤖 [Pipeline {job_id}] Step 2/5: Curating top comments with Gemini...")
            script = curation_service.curate_and_generate_script(
                raw_comments=raw_comments,
                comment_count=comment_count
            )
            job.script = script

            # Step 3: Audio Synthesis (TTS) & Card Snapshot Generation (Pillow)
            job.status = JobStatus.SYNTHESIZING
            logger.info(f"🎙️ [Pipeline {job_id}] Step 3/5: Generating TTS audio & comment cards...")

            card_images = []
            audio_paths = []

            # Generate hook audio
            hook_audio = await tts_service.generate_speech(script.hook_narration)
            audio_paths.append(hook_audio)

            for reaction in script.reactions:
                # Generate audio for each comment roast
                r_audio = await tts_service.generate_speech(reaction.roast_narration)
                audio_paths.append(r_audio)

                # Render comment card PNG
                card_img = card_renderer_service.render_comment_card_to_image(
                    author=reaction.author,
                    comment_text=reaction.comment_text,
                    likes=reaction.likes,
                    replies=reaction.replies,
                    avatar_url=reaction.avatar_url
                )
                card_images.append(card_img)

            # Step 4: Video Composition (Segment assembly & kinetic typography concatenation)
            job.status = JobStatus.RENDERING
            logger.info(f"🎬 [Pipeline {job_id}] Step 4/5: Compositing final vertical 9:16 video...")

            output_filename = f"reaction_{job_id}.mp4"
            rendered_path = video_compositor_service.compose_reaction_video(
                source_video_path=video_path,
                comment_card_images=card_images,
                tts_audio_paths=audio_paths,
                hook_narration_text=script.hook_narration,
                output_filename=output_filename
            )
            job.rendered_video_path = rendered_path

            # Step 5: Completed
            job.status = JobStatus.COMPLETED
            logger.info(f"✨ [Pipeline {job_id}] Step 5/5: Pipeline completed successfully! Output: {rendered_path}")

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            logger.error(f"❌ [Pipeline {job_id}] Pipeline failed: {str(e)}")

        return job

    def get_job(self, job_id: str) -> VideoJob:
        return self.jobs.get(job_id)


pipeline_orchestrator = PipelineOrchestrator()