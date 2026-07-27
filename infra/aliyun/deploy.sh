#!/usr/bin/env bash
set -euo pipefail

readonly repository_url="https://github.com/poaterjordi-netizen/mobility_management_agent.git"
readonly release_ref="${1:-main}"
readonly deploy_root="/opt/mobility-management-agent"
readonly checkout_root="${deploy_root}/source"
readonly venv_root="${deploy_root}/venv"
readonly releases_root="${deploy_root}/releases"
readonly compose_project="mobility-management-agent"
readonly docker_network="mobility-management-agent"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (for example through Alibaba Cloud Assistant)." >&2
  exit 1
fi

for required_command in git curl; do
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

  if ! docker build \
    --file "${checkout_root}/infra/docker/api.Dockerfile" \
    --tag "${api_image}" \
    "${checkout_root}"; then
    return 1
  fi
  if ! docker build \
    --file "${checkout_root}/infra/docker/web.Dockerfile" \
    --tag "${web_image}" \
    "${checkout_root}"; then
    return 1
  fi

  systemctl stop mobility-management-agent-api.service \
    mobility-management-agent-web.service >/dev/null 2>&1 || true

  if ! docker network inspect "${docker_network}" >/dev/null 2>&1; then
    docker network create "${docker_network}" >/dev/null
  fi

  docker rm --force mobility-management-agent-web mobility-management-agent-api \
    >/dev/null 2>&1 || true

  if ! docker run --detach \
    --name mobility-management-agent-api \
    --network "${docker_network}" \
    --network-alias api \
    --restart unless-stopped \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=32m \
    --security-opt no-new-privileges:true \
    --env MOBILITY_ENV=staging \
    --env MOBILITY_DATA_MODE=mixed \
    --env MOBILITY_PUBLIC_DATA_ENABLED=true \
    --env MOBILITY_API_HOST=0.0.0.0 \
    --env MOBILITY_API_PORT=8000 \
    --health-cmd "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)\"" \
    --health-interval 15s \
    --health-timeout 3s \
    --health-retries 5 \
    --health-start-period 10s \
    --publish 127.0.0.1:18082:8000 \
    "${api_image}" >/dev/null; then
    return 1
  fi

  if ! docker run --detach \
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
    "${web_image}" >/dev/null; then
    docker rm --force mobility-management-agent-api >/dev/null 2>&1 || true
    return 1
  fi
}

deploy_natively() {
  local commit_sha release_root
  commit_sha="$(git -C "${checkout_root}" rev-parse --short=12 HEAD)"
  release_root="${releases_root}/${commit_sha}"

  for native_command in python3 node npm; do
    if ! command -v "${native_command}" >/dev/null 2>&1; then
      echo "Native fallback requires ${native_command}." >&2
      return 1
    fi
  done

  docker rm --force mobility-management-agent-web mobility-management-agent-api \
    >/dev/null 2>&1 || true

  python3 -m venv "${venv_root}"
  "${venv_root}/bin/python" -m pip install --no-cache-dir "${checkout_root}"

  (
    cd "${checkout_root}/clients/web"
    npm ci
    VITE_BASE_PATH=/mobility/ VITE_API_BASE=/mobility npm run build
  )

  install -d -m 0755 "${release_root}/web"
  cp -a "${checkout_root}/clients/web/dist/." "${release_root}/web/"
  ln -sfn "${release_root}/web" "${deploy_root}/current-web"

  if ! id mobility-agent >/dev/null 2>&1; then
    useradd --system --home-dir /nonexistent --shell /sbin/nologin mobility-agent
  fi

  cat >/etc/systemd/system/mobility-management-agent-api.service <<EOF
[Unit]
Description=Mobility Management Agent API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=mobility-agent
Group=mobility-agent
WorkingDirectory=${checkout_root}
Environment=MOBILITY_ENV=staging
Environment=MOBILITY_DATA_MODE=mixed
Environment=MOBILITY_PUBLIC_DATA_ENABLED=true
Environment=MOBILITY_API_HOST=127.0.0.1
Environment=MOBILITY_API_PORT=18082
ExecStart=${venv_root}/bin/mobility-agent-api
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

  cat >/etc/systemd/system/mobility-management-agent-web.service <<EOF
[Unit]
Description=Mobility Management Agent Static Web
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=mobility-agent
Group=mobility-agent
WorkingDirectory=${deploy_root}/current-web
ExecStart=/usr/bin/python3 -m http.server 18081 --bind 127.0.0.1 --directory ${deploy_root}/current-web
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now mobility-management-agent-api.service
  systemctl enable --now mobility-management-agent-web.service
  systemctl restart mobility-management-agent-api.service
  systemctl restart mobility-management-agent-web.service
}

deployment_mode="docker"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  systemctl stop mobility-management-agent-api.service \
    mobility-management-agent-web.service >/dev/null 2>&1 || true
  docker compose \
    --project-name "${compose_project}" \
    --file "${checkout_root}/compose.yaml" \
    up --detach --build --remove-orphans
elif command -v docker-compose >/dev/null 2>&1; then
  systemctl stop mobility-management-agent-api.service \
    mobility-management-agent-web.service >/dev/null 2>&1 || true
  docker-compose \
    --project-name "${compose_project}" \
    --file "${checkout_root}/compose.yaml" \
    up --detach --build --remove-orphans
else
  if command -v docker >/dev/null 2>&1; then
    echo "Docker Compose is unavailable; trying isolated raw Docker containers."
  fi
  if ! command -v docker >/dev/null 2>&1 || ! deploy_with_raw_docker; then
    echo "Container deployment is unavailable; using native systemd services."
    deployment_mode="native"
    deploy_natively
  fi
fi

for attempt in {1..30}; do
  if curl --fail --silent --show-error http://127.0.0.1:18081/ >/dev/null \
    && curl --fail --silent --show-error http://127.0.0.1:18082/health >/dev/null; then
    echo "Mobility Management Agent web/API are healthy on 18081/18082 (${deployment_mode})."
    if [[ "${deployment_mode}" == "native" ]]; then
      systemctl --no-pager --full status mobility-management-agent-api.service \
        mobility-management-agent-web.service | sed -n '1,80p'
    else
      docker ps \
        --filter name=mobility-management-agent \
        --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
    fi
    exit 0
  fi
  sleep 2
done

docker logs --tail 120 mobility-management-agent-api 2>/dev/null || true
docker logs --tail 120 mobility-management-agent-web 2>/dev/null || true
journalctl --no-pager -u mobility-management-agent-api.service \
  -u mobility-management-agent-web.service -n 120 2>/dev/null || true
echo "Deployment health check failed." >&2
exit 1
