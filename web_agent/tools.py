from __future__ import annotations

import time
from typing import Any, Dict, Optional

from playwright.sync_api import Page


class WebToolExecutor:
    def __init__(self, page: Page):
        self._page = page

    def execute(self, name: str, arguments: Dict[str, Any]) -> Optional[str]:
        if name == "goto":
            url = str(arguments["url"])
            self._page.goto(url, wait_until="domcontentloaded")
            return f"navigated:{url}"

        if name == "click":
            selector = str(arguments["selector"])
            self._page.locator(selector).first.click(timeout=10_000)
            return f"clicked:{selector}"

        if name == "type":
            selector = str(arguments["selector"])
            text = str(arguments["text"])
            loc = self._page.locator(selector).first
            loc.click(timeout=10_000)
            loc.fill("")
            loc.type(text)
            return f"typed:{selector}"

        if name == "press":
            key = str(arguments["key"])
            self._page.keyboard.press(key)
            return f"pressed:{key}"

        if name == "wait":
            seconds = float(arguments["seconds"])
            time.sleep(seconds)
            return f"waited:{seconds}"

        if name == "done":
            return str(arguments.get("message") or "done")

        raise ValueError(f"Unknown tool: {name}")
