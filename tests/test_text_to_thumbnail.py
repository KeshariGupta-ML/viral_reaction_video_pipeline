from pathlib import Path
from PIL import Image
from app.services.thumbnail_generator import thumbnail_service

# Load any frame
base_img = Image.open("E:/Keshari work/viral_reaction_video_pipeline/storage/output/test_output_reaction_thumb.jpg").convert("RGBA")

# Add the multi-colored hook text
result_img = thumbnail_service.render_multicolor_bottom_hook(
    base_canvas=base_img,
    hook_text="भाई, क्या बवाल डांस है!",
)
result_img.convert("RGB").save("test_hook_thumb.jpg")
print("✅ Created test_hook_thumb.jpg with multi-color bottom hook text!")