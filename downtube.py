import os
import uuid
from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from yt_dlp import YoutubeDL
from pathlib import Path
from urllib.parse import quote

import logging
import colorlog

handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter("%(log_color)s%(levelname)s:%(name)s:%(message)s")
)

logger = logging.getLogger(__name__)
logger.addHandler(handler)

app = FastAPI()
templates = Jinja2Templates(directory="downtube/templates")

downloads = {}


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/download", response_class=HTMLResponse)
async def download_video(
    request: Request, background_task: BackgroundTasks, video_url: str = Form(...)
):
    try:
        if "youtube.com" not in video_url and "youtu.be" not in video_url:
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    download_id = str(uuid.uuid4())
    downloads[download_id] = {"status": "downloading", "filename": None}

    background_task.add_task(process_video_download, video_url, download_id)

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "message": "Video download initiated",
            "download_id": download_id,
        },
    )


@app.get("/download_video/{download_id}", response_class=FileResponse)
async def download_video_file(download_id: str):
    if download_id not in downloads or downloads[download_id]["status"] != "completed":
        raise HTTPException(status_code=404, detail="Video not ready")

    video_path = downloads[download_id]["filename"]
    if not os.path.isfile(video_path):
        raise HTTPException(status_code=404, detail="Video not found")

    video_name = os.path.basename(video_path)
    response = FileResponse(
        path=video_path, media_type="video/mp4", filename=video_name
    )

    # Optionally delete the file after serving
    # os.remove(video_path)
    return response


@app.get("/status/{download_id}")
async def check_status(download_id: str):
    if download_id not in downloads:
        raise HTTPException(status_code=404, detail="Download not found")
    return downloads[download_id]


def fetch_video_path(video_url: str):
    """
    Fetch the file path for a video from its URL without downloading it.
    """

    ydl_opts = {
        "format": "best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
    }
    with YoutubeDL(ydl_opts) as ydl:
        yt = ydl.extract_info(video_url, download=False)

    return ydl.prepare_filename(yt)


def process_video_download(video_url: str, download_id: str):
    print(f"Downloading video from {video_url}")

    ydl_opts = {
        "format": "best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
    }
    with YoutubeDL(ydl_opts) as ydl:
        yt = ydl.extract_info(video_url, download=True)
        video_filename = ydl.prepare_filename(yt)

    downloads[download_id]["status"] = "completed"
    downloads[download_id]["filename"] = video_filename

    print(f"Video has been downloaded: {yt['title']} ({yt['duration']}) seconds")
