from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import pyautogui
from PIL import Image


@dataclass(frozen=True)
class Screenshot:
    image: Image.Image
    path: Optional[Path]
    size: Tuple[int, int]

    def to_png_bytes(self) -> bytes:
        buf = io.BytesIO()
        self.image.save(buf, format="PNG")
        return buf.getvalue()

    def to_data_url(self) -> str:
        buf = io.BytesIO()
        self.image.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"


def get_screenshot(save_path: Optional[str] = None) -> Screenshot:
    image = pyautogui.screenshot()  # PIL.Image
    path: Optional[Path] = None
    if save_path:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
    return Screenshot(image=image, path=path, size=image.size)
