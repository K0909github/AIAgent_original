from __future__ import annotations

import base64
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from google import genai
from google.genai import errors as genai_errors
from google.genai import types


app = FastAPI(title="web-agent-planner", version="0.1.0")


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
            "name": "goto",
            "description": "Navigate the browser to a URL.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"url": {"type": "STRING"}},
                "required": ["url"],
            },
        },
        {
            "name": "click",
            "description": "Click an element by CSS selector.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"selector": {"type": "STRING"}},
                "required": ["selector"],
            },
        },
        {
            "name": "type",
            "description": "Type text into an input/textarea by CSS selector.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"selector": {"type": "STRING"}, "text": {"type": "STRING"}},
                "required": ["selector", "text"],
            },
        },
        {
            "name": "press",
            "description": "Press a keyboard key (e.g. Enter, Tab).",
            "parameters": {
                "type": "OBJECT",
                "properties": {"key": {"type": "STRING"}},
                "required": ["key"],
            },
        },
        {
            "name": "wait",
            "description": "Wait for a number of seconds.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"seconds": {"type": "NUMBER", "minimum": 0}},
                "required": ["seconds"],
            },
        },
        {
            "name": "done",
            "description": "Finish the task when it is complete.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"message": {"type": "STRING", "nullable": True}},
                "required": [],
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
        "You are a web browser automation planner. You must operate the page by calling tools. "
        "Decide the SINGLE next best tool call. If the task is complete, call done. "
        "When interacting with the page, use stable CSS selectors (prefer input[name=...], button:has-text(...), etc.)."
        " If the page is a CAPTCHA/robot check (e.g. 'unusual traffic', 'verify you are not a robot'), "
        "you MUST call done with a short message explaining that automation cannot proceed on that page."
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

    try:
        resp = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(tools=tools, tool_config=tool_config),
        )
    except genai_errors.ClientError as e:
        # Common transient/quotas: return a graceful "done" so the web-agent can exit without crashing.
        msg = str(e)
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
            return PlanResponse(
                action={
                    "name": "done",
                    "arguments": {
                        "message": "Gemini API quota/rate-limit reached. Please wait and retry later (or lower WEB_AGENT_MAX_STEPS / upgrade billing)."
                    },
                },
                reason="quota_exhausted",
            )
        raise

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
