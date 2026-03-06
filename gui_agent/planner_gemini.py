from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from google import genai
from google.genai import types

from .perception import Screenshot
from .tools import get_tool_specs


@dataclass(frozen=True)
class PlannedAction:
    name: str
    arguments: Dict[str, Any]


class GeminiPlanner:
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self._client = genai.Client(api_key=key)
        self._model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def plan(
        self,
        task: str,
        screenshot: Screenshot,
        step: int,
        max_steps: int,
        last_tool_result: Optional[str] = None,
    ) -> Tuple[Optional[PlannedAction], str]:
        tool_specs = get_tool_specs()

        function_declarations: list[dict[str, Any]] = [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.json_schema,
            }
            for t in tool_specs
        ]

        tools = [types.Tool(function_declarations=function_declarations)]
        tool_config = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="ANY",
                allowed_function_names=[t.name for t in tool_specs],
            )
        )

        system = (
            "You are a GUI automation planner. You must operate a computer UI by calling tools. "
            "Decide the SINGLE next best tool call. If the task is complete, call done. "
            "Use screen coordinates as integers."
        )

        user_text = (
            f"System: {system}\n"
            f"Task: {task}\n"
            f"Step: {step}/{max_steps}\n"
            f"Screen size: {screenshot.size[0]}x{screenshot.size[1]}\n"
        )
        if last_tool_result:
            user_text += f"Last result: {last_tool_result}\n"

        image_part = types.Part.from_bytes(data=screenshot.to_png_bytes(), mime_type="image/png")
        contents = [types.Content(role="user", parts=[types.Part(text=user_text), image_part])]

        config = types.GenerateContentConfig(
            tools=tools,
            tool_config=tool_config,
        )

        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )

        try:
            parts = response.candidates[0].content.parts
        except Exception:
            parts = []

        for part in parts:
            fc = getattr(part, "function_call", None)
            if not fc:
                continue
            try:
                args = dict(fc.args) if fc.args is not None else {}
            except Exception:
                args = {}
            return PlannedAction(name=fc.name, arguments=args), f"tool_call:{fc.name}"

        # No function call: return any text for debugging.
        text = getattr(response, "text", None) or "no_tool_call"
        return None, text
