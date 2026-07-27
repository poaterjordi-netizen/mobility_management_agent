#!/usr/bin/env bash
set -euo pipefail

readonly repository_url="https://github.com/poaterjordi-netizen/mobility_management_agent.git"
readonly release_ref="${1:-main}"
readonly deploy_root="/opt/mobility-management-agent"
readonly checkout_root="${deploy_root}/source"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (for example through Alibaba Cloud Assistant)." >&2
  exit 1
fi

for required_command in git docker curl; do
  if ! command -v "${required_command}" >/dev/null 2>&1; then
    echo "Missing required command: ${required_command}" >&2
    exit 1
  fi
done

install -d -m 0755 "${deploy_root}"

if [[ -d "${checkout_root}/.git" ]]; then
  git -C "${checkout_root}" fetch --prune origin
else
  git clone "${repository_url}" "${checkout_root}"
fi

git -C "${checkout_root}" checkout --detach "${release_ref}"
git -C "${checkout_root}" status --short

docker compose \
  --project-name mobility-management-agent \
  --file "${checkout_root}/compose.yaml" \
  up --detach --build --remove-orphans

for attempt in {1..30}; do
  if curl --fail --silent --show-error http://127.0.0.1:18081/health >/dev/null; then
    echo "Mobility Management Agent is healthy on 127.0.0.1:18081."
    docker compose \
      --project-name mobility-management-agent \
      --file "${checkout_root}/compose.yaml" \
      ps
    exit 0
  fi
  sleep 2
done

docker compose \
  --project-name mobility-management-agent \
  --file "${checkout_root}/compose.yaml" \
  logs --tail 120
echo "Deployment health check failed." >&2
exit 1
