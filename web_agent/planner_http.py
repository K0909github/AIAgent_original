from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests

from .perception import WebScreenshot


@dataclass(frozen=True)
class PlannedAction:
    name: str
    arguments: Dict[str, Any]


class HTTPPlanner:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    def plan(
        self,
        task: str,
        screenshot: WebScreenshot,
        step: int,
        max_steps: int,
        last_tool_result: Optional[str] = None,
        page_url: Optional[str] = None,
    ) -> Tuple[Optional[PlannedAction], str]:
        context = task
        if page_url:
            context += f"\nCurrent URL: {page_url}" 

        payload = {
            "task": context,
            "step": step,
            "max_steps": max_steps,
            "screen_size": {"w": screenshot.width, "h": screenshot.height},
            "image_data_url": screenshot.to_data_url(),
            "last_tool_result": last_tool_result,
        }
        r = requests.post(f"{self._base_url}/plan", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        action = data.get("action")
        if not action:
            return None, data.get("reason", "no_action")
        return PlannedAction(name=action["name"], arguments=action.get("arguments", {})), data.get("reason", "tool_call")
