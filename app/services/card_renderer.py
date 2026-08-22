import os
import uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from app.core.logger import logger
from config import settings


class CardRendererService:
    def __init__(self, output_dir: Path = settings.TEMP_DIR):
        self.output_dir = output_dir

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

    def render_comment_card_to_image(
        self,
        author: str,
        comment_text: str,
        likes: str = "1.2K",
        replies: str = "45",
        avatar_url: str = None
    ) -> Path:
        """Natively renders a high-definition dark-mode comment card PNG using Pillow."""
        card_id = str(uuid.uuid4())[:8]
        output_path = self.output_dir / f"card_{card_id}.png"

        logger.info(f"🎨 [Card Renderer] Natively drawing comment card for author: '{author}'")

        width, height = 1000, 360
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        card_box = (15, 15, width - 15, height - 15)
        draw.rounded_rectangle(card_box, radius=40, fill=(15, 23, 42, 235), outline=(255, 255, 255, 60), width=3)

        try:
            font_title = ImageFont.truetype("arial.ttf", 34)
            font_subtitle = ImageFont.truetype("arial.ttf", 22)
            font_body = ImageFont.truetype("arial.ttf", 32)
            font_meta = ImageFont.truetype("arial.ttf", 24)
        except IOError:
            font_title = font_subtitle = font_body = font_meta = ImageFont.load_default()

        # Avatar placeholder
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