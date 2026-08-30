#!/usr/bin/env bash
set -euo pipefail

deployment_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compose_file="$deployment_dir/compose.yaml"
env_file="${DEPLOY_ENV_FILE:-$deployment_dir/.env}"
export PORTFOLIO_ENV_FILE="$env_file"

if [[ ! -f "$env_file" ]]; then
  echo "Missing server environment file: $env_file" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a

for variable in GEMINI_API_KEY PUBLIC_HOSTNAME PUBLIC_ORIGIN CERTBOT_EMAIL; do
  if [[ -z "${!variable:-}" ]]; then
    echo "Missing required value in $env_file: $variable" >&2
    exit 1
  fi
done

if [[ "${RAG_RETRIEVAL_MODE:-local_hybrid}" == "local_hybrid" ]]; then
  docker compose --env-file "$env_file" -f "$compose_file" up -d ollama
  docker compose --env-file "$env_file" -f "$compose_file" --profile maintenance run --rm model-init
  docker compose --env-file "$env_file" -f "$compose_file" --profile maintenance run --rm indexer
fi

docker compose --env-file "$env_file" -f "$compose_file" up -d --build portfolio

portfolio_id=""
for _ in $(seq 1 15); do
  portfolio_id="$(docker compose --env-file "$env_file" -f "$compose_file" ps -q portfolio)"
  if [[ -n "$portfolio_id" ]]; then
    break
  fi
  sleep 1
done

if [[ -z "$portfolio_id" ]]; then
  echo "Portfolio container was not created. Inspect: docker compose -f $compose_file logs portfolio" >&2
  exit 1
fi

for _ in $(seq 1 45); do
  health_status="$(docker inspect -f '{{.State.Health.Status}}' "$portfolio_id" 2>/dev/null || true)"
  if [[ "$health_status" == "healthy" ]]; then
    break
  fi
  sleep 2
done

health_status="$(docker inspect -f '{{.State.Health.Status}}' "$portfolio_id" 2>/dev/null || true)"
if [[ "$health_status" != "healthy" ]]; then
  echo "Portfolio container did not become healthy. Inspect: docker compose -f $compose_file logs portfolio" >&2
  exit 1
fi

if docker compose --env-file "$env_file" -f "$compose_file" --profile maintenance run --rm --no-deps --entrypoint sh certbot -c '[ -f /etc/letsencrypt/live/portfolio/fullchain.pem ]'; then
  docker compose --env-file "$env_file" -f "$compose_file" up -d nginx
  echo "Portfolio and HTTPS gateway are running."
else
  echo "Portfolio is healthy. Run deployment/bootstrap_tls.sh after DNS points PUBLIC_HOSTNAME at this server."
fi
