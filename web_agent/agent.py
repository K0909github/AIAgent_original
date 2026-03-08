from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import sync_playwright

from .perception import WebScreenshot
from .planner_http import HTTPPlanner
from .tools import WebToolExecutor


@dataclass
class AgentConfig:
    task: str
    max_steps: int = 10
    planner_url: str = "http://planner:8000"
    start_url: str = "https://www.google.com"
    screenshot_dir: str = "screens"


class WebAgent:
    def __init__(self, config: AgentConfig):
        self._config = config
        self._planner = HTTPPlanner(config.planner_url)
        self._last_tool_result: Optional[str] = None

    def run(self) -> None:
        os.makedirs(self._config.screenshot_dir, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()
            page.goto(self._config.start_url, wait_until="domcontentloaded")
            executor = WebToolExecutor(page)

            for step in range(1, self._config.max_steps + 1):
                png = page.screenshot(full_page=True)
                vw = page.viewport_size["width"] if page.viewport_size else 1280
                vh = page.viewport_size["height"] if page.viewport_size else 720
                shot = WebScreenshot(png_bytes=png, width=vw, height=vh)

                action, reason = self._planner.plan(
                    task=self._config.task,
                    screenshot=shot,
                    step=step,
                    max_steps=self._config.max_steps,
                    last_tool_result=self._last_tool_result,
                    page_url=page.url,
                )

                # Save screenshot for debugging
                with open(os.path.join(self._config.screenshot_dir, f"step_{step}.png"), "wb") as f:
                    f.write(png)

                if action is None:
                    self._last_tool_result = f"planner_no_action:{reason}"
                    continue

                result = executor.execute(action.name, action.arguments)
                if action.name == "done":
                    return
                self._last_tool_result = result or f"executed:{action.name}"

            browser.close()
