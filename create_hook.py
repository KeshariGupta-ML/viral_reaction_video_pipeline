import os
from pathlib import Path
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

load_dotenv()

client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
voice_id = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")

hook_text = "Pehle video dekho, fir iske comments padhte hain! Aur meri mehnat ke liye subscribe aur like thok ke jana!"
output_path = Path("assets/audio/static_hook.mp3")
output_path.parent.mkdir(parents=True, exist_ok=True)

# Remove old corrupted file if present
if output_path.exists():
    output_path.unlink()

print("Generating clean static hook...")
audio_stream = client.text_to_speech.convert(
    voice_id=voice_id,
    text=hook_text,
    model_id="eleven_multilingual_v2",
    output_format="mp3_44100_128"
)

with open(output_path, "wb") as f:
    for chunk in audio_stream:
        f.write(chunk)

print(f"Done! File size: {output_path.stat().st_size} bytes")