from __future__ import annotations

import io
import os
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDGET_BUILD = "right-mascot-split-metadata-v3"

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
MASCOTS = ASSETS / "mascots"
NOW_PLAYING_MASCOT = MASCOTS / "now-playing.png"
NOW_PLAYING_MASCOT_WIDTH = 320
NOW_PLAYING_MASCOT_POSITION = (1210, 65)

CANVAS_SIZE = (1672, 941)
ALBUM_BOX = (138, 299, 471, 646)  # user-confirmed exact inner boundary
ALBUM_RADIUS = 18
TEXT_SAFE_BOX = (520, 388, 1450, 625)

INK = (71, 49, 91, 255)
ALBUM_INK = (89, 123, 122, 255)
FOOTER_INK = (165, 93, 79, 255)
CREAM = (241, 231, 205, 255)


# Built-in 5x7 bitmap alphabet. No external font and no Pillow font fallback.
PIXEL_GLYPHS = {
    "A": ["01110","10001","10001","11111","10001","10001","10001"],
    "B": ["11110","10001","10001","11110","10001","10001","11110"],
    "C": ["01111","10000","10000","10000","10000","10000","01111"],
    "D": ["11110","10001","10001","10001","10001","10001","11110"],
    "E": ["11111","10000","10000","11110","10000","10000","11111"],
    "F": ["11111","10000","10000","11110","10000","10000","10000"],
    "G": ["01111","10000","10000","10111","10001","10001","01111"],
    "H": ["10001","10001","10001","11111","10001","10001","10001"],
    "I": ["11111","00100","00100","00100","00100","00100","11111"],
    "J": ["00111","00010","00010","00010","10010","10010","01100"],
    "K": ["10001","10010","10100","11000","10100","10010","10001"],
    "L": ["10000","10000","10000","10000","10000","10000","11111"],
    "M": ["10001","11011","10101","10101","10001","10001","10001"],
    "N": ["10001","11001","10101","10011","10001","10001","10001"],
    "O": ["01110","10001","10001","10001","10001","10001","01110"],
    "P": ["11110","10001","10001","11110","10000","10000","10000"],
    "Q": ["01110","10001","10001","10001","10101","10010","01101"],
    "R": ["11110","10001","10001","11110","10100","10010","10001"],
    "S": ["01111","10000","10000","01110","00001","00001","11110"],
    "T": ["11111","00100","00100","00100","00100","00100","00100"],
    "U": ["10001","10001","10001","10001","10001","10001","01110"],
    "V": ["10001","10001","10001","10001","10001","01010","00100"],
    "W": ["10001","10001","10001","10101","10101","10101","01010"],
    "X": ["10001","10001","01010","00100","01010","10001","10001"],
    "Y": ["10001","10001","01010","00100","00100","00100","00100"],
    "Z": ["11111","00001","00010","00100","01000","10000","11111"],
    "0": ["01110","10001","10011","10101","11001","10001","01110"],
    "1": ["00100","01100","00100","00100","00100","00100","01110"],
    "2": ["01110","10001","00001","00010","00100","01000","11111"],
    "3": ["11110","00001","00001","01110","00001","00001","11110"],
    "4": ["00010","00110","01010","10010","11111","00010","00010"],
    "5": ["11111","10000","10000","11110","00001","00001","11110"],
    "6": ["01110","10000","10000","11110","10001","10001","01110"],
    "7": ["11111","00001","00010","00100","01000","01000","01000"],
    "8": ["01110","10001","10001","01110","10001","10001","01110"],
    "9": ["01110","10001","10001","01111","00001","00001","01110"],
    "-": ["00000","00000","00000","11111","00000","00000","00000"],
    ".": ["00000","00000","00000","00000","00000","00110","00110"],
    ":": ["00000","00110","00110","00000","00110","00110","00000"],
    "/": ["00001","00010","00010","00100","01000","01000","10000"],
    "&": ["01100","10010","10100","01000","10101","10010","01101"],
    "'": ["00100","00100","00000","00000","00000","00000","00000"],
    "?": ["01110","10001","00001","00010","00100","00000","00100"],
    "!": ["00100","00100","00100","00100","00100","00000","00100"],
    "¡": ["00100","00000","00100","00100","00100","00100","00100"],
    "¿": ["00100","00000","00100","01000","10000","10001","01110"],
    "·": ["00000","00000","00000","00100","00000","00000","00000"],
    "(": ["00010","00100","01000","01000","01000","00100","00010"],
    ")": ["01000","00100","00010","00010","00010","00100","01000"],
    " ": ["00000"]*7,
}

# Accented letters reuse the exact unaccented 5x7 letterform. The accent is
# drawn above the normal cap height, so accented letters remain the same size
# and baseline as the rest of the custom alphabet.
ACCENTED_LETTERS = {
    "Á": ("A", "acute"),
    "É": ("E", "acute"),
    "Í": ("I", "acute"),
    "Ó": ("O", "acute"),
    "Ú": ("U", "acute"),
    "Ü": ("U", "diaeresis"),
    "Ñ": ("N", "tilde"),
}

ACCENT_BITMAPS = {
    "acute": ["00010", "00100"],
    "diaeresis": ["01010"],
    "tilde": ["01010", "10100"],
}


def _pixel_measure(text: str, scale: int, spacing: int = 1) -> int:
    if not text:
        return 0
    return len(text) * (5 + spacing) * scale - spacing * scale


def _fit_pixel_line(text: str, max_width: int, start_scale: int, minimum_scale: int) -> tuple[str, int]:
    clean = " ".join(unicodedata.normalize("NFC", str(text or "")).upper().split())
    for scale in range(start_scale, minimum_scale - 1, -1):
        if _pixel_measure(clean, scale) <= max_width:
            return clean, scale
    scale = minimum_scale
    suffix = "..."
    while clean and _pixel_measure(clean + suffix, scale) > max_width:
        clean = clean[:-1]
    return (clean.rstrip() + suffix if clean else suffix), scale


def _draw_bitmap(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    rows: list[str],
    scale: int,
    fill: tuple[int, int, int, int],
) -> None:
    x0, y0 = xy
    for row, bits in enumerate(rows):
        for col, bit in enumerate(bits):
            if bit == "1":
                draw.rectangle(
                    (
                        x0 + col * scale,
                        y0 + row * scale,
                        x0 + (col + 1) * scale - 1,
                        y0 + (row + 1) * scale - 1,
                    ),
                    fill=fill,
                )


def _draw_pixel_text(canvas: Image.Image, xy: tuple[int, int], text: str, scale: int, fill: tuple[int, int, int, int], spacing: int = 1) -> None:
    draw = ImageDraw.Draw(canvas)
    x0, y0 = xy
    cursor = x0

    for char in unicodedata.normalize("NFC", str(text)).upper():
        base_char, accent_name = ACCENTED_LETTERS.get(char, (char, None))
        glyph = PIXEL_GLYPHS.get(base_char, PIXEL_GLYPHS["?"])

        # The base letter is drawn exactly like its unaccented counterpart.
        _draw_bitmap(draw, (cursor, y0), glyph, scale, fill)

        if accent_name:
            accent = ACCENT_BITMAPS[accent_name]
            # Leave one blank pixel row between the accent and the letter.
            accent_y = y0 - (len(accent) + 1) * scale
            _draw_bitmap(draw, (cursor, accent_y), accent, scale, fill)

        cursor += (5 + spacing) * scale


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def _crop_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = image.convert("RGBA")
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side)).resize(size, Image.Resampling.LANCZOS)


def _fallback_cover(size: tuple[int, int]) -> Image.Image:
    cover = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(cover)
    cx, cy = size[0] // 2, size[1] // 2
    draw.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=(0, 0, 0, 255))
    return cover


def _download_cover(url: str, size: tuple[int, int]) -> Image.Image:
    if not url:
        return _fallback_cover(size)
    try:
        response = requests.get(url, timeout=15, headers={"User-Agent": "manakin-now-playing-widget/1.0"})
        response.raise_for_status()
        return _crop_cover(Image.open(io.BytesIO(response.content)), size)
    except Exception:
        return _fallback_cover(size)


def _clean_dynamic_text_area(template: Image.Image) -> Image.Image:
    """Cover only the old sample lettering, with softly feathered matching cream texture."""
    base = template.copy().convert("RGBA")
    patch = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(patch, "RGBA")

    # Kept safely inside the illustrated field so no border artwork is touched.
    draw.rounded_rectangle((520, 392, 1450, 620), radius=34, fill=(241, 231, 205, 238))
    draw.rounded_rectangle((558, 315, 806, 366), radius=22, fill=(229, 202, 158, 205))

    # Feathering prevents the cleanup from reading as a pasted rectangular panel.
    alpha = patch.getchannel("A").filter(ImageFilter.GaussianBlur(18))
    patch.putalpha(alpha)
    return Image.alpha_composite(base, patch)



def fetch_track_user_playcount(artist: str, track: str, user: str, api_key: str) -> int | None:
    artist = str(artist or "").strip()
    track = str(track or "").strip()
    user = str(user or "").strip()
    if not artist or not track or not user:
        return None

    response = requests.get(
        "https://ws.audioscrobbler.com/2.0/",
        params={
            "method": "track.getInfo",
            "artist": artist,
            "track": track,
            "username": user,
            "api_key": api_key,
            "format": "json",
            "autocorrect": 1,
        },
        timeout=15,
        headers={"User-Agent": "manakin-now-playing-widget/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(payload.get("message", "track.getInfo returned an error"))

    raw_count = (payload.get("track", {}) or {}).get("userplaycount")
    try:
        return int(raw_count)
    except (TypeError, ValueError):
        return None


def fetch_lastfm_track(user: str, api_key: str) -> dict[str, Any]:
    response = requests.get(
        "https://ws.audioscrobbler.com/2.0/",
        params={
            "method": "user.getRecentTracks",
            "user": user,
            "api_key": api_key,
            "format": "json",
            "limit": 1,
            "extended": 0,
        },
        timeout=15,
        headers={"User-Agent": "manakin-now-playing-widget/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(payload.get("message", "Last.fm returned an error"))

    tracks = payload.get("recenttracks", {}).get("track", [])
    if isinstance(tracks, dict):
        tracks = [tracks]
    if not tracks:
        return {
            "track": "NO RECENT TRACK",
            "artist": user,
            "album": "",
            "image_url": "",
            "now_playing": False,
            "timestamp": None,
            "user_playcount": None,
            "is_familiar_track": False,
        }

    item = tracks[0]
    artist = item.get("artist", {})
    album = item.get("album", {})
    images = item.get("image", []) or []
    image_url = ""
    for candidate in reversed(images):
        if candidate.get("#text"):
            image_url = candidate["#text"]
            break

    artist_name = artist.get("#text") if isinstance(artist, dict) else str(artist)
    album_name = album.get("#text") if isinstance(album, dict) else str(album)
    track_name = item.get("name") or "UNKNOWN TRACK"

    now_playing = item.get("@attr", {}).get("nowplaying") == "true"
    timestamp = None
    if not now_playing:
        timestamp_text = item.get("date", {}).get("uts")
        if timestamp_text:
            timestamp = int(timestamp_text)

    user_playcount = None
    try:
        user_playcount = fetch_track_user_playcount(
            artist_name,
            track_name,
            user,
            api_key,
        )
    except Exception:
        user_playcount = None

    return {
        "track": track_name,
        "artist": artist_name,
        "album": album_name,
        "image_url": image_url,
        "now_playing": now_playing,
        "timestamp": timestamp,
        "user_playcount": user_playcount,
        "is_familiar_track": bool(user_playcount is not None and user_playcount >= 20),
    }


def _relative_time(timestamp: int | None) -> str:
    if not timestamp:
        return ""
    seconds = max(0, int(datetime.now(timezone.utc).timestamp()) - timestamp)
    minutes = seconds // 60
    if minutes < 1:
        return "moments ago"
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"



def _overlay_now_playing_mascot(canvas: Image.Image) -> Image.Image:
    if not NOW_PLAYING_MASCOT.exists():
        return canvas

    mascot = Image.open(NOW_PLAYING_MASCOT).convert("RGBA")
    width = NOW_PLAYING_MASCOT_WIDTH
    height = int(mascot.size[1] * (width / mascot.size[0]))
    mascot = mascot.resize((width, height), Image.Resampling.LANCZOS)

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.alpha_composite(mascot, NOW_PLAYING_MASCOT_POSITION)
    return Image.alpha_composite(canvas, layer)

def render_widget(track: dict[str, Any]) -> Image.Image:
    template = Image.open(ASSETS / "widget-template-clean.png").convert("RGBA")
    if template.size != CANVAS_SIZE:
        raise RuntimeError(f"Unexpected template size: {template.size}")

    canvas = template.copy()

    # Exact confirmed album placement; no automatic alignment or guessed offsets.
    x1, y1, x2, y2 = ALBUM_BOX
    cover_size = (x2 - x1, y2 - y1)
    cover = _download_cover(str(track.get("image_url") or ""), cover_size)
    cover_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    cover_layer.paste(cover, (x1, y1), _rounded_mask(cover_size, ALBUM_RADIUS))
    canvas = Image.alpha_composite(canvas, cover_layer)

    if track.get("now_playing"):
        canvas = _overlay_now_playing_mascot(canvas)

    status = "NOW PLAYING" if track.get("now_playing") else "LAST HEARD"
    status_box = (565, 318, 798, 360)
    status_scale = 3
    status_width = _pixel_measure(status, status_scale)
    status_height = 7 * status_scale
    status_x = int((status_box[0] + status_box[2] - status_width) / 2)
    status_y = int((status_box[1] + status_box[3] - status_height) / 2)
    _draw_pixel_text(canvas, (status_x, status_y), status, status_scale, INK)

    # Reserve the right side of the information panel for the mascot.
    # Track receives the strongest hierarchy; artist and album share line two.
    track_text = str(track.get("track") or "UNKNOWN TRACK")
    track_text, track_scale = _fit_pixel_line(track_text, 650, 5, 3)
    _draw_pixel_text(canvas, (548, 404), track_text, track_scale, INK)

    artist = str(track.get("artist") or "UNKNOWN ARTIST")
    album = str(track.get("album") or "UNKNOWN ALBUM")
    detail_text = f"{artist} - {album}"
    detail_text, detail_scale = _fit_pixel_line(detail_text, 650, 4, 2)
    _draw_pixel_text(canvas, (558, 495), detail_text, detail_scale, ALBUM_INK)

    footer = "via last.fm"
    if not track.get("now_playing"):
        age = _relative_time(track.get("timestamp"))
        if age:
            footer += f"  ·  {age}"
    footer_text, footer_scale = _fit_pixel_line(footer, 760, 3, 2)
    _draw_pixel_text(canvas, (585, 567), footer_text, footer_scale, FOOTER_INK)

    return canvas


def render_png_bytes(track: dict[str, Any]) -> bytes:
    image = render_widget(track)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def current_widget_bytes() -> bytes:
    api_key = os.environ.get("LASTFM_API_KEY", "").strip()
    user = os.environ.get("LASTFM_USER", "manakin_zZ").strip() or "manakin_zZ"
    if not api_key:
        raise RuntimeError("LASTFM_API_KEY is not configured")
    return render_png_bytes(fetch_lastfm_track(user, api_key))
