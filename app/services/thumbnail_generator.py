import math
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import List, Optional, Tuple, Union

import ffmpeg
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from app.core.logger import logger
from app.services.video_compositor import video_compositor_service
from config import settings


class FaceBoundingBox(BaseModel):
    box_2d: list[int] = Field(
        ...,
        description="Bounding box for the main person's face or head as [ymin, xmin, ymax, xmax] normalized from 0 to 1000.",
    )


# Rotating palette for word-by-word thumbnail hook styling
HOOK_WORD_PALETTE: List[Tuple[int, int, int, int]] = [
    (255, 235, 0, 255),    # High-impact Neon Yellow
    (255, 255, 255, 255),  # Pure Crisp White
    (0, 240, 255, 255),    # Electric Cyan
    (255, 120, 0, 255),    # Vibrant Orange
    (255, 40, 130, 255),   # Hot Punch Pink
    (150, 255, 30, 255),   # Toxic Lime
]


def clean_hook_text_glyphs(text: str) -> str:
    """
    Removes color emojis, symbol pictographs, and unsupported glyphs
    that cause empty rectangular box ('tofu') artifacts in Devanagari fonts.
    Retains Devanagari (Hindi), English letters, numbers, and basic punctuation.
    """
    # Regex keeps Devanagari (\u0900-\u097F), Latin letters, digits, and basic punctuation (, ! ? . ' " -)
    cleaned = re.sub(r'[^\u0900-\u097Fa-zA-Z0-9\s,!?.\'\"-]', '', text)
    # Collapse duplicate spaces
    return re.sub(r'\s+', ' ', cleaned).strip()
def ensure_devanagari_font(font_size: int = 135) -> ImageFont.ImageFont:
    """
    Locates a bold Hindi/Devanagari font or auto-downloads
    NotoSansDevanagari-Bold.ttf from Google Fonts.
    """
    fonts_dir = Path("assets") / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    local_font_file = fonts_dir / "NotoSansDevanagari-Bold.ttf"

    if not local_font_file.exists():
        logger.info("📥 [Thumbnail] Downloading NotoSansDevanagari-Bold.ttf...")
        font_url = (
            "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/"
            "hinted/ttf/NotoSansDevanagari/NotoSansDevanagari-Bold.ttf"
        )
        try:
            urllib.request.urlretrieve(font_url, str(local_font_file))
            logger.info("✅ [Thumbnail] Downloaded NotoSansDevanagari-Bold.ttf successfully.")
        except Exception as e:
            logger.warning(f"⚠️ [Thumbnail] Could not auto-download font: {e}")

    candidates = [
        str(local_font_file),
        "C:\\Windows\\Fonts\\NirmalaB.ttf",
        "C:\\Windows\\Fonts\\Nirmala.ttf",
        "C:\\Windows\\Fonts\\mangalb.ttf",
        "C:\\Windows\\Fonts\\mangal.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
        "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
        "/usr/share/fonts/truetype/gargi/gargi.ttf",
    ]

    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                return ImageFont.truetype(candidate, font_size)
            except Exception:
                continue

    try:
        return ImageFont.truetype("arialbd.ttf", font_size)
    except Exception:
        return ImageFont.load_default()


class ThumbnailGeneratorService:

    def __init__(
        self,
        temp_dir: Path = settings.TEMP_DIR,
        output_dir: Path = settings.OUTPUT_DIR,
    ):
        self.temp_dir = temp_dir
        self.output_dir = output_dir

        api_key = getattr(settings, "GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY"))
        self.client = genai.Client(api_key=api_key) if api_key else None
        self.arrow_asset_path = getattr(settings, "ASSETS_DIR", Path("assets")) / "images" / "arrow.png"

    # -------------------------------------------------------------------------
    # 1. Gemini Vision: Detect Face Bounding Box
    # -------------------------------------------------------------------------
    def detect_face_box_with_gemini(
        self, image_path: Path
    ) -> Tuple[int, int, int, int]:
        default_box = (380, 400, 700, 800)
        if not self.client:
            return default_box

        try:
            with Image.open(image_path) as img:
                img_w, img_h = img.size

            uploaded_image = Image.open(image_path)
            prompt = (
                "Locate the primary person's face or head in this image. "
                "Return the exact bounding box as [ymin, xmin, ymax, xmax] on a scale of 0 to 1000."
            )

            response = self.client.models.generate_content(
                model=getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash"),
                contents=[uploaded_image, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=FaceBoundingBox,
                    temperature=0.1,
                ),
            )

            box_data = FaceBoundingBox.model_validate_json(response.text)
            ymin_n, xmin_n, ymax_n, xmax_n = box_data.box_2d

            xmin = int((xmin_n / 1000.0) * img_w)
            ymin = int((ymin_n / 1000.0) * img_h)
            xmax = int((xmax_n / 1000.0) * img_w)
            ymax = int((ymax_n / 1000.0) * img_h)
            return (xmin, ymin, xmax, ymax)
        except Exception as e:
            logger.warning(f"⚠️ [Thumbnail] Gemini detection fallback: {e}")
            return default_box

    # -------------------------------------------------------------------------
    # 2. Overlay Arrow Asset (assets/images/arrow.png)
    # -------------------------------------------------------------------------
    def overlay_arrow_image(
        self,
        base_canvas: Optional[Union[Image.Image, Path, str]] = None,
        face_box: Tuple[int, int, int, int] = (380, 400, 700, 800),
        output_path: Optional[Path] = None,
        image_path: Optional[Union[Image.Image, Path, str]] = None,
        **kwargs,
    ) -> Union[Image.Image, Path]:
        source = image_path if image_path is not None else base_canvas
        if source is None:
            raise ValueError("Either image_path or base_canvas must be provided.")

        if isinstance(source, (str, Path)):
            base = Image.open(source).convert("RGBA")
        else:
            base = source.convert("RGBA")

        canvas_w, canvas_h = base.size

        if not self.arrow_asset_path.exists():
            logger.warning(f"⚠️ [Thumbnail] Arrow asset missing: {self.arrow_asset_path}")
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                base.convert("RGB").save(str(output_path), "JPEG", quality=95)
                return output_path
            return base

        raw_arrow = Image.open(self.arrow_asset_path).convert("RGBA")

        arrow_w = 320
        aspect = raw_arrow.height / raw_arrow.width
        arrow_h = int(arrow_w * aspect)
        raw_arrow = raw_arrow.resize((arrow_w, arrow_h), Image.Resampling.LANCZOS)

        xmin, ymin, xmax, ymax = face_box
        face_target_y = int(ymin + (ymax - ymin) * 0.40)

        space_left = xmin
        space_right = canvas_w - xmax

        if space_right >= space_left:
            target_x = min(canvas_w - 40, xmax + 20)
            target_y = face_target_y

            start_x = min(canvas_w - 50, target_x + 280)
            start_y = max(80, target_y - 250)

            dx = target_x - start_x
            dy = target_y - start_y
            angle_deg = math.degrees(math.atan2(dy, dx))

            rot_deg = angle_deg - 135
            arrow = raw_arrow.rotate(-rot_deg, expand=True, resample=Image.BICUBIC)

            paste_x = target_x
            paste_y = max(40, target_y - arrow.height + 30)
        else:
            target_x = max(40, xmin - 20)
            target_y = face_target_y

            start_x = max(40, target_x - 280)
            start_y = max(80, target_y - 250)

            flipped_arrow = raw_arrow.transpose(Image.FLIP_LEFT_RIGHT)

            dx = target_x - start_x
            dy = target_y - start_y
            angle_deg = math.degrees(math.atan2(dy, dx))

            rot_deg = angle_deg - 45
            arrow = flipped_arrow.rotate(-rot_deg, expand=True, resample=Image.BICUBIC)

            paste_x = max(20, target_x - arrow.width)
            paste_y = max(40, target_y - arrow.height + 30)

        paste_x = max(10, min(canvas_w - arrow.width - 10, paste_x))
        paste_y = max(10, min(canvas_h - arrow.height - 10, paste_y))

        base.paste(arrow, (int(paste_x), int(paste_y)), arrow)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            base.convert("RGB").save(str(output_path), "JPEG", quality=95)
            return output_path

        return base

    # -------------------------------------------------------------------------
    # 3. High-Impact Multi-Color Bottom Hook Text
    # -------------------------------------------------------------------------
    def render_multicolor_bottom_hook(
            self,
            base_canvas: Image.Image,
            hook_text: str,
            y_bottom_offset: int = 300,
    ) -> Image.Image:
        """
        Renders clean, high-visibility multi-colored hook typography
        with a balanced, thin black outline and subtle 3D drop shadow.
        """
        if not hook_text or not hook_text.strip():
            return base_canvas

        # Clean emojis and unsupported symbol glyphs
        clean_text = clean_hook_text_glyphs(hook_text)
        if not clean_text:
            clean_text = "ये क्या देख लिया!"

        canvas_w, canvas_h = base_canvas.size
        words = clean_text.split()
        if not words:
            return base_canvas

        if len(words) <= 3:
            lines = [words]
        else:
            mid = math.ceil(len(words) / 2)
            lines = [words[:mid], words[mid:]]

        target_font_size = 135
        max_allowable_width = canvas_w - 100

        while target_font_size >= 90:
            font = ensure_devanagari_font(font_size=target_font_size)
            dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            dummy_draw = ImageDraw.Draw(dummy_img)
            space_w = dummy_draw.textlength(" ", font=font)

            widths = [
                sum(dummy_draw.textlength(w, font=font) for w in l) + (len(l) - 1) * space_w
                for l in lines
            ]
            if max(widths) <= max_allowable_width:
                break
            target_font_size -= 6

        font = ensure_devanagari_font(font_size=target_font_size)
        dummy_img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        dummy_draw = ImageDraw.Draw(dummy_img)
        space_w = dummy_draw.textlength(" ", font=font)

        line_height = int(target_font_size * 1.35)
        total_text_h = len(lines) * line_height
        start_y = canvas_h - y_bottom_offset - total_text_h

        text_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_layer)

        def get_line_w(word_list):
            return sum(dummy_draw.textlength(w, font=font) for w in word_list) + (len(word_list) - 1) * space_w

        # --- Reduced boundary parameters ---
        # Subtle, crisp outline (5px - 6px instead of 14px - 18px)
        stroke_w = max(4, int(target_font_size * 0.045))
        # Tight, soft 3D shadow offset (3px x 4px)
        shadow_offset = (max(2, int(target_font_size * 0.025)), max(3, int(target_font_size * 0.035)))

        word_color_idx = 0

        for line_idx, line_words in enumerate(lines):
            line_w = get_line_w(line_words)
            curr_x = int((canvas_w - line_w) // 2)
            curr_y = int(start_y + (line_idx * line_height))

            for word in line_words:
                color = HOOK_WORD_PALETTE[word_color_idx % len(HOOK_WORD_PALETTE)]
                word_color_idx += 1

                # 1. Subtle, Tight Shadow (No bloated extra stroke)
                draw.text(
                    (curr_x + shadow_offset[0], curr_y + shadow_offset[1]),
                    word,
                    font=font,
                    fill=(0, 0, 0, 180),
                    stroke_width=stroke_w,
                    stroke_fill=(0, 0, 0, 180),
                )

                # 2. Refined, Crisp Black Character Border
                draw.text(
                    (curr_x, curr_y),
                    word,
                    font=font,
                    fill=(0, 0, 0, 255),
                    stroke_width=stroke_w,
                    stroke_fill=(0, 0, 0, 255),
                )

                # 3. Vivid Colored Word Face
                draw.text(
                    (curr_x, curr_y),
                    word,
                    font=font,
                    fill=color,
                )

                curr_x += int(dummy_draw.textlength(word, font=font) + space_w)

        return Image.alpha_composite(base_canvas, text_layer)

    # -------------------------------------------------------------------------
    # 4. Keyframe Extraction & Embedding
    # -------------------------------------------------------------------------
    def get_keyframe_from_compositor(self, video_path: Path) -> Path:
        candidate_frames = video_compositor_service.extract_candidate_keyframes(
            video_path=video_path, output_dir=self.temp_dir, count=3
        )
        if candidate_frames:
            return candidate_frames[len(candidate_frames) // 2]

        fallback_frame = self.temp_dir / f"fallback_{uuid.uuid4().hex[:6]}.jpg"
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
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_video_path

    def embed_container_cover(
        self,
        video_path: Path,
        thumbnail_path: Path,
        output_video_path: Path,
    ) -> Path:
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
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_video_path

    # -------------------------------------------------------------------------
    # 5. Full Pipeline
    # -------------------------------------------------------------------------
    def generate_and_attach(
        self,
        video_path: Path,
        title: str,
        description: str = "",
        output_video_path: Optional[Path] = None,
        hook_text: Optional[str] = None,
    ) -> Path:
        target_output = output_video_path or video_path

        self.output_dir.mkdir(parents=True, exist_ok=True)
        saved_thumb_file = self.output_dir / f"{target_output.stem}_thumb.jpg"

        # 1. Extract base keyframe
        temp_thumb = self.get_keyframe_from_compositor(video_path)

        # 2. Locate person's face via Gemini Flash
        face_box = self.detect_face_box_with_gemini(temp_thumb)

        # 3. Composite Arrow + Multi-Color Bottom Hook Text
        base_img = Image.open(temp_thumb).convert("RGBA")
        base_img = self.overlay_arrow_image(base_canvas=base_img, face_box=face_box)

        text_to_draw = hook_text or title or "WAIT FOR THE END!"
        base_img = self.render_multicolor_bottom_hook(base_img, hook_text=text_to_draw)

        composite_thumb_path = self.temp_dir / f"thumb_final_{uuid.uuid4().hex[:6]}.jpg"
        base_img.convert("RGB").save(str(composite_thumb_path), "JPEG", quality=95)

        shutil.copy(composite_thumb_path, saved_thumb_file)
        logger.info(f"📸 [Thumbnail] Saved permanent thumbnail image: {saved_thumb_file.name}")

        # 4. Prepend as Frame 0
        video_with_frame0 = self.temp_dir / f"f0_{uuid.uuid4().hex[:6]}.mp4"
        self.prepend_thumbnail_as_frame_zero(
            video_path=video_path,
            thumbnail_path=composite_thumb_path,
            output_video_path=video_with_frame0,
            freeze_duration=0.30,
        )

        # 5. Embed cover art
        final_staged = self.temp_dir / f"final_{uuid.uuid4().hex[:6]}.mp4"
        self.embed_container_cover(
            video_path=video_with_frame0,
            thumbnail_path=composite_thumb_path,
            output_video_path=final_staged,
        )

        final_staged.replace(target_output)

        if video_with_frame0.exists():
            video_with_frame0.unlink(missing_ok=True)

        logger.info(f"✨ [Thumbnail] Finished attaching thumbnail: {target_output.name}")
        return target_output


thumbnail_service = ThumbnailGeneratorService()