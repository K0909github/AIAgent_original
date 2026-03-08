#!/usr/bin/env bash
set -euo pipefail

# Run compose and propagate the web-agent exit code,
# then copy screenshots out of the (stopped) container into ./screens.
# This works even when bind mounts don't map to this workspace (e.g. Dev Containers).

exit_code=0

docker compose up --build --abort-on-container-exit --exit-code-from web-agent || exit_code=$?

mkdir -p ./screens

container_id="$(docker compose ps -a -q web-agent || true)"
if [[ -n "$container_id" ]]; then
  # Copy any screenshots created by the agent.
  # Use `|| true` so we still exit with the agent's exit code.
  docker cp "${container_id}:/app/screens/." ./screens/ || true
fi

exit "$exit_code"
