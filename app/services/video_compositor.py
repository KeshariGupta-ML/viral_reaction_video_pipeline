import os
import uuid
from pathlib import Path
from typing import List, Optional, Tuple, Any
import ffmpeg

from app.core.logger import logger
from app.services.card_renderer import card_renderer_service
from app.schemas.script import VideoScript
from config import settings


class VideoCompositorService:
    def __init__(self, output_dir: Path = settings.OUTPUT_DIR, temp_dir: Path = settings.TEMP_DIR):
        self.output_dir = output_dir
        self.temp_dir = temp_dir

    def _find_transition_meme(self) -> Optional[Path]:
        """Finds any transition meme matching 'chaliye' or 'suru' in assets/memes."""
        if not settings.MEMES_DIR.exists():
            return None
        for ext in ["*.mp4", "*.webm", "*.mov", "*.mkv"]:
            for file_path in settings.MEMES_DIR.glob(ext):
                if any(kw in file_path.stem.lower() for kw in ["chaliye", "suru", "shuru", "start"]):
                    logger.info(f"🎬 [Video Compositor] Found transition meme: {file_path.name}")
                    return file_path
        logger.warning(
            f"⚠️ [Video Compositor] No transition meme found in {settings.MEMES_DIR}. Please place 'chaliye_shuru_karte_hai.mp4' in assets/memes/"
        )
        return None

    def get_media_duration(self, media_path: Path) -> float:
        try:
            probe = ffmpeg.probe(str(media_path))
            return float(probe["format"]["duration"])
        except Exception:
            return 4.0

    def _render_hook_intro_segment(
        self,
        source_video: Path,
        duration: float,
        audio_path: Path,
        output_segment: Path,
        top_banner_img: Optional[Path],
        spoken_timeline: List[Tuple[Path, float, float]]
    ):
        """
        Renders Hook Intro Scene:
        - Top persistent dynamic banner (hook_comment) stays at y=180 for the full duration.
        - Spoken 3-word chunks (hook_text) cycle sequentially at y=(H-h)/2 + 250.
        """
        in_vid = ffmpeg.input(str(source_video), ss=0)
        in_aud = ffmpeg.input(str(audio_path))

        bg = (
            in_vid.video
            .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')
            .filter('crop', 1080, 1920)
            .filter('boxblur', 30, 5)
            .filter('loop', loop=-1, size=1)
            .filter('trim', duration=duration)
            .filter('fps', fps=30)
            .filter('setpts', 'PTS-STARTPTS')
        )

        fg = (
            in_vid.video
            .filter('scale', 1080, 1920, force_original_aspect_ratio='decrease')
            .filter('loop', loop=-1, size=1)
            .filter('trim', duration=duration)
            .filter('fps', fps=30)
            .filter('setpts', 'PTS-STARTPTS')
        )

        comp = ffmpeg.overlay(bg, fg, x='(W-w)/2', y='(H-h)/2')

        # 1. Overlay Top Persistent Themed Banner for the full hook duration
        if top_banner_img and top_banner_img.exists():
            top_in = ffmpeg.input(str(top_banner_img), loop=1, t=duration)
            scaled_top = top_in.video.filter('scale', 980, -1).filter('fps', fps=30).filter('setpts', 'PTS-STARTPTS')
            comp = ffmpeg.overlay(
                comp,
                scaled_top,
                x='(W-w)/2',
                y=180,  # Safe eye-level placement above subjects
                enable=f'between(t,0,{duration:.2f})'
            )

        # 2. Overlay Sequenced 3-Word Narration Badges in the lower third
        for img_path, start_t, end_t in spoken_timeline:
            if img_path.exists():
                txt_in = ffmpeg.input(str(img_path))
                scaled_txt = txt_in.video.filter('scale', 960, -1).filter('fps', fps=30).filter('setpts', 'PTS-STARTPTS')
                comp = ffmpeg.overlay(
                    comp,
                    scaled_txt,
                    x='(W-w)/2',
                    y='(H-h)/2 + 250',
                    enable=f'between(t,{start_t:.2f},{end_t:.2f})'
                )

        aud = (
            in_aud.audio
            .filter('aformat', sample_rates='44100', channel_layouts='stereo')
            .filter('atrim', duration=duration)
            .filter('asetpts', 'PTS-STARTPTS')
        )

        out = ffmpeg.output(
            comp,
            aud,
            str(output_segment),
            vcodec='libx264',
            acodec='aac',
            audio_bitrate='192k',
            pix_fmt='yuv420p',
            r=30,
            t=duration
        )
        out.run(overwrite_output=True, capture_stdout=True, capture_stderr=True)

    def _render_video_playback_segment(self, source_video: Path, max_duration: float, output_segment: Path):
        """Plays source video at 1.0x normal speed with normalized framerate and audio[cite: 1]."""
        total_vid_duration = self.get_media_duration(source_video)
        vid_duration = min(total_vid_duration, max_duration)

        in_vid = ffmpeg.input(str(source_video), t=vid_duration)

        bg = (
            in_vid.video
            .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')
            .filter('crop', 1080, 1920)
            .filter('boxblur', 25, 5)
            .filter('trim', duration=vid_duration)
            .filter('fps', fps=30)
            .filter('setpts', 'PTS-STARTPTS')
        )

        fg = (
            in_vid.video
            .filter('scale', 1080, 1920, force_original_aspect_ratio='decrease')
            .filter('trim', duration=vid_duration)
            .filter('fps', fps=30)
            .filter('setpts', 'PTS-STARTPTS')
        )

        comp = ffmpeg.overlay(bg, fg, x='(W-w)/2', y='(H-h)/2')

        aud = (
            in_vid.audio
            .filter('aformat', sample_rates='44100', channel_layouts='stereo')
            .filter('atrim', duration=vid_duration)
            .filter('asetpts', 'PTS-STARTPTS')
        )

        out = ffmpeg.output(
            comp,
            aud,
            str(output_segment),
            vcodec='libx264',
            acodec='aac',
            audio_bitrate='192k',
            pix_fmt='yuv420p',
            r=30,
            t=vid_duration
        )
        out.run(overwrite_output=True, capture_stdout=True, capture_stderr=True)

    def _render_meme_clip_segment(self, meme_video_path: Path, output_segment: Path, max_duration: float = 3.5):
        """Normalizes meme clip into standard 1080x1920 30FPS format[cite: 1]."""
        dur = min(self.get_media_duration(meme_video_path), max_duration)
        in_vid = ffmpeg.input(str(meme_video_path), t=dur)

        bg = (
            in_vid.video
            .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')
            .filter('crop', 1080, 1920)
            .filter('boxblur', 30, 5)
            .filter('trim', duration=dur)
            .filter('fps', fps=30)
            .filter('setpts', 'PTS-STARTPTS')
        )

        fg = (
            in_vid.video
            .filter('scale', 1080, 1920, force_original_aspect_ratio='decrease')
            .filter('trim', duration=dur)
            .filter('fps', fps=30)
            .filter('setpts', 'PTS-STARTPTS')
        )

        comp = ffmpeg.overlay(bg, fg, x='(W-w)/2', y='(H-h)/2')

        aud = (
            in_vid.audio
            .filter('aformat', sample_rates='44100', channel_layouts='stereo')
            .filter('atrim', duration=dur)
            .filter('asetpts', 'PTS-STARTPTS')
        )

        out = ffmpeg.output(
            comp,
            aud,
            str(output_segment),
            vcodec='libx264',
            acodec='aac',
            audio_bitrate='192k',
            pix_fmt='yuv420p',
            r=30,
            t=dur
        )
        out.run(overwrite_output=True, capture_stdout=True, capture_stderr=True)

    def _render_comment_reaction_segment(
        self,
        source_video: Path,
        duration: float,
        audio_path: Path,
        comment_card_img: Path,
        output_segment: Path
    ):
        """Renders Comment Reaction segment with paused/blurred video & centered comment card[cite: 1]."""
        in_vid = ffmpeg.input(str(source_video), ss=0)
        in_aud = ffmpeg.input(str(audio_path))

        bg = (
            in_vid.video
            .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')
            .filter('crop', 1080, 1920)
            .filter('boxblur', 45, 6)
            .filter('loop', loop=-1, size=1)
            .filter('trim', duration=duration)
            .filter('fps', fps=30)
            .filter('setpts', 'PTS-STARTPTS')
        )

        fg = (
            in_vid.video
            .filter('scale', 1080, 1920, force_original_aspect_ratio='decrease')
            .filter('loop', loop=-1, size=1)
            .filter('trim', duration=duration)
            .filter('fps', fps=30)
            .filter('setpts', 'PTS-STARTPTS')
        )

        comp = ffmpeg.overlay(bg, fg, x='(W-w)/2', y='(H-h)/2')

        if comment_card_img and comment_card_img.exists():
            img_in = ffmpeg.input(str(comment_card_img), loop=1, t=duration)
            scaled_img = (
                img_in.video
                .filter('scale', 960, -1)
                .filter('fps', fps=30)
                .filter('setpts', 'PTS-STARTPTS')
            )
            comp = ffmpeg.overlay(comp, scaled_img, x='(W-w)/2', y='(H-h)/2 + 250')

        aud = (
            in_aud.audio
            .filter('aformat', sample_rates='44100', channel_layouts='stereo')
            .filter('atrim', duration=duration)
            .filter('asetpts', 'PTS-STARTPTS')
        )

        out = ffmpeg.output(
            comp,
            aud,
            str(output_segment),
            vcodec='libx264',
            acodec='aac',
            audio_bitrate='192k',
            pix_fmt='yuv420p',
            r=30,
            t=duration
        )
        out.run(overwrite_output=True, capture_stdout=True, capture_stderr=True)

    def compose_reaction_video(
        self,
        source_video_path: Path,
        comment_card_images: List[Path],
        tts_audio_paths: List[Path],
        script: VideoScript,
        output_filename: Optional[str] = None,
        banner_theme: Optional[str] = None
    ) -> Path:
        """Assembles all scenes into the final vertical 9:16 reaction short[cite: 1]."""
        out_name = output_filename or f"reaction_{str(uuid.uuid4())[:8]}.mp4"
        output_path = self.output_dir / out_name
        segments: List[Path] = []

        logger.info("🎬 [Video Compositor] Assembling reaction video with persistent hook banner & kinetic intro...")

        try:
            # ----------------------------------------------------
            # Scene 1: Hook Intro (Persistent top banner + timed spoken chunks + static audio)
            # ----------------------------------------------------
            if tts_audio_paths:
                hook_audio = Path(tts_audio_paths[0])
                hook_duration = self.get_media_duration(hook_audio)
                seg1_path = self.temp_dir / f"seg_1_hook_{uuid.uuid4().hex[:6]}.mp4"

                hook_comment_val = getattr(script, "hook_comment", None)
                hook_narration_val = getattr(script, "hook_narration", "Pehle ye video dekho, fir iske comments padhte hain!")

                top_banner_img, spoken_timeline = card_renderer_service.render_bold_hook_text_overlays(
                    hook_text=hook_narration_val,
                    hook_comment=hook_comment_val,
                    total_duration=hook_duration,
                    theme=banner_theme,
                    job_seed=source_video_path.name
                )

                self._render_hook_intro_segment(
                    source_video=source_video_path,
                    duration=hook_duration,
                    audio_path=hook_audio,
                    output_segment=seg1_path,
                    top_banner_img=top_banner_img,
                    spoken_timeline=spoken_timeline
                )
                segments.append(seg1_path)

                # ----------------------------------------------------
                # Scene 2: Video Playback (Up to 10s at normal speed)
                # ----------------------------------------------------
                seg2_path = self.temp_dir / f"seg_2_play_{uuid.uuid4().hex[:6]}.mp4"
                self._render_video_playback_segment(
                    source_video=source_video_path,
                    max_duration=10.0,
                    output_segment=seg2_path
                )
                segments.append(seg2_path)

                # ----------------------------------------------------
                # Scene 2.5: "Chaliye Shuru Karte Hain" Transition Meme
                # ----------------------------------------------------
                transition_meme = self._find_transition_meme()
                if transition_meme and transition_meme.exists():
                    seg_trans_path = self.temp_dir / f"seg_trans_{uuid.uuid4().hex[:6]}.mp4"
                    self._render_meme_clip_segment(transition_meme, seg_trans_path, max_duration=3.5)
                    segments.append(seg_trans_path)
                else:
                    logger.warning("⚠️ [Video Compositor] Skipping transition scene because meme file is missing.")

            # ----------------------------------------------------
            # Scene 3+: Comment Reactions & Contextual AI Memes
            # ----------------------------------------------------
            for idx, (card_img, reaction) in enumerate(zip(comment_card_images, script.reactions)):
                audio_idx = idx + 1
                if audio_idx < len(tts_audio_paths):
                    # Step A: Comment Card Roast
                    c_audio = Path(tts_audio_paths[audio_idx])
                    c_duration = self.get_media_duration(c_audio)
                    seg_c_path = self.temp_dir / f"seg_comment_{idx}_{uuid.uuid4().hex[:6]}.mp4"

                    self._render_comment_reaction_segment(
                        source_video=source_video_path,
                        duration=c_duration,
                        audio_path=c_audio,
                        comment_card_img=card_img,
                        output_segment=seg_c_path
                    )
                    segments.append(seg_c_path)

                    # Step B: Matching Meme Cutaway
                    if reaction.meme_clip:
                        meme_path = settings.MEMES_DIR / reaction.meme_clip
                        if meme_path.exists():
                            seg_meme_path = self.temp_dir / f"seg_meme_{idx}_{uuid.uuid4().hex[:6]}.mp4"
                            self._render_meme_clip_segment(meme_path, seg_meme_path, max_duration=3.5)
                            segments.append(seg_meme_path)

            # ----------------------------------------------------
            # Concatenate All Segments
            # ----------------------------------------------------
            concat_txt = self.temp_dir / f"concat_{uuid.uuid4().hex[:6]}.txt"
            with open(concat_txt, "w", encoding="utf-8") as f:
                for seg in segments:
                    safe_path = str(seg.resolve()).replace("\\", "/")
                    f.write(f"file '{safe_path}'\n")

            ffmpeg.input(str(concat_txt), format='concat', safe=0).output(
                str(output_path),
                c='copy'
            ).run(overwrite_output=True, capture_stdout=True, capture_stderr=True)

            # Cleanup temporary intermediate segment files
            for seg in segments:
                if seg.exists():
                    seg.unlink()
            if concat_txt.exists():
                concat_txt.unlink()

            logger.info(f"✨ [Video Compositor] Finished rendering final video at: {output_path}")
            return output_path

        except ffmpeg.Error as e:
            err_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
            logger.error(f"❌ [Video Compositor] FFmpeg error: {err_msg}")
            raise RuntimeError(f"FFmpeg compositing error: {err_msg}")


video_compositor_service = VideoCompositorService()