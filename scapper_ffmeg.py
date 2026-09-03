import shutil
import yt_dlp

print(f"FFmpeg detected by Python: {shutil.which('ffmpeg')}")

url = "https://www.youtube.com/shorts/LtU_3Ep6qLE"
with yt_dlp.YoutubeDL({'listformats': True}) as ydl:
    ydl.extract_info(url, download=False)