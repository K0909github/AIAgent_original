from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pyautogui


def _is_dry_run() -> bool:
    return os.getenv("GUI_AGENT_DRY_RUN", "0").strip() in {"1", "true", "True"}


def click(x: int, y: int) -> None:
    if _is_dry_run():
        return
    pyautogui.click(x, y)


def type_text(text: str) -> None:
    if _is_dry_run():
        return
    interval = float(os.getenv("GUI_AGENT_TYPE_INTERVAL", "0.0"))
    pyautogui.write(text, interval=interval)


def scroll(amount: int) -> None:
    if _is_dry_run():
        return
    pyautogui.scroll(amount)


def wait(seconds: float) -> None:
    time.sleep(seconds)


def done(message: Optional[str] = None) -> None:
    # No-op tool; used by the planner to indicate completion.
    return


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    json_schema: Dict[str, Any]


def get_tool_specs() -> List[ToolSpec]:
    return [
        ToolSpec(
            name="click",
            description="Click at screen coordinates (x, y).",
            json_schema={
                "type": "object",
                "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
                "required": ["x", "y"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="type_text",
            description="Type text into the currently focused input.",
            json_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="scroll",
            description="Scroll the mouse wheel by amount (positive=up, negative=down).",
            json_schema={
                "type": "object",
                "properties": {"amount": {"type": "integer"}},
                "required": ["amount"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="wait",
            description="Wait for a number of seconds.",
            json_schema={
                "type": "object",
                "properties": {"seconds": {"type": "number", "minimum": 0}},
                "required": ["seconds"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="done",
            description="Finish the task when it is complete.",
            json_schema={
                "type": "object",
                "properties": {"message": {"type": ["string", "null"]}},
                "required": [],
                "additionalProperties": False,
            },
        ),
    ]


def execute_tool(name: str, arguments: Dict[str, Any]) -> None:
    if name == "click":
        click(int(arguments["x"]), int(arguments["y"]))
        return
    if name == "type_text":
        type_text(str(arguments["text"]))
        return
    if name == "scroll":
        scroll(int(arguments["amount"]))
        return
    if name == "wait":
        wait(float(arguments["seconds"]))
        return
    if name == "done":
        done(arguments.get("message"))
        return

    raise ValueError(f"Unknown tool: {name}")
