import os
import re
import uuid
import textwrap
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji

from app.core.logger import logger
from config import settings


def _strip_unsupported_characters(text: str) -> str:
    """Strips non-ASCII glyphs for standard TTF rendering fallbacks."""
    return re.sub(r'[^\x00-\x7F]+', '', text).strip()


def _get_bold_font(font_size: int = 64) -> ImageFont.ImageFont:
    """Loads ultra-bold condensed headline font."""
    for font_name in ["impact.ttf", "arialbd.ttf", "Arial Bold.ttf"]:
        try:
            return ImageFont.truetype(font_name, font_size)
        except IOError:
            continue
    return ImageFont.load_default()


class CardRendererService:
    def __init__(self, output_dir: Path = settings.TEMP_DIR):
        self.output_dir = output_dir

    def _draw_default_avatar(self, draw: ImageDraw.Draw, author: str, box: tuple, font: ImageFont.ImageFont):
        """Draws a clean, deterministic letter avatar circle based on author handle."""
        x0, y0, x1, y1 = box
        w = x1 - x0
        h = y1 - y0

        palette = [
            (29, 155, 240, 255),   # Twitter Blue
            (239, 68, 68, 255),    # Crimson Red
            (16, 185, 129, 255),   # Emerald Green
            (168, 85, 247, 255),   # Purple
            (249, 115, 22, 255),   # Amber Orange
        ]
        bg_color = palette[abs(hash(author)) % len(palette)]
        draw.ellipse(box, fill=bg_color)

        initial = (author.strip().lstrip("@")[:1] or "U").upper()
        center_x = x0 + (w // 2)
        center_y = y0 + (h // 2) - 1
        draw.text((center_x, center_y), initial, fill=(255, 255, 255, 255), font=font, anchor="mm")

    def render_bold_hook_text_overlays(
        self,
        hook_text: str = "Pehle ye video dekho, fir iske comments padhte hain! Aur like subscribe thok ke jaiyega!",
        total_duration: float = 5.0
    ) -> List[Tuple[Path, float, float]]:
        """
        Splits hook narration text into sequenced 3-word kinetic typography badges.
        Returns: List of (image_path, start_time, end_time)
        """
        words = _strip_unsupported_characters(hook_text).replace("!", "").replace(",", "").split()
        chunk_size = 3
        chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
        if not chunks:
            chunks = [hook_text]

        time_per_chunk = total_duration / max(len(chunks), 1)
        spoken_chunks_timeline = []
        font = _get_bold_font(font_size=64)

        for idx, chunk in enumerate(chunks):
            start_t = idx * time_per_chunk
            end_t = (idx + 1) * time_per_chunk
            img_id = str(uuid.uuid4())[:6]
            output_path = self.output_dir / f"hook_chunk_{img_id}.png"

            width, height = 1000, 260
            image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)

            # High-visibility dark badge with neon-yellow rim
            badge_box = (20, 20, width - 20, height - 20)
            draw.rounded_rectangle(
                badge_box,
                radius=36,
                fill=(0, 0, 0, 215),
                outline=(250, 204, 21, 255),
                width=5
            )

            text_upper = chunk.upper()
            # Black drop shadow
            draw.text((width // 2 - 2, height // 2 + 2), text_upper, fill=(0, 0, 0, 255), font=font, anchor="mm")
            # Neon yellow text
            draw.text((width // 2, height // 2), text_upper, fill=(250, 204, 21, 255), font=font, anchor="mm")

            image.save(str(output_path), "PNG")
            spoken_chunks_timeline.append((output_path, start_t, end_t))

        return spoken_chunks_timeline

    def render_comment_card_to_image(
        self,
        author: str,
        comment_text: str,
        likes: str = "1.2K",
        replies: str = "45",
        avatar_url: str = None
    ) -> Path:
        """Renders clean white card with color palette avatars, word-wrapped body, and full emoji support."""
        card_id = str(uuid.uuid4())[:8]
        output_path = self.output_dir / f"card_{card_id}.png"

        TWITTER_BLUE = (29, 155, 240, 255)
        CARD_BG = (255, 255, 255, 255)
        TEXT_BLACK = (15, 20, 25, 255)
        TEXT_MUTED = (83, 100, 113, 255)
        DIVIDER_COLOR = (239, 243, 244, 255)

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

        # 2. Dynamic letter avatar circle
        avatar_box = (45, 40, 115, 110)
        self._draw_default_avatar(draw, author, avatar_box, font_avatar)

        # 3. Divider Line
        draw.line([(45, 295), (width - 45, 295)], fill=DIVIDER_COLOR, width=3)

        # 4. Word-wrap comment body (max 2 lines, up to 36 chars per line)
        wrapped_lines = textwrap.wrap(f'"{comment_text}"', width=36)
        if len(wrapped_lines) > 2:
            wrapped_lines = wrapped_lines[:2]
            wrapped_lines[1] = wrapped_lines[1][:32] + '..."'

        # 5. Emoji-safe text rendering with Pilmoji
        clean_author = author if author.startswith("@") else f"@{author}"
        with Pilmoji(image) as pilmoji:
            # Author handle
            pilmoji.text((135, 42), clean_author, fill=TWITTER_BLUE, font=font_title)

            # Subtitle
            pilmoji.text((135, 88), "🔥 Top Comment", fill=TEXT_MUTED, font=font_subtitle)

            # Multi-line comment body
            line_y = 145 if len(wrapped_lines) == 2 else 170
            for line in wrapped_lines:
                pilmoji.text((45, line_y), line, fill=TEXT_BLACK, font=font_body)
                line_y += 45

            # Footer metrics
            footer_text = f"❤️ {likes} Likes      💬 {replies} Replies"
            pilmoji.text((45, 318), footer_text, fill=TWITTER_BLUE, font=font_meta)

        image.save(str(output_path), "PNG")
        logger.info(f"✅ [Card Renderer] Comment card saved: {output_path.name}")
        return output_path


card_renderer_service = CardRendererService()