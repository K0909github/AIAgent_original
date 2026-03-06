from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Tuple

from .perception import Screenshot, get_screenshot
from .tools import execute_tool


class Planner(Protocol):
    def plan(
        self,
        task: str,
        screenshot: Screenshot,
        step: int,
        max_steps: int,
        last_tool_result: Optional[str] = None,
    ) -> Tuple[Optional[object], str]: ...


@dataclass
class AgentConfig:
    task: str
    max_steps: int = 10
    screenshot_path: str = "screens/step.png"


class GUIAgent:
    def __init__(self, planner: Planner, config: AgentConfig):
        self._planner = planner
        self._config = config
        self._last_tool_result: Optional[str] = None

    def run(self) -> None:
        for step in range(1, self._config.max_steps + 1):
            screenshot = get_screenshot(save_path=f"screens/step_{step}.png")
            action, reason = self._planner.plan(
                task=self._config.task,
                screenshot=screenshot,
                step=step,
                max_steps=self._config.max_steps,
                last_tool_result=self._last_tool_result,
            )

            if action is None:
                self._last_tool_result = f"planner_no_action:{reason}"
                continue

            name = getattr(action, "name")
            args = getattr(action, "arguments")
            execute_tool(name, args)

            if name == "done":
                return

            self._last_tool_result = f"executed:{name}"
