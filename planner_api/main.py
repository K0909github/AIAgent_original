from __future__ import annotations

import base64
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


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
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set")

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

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

    # Expect data URL: data:image/png;base64,...
    if "," not in req.image_data_url:
        raise HTTPException(status_code=400, detail="image_data_url must be a data URL")
    _, b64 = req.image_data_url.split(",", 1)
    try:
        image_bytes = base64.b64decode(b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid image_data_url: {e}")

    tool_specs = _tool_specs()
    tools = [types.Tool(function_declarations=tool_specs)]
    tool_config = types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode="ANY",
            allowed_function_names=[t["name"] for t in tool_specs],
        )
    )

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part(text=f"System: {system}\n" + user_text),
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            ],
        )
    ]

    resp = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(tools=tools, tool_config=tool_config),
    )

    try:
        parts = resp.candidates[0].content.parts
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
        return PlanResponse(action={"name": fc.name, "arguments": args}, reason=f"tool_call:{fc.name}")

    return PlanResponse(action=None, reason=getattr(resp, "text", None) or "no_tool_call")
