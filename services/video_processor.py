import io
import os
import tempfile
from typing import Optional

import numpy as np
from moviepy.editor import ImageClip, VideoClip, VideoFileClip, concatenate_videoclips
from PIL import Image, ImageDraw

from services.image_processor import _get_font, _wrap_text, process_image

TARGET_W = 720
TARGET_H = 1280
FPS = 24

_SLIDE_DURATION = {
    "ken_burns": 3.0,
    "fast_cut": 0.7,
    "hook_slides": 2.0,
}
_HOOK_DURATION = 2.5


def _extract_first_frame(video_data: bytes) -> bytes:
    tmp = tempfile.mktemp(suffix=".mp4")
    try:
        with open(tmp, "wb") as f:
            f.write(video_data)
        with VideoFileClip(tmp) as clip:
            frame = clip.get_frame(0)
        img = Image.fromarray(frame)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        return buf.getvalue()
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _ensure_image_bytes(data: bytes) -> bytes:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        return data
    except Exception:
        return _extract_first_frame(data)


def _fit_to_frame(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    target_ratio = TARGET_W / TARGET_H
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        new_w = int(img.height * target_ratio)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, img.height))
    else:
        new_h = int(img.width / target_ratio)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, img.width, top + new_h))

    return img.resize((TARGET_W, TARGET_H), Image.LANCZOS)


def _ken_burns_clip(img_array: np.ndarray, duration: float, zoom_in: bool = True) -> VideoClip:
    h, w = img_array.shape[:2]

    def make_frame(t: float) -> np.ndarray:
        progress = t / duration
        zoom = 1.0 + 0.12 * progress if zoom_in else 1.12 - 0.12 * progress
        nw, nh = int(w * zoom), int(h * zoom)
        resized = np.array(Image.fromarray(img_array).resize((nw, nh), Image.LANCZOS))
        y0, x0 = (nh - h) // 2, (nw - w) // 2
        return resized[y0:y0 + h, x0:x0 + w]

    return VideoClip(make_frame, duration=duration).set_fps(FPS)


def _hook_text_clip(text: str, duration: float = _HOOK_DURATION) -> ImageClip:
    img = Image.new("RGB", (TARGET_W, TARGET_H), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_size = max(56, TARGET_W // 9)
    font = _get_font(font_size)
    lines = _wrap_text(text.upper(), font, int(TARGET_W * 0.82))
    line_h = font_size + 14
    total_h = len(lines) * line_h
    y = (TARGET_H - total_h) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (TARGET_W - (bbox[2] - bbox[0])) // 2
        draw.text((x + 3, y + 3), line, fill=(0, 0, 0, 180), font=font)
        draw.text((x, y), line, fill=(255, 255, 255), font=font)
        y += line_h

    return ImageClip(np.array(img), duration=duration)


def create_reels_video(
    images: list[bytes],
    filter_name: str = "none",
    overlay_text: Optional[str] = None,
    overlay_style: str = "banner",
    reel_format: str = "ken_burns",
    hook_text: Optional[str] = None,
) -> bytes:
    slide_duration = _SLIDE_DURATION.get(reel_format, 3.0)
    clips = []

    if reel_format == "hook_slides" and hook_text:
        clips.append(_hook_text_clip(hook_text))

    for i, img_data in enumerate(images):
        processed = process_image(_ensure_image_bytes(img_data), filter_name, overlay_text, overlay_style)
        img_arr = np.array(_fit_to_frame(Image.open(io.BytesIO(processed))))

        if reel_format == "ken_burns":
            clip = _ken_burns_clip(img_arr, slide_duration, zoom_in=(i % 2 == 0))
        else:
            clip = ImageClip(img_arr, duration=slide_duration)

        clips.append(clip)

    if not clips:
        raise ValueError("No clips to render")

    video = concatenate_videoclips(clips, method="compose").set_fps(FPS)

    tmp_path = tempfile.mktemp(suffix=".mp4")
    try:
        video.write_videofile(tmp_path, fps=FPS, codec="libx264", audio=False, logger=None)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        video.close()
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
