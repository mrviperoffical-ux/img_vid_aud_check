import os
import uuid
import shutil
import requests
import subprocess


from fastapi import APIRouter
from app.schemas import AnalyzeRequest
from app.services.video import extract_frames
from app.services.nudity import check_nudity, check_image_nudity
from app.utils.s3 import upload_frame

# ✅ Router
moderation_router = APIRouter(prefix="/moderation")

UPLOAD_DIR = "app/temp"


# ✅ Health check
@moderation_router.get("/health")
def health():
    return {"status": "ok"}


# ✅ Helpers
def create_request_dir():
    request_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_DIR, request_id)
    os.makedirs(path, exist_ok=True)
    return path


def download_video(url: str, output_dir: str):
    video_path = os.path.join(output_dir, "video.mp4")

    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    with open(video_path, "wb") as f:
        for chunk in response.iter_content(1024 * 1024):
            if chunk:
                f.write(chunk)

    return video_path

def download_file(url: str, output_dir: str, filename: str):
    path = os.path.join(output_dir, filename)

    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    with open(path, "wb") as f:
        for chunk in response.iter_content(1024 * 1024):
            if chunk:
                f.write(chunk)

    return path

def cleanup(path):
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)

def get_ffmpeg_path():
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    local_ffmpeg = os.path.join(base_dir, "bin", "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg
    return None

def convert_to_h264(input_path, output_dir):
    ffmpeg_bin = get_ffmpeg_path()
    if not ffmpeg_bin:
        return input_path

    output_path = os.path.join(output_dir, "converted.mp4")

    command = [
        ffmpeg_bin,
        "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        output_path
    ]

    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
    except Exception:
        pass

    return input_path


# ✅ Main API
@moderation_router.post("/analyze")
def analyze(req: AnalyzeRequest):
    request_dir = create_request_dir()

    try:
        s3_url = None

        # =====================
        # 🖼 IMAGE FLOW
        # =====================
        if req.contentType == "image":
            image_path = download_file(req.url, request_dir, "image.jpg")

            is_nude, nude_image = check_image_nudity(image_path)

            # if is_nude and nude_image:
            #     s3_url = upload_frame(nude_image)

            return {
                "type": "image",
                "nudity": is_nude,
                # "nudity_frame_url": s3_url,
                "final": "NSFW" if is_nude else "Safe"
            }

        # =====================
        # 🎥 VIDEO FLOW
        # =====================
        else:
            video_path = download_file(req.url, request_dir, "video.mp4")

            video_path = convert_to_h264(video_path, request_dir)

            frames = extract_frames(
                video_path,
                output_dir=request_dir,
                frames_per_second=req.frames_per_second
            )

            is_nude, nude_frame = check_nudity(frames)

            if is_nude and nude_frame:
                s3_url = upload_frame(nude_frame)

            return {
                "type": "video",
                "nudity": is_nude,
                "frames_analyzed": len(frames),
                "nudity_frame_url": s3_url,
                "final": "NSFW" if is_nude else "Safe"
            }

    finally:
        print("Cleaning up...")
        cleanup(request_dir)