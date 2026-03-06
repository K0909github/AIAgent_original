from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from openai import OpenAI


app = FastAPI(title="gui-agent-planner", version="0.1.0")


class ScreenSize(BaseModel):
    w: int
    h: int


class PlanRequest(BaseModel):
    task: str = Field(..., min_length=1)
    step: int = Field(..., ge=1)
    max_steps: int = Field(..., ge=1)
    screen_size: ScreenSize
    image_data_url: str = Field(..., min_length=10)
    last_tool_result: Optional[str] = None


class PlanResponse(BaseModel):
    action: Optional[Dict[str, Any]] = None
    reason: str


def _tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": "click",
            "description": "Click at screen coordinates (x, y).",
            "parameters": {
                "type": "object",
                "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
                "required": ["x", "y"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "type_text",
            "description": "Type text into the currently focused input.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "scroll",
            "description": "Scroll the mouse wheel by amount (positive=up, negative=down).",
            "parameters": {
                "type": "object",
                "properties": {"amount": {"type": "integer"}},
                "required": ["amount"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "wait",
            "description": "Wait for a number of seconds.",
            "parameters": {
                "type": "object",
                "properties": {"seconds": {"type": "number", "minimum": 0}},
                "required": ["seconds"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "done",
            "description": "Finish the task when it is complete.",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": ["string", "null"]}},
                "required": [],
                "additionalProperties": False,
            },
        },
    ]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest) -> PlanResponse:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")

    client = OpenAI()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    system = (
        "You are a GUI automation planner. You must operate a computer UI by calling tools. "
        "Decide the SINGLE next best tool call. If the task is complete, call done. "
        "Use screen coordinates as integers."
    )

    user_text = (
        f"Task: {req.task}\n"
        f"Step: {req.step}/{req.max_steps}\n"
        f"Screen size: {req.screen_size.w}x{req.screen_size.h}\n"
    )
    if req.last_tool_result:
        user_text += f"Last result: {req.last_tool_result}\n"

    resp = client.responses.create(
        model=model,
        instructions=system,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_text},
                    {"type": "input_image", "image_url": req.image_data_url},
                ],
            }
        ],
        tools=_tool_specs(),
    )

    for item in getattr(resp, "output", []) or []:
        if item.type == "function_call":
            name = item.name
            args_raw = item.arguments or "{}"
            try:
                args = json.loads(args_raw)
            except Exception:
                args = {}
            return PlanResponse(action={"name": name, "arguments": args}, reason=f"tool_call:{name}")

    return PlanResponse(action=None, reason="no_tool_call")
