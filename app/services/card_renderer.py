import os
import uuid
from pathlib import Path
<<<<<<< HEAD
from typing import List, Tuple
=======
>>>>>>> origin/main
from PIL import Image, ImageDraw, ImageFont

from app.core.logger import logger
from config import settings


class CardRendererService:
    def __init__(self, output_dir: Path = settings.TEMP_DIR):
        self.output_dir = output_dir

<<<<<<< HEAD
    def render_bold_hook_text_overlays(
        self,
        hook_text: str = "Pehle ye video dekho, feer iske comments padhte hain! Aur like subscribe thok ke jaiyega!",
        total_duration: float = 5.0
    ) -> List[Tuple[Path, float, float]]:
        """
        Splits hook text into 2-3 word chunks and renders bold, high-contrast kinetic typography images.
        Returns a list of (image_path, start_time, end_time).
        """
        words = hook_text.replace("!", "").replace(",", "").split()
        # Group into 3 words per frame
        chunk_size = 3
        chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

        time_per_chunk = total_duration / max(len(chunks), 1)
        overlay_timeline = []

        try:
            # High-impact bold font
            font = ImageFont.truetype("arialbd.ttf", 64)
        except IOError:
            try:
                font = ImageFont.truetype("arial.ttf", 64)
            except IOError:
                font = ImageFont.load_default()

        for idx, chunk in enumerate(chunks):
            start_t = idx * time_per_chunk
            end_t = (idx + 1) * time_per_chunk
            img_id = str(uuid.uuid4())[:6]
            output_path = self.output_dir / f"hook_bold_{img_id}.png"

            # Create canvas
            width, height = 1000, 260
            image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)

            # Draw glowing dark-yellow backdrop badge
            badge_box = (20, 20, width - 20, height - 20)
            draw.rounded_rectangle(badge_box, radius=36, fill=(0, 0, 0, 200), outline=(250, 204, 21, 240), width=5)

            # Draw heavy black drop-shadow for 3D punch
            text_upper = chunk.upper()
            draw.text((width // 2 - 2, height // 2 + 2), text_upper, fill=(0, 0, 0, 255), font=font, anchor="mm")
            # Draw bright bold yellow text
            draw.text((width // 2, height // 2), text_upper, fill=(250, 204, 21, 255), font=font, anchor="mm")

            image.save(str(output_path), "PNG")
            overlay_timeline.append((output_path, start_t, end_t))

        return overlay_timeline
=======
    def render_intro_card_to_image(self, text: str = "Pehle ye video dekho, fir iske comments padhte hain! 👇") -> Path:
        """Renders an attractive intro hook banner PNG natively using Pillow."""
        card_id = str(uuid.uuid4())[:8]
        output_path = self.output_dir / f"intro_banner_{card_id}.png"

        width, height = 980, 240
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Draw semi-transparent glass backdrop
        card_box = (10, 10, width - 10, height - 10)
        draw.rounded_rectangle(card_box, radius=32, fill=(15, 23, 42, 230), outline=(56, 189, 248, 200), width=4)

        try:
            font_title = ImageFont.truetype("arial.ttf", 36)
            font_sub = ImageFont.truetype("arial.ttf", 26)
        except IOError:
            font_title = font_sub = ImageFont.load_default()

        # Draw intro text
        draw.text((40, 45), "👀 Pehle ye video dekho,", fill=(255, 255, 255, 255), font=font_title)
        draw.text((40, 100), "fir iske comments padhte hain!", fill=(56, 189, 248, 255), font=font_title)
        draw.text((40, 165), "🔥 Like & Subscribe thok ke jaiyega!", fill=(226, 232, 240, 220), font=font_sub)

        image.save(str(output_path), "PNG")
        return output_path
>>>>>>> origin/main

    def render_comment_card_to_image(
        self,
        author: str,
        comment_text: str,
        likes: str = "1.2K",
        replies: str = "45",
        avatar_url: str = None
    ) -> Path:
<<<<<<< HEAD
        """Natively renders a dark-mode comment card PNG using Pillow."""
=======
        """Natively renders a high-definition dark-mode comment card PNG using Pillow."""
>>>>>>> origin/main
        card_id = str(uuid.uuid4())[:8]
        output_path = self.output_dir / f"card_{card_id}.png"

        logger.info(f"🎨 [Card Renderer] Natively drawing comment card for author: '{author}'")

        width, height = 1000, 360
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        card_box = (15, 15, width - 15, height - 15)
        draw.rounded_rectangle(card_box, radius=40, fill=(15, 23, 42, 235), outline=(255, 255, 255, 60), width=3)

        try:
<<<<<<< HEAD
            font_title = ImageFont.truetype("arialbd.ttf", 34)
            font_subtitle = ImageFont.truetype("arial.ttf", 22)
            font_body = ImageFont.truetype("arialbd.ttf", 32)
=======
            font_title = ImageFont.truetype("arial.ttf", 34)
            font_subtitle = ImageFont.truetype("arial.ttf", 22)
            font_body = ImageFont.truetype("arial.ttf", 32)
>>>>>>> origin/main
            font_meta = ImageFont.truetype("arial.ttf", 24)
        except IOError:
            font_title = font_subtitle = font_body = font_meta = ImageFont.load_default()

<<<<<<< HEAD
        # Avatar circle
=======
        # Avatar placeholder
>>>>>>> origin/main
        avatar_box = (50, 45, 120, 115)
        draw.ellipse(avatar_box, fill=(56, 189, 248, 255))

        # Author and badges
        draw.text((140, 45), author, fill=(56, 189, 248, 255), font=font_title)
        draw.text((140, 88), "Top Comment • 🔥 Most Liked", fill=(148, 163, 184, 255), font=font_subtitle)

        # Body Text
        formatted_comment = f'"{comment_text}"'
        if len(formatted_comment) > 65:
            formatted_comment = formatted_comment[:62] + "..."
        draw.text((50, 150), formatted_comment, fill=(255, 255, 255, 255), font=font_body)

        # Meta (Likes & Replies)
        footer_text = f"❤️  {likes}      💬  {replies} replies"
        draw.text((50, 280), footer_text, fill=(148, 163, 184, 255), font=font_meta)

        image.save(str(output_path), "PNG")
        logger.info(f"✅ [Card Renderer] Comment card image saved to: {output_path}")
        return output_path


card_renderer_service = CardRendererService()