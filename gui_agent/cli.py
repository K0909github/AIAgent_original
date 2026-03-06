from __future__ import annotations

import argparse
import os
import sys

from .agent import AgentConfig, GUIAgent
from .planner_http import HTTPPlanner
from .planner_gemini import GeminiPlanner


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gui-agent", description="Minimal Python GUI agent (Observe→Think→Act)")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run the GUI agent")
    run.add_argument("--task", required=True, help="Natural language task to execute")
    run.add_argument("--max-steps", type=int, default=10)
    run.add_argument(
        "--planner",
        choices=["local", "http"],
        default="local",
        help="local=call Gemini directly, http=call planner API",
    )
    run.add_argument("--planner-url", default="http://localhost:8000", help="Base URL for http planner")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not actually click/type/scroll (sets GUI_AGENT_DRY_RUN=1)",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "run":
        if args.dry_run:
            os.environ["GUI_AGENT_DRY_RUN"] = "1"

        if args.planner == "local":
            if not os.getenv("GEMINI_API_KEY"):
                print("GEMINI_API_KEY is not set. Copy .env.example to .env and set your key.", file=sys.stderr)
                return 2
            planner = GeminiPlanner()
        else:
            planner = HTTPPlanner(args.planner_url)

        agent = GUIAgent(planner=planner, config=AgentConfig(task=args.task, max_steps=args.max_steps))
        agent.run()
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
