from __future__ import annotations

import base64
from dataclasses import dataclass


@dataclass(frozen=True)
class WebScreenshot:
    png_bytes: bytes
    width: int
    height: int

    def to_data_url(self) -> str:
        b64 = base64.b64encode(self.png_bytes).decode("ascii")
        return f"data:image/png;base64,{b64}"
