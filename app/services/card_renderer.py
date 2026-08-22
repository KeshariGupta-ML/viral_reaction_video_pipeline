import os
import uuid
from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFont

from app.core.logger import logger
from config import settings


class CardRendererService:
    def __init__(self, output_dir: Path = settings.TEMP_DIR):
        self.output_dir = output_dir

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

        # 1. Clean White Card Backdrop with Red Border
        card_box = (15, 15, width - 15, height - 15)
        draw.rounded_rectangle(card_box, radius=36, fill=(255, 255, 255, 255), outline=(255, 0, 51, 255), width=5)

        try:
            font_title = ImageFont.truetype("arialbd.ttf", 36)
            font_subtitle = ImageFont.truetype("arialbd.ttf", 22)
            font_body = ImageFont.truetype("arialbd.ttf", 34)
            font_meta = ImageFont.truetype("arialbd.ttf", 24)
        except IOError:
            font_title = font_subtitle = font_body = font_meta = ImageFont.load_default()

        # 2. Red Avatar Ring
        avatar_box = (45, 40, 115, 110)
        draw.ellipse(avatar_box, fill=(255, 241, 242, 255), outline=(255, 0, 51, 255), width=4)

        # 3. Red Bold Author Name
        draw.text((135, 42), author, fill=(225, 29, 72, 255), font=font_title)
        draw.text((135, 88), "🔥 Top Comment", fill=(100, 116, 139, 255), font=font_subtitle)

        # 4. Jet Black Bold Comment Text
        formatted_comment = f'"{comment_text}"'
        if len(formatted_comment) > 60:
            formatted_comment = formatted_comment[:57] + '..."'
        draw.text((45, 155), formatted_comment, fill=(15, 23, 42, 255), font=font_body)

        # 5. Divider Line
        draw.line([(45, 295), (width - 45, 295)], fill=(226, 232, 240, 255), width=3)

        # 6. Metrics
        footer_text = f"❤️ {likes} Likes      💬 {replies} Replies"
        draw.text((45, 318), footer_text, fill=(225, 29, 72, 255), font=font_meta)

        image.save(str(output_path), "PNG")
        return output_path


card_renderer_service = CardRendererService()