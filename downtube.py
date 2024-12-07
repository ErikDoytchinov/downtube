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
app.mount("/static", StaticFiles(directory="downtube/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("downtube/static/favicon.ico")


@app.post("/download", response_class=HTMLResponse)
async def download_content(
    request: Request,
    background_task: BackgroundTasks,
    video_url: str = Form(...),
    download_type: str = Form(...),
):
    try:
        if "youtube.com" not in video_url and "youtu.be" not in video_url:
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    download_id = str(uuid.uuid4())
    downloads[download_id] = {"status": "downloading", "filename": None}

    background_task.add_task(process_download, video_url, download_id, download_type)

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "message": "Your download is being prepared...",
            "download_id": download_id,
            "download_type": download_type,  # pass "video" or "audio" here
        },
    )


@app.get("/download_video/{download_id}", response_class=FileResponse)
async def download_video_file(download_id: str, background_task: BackgroundTasks):
    if download_id not in downloads or downloads[download_id]["status"] != "completed":
        raise HTTPException(status_code=404, detail="Content not ready")

    file_path = downloads[download_id]["filename"]
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    file_name = os.path.basename(file_path)

    # Schedule the file removal after the response is sent
    background_task.add_task(remove_file, file_path, download_id)

    # Determine media_type based on extension
    media_type = (
        "video/mp4"
        if file_path.lower().endswith((".mp4", ".mkv", ".webm"))
        else "audio/mpeg"
    )
    return FileResponse(path=file_path, media_type=media_type, filename=file_name)


@app.get("/version")
async def version():
    return {"version": "1.0.0"}


@app.get("/status/{download_id}")
async def check_status(download_id: str):
    if download_id not in downloads:
        raise HTTPException(status_code=404, detail="Download not found")
    return downloads[download_id]


def process_download(video_url: str, download_id: str, download_type: str):
    print(f"Downloading {download_type} from {video_url}")

    # Common YDL options
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

    # First check duration
    with YoutubeDL(ydl_opts) as ydl:
        yt = ydl.extract_info(video_url, download=False)
        if yt["duration"] > MAX_VIDEO_DURATION:
            downloads[download_id]["status"] = "too-large"
            return

    # Now actually download
    with YoutubeDL(ydl_opts) as ydl:
        yt = ydl.extract_info(video_url, download=True)
        file_filename = ydl.prepare_filename(yt)
        # sometimes when downloading a audio file, the filename is not the same as the output, the end is .webm not .mp3
        if download_type == "audio":
            file_filename = file_filename.replace(".webm", ".mp3")

    downloads[download_id]["status"] = "completed"
    downloads[download_id]["filename"] = file_filename

    print(f"Downloaded: {yt['title']} ({yt['duration']} seconds) as {download_type}")


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
