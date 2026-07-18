from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from renderer import current_widget_bytes, render_png_bytes


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            body = current_widget_bytes()
            status = 200
        except Exception as exc:
            body = render_png_bytes({
                "track": "WIDGET ERROR",
                "artist": "CHECK VERCEL SETTINGS",
                "album": str(exc)[:80],
                "image_url": "",
                "now_playing": False,
                "timestamp": None,
            })
            status = 500

        self.send_response(status)
        self.send_header("Content-Type", "image/png")
        self.send_header("Cache-Control", "public, max-age=0, s-maxage=60")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
