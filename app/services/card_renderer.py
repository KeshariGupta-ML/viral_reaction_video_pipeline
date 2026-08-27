import os
import re
import uuid
import math
from enum import Enum
from pathlib import Path
import random
from typing import List, Tuple, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from app.core.logger import logger
from config import settings

# High-CTR Viral Hook Fallback Pool
DEFAULT_HOOK_COMMENTS: List[str] = [
    "WAIT FOR THE END!",
    "BRO DELETED HIS ACCOUNT!",
    "WAIT TILL THE END!",
    "WHAT JUST HAPPENED!",
]


class BannerTheme(str, Enum):
    KINETIC_YELLOW = "kinetic_yellow"   # Neon Yellow (#CCFF00) + Black Stroke
    CRIMSON_CYBER = "crimson_cyber"     # Hot Red + White / Black Stroke
    ELECTRIC_CYAN = "electric_cyan"     # Neon Cyan + Black Stroke
    NEON_PURPLE = "neon_purple"         # Purple + Neon Yellow Stroke
    TOXIC_LIME = "toxic_lime"           # Neon Lime + Black Stroke
    MINIMAL_DARK = "minimal_dark"       # Obsidian Black + Neon Gold


THEME_CONFIGS: Dict[BannerTheme, Dict[str, Any]] = {
    BannerTheme.KINETIC_YELLOW: {
        "text_color": (215, 255, 0, 255),       # Vibrant Neon Yellow
        "stroke_color": (0, 0, 0, 255),          # Heavy Black Letter Outline
        "bubble_fill": (205, 255, 0, 255),       # Outer Neon Bubble
        "bubble_stroke": (0, 0, 0, 255),        # Bubble Outline
        "shadow_color": (0, 0, 0, 220),          # Ambient Drop Shadow
    },
    BannerTheme.CRIMSON_CYBER: {
        "text_color": (255, 255, 255, 255),
        "stroke_color": (0, 0, 0, 255),
        "bubble_fill": (244, 63, 94, 255),
        "bubble_stroke": (0, 0, 0, 255),
        "shadow_color": (0, 0, 0, 220),
    },
    BannerTheme.ELECTRIC_CYAN: {
        "text_color": (6, 235, 255, 255),
        "stroke_color": (0, 0, 0, 255),
        "bubble_fill": (6, 215, 245, 255),
        "bubble_stroke": (0, 0, 0, 255),
        "shadow_color": (0, 0, 0, 220),
    },
    BannerTheme.NEON_PURPLE: {
        "text_color": (255, 230, 0, 255),
        "stroke_color": (0, 0, 0, 255),
        "bubble_fill": (168, 85, 247, 255),
        "bubble_stroke": (0, 0, 0, 255),
        "shadow_color": (0, 0, 0, 220),
    },
    BannerTheme.TOXIC_LIME: {
        "text_color": (163, 255, 30, 255),
        "stroke_color": (0, 0, 0, 255),
        "bubble_fill": (150, 250, 20, 255),
        "bubble_stroke": (0, 0, 0, 255),
        "shadow_color": (0, 0, 0, 220),
    },
    BannerTheme.MINIMAL_DARK: {
        "text_color": (255, 255, 255, 255),
        "stroke_color": (0, 0, 0, 255),
        "bubble_fill": (25, 30, 45, 255),
        "bubble_stroke": (250, 204, 21, 255),
        "shadow_color": (0, 0, 0, 240),
    }
}


def _strip_unsupported_characters(text: str) -> str:
    """Strips unsupported unicode glyphs that cause empty box [ ] rendering."""
    return re.sub(r'[^\x00-\x7F]+', '', text).strip()


def _get_impact_font(font_size: int = 76) -> ImageFont.ImageFont:
    """Loads ultra-bold condensed headline fonts (Impact/Arial Black)."""
    for font_name in ["impact.ttf", "Impact.ttf", "ariblk.ttf", "arialbd.ttf", "Arial Bold.ttf"]:
        try:
            return ImageFont.truetype(font_name, font_size)
        except IOError:
            continue
    return ImageFont.load_default()


class CardRendererService:
    def __init__(self, output_dir: Path = settings.TEMP_DIR):
        self.output_dir = output_dir

    def _get_theme_by_seed(self, seed_str: str) -> BannerTheme:
        """Deterministically picks a banner theme based on seed."""
        themes = list(BannerTheme)
        idx = hash(seed_str) % len(themes)
        return themes[idx]

    def _render_standard_hook_badge(self, text: str, font: ImageFont.ImageFont, output_path: Path):
        """Draws standard dark-yellow glowing badge for bottom spoken chunks."""
        width, height = 1000, 260
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        badge_box = (20, 20, width - 20, height - 20)
        draw.rounded_rectangle(badge_box, radius=36, fill=(0, 0, 0, 210), outline=(250, 204, 21, 240), width=5)

        clean = _strip_unsupported_characters(text).upper()
        draw.text((width // 2 - 2, height // 2 + 2), clean, fill=(0, 0, 0, 255), font=font, anchor="mm")
        draw.text((width // 2, height // 2), clean, fill=(250, 204, 21, 255), font=font, anchor="mm")

        image.save(str(output_path), "PNG")

    def _render_themed_comment_banner(
        self,
        text: str,
        font: ImageFont.ImageFont,
        cfg: Dict[str, Any],
        output_path: Path
    ):
        """
        Renders a 2-line organic neon-sticker badge matching the viral YouTube Shorts reference:
        - Multi-line tight layout with heavy black font strokes
        - Organic neon bubble outline background
        - Deep directional 3D shadow and slight dynamic tilt
        """
        clean_text = _strip_unsupported_characters(text).upper()
        if not clean_text:
            clean_text = "HE REGRETTED\nTHIS INSTANTLY!"

        # Split into 2 lines if text contains more than 2 words
        words = clean_text.split()
        if len(words) >= 3 and "\n" not in clean_text:
            mid = math.ceil(len(words) / 2)
            lines = [" ".join(words[:mid]), " ".join(words[mid:])]
        else:
            lines = clean_text.split("\n")

        formatted_text = "\n".join(lines)

        canvas_w, canvas_h = 1080, 460
        base_canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

        # 1. Create text mask for the organic contour bubble
        mask = Image.new("L", (canvas_w, canvas_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.multiline_text(
            (canvas_w // 2, canvas_h // 2),
            formatted_text,
            font=font,
            fill=255,
            anchor="mm",
            align="center",
            spacing=10,
            stroke_width=24
        )

        # 2. Expand mask to create the thick neon bubble
        dilated_mask = mask.filter(ImageFilter.MaxFilter(size=27))
        bubble_edge = mask.filter(ImageFilter.MaxFilter(size=35))

        # 3. Directional 3D Drop Shadow
        shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow_layer)
        s_draw.bitmap((8, 16), bubble_edge, fill=cfg["shadow_color"])
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=10))
        base_canvas = Image.alpha_composite(base_canvas, shadow_layer)

        # 4. Outer Black Border & Neon Bubble Fill
        draw = ImageDraw.Draw(base_canvas)
        draw.bitmap((0, 0), bubble_edge, fill=cfg["bubble_stroke"])
        draw.bitmap((0, 0), dilated_mask, fill=cfg["bubble_fill"])

        # 5. Render Slanted/Stroked Text
        # Heavy black outline on individual text characters
        draw.multiline_text(
            (canvas_w // 2, canvas_h // 2),
            formatted_text,
            font=font,
            fill=cfg["text_color"],
            anchor="mm",
            align="center",
            spacing=10,
            stroke_width=8,
            stroke_fill=cfg["stroke_color"]
        )

        # 6. Apply -3.5 degree kinetic angle rotation
        rotated_banner = base_canvas.rotate(3.5, resample=Image.BICUBIC, expand=False)
        rotated_banner.save(str(output_path), "PNG")

    def render_bold_hook_text_overlays(
        self,
        hook_text: str = "Pehle ye video dekho, fir iske comments padhte hain! Aur like subscribe thok ke jaiyega!",
        hook_comment: Optional[str] = None,
        total_duration: float = 5.0,
        theme: Optional[str] = None,
        job_seed: str = ""
    ) -> Tuple[Optional[Path], List[Tuple[Path, float, float]]]:
        """
        Renders:
        1. top_banner_path: Persistent dynamic neon-sticker banner for hook_comment.
        2. spoken_chunks_timeline: Timed list of 3-word narration badge paths for hook_text.
        """
        if not hook_comment or str(hook_comment).strip().lower() in ["none", "null", ""]:
            hook_comment = random.choice(DEFAULT_HOOK_COMMENTS)

        selected_theme = BannerTheme.KINETIC_YELLOW
        if theme and theme in BannerTheme._value2member_map_:
            selected_theme = BannerTheme(theme)
        elif job_seed:
            selected_theme = self._get_theme_by_seed(job_seed)

        cfg = THEME_CONFIGS[selected_theme]
        font = _get_impact_font(font_size=76)

        # 1. Render Top Persistent Themed Neon Banner
        top_banner_path = self.output_dir / f"hook_banner_{selected_theme.value}_{uuid.uuid4().hex[:6]}.png"
        self._render_themed_comment_banner(hook_comment, font, cfg, top_banner_path)

        # 2. Render Sequenced 3-Word Lower Narration Badges
        words = _strip_unsupported_characters(hook_text).replace("!", "").replace(",", "").split()
        chunk_size = 3
        chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
        if not chunks:
            chunks = [hook_text]

        time_per_chunk = total_duration / max(len(chunks), 1)
        spoken_chunks_timeline = []

        try:
            body_font = ImageFont.truetype("arialbd.ttf", 64)
        except IOError:
            body_font = font

        for idx, chunk in enumerate(chunks):
            start_t = idx * time_per_chunk
            end_t = (idx + 1) * time_per_chunk
            img_id = str(uuid.uuid4())[:6]
            output_path = self.output_dir / f"hook_bold_{img_id}.png"

            self._render_standard_hook_badge(chunk, body_font, output_path)
            spoken_chunks_timeline.append((output_path, start_t, end_t))

        return top_banner_path, spoken_chunks_timeline

    def render_comment_card_to_image(
        self,
        author: str,
        comment_text: str,
        likes: str = "1.2K",
        replies: str = "45",
        avatar_url: str = None
    ) -> Path:
        """Renders clean white card with bold red author and black comment text."""
        card_id = str(uuid.uuid4())[:8]
        output_path = self.output_dir / f"card_{card_id}.png"

        width, height = 1000, 390
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        card_box = (15, 15, width - 15, height - 15)
        draw.rounded_rectangle(card_box, radius=36, fill=(255, 255, 255, 255), outline=(255, 0, 51, 255), width=5)

        try:
            font_title = ImageFont.truetype("arialbd.ttf", 36)
            font_subtitle = ImageFont.truetype("arialbd.ttf", 22)
            font_body = ImageFont.truetype("arialbd.ttf", 34)
            font_meta = ImageFont.truetype("arialbd.ttf", 24)
        except IOError:
            font_title = font_subtitle = font_body = font_meta = ImageFont.load_default()

        # Red Avatar Ring
        avatar_box = (45, 40, 115, 110)
        draw.ellipse(avatar_box, fill=(255, 241, 242, 255), outline=(255, 0, 51, 255), width=4)

        # Red Bold Author Name
        draw.text((135, 42), author, fill=(225, 29, 72, 255), font=font_title)
        draw.text((135, 88), "🔥 Top Comment", fill=(100, 116, 139, 255), font=font_subtitle)

        # Black Comment Body Text
        formatted_comment = f'"{comment_text}"'
        if len(formatted_comment) > 60:
            formatted_comment = formatted_comment[:57] + '..."'
        draw.text((45, 155), formatted_comment, fill=(15, 23, 42, 255), font=font_body)

        # Divider & Metrics
        draw.line([(45, 295), (width - 45, 295)], fill=(226, 232, 240, 255), width=3)
        footer_text = f"❤️ {likes} Likes      💬 {replies} Replies"
        draw.text((45, 318), footer_text, fill=(225, 29, 72, 255), font=font_meta)

        image.save(str(output_path), "PNG")
        return output_path


card_renderer_service = CardRendererService()