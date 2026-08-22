import sys
import asyncio
import uuid

# Fix for Windows Playwright subprocess NotImplementedError
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os
from fastapi import FastAPI, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.pipeline import pipeline_orchestrator
from app.schemas.video import JobStatus
from config import settings

app = FastAPI(title="Automated Viral Comment Reaction Generator", version="1.0.0")

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
        comment_count: int = Form(3)
):
    """Initiates a background worker job to compile the reaction video pipeline."""
    job_id = str(uuid.uuid4())[:8]

    background_tasks.add_task(
        pipeline_orchestrator.run_pipeline,
        job_id=job_id,
        video_url=video_url,
        comment_count=comment_count
    )

    return JSONResponse({
        "status": "queued",
        "job_id": job_id,
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
        "script": job.script.dict() if job.script else None,
        "rendered_video_url": f"/output/{job.rendered_video_path.name}" if job.rendered_video_path else None,
        "error_message": job.error_message
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.DEBUG)