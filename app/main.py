import json
import sys
import asyncio
import uuid
from pathlib import Path

import httpx

from app.core.logger import logger

# Fix for Windows Playwright subprocess NotImplementedError
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os
from fastapi import FastAPI, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.services.gdrive_uploader import gdrive_service
from app.core.pipeline import pipeline_orchestrator
from config import settings

app = FastAPI(title="Automated Viral Comment Reaction Generator", version="1.0.0")
# N8N_WEBHOOK_URL = "http://localhost:5678/webhook/trigger-to-upload-video"
N8N_WEBHOOK_URL = "http://localhost:5678/webhook-test/trigger-to-upload-video"

# Mount static and output storage paths
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")
app.mount("/output", StaticFiles(directory=str(settings.OUTPUT_DIR)), name="output")

# Template renderer setup
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Renders the main Bootstrap 5 web dashboard."""
    return templates.TemplateResponse("base.html", {"request": request})


@app.post("/api/generate")
async def start_generation_job(
        background_tasks: BackgroundTasks,
        video_url: str = Form(...),
        voice_style: str = Form("hinglish_energetic"),
        comment_count: int = Form(3),
        schedule_offset_days: int = Form(0)  # <-- Added schedule offset
):
    """Initiates a background worker job to compile the reaction video pipeline."""
    job_id = str(uuid.uuid4())[:8]

    # Pre-register job and record schedule offset
    job = pipeline_orchestrator.create_job(job_id=job_id, video_url=video_url)
    job.schedule_offset_days = schedule_offset_days

    background_tasks.add_task(
        pipeline_orchestrator.run_pipeline,
        job_id=job_id,
        video_url=video_url,
        comment_count=comment_count
    )

    return JSONResponse({
        "status": "queued",
        "job_id": job_id,
        "schedule_offset_days": schedule_offset_days,
        "message": "Reaction video generation pipeline started in the background."
    })


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Polls the current status, script data, and output video path for a job."""
    job = pipeline_orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job ID not found.")

    return {
        "job_id": job.job_id,
        "status": job.status,
        "source_url": job.source_url,
        "schedule_offset_days": getattr(job, "schedule_offset_days", 0),
        "script": job.script.dict() if job.script else None,
        "rendered_video_url": f"/output/{job.rendered_video_path.name}" if job.rendered_video_path else None,
        "error_message": job.error_message
    }


@app.post("/api/job/{job_id}/upload-drive")
async def upload_job_to_drive(job_id: str):
    job = pipeline_orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    video_path = Path(job.rendered_video_path) if job.rendered_video_path else (
                settings.OUTPUT_DIR / f"reaction_{job_id}.mp4")
    if not video_path.exists():
        raise HTTPException(status_code=400, detail=f"Rendered video not found at: {video_path}")

    # 1. Locate the cached scraped metadata to grab source title & uploader
    import hashlib
    url_hash = hashlib.sha256(job.source_url.strip().encode("utf-8")).hexdigest()[:12]
    cached_meta_path = settings.VIDEOS_DIR / f"{url_hash}_metadata.json"

    source_meta = {}
    if cached_meta_path.exists():
        try:
            with open(cached_meta_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                source_meta = cached_data.get("metadata", {})
        except Exception as e:
            logger.warning(f"Could not load scraped metadata: {e}")

    # 2. Build complete JSON matching what n8n expects
    json_path = settings.VIDEOS_DIR / f"{job_id}.json"
    raw_metadata = {
        "job_id": job.job_id,
        "source_url": job.source_url,
        "schedule_offset_days": getattr(job, "schedule_offset_days", 0),
        "metadata": {
            "title": source_meta.get("title") or "Viral Reaction",
            "uploader": source_meta.get("uploader") or "Creator",
            "duration": source_meta.get("duration")
        },
        "script": job.script.model_dump() if hasattr(job.script, "model_dump") else getattr(job.script, "dict",
                                                                                            lambda: job.script)()
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(raw_metadata, f, ensure_ascii=False, indent=2)

    # 3. Upload Output MP4 and JSON to Google Drive
    video_res = await gdrive_service.upload_file(
        file_path=video_path,
        mime_type="video/mp4",
        custom_filename=f"reaction_{job_id}.mp4"
    )

    json_res = await gdrive_service.upload_file(
        file_path=json_path,
        mime_type="application/json",
        custom_filename=f"raw_metadata_{job_id}.json"
    )

    return {
        "status": "success",
        "video_drive_link": video_res.get("webViewLink"),
        "json_drive_link": json_res.get("webViewLink")
    }

@app.post("/api/trigger-to-upload-video")
async def trigger_temp_upload_workflow():
    try:
        # 1. Check if files exist in Google Drive Temp Folder
        drive_files = await gdrive_service.list_temp_files()

        if not drive_files:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "No file is available in Google Drive temp folder."}
            )

        video_file = next((f for f in drive_files if f["name"].endswith(".mp4")), None)
        json_file = next((f for f in drive_files if f["name"].endswith(".json")), None)

        if not video_file:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "No .mp4 video found in Google Drive temp folder."}
            )

        # 2. Trigger n8n Webhook with detected files payload
        payload = {
            "temp_folder_id": settings.GOOGLE_DRIVE_FOLDER_ID,
            "video_file_id": video_file["id"],
            "video_name": video_file["name"],
            "json_file_id": json_file["id"] if json_file else None,
            "json_name": json_file["name"] if json_file else None,
            "total_files": len(drive_files)
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(N8N_WEBHOOK_URL, json=payload, timeout=10.0)

        return {
            "status": "success",
            "message": f"n8n upload workflow triggered successfully for '{video_file['name']}'!",
            "n8n_status_code": response.status_code,
            "files": payload
        }

    except Exception as e:
        logger.error(f"Error checking GDrive or calling n8n: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.DEBUG)