import os
import uuid
from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from yt_dlp import YoutubeDL
from pathlib import Path
import asyncio

import logging
import colorlog

handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter("%(log_color)s%(levelname)s:%(name)s:%(message)s")
)

logger = logging.getLogger(__name__)
logger.addHandler(handler)

templates = Jinja2Templates(directory="downtube/templates")
downloads = {}
MAX_VIDEO_DURATION = 600
CLEANUP_INTERVAL = 350


async def on_startup(app: FastAPI):
    Path("downloads").mkdir(exist_ok=True)
    for file in os.listdir("downloads"):
        os.remove(f"downloads/{file}")

    cleanup_task = asyncio.create_task(cleanup_undownload_videos())
    app.state.cleanup_task = cleanup_task

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        print("Cleanup task successfully cancelled during shutdown.")


app = FastAPI(lifespan=on_startup)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return StaticFiles(directory="static").file_response("favicon.ico")


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
async def download_video_file(download_id: str, background_task: BackgroundTasks):
    if download_id not in downloads or downloads[download_id]["status"] != "completed":
        raise HTTPException(status_code=404, detail="Video not ready")

    video_path = downloads[download_id]["filename"]
    if not os.path.isfile(video_path):
        raise HTTPException(status_code=404, detail="Video not found")

    video_name = os.path.basename(video_path)

    # Schedule the file removal after the response is sent
    background_task.add_task(remove_file, video_path, download_id)

    return FileResponse(path=video_path, media_type="video/mp4", filename=video_name)


# version check
@app.get("/version")
async def version():
    return {"version": "1.0.0"}


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
        "cookiefile": "www.youtube.com_cookies.txt",
        "format": "best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
    }
    with YoutubeDL(ydl_opts) as ydl:
        yt = ydl.extract_info(video_url, download=False)

    return ydl.prepare_filename(yt)


def process_video_download(video_url: str, download_id: str):
    print(f"Downloading video from {video_url}")

    # check if video is too big
    ydl_opts = {
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            + "AppleWebKit/537.36 (KHTML, like Gecko) "
            + "Chrome/58.0.3029.110 Safari/537.3"
        },
        "cookiefile": "www.youtube.com_cookies.txt",
        "format": "best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
    }
    with YoutubeDL(ydl_opts) as ydl:
        yt = ydl.extract_info(video_url, download=False)
        if yt["duration"] > MAX_VIDEO_DURATION:
            downloads[download_id]["status"] = "too-large"
            return

    with YoutubeDL(ydl_opts) as ydl:
        yt = ydl.extract_info(video_url, download=True)
        video_filename = ydl.prepare_filename(yt)

    downloads[download_id]["status"] = "completed"
    downloads[download_id]["filename"] = video_filename

    print(f"Video has been downloaded: {yt['title']} ({yt['duration']}) seconds")


async def cleanup_undownload_videos():
    """
    Removes videos that have ran out of time to download.
    This function will be called periodically. Removing videos
    that have been in the "completed" state for too long.
    """
    while True:
        try:
            for download_id, download_info in list(downloads.items()):
                if download_info["status"] == "completed":
                    remove_file(download_info["filename"], download_id)
                    print(f"Removed download {download_id}")
            await asyncio.sleep(CLEANUP_INTERVAL)
        except asyncio.CancelledError:
            print("Cleanup task cancelled.")
            break
        except Exception as e:
            print(f"An error occurred in cleanup task: {e}")
            await asyncio.sleep(CLEANUP_INTERVAL)


def remove_file(path: str, download_id: str):
    try:
        os.remove(path)
        downloads[download_id]["status"] = "deleted"
        downloads.pop(download_id)
    except Exception as e:
        # Optionally log the error
        print(f"Error deleting file {path}: {e}")
