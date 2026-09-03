import os
import re
import uuid
import math
from enum import Enum
from pathlib import Path
import random
from typing import List, Tuple, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pilmoji import Pilmoji

from app.core.logger import logger
from config import settings

# High-CTR Viral Hook Fallback Pool
DEFAULT_HOOK_COMMENTS: List[str] = [
    "WAIT FOR THE END!",
    "BHAI BAWAAL MMOVE HAI!",
    "WAIT TILL THE END!",
    "WHAT JUST HAPPENED!",
]


class BannerTheme(str, Enum):
    KINETIC_YELLOW = "kinetic_yellow"  # Neon Yellow (#CCFF00) + Black Stroke
    CRIMSON_CYBER = "crimson_cyber"  # Hot Red + White / Black Stroke
    ELECTRIC_CYAN = "electric_cyan"  # Neon Cyan + Black Stroke
    NEON_PURPLE = "neon_purple"  # Purple + Neon Yellow Stroke
    TOXIC_LIME = "toxic_lime"  # Neon Lime + Black Stroke
    MINIMAL_DARK = "minimal_dark"  # Obsidian Black + Neon Gold


THEME_CONFIGS: Dict[BannerTheme, Dict[str, Any]] = {
    BannerTheme.KINETIC_YELLOW: {
        "text_color": (215, 255, 0, 255),  # Vibrant Neon Yellow
        "stroke_color": (0, 0, 0, 255),  # Heavy Black Letter Outline
        "stroke_width": 8,
    },
    BannerTheme.CRIMSON_CYBER: {
        "text_color": (255, 255, 255, 255),
        "stroke_color": (0, 0, 0, 255),
        "stroke_width": 8,
    },
    BannerTheme.ELECTRIC_CYAN: {
        "text_color": (6, 235, 255, 255),
        "stroke_color": (0, 0, 0, 255),
        "stroke_width": 8,
    },
    BannerTheme.NEON_PURPLE: {
        "text_color": (255, 230, 0, 255),
        "stroke_color": (0, 0, 0, 255),
        "stroke_width": 8,
    },
    BannerTheme.TOXIC_LIME: {
        "text_color": (163, 255, 30, 255),
        "stroke_color": (0, 0, 0, 255),
        "stroke_width": 8,
    },
    BannerTheme.MINIMAL_DARK: {
        "text_color": (255, 255, 255, 255),
        "stroke_color": (0, 0, 0, 255),
        "stroke_width": 8,
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


def _measure_line_width(font: ImageFont.ImageFont, text: str, stroke_w: int, tracking: int = 3) -> int:
    """Measures precise line width using typographic advance plus subtle tracking."""
    if not text:
        return 0
    total_w = 0
    for i, char in enumerate(text):
        if char == " ":
            total_w += int(font.getlength(" "))
        else:
            total_w += int(font.getlength(char)) + (tracking if i < len(text) - 1 else 0)
    # Include the stroke overhang on the outer left and right edges
    return total_w + (stroke_w * 2)


def _draw_text_with_letter_spacing(
        draw: ImageDraw.Draw,
        text: str,
        xy: tuple,
        font: ImageFont.ImageFont,
        fill: tuple,
        stroke_fill: tuple,
        stroke_width: int,
        tracking: int = 3
):
    """
    Renders text using typographic advance to maintain snug, punchy kerning
    without character strokes merging together.
    """
    x, y = xy
    # Offset starting X to account for outer left stroke boundary
    x += stroke_width

    for i, char in enumerate(text):
        if char == " ":
            x += int(font.getlength(" "))
            continue

        draw.text(
            (x, y),
            char,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill
        )
        # Advance by natural font advance + small tracking buffer
        char_advance = int(font.getlength(char))
        x += char_advance + tracking


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

    def _draw_default_avatar(self, draw: ImageDraw.Draw, author: str, box: tuple):
        """Draws a clean, dynamic letter avatar based on author name."""
        x0, y0, x1, y1 = box
        w = x1 - x0
        h = y1 - y0

        # Deterministic palette based on username
        palette = [
            (239, 68, 68, 255),  # Red
            (249, 115, 22, 255),  # Orange
            (16, 185, 129, 255),  # Emerald
            (59, 130, 246, 255),  # Blue
            (168, 85, 247, 255),  # Purple
            (236, 72, 153, 255),  # Pink
            (14, 165, 233, 255),  # Sky
        ]
        bg_color = palette[hash(author) % len(palette)]

        # 1. Circle Background & Red Accent Ring
        draw.ellipse(box, fill=bg_color, outline=(255, 0, 51, 255), width=3)

        # 2. Bold Initial Letter
        initial = (author.strip()[:1] or "U").upper()
        try:
            initial_font = ImageFont.truetype("arialbd.ttf", int(h * 0.55))
        except IOError:
            initial_font = ImageFont.load_default()

        center_x = x0 + (w // 2)
        center_y = y0 + (h // 2) - 2
        draw.text((center_x, center_y), initial, fill=(255, 255, 255, 255), font=initial_font, anchor="mm")

    def _render_themed_comment_banner(
            self,
            text: str,
            font: ImageFont.ImageFont,
            cfg: Dict[str, Any],
            output_path: Path
    ):
        clean_text = _strip_unsupported_characters(text).upper()
        if not clean_text:
            clean_text = "GAJAB FIGURE\nYAAR"

        # Split into 2 lines if 3 or more words
        words = clean_text.split()
        if len(words) >= 3 and "\n" not in clean_text:
            mid = math.ceil(len(words) / 2)
            lines = [" ".join(words[:mid]), " ".join(words[mid:])]
        else:
            lines = clean_text.split("\n")

        # 5-6px outline gives a bold border without eating the font's negative space
        stroke_w = cfg.get("stroke_width", 6)
        text_color = cfg.get("text_color", (215, 255, 0, 255))
        stroke_color = cfg.get("stroke_color", (0, 0, 0, 255))

        # Tight tracking: 2px to 4px keeps letters close like thumbnail typography
        tracking = 3
        line_spacing = 8

        # 1. Measure total dimensions
        line_widths = [_measure_line_width(font, line, stroke_w, tracking) for line in lines]
        max_line_w = max(line_widths) if line_widths else 200

        # Calculate exact text line height
        dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        dummy_draw = ImageDraw.Draw(dummy_img)
        char_bbox = dummy_draw.textbbox((0, 0), "HG", font=font, stroke_width=stroke_w)
        line_h = char_bbox[3] - char_bbox[1]
        total_text_h = (line_h * len(lines)) + (line_spacing * (len(lines) - 1))

        pad = stroke_w * 4
        raw_w = max_line_w + (pad * 2)
        raw_h = total_text_h + (pad * 2)

        # 2. Draw snug text onto intermediate transparent canvas
        temp_canvas = Image.new("RGBA", (raw_w, raw_h), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_canvas)

        curr_y = pad
        for idx, line in enumerate(lines):
            line_w = line_widths[idx]
            curr_x = (raw_w - line_w) // 2
            _draw_text_with_letter_spacing(
                draw=temp_draw,
                text=line,
                xy=(curr_x, curr_y),
                font=font,
                fill=text_color,
                stroke_fill=stroke_color,
                stroke_width=stroke_w,
                tracking=tracking
            )
            curr_y += line_h + line_spacing

        # 3. Vertical stretch (1.75x - 1.9x yields the tall condensed look without distorting edges)
        stretched_w = raw_w
        stretched_h = int(raw_h * 1.8)
        stretched_text = temp_canvas.resize((stretched_w, stretched_h), resample=Image.Resampling.BICUBIC)

        # 4. Center onto transparent overlay
        canvas_w = 1080
        canvas_h = max(stretched_h + 40, 420)
        final_canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

        paste_x = (canvas_w - stretched_w) // 2
        paste_y = (canvas_h - stretched_h) // 2
        final_canvas.paste(stretched_text, (paste_x, paste_y), stretched_text)

        final_canvas.save(str(output_path), "PNG")
        return output_path

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
        """Renders clean white card with Twitter Blue accents, initial avatar, and emoji support."""
        card_id = str(uuid.uuid4())[:8]
        output_path = self.output_dir / f"card_{card_id}.png"

        # Twitter Color Palette
        TWITTER_BLUE = (29, 155, 240, 255)  # #1D9BF0
        CARD_BG = (255, 255, 255, 255)  # Pure White
        TEXT_BLACK = (15, 20, 25, 255)  # Crisp Black
        TEXT_MUTED = (83, 100, 113, 255)  # Twitter Muted Gray
        DIVIDER_COLOR = (239, 243, 244, 255)  # Light Border Gray

        width, height = 1000, 390
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # 1. White Card Backdrop with Twitter Blue Border
        card_box = (15, 15, width - 15, height - 15)
        draw.rounded_rectangle(card_box, radius=36, fill=CARD_BG, outline=TWITTER_BLUE, width=5)

        try:
            font_title = ImageFont.truetype("arialbd.ttf", 36)
            font_subtitle = ImageFont.truetype("arialbd.ttf", 22)
            font_body = ImageFont.truetype("arialbd.ttf", 34)
            font_meta = ImageFont.truetype("arialbd.ttf", 24)
            font_avatar = ImageFont.truetype("arialbd.ttf", 40)
        except IOError:
            font_title = font_subtitle = font_body = font_meta = font_avatar = ImageFont.load_default()

        # 2. Twitter Default Avatar Circle with Bold Initial
        avatar_box = (45, 40, 115, 110)
        draw.ellipse(avatar_box, fill=TWITTER_BLUE)
        initial = (author.strip().lstrip("@")[:1] or "U").upper()
        draw.text((80, 73), initial, fill=(255, 255, 255, 255), font=font_avatar, anchor="mm")

        # 3. Twitter Blue Author Name & Handle
        clean_author = author if author.startswith("@") else f"@{author}"
        draw.text((135, 42), clean_author, fill=TWITTER_BLUE, font=font_title)

        # 4. Divider Line
        draw.line([(45, 295), (width - 45, 295)], fill=DIVIDER_COLOR, width=3)

        # 5. Format Comment Body
        formatted_comment = f'"{comment_text}"'
        if len(formatted_comment) > 60:
            formatted_comment = formatted_comment[:57] + '..."'

        # 6. Render Emoji Layers via Pilmoji (Single pass to avoid double rendering)
        with Pilmoji(image) as pilmoji:
            # Top comment subtitle (single render)
            pilmoji.text((135, 88), "🔥 Top Comment", fill=TEXT_MUTED, font=font_subtitle)

            # High-contrast body text with real colored emojis
            pilmoji.text((45, 155), formatted_comment, fill=TEXT_BLACK, font=font_body)

            # Footer metrics with Twitter Blue accent
            footer_text = f"❤️ {likes} Likes      💬 {replies} Replies"
            pilmoji.text((45, 318), footer_text, fill=TWITTER_BLUE, font=font_meta)

        image.save(str(output_path), "PNG")
        logger.info(f"✅ [Card Renderer] Comment card image saved to: {output_path}")
        return output_path


card_renderer_service = CardRendererService()
