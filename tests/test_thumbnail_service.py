import os
import shutil
from pathlib import Path
from PIL import Image

from app.core.logger import logger
from app.services.thumbnail_generator import thumbnail_service
from config import settings


def find_test_source_video() -> Path:
    output_dir = Path(settings.OUTPUT_DIR)

    target = output_dir / "reaction_5d6064d0.mp4"
    if target.exists():
        return target

    videos = list(output_dir.glob("*.mp4"))
    if videos:
        return videos[0]

    raise FileNotFoundError(
        f"No MP4 video found in {output_dir.resolve()}. Please place an MP4 file there first."
    )


def test_thumbnail_feature():
    logger.info("🧪 [Thumbnail Test] Starting thumbnail test...")

    source_video = find_test_source_video()
    logger.info(f"📹 [Thumbnail Test] Testing with video: {source_video.name}")

    test_sandbox = Path(settings.TEMP_DIR) / "thumbnail_test_sandbox"
    test_sandbox.mkdir(parents=True, exist_ok=True)

    test_input_video = test_sandbox / "sample_video.mp4"
    shutil.copy(source_video, test_input_video)

    # 1. Keyframe Extraction
    logger.info("📸 [Step 1] Extracting video keyframe...")
    keyframe_path = thumbnail_service.get_keyframe_from_compositor(test_input_video)
    assert keyframe_path.exists() and keyframe_path.stat().st_size > 0

    with Image.open(keyframe_path) as img:
        assert img.size == (1080, 1920)

    # 2. Gemini Face Localization
    logger.info("🤖 [Step 2] Pinpointing face box via Gemini Flash...")
    face_box = thumbnail_service.detect_face_box_with_gemini(keyframe_path)
    assert len(face_box) == 4
    xmin, ymin, xmax, ymax = face_box
    assert xmax > xmin and ymax > ymin

    # 3. Arrow Overlay (assets/images/arrow.png)
    logger.info("🎯 [Step 3] Overlaying 3D Arrow...")
    arrow_test_output = test_sandbox / "test_arrow_only.jpg"
    arrowed_image_path = thumbnail_service.overlay_arrow_image(
        image_path=keyframe_path,
        face_box=face_box,
        output_path=arrow_test_output,
    )
    assert Path(arrowed_image_path).exists() and Path(arrowed_image_path).stat().st_size > 0

    # 4. Multi-Color Bottom Hook Text
    logger.info("✍️ [Step 4] Rendering multi-color bottom hook text...")
    sample_hindi_hook = "भाई, क्या बवाल डांस है!"
    with Image.open(arrowed_image_path).convert("RGBA") as base_canvas:
        hook_canvas = thumbnail_service.render_multicolor_bottom_hook(
            base_canvas=base_canvas,
            hook_text=sample_hindi_hook,
            y_bottom_offset=300,
        )
        text_test_output = test_sandbox / "test_hook_text_only.jpg"
        hook_canvas.convert("RGB").save(str(text_test_output), "JPEG", quality=95)

    assert text_test_output.exists()

    # 5. Full Pipeline Test
    logger.info("🚀 [Step 5] Running full generate_and_attach pipeline...")
    final_video_dest = test_sandbox / "test_reaction_short_final.mp4"

    processed_video = thumbnail_service.generate_and_attach(
        video_path=test_input_video,
        title="Test Reaction Short",
        description="Testing thumbnail arrow placement and hook text",
        output_video_path=final_video_dest,
        hook_text=sample_hindi_hook,
    )

    expected_thumb_file = Path(settings.OUTPUT_DIR) / f"{final_video_dest.stem}_thumb.jpg"

    assert processed_video.exists() and processed_video.stat().st_size > 0
    assert expected_thumb_file.exists() and expected_thumb_file.stat().st_size > 0

    logger.info(f"✅ Video created: {processed_video}")
    logger.info(f"✅ Thumbnail created: {expected_thumb_file}")
    logger.info("🎉 All thumbnail feature tests passed successfully!")


if __name__ == "__main__":
    test_thumbnail_feature()