from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from .perception import Screenshot
from .tools import ToolSpec, get_tool_specs


@dataclass(frozen=True)
class PlannedAction:
    name: str
    arguments: Dict[str, Any]


class OpenAIPlanner:
    def __init__(self, model: Optional[str] = None):
        self._client = OpenAI()
        self._model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def _tools_payload(self, tool_specs: List[ToolSpec]) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": t.name,
                "description": t.description,
                "parameters": t.json_schema,
            }
            for t in tool_specs
        ]

    def plan(
        self,
        task: str,
        screenshot: Screenshot,
        step: int,
        max_steps: int,
        last_tool_result: Optional[str] = None,
    ) -> Tuple[Optional[PlannedAction], str]:
        tool_specs = get_tool_specs()

        system = (
            "You are a GUI automation planner. You must operate a computer UI by calling tools. "
            "Decide the SINGLE next best tool call. If the task is complete, call done. "
            "Use screen coordinates as integers."
        )

        user_text = (
            f"Task: {task}\n"
            f"Step: {step}/{max_steps}\n"
            f"Screen size: {screenshot.size[0]}x{screenshot.size[1]}\n"
        )
        if last_tool_result:
            user_text += f"Last result: {last_tool_result}\n"

        # Responses API supports images + tool calling.
        resp = self._client.responses.create(
            model=self._model,
            instructions=system,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_text},
                        {"type": "input_image", "image_url": screenshot.to_data_url()},
                    ],
                }
            ],
            tools=self._tools_payload(tool_specs),
        )

        # Parse first tool call (if any)
        for item in getattr(resp, "output", []) or []:
            if item.type == "function_call":
                name = item.name
                args_raw = item.arguments or "{}"
                try:
                    args = json.loads(args_raw)
                except Exception:
                    args = {}
                return PlannedAction(name=name, arguments=args), f"tool_call:{name}"

        # Fallback: no tool call — return model text if present
        text = ""
        for item in getattr(resp, "output", []) or []:
            if item.type in {"output_text", "message"}:
                try:
                    text += item.text
                except Exception:
                    pass

        return None, (text or "no_tool_call")
