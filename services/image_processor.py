import io
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

try:
    from pilmoji import Pilmoji
    _PILMOJI = True
except ImportError:
    _PILMOJI = False


def _apply_filter(img: Image.Image, filter_name: str) -> Image.Image:
    img = img.convert("RGB")

    if filter_name == "vintage":
        img = ImageEnhance.Color(img).enhance(0.7)
        img = ImageEnhance.Brightness(img).enhance(1.05)
        r, g, b = img.split()
        r = r.point(lambda x: min(255, int(x * 1.15)))
        b = b.point(lambda x: int(x * 0.88))
        img = Image.merge("RGB", (r, g, b))

    elif filter_name == "bright":
        img = ImageEnhance.Brightness(img).enhance(1.3)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img = ImageEnhance.Color(img).enhance(1.15)

    elif filter_name == "bw":
        img = img.convert("L").convert("RGB")
        img = ImageEnhance.Contrast(img).enhance(1.3)

    elif filter_name == "warm":
        r, g, b = img.split()
        r = r.point(lambda x: min(255, int(x * 1.12)))
        g = g.point(lambda x: min(255, int(x * 1.04)))
        b = b.point(lambda x: int(x * 0.88))
        img = Image.merge("RGB", (r, g, b))
        img = ImageEnhance.Brightness(img).enhance(1.05)

    elif filter_name == "cool":
        r, g, b = img.split()
        r = r.point(lambda x: int(x * 0.9))
        b = b.point(lambda x: min(255, int(x * 1.18)))
        img = Image.merge("RGB", (r, g, b))

    return img


def _get_font(size: int):
    for path in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    measure = ImageDraw.Draw(Image.new("L", (1, 1)))
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        current.append(word)
        bbox = measure.textbbox((0, 0), " ".join(current), font=font)
        if bbox[2] > max_width:
            if len(current) > 1:
                current.pop()
                lines.append(" ".join(current))
                current = [word]
            else:
                lines.append(" ".join(current))
                current = []
    if current:
        lines.append(" ".join(current))
    return lines or [text]


def _render_lines(
    img: Image.Image,
    lines: list[str],
    font,
    x_center: int,
    y_start: int,
    line_h: int,
) -> None:
    draw = ImageDraw.Draw(img)
    positions: list[tuple[int, int]] = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = x_center - (bbox[2] - bbox[0]) // 2
        positions.append((x, y_start))
        y_start += line_h

    # Drop shadow (rendered without emoji — shadow is subtle so missing emoji glyphs are fine)
    for (x, y), line in zip(positions, lines):
        draw.text((x + 2, y + 2), line, fill=(0, 0, 0, 200), font=font)

    if _PILMOJI:
        with Pilmoji(img) as pilmoji:
            for (x, y), line in zip(positions, lines):
                pilmoji.text((x, y), line, fill=(255, 255, 255, 255), font=font)
    else:
        for (x, y), line in zip(positions, lines):
            draw.text((x, y), line, fill=(255, 255, 255, 255), font=font)


def _add_text_overlay(img: Image.Image, text: str, style: str = "banner") -> Image.Image:
    img = img.convert("RGBA")
    width, height = img.size
    font_size = max(22, width // 22)
    font = _get_font(font_size)
    line_h = font_size + 8

    if style in ("banner", "top"):
        banner_h = int(height * 0.22)
        bar = Image.new("RGBA", img.size, (0, 0, 0, 0))
        bar_draw = ImageDraw.Draw(bar)
        if style == "top":
            bar_draw.rectangle([(0, 0), (width, banner_h)], fill=(0, 0, 0, 165))
        else:
            bar_draw.rectangle([(0, height - banner_h), (width, height)], fill=(0, 0, 0, 165))
        img = Image.alpha_composite(img, bar)

        lines = _wrap_text(text, font, int(width * 0.85))
        total_h = len(lines) * line_h
        if style == "top":
            y = (banner_h - total_h) // 2
        else:
            y = height - banner_h + (banner_h - total_h) // 2
        _render_lines(img, lines, font, width // 2, y, line_h)

    elif style == "shadow":
        font_size = max(32, width // 16)
        font = _get_font(font_size)
        line_h = font_size + 10
        lines = _wrap_text(text, font, int(width * 0.85))
        total_h = len(lines) * line_h
        y = height - int(height * 0.15) - total_h
        _render_lines(img, lines, font, width // 2, y, line_h)

    return img.convert("RGB")


def process_image(
    image_data: bytes,
    filter_name: str = "none",
    overlay_text: Optional[str] = None,
    overlay_style: str = "banner",
) -> bytes:
    img = Image.open(io.BytesIO(image_data))

    if filter_name != "none":
        img = _apply_filter(img, filter_name)

    if overlay_text:
        img = _add_text_overlay(img, overlay_text, style=overlay_style)

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=92)
    return output.getvalue()


_COVER_W = 720
_COVER_H = 1280

_IMPACT_FONT_PATHS = [
    str(Path(__file__).parent.parent / "assets" / "fonts" / "Impact.ttf"),
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
    "/Library/Fonts/Impact.ttf",
]


def _get_impact_font(size: int):
    for path in _IMPACT_FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return _get_font(size)  # fallback to system bold


def _fit_to_9x16(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    target_ratio = _COVER_W / _COVER_H
    img_ratio = img.width / img.height
    if img_ratio > target_ratio:
        new_w = int(img.height * target_ratio)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, img.height))
    else:
        new_h = int(img.width / target_ratio)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, img.width, top + new_h))
    return img.resize((_COVER_W, _COVER_H), Image.LANCZOS)


def _add_bottom_gradient(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    w, h = img.size
    gradient_h = int(h * 0.45)
    gradient = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    for y in range(gradient_h):
        alpha = int(180 * (y / gradient_h))
        arr[h - gradient_h + y, :, 3] = alpha
    gradient = Image.fromarray(arr, "RGBA")
    return Image.alpha_composite(img, gradient)


def create_cover(image_data: bytes, title: str, subtitle: str) -> bytes:
    img = Image.open(io.BytesIO(image_data))
    img = _fit_to_9x16(img)
    img = img.convert("RGBA")

    w, h = img.size

    # Dark overlay across the entire image
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 150))
    img = Image.alpha_composite(img, overlay)

    title_size = max(96, w // 6)
    subtitle_size = max(42, w // 14)
    title_font = _get_impact_font(title_size)
    subtitle_font = _get_impact_font(subtitle_size)

    max_text_w = int(w * 0.88)
    title_lines = _wrap_text(title.upper(), title_font, max_text_w)
    subtitle_lines = _wrap_text(subtitle.upper(), subtitle_font, max_text_w)

    title_line_h = int(title_size * 1.15)
    subtitle_line_h = int(subtitle_size * 1.15)
    gap = int(h * 0.03)

    title_block_h = len(title_lines) * title_line_h
    subtitle_block_h = len(subtitle_lines) * subtitle_line_h
    text_block_h = title_block_h + gap + subtitle_block_h

    # Vertically centered
    y_title = (h - text_block_h) // 2
    y_sub = y_title + title_block_h + gap

    _render_lines(img, title_lines, title_font, w // 2, y_title, title_line_h)
    _render_lines(img, subtitle_lines, subtitle_font, w // 2, y_sub, subtitle_line_h)

    output = io.BytesIO()
    img.convert("RGB").save(output, format="JPEG", quality=95)
    return output.getvalue()
