#!/usr/bin/env bash
set -euo pipefail

readonly repository_url="https://github.com/poaterjordi-netizen/mobility_management_agent.git"
readonly release_ref="${1:-main}"
readonly deploy_root="/opt/mobility-management-agent"
readonly checkout_root="${deploy_root}/source"
readonly compose_project="mobility-management-agent"
readonly docker_network="mobility-management-agent"

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

deploy_with_raw_docker() {
  local commit_sha api_image web_image
  commit_sha="$(git -C "${checkout_root}" rev-parse --short=12 HEAD)"
  api_image="mobility-management-agent-api:${commit_sha}"
  web_image="mobility-management-agent-web:${commit_sha}"

  docker build \
    --file "${checkout_root}/infra/docker/api.Dockerfile" \
    --tag "${api_image}" \
    "${checkout_root}"
  docker build \
    --file "${checkout_root}/infra/docker/web.Dockerfile" \
    --tag "${web_image}" \
    "${checkout_root}"

  if ! docker network inspect "${docker_network}" >/dev/null 2>&1; then
    docker network create "${docker_network}" >/dev/null
  fi

  docker rm --force mobility-management-agent-web mobility-management-agent-api \
    >/dev/null 2>&1 || true

  docker run --detach \
    --name mobility-management-agent-api \
    --network "${docker_network}" \
    --network-alias api \
    --restart unless-stopped \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=32m \
    --security-opt no-new-privileges:true \
    --env MOBILITY_ENV=staging \
    --env MOBILITY_API_HOST=0.0.0.0 \
    --env MOBILITY_API_PORT=8000 \
    --health-cmd "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)\"" \
    --health-interval 15s \
    --health-timeout 3s \
    --health-retries 5 \
    --health-start-period 10s \
    "${api_image}" >/dev/null

  docker run --detach \
    --name mobility-management-agent-web \
    --network "${docker_network}" \
    --restart unless-stopped \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=32m \
    --security-opt no-new-privileges:true \
    --publish 127.0.0.1:18081:8080 \
    --health-cmd "wget -q -O /dev/null http://127.0.0.1:8080/health" \
    --health-interval 15s \
    --health-timeout 3s \
    --health-retries 5 \
    --health-start-period 10s \
    "${web_image}" >/dev/null
}

if docker compose version >/dev/null 2>&1; then
  docker compose \
    --project-name "${compose_project}" \
    --file "${checkout_root}/compose.yaml" \
    up --detach --build --remove-orphans
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose \
    --project-name "${compose_project}" \
    --file "${checkout_root}/compose.yaml" \
    up --detach --build --remove-orphans
else
  echo "Docker Compose is unavailable; using isolated raw Docker containers."
  deploy_with_raw_docker
fi

for attempt in {1..30}; do
  if curl --fail --silent --show-error http://127.0.0.1:18081/health >/dev/null; then
    echo "Mobility Management Agent is healthy on 127.0.0.1:18081."
    docker ps \
      --filter name=mobility-management-agent \
      --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
    exit 0
  fi
  sleep 2
done

docker logs --tail 120 mobility-management-agent-api 2>/dev/null || true
docker logs --tail 120 mobility-management-agent-web 2>/dev/null || true
echo "Deployment health check failed." >&2
exit 1
