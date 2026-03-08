from __future__ import annotations

import argparse

from .agent import AgentConfig, WebAgent


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="web-agent", description="Docker-first Web GUI agent (Playwright + Gemini planner)")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="Run the web agent")
    run.add_argument("--task", required=True)
    run.add_argument("--max-steps", type=int, default=10)
    run.add_argument("--planner-url", default="http://planner:8000")
    run.add_argument("--start-url", default="https://duckduckgo.com")
    run.add_argument("--screenshot-dir", default="screens")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "run":
        agent = WebAgent(
            AgentConfig(
                task=args.task,
                max_steps=args.max_steps,
                planner_url=args.planner_url,
                start_url=args.start_url,
                screenshot_dir=args.screenshot_dir,
            )
        )
        agent.run()
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
