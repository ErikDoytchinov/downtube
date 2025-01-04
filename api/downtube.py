import json
import os
import uuid
from fastapi import FastAPI, APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel
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

downloads = {}
MAX_VIDEO_DURATION = 3600  # 1 hour
CLEANUP_INTERVAL = 350  # ~5 minutes


# ------------------------
# FastAPI lifespan function
# ------------------------
async def on_startup(app: FastAPI):
    # Create downloads dir if not present and clean old files at startup
    Path("downloads").mkdir(exist_ok=True)
    for file in os.listdir("downloads"):
        os.remove(f"downloads/{file}")

    cleanup_task = asyncio.create_task(cleanup_undownload_videos())
    app.state.cleanup_task = cleanup_task

    # Startup context manager yields here
    yield

    # Shutdown logic
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        logger.info("Cleanup task successfully cancelled during shutdown.")


# ------------------------
# Create FastAPI app
# ------------------------
app = FastAPI(lifespan=on_startup)

# ------------------------
# CORS settings
# ------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://downtube.doytchinov.eu"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------
# Create a router with /api prefix
# ------------------------
api_router = APIRouter(prefix="/api")


@api_router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    logger.info("Root page accessed")
    return "Hello, World!"


class DownloadRequest(BaseModel):
    video_url: str
    download_type: str


@api_router.post("/download")
async def download_content(request: DownloadRequest, background_task: BackgroundTasks):
    video_url = request.video_url
    download_type = request.download_type

    if "youtube.com" not in video_url and "youtu.be" not in video_url:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    download_id = str(uuid.uuid4())
    downloads[download_id] = {"status": "downloading", "filename": None}

    background_task.add_task(process_download, video_url, download_id, download_type)

    return {
        "download_id": download_id,
        "download_type": download_type,
        "status": "downloading",
    }


@api_router.get("/download_video/{download_id}", response_class=FileResponse)
async def download_video_file(download_id: str, background_task: BackgroundTasks):
    if download_id not in downloads or downloads[download_id]["status"] != "completed":
        raise HTTPException(status_code=404, detail="Content not ready")

    file_path = downloads[download_id]["filename"]
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Schedule removal of the file after it's downloaded
    background_task.add_task(remove_file, file_path, download_id)

    file_name = os.path.basename(file_path)
    media_type = (
        "video/mp4"
        if file_path.lower().endswith((".mp4", ".mkv", ".webm"))
        else "audio/mpeg"
    )
    return FileResponse(path=file_path, media_type=media_type, filename=file_name)


@api_router.get("/version")
async def version():
    return {"version": "1.0.0"}


@api_router.get("/status/{download_id}")
async def sse_status(download_id: str):
    async def event_stream():
        while True:
            if download_id in downloads:
                yield f"data: {json.dumps(downloads[download_id])}\n\n"
            else:
                yield 'data: {"status": "not found"}\n\n'
                break
            await asyncio.sleep(1)  # Adjust interval as needed

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ------------------------
# Register the router
# ------------------------
app.include_router(api_router)


# ------------------------
# Utility / Download logic
# ------------------------
def process_download(video_url: str, download_id: str, download_type: str):
    print(f"Downloading {download_type} from {video_url}")

    base_ydl_opts = {
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/58.0.3029.110 Safari/537.3"
            )
        },
        "cookiefile": "www.youtube.com_cookies.txt",
        "outtmpl": "downloads/%(title)s.%(ext)s",
    }

    # Adjust format depending on download_type
    if download_type == "audio":
        ydl_opts = {
            **base_ydl_opts,
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }
    else:
        # default to video
        ydl_opts = {**base_ydl_opts, "format": "best"}

    try:
        # Check video duration first
        with YoutubeDL(ydl_opts) as ydl:
            yt = ydl.extract_info(video_url, download=False)
            if yt["duration"] > MAX_VIDEO_DURATION:
                downloads[download_id]["status"] = "too-large"
                return

        # Download video/audio
        with YoutubeDL(ydl_opts) as ydl:
            yt = ydl.extract_info(video_url, download=True)
            file_filename = ydl.prepare_filename(yt)

            if download_type == "audio":
                file_filename = file_filename.replace(".webm", ".mp3")

            downloads[download_id]["status"] = "completed"
            downloads[download_id]["filename"] = file_filename
            print(f"Downloaded: {yt['title']} as {download_type}")
    except Exception as e:
        print(f"Download failed: {e}")
        downloads[download_id]["status"] = "error"


async def cleanup_undownload_videos():
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
        print(f"Error deleting file {path}: {e}")
