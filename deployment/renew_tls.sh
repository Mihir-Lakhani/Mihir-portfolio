#!/usr/bin/env bash
set -euo pipefail

deployment_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compose_file="$deployment_dir/compose.yaml"
env_file="${DEPLOY_ENV_FILE:-$deployment_dir/.env}"
export PORTFOLIO_ENV_FILE="$env_file"

docker compose --env-file "$env_file" -f "$compose_file" --profile maintenance run --rm certbot renew --quiet
docker compose --env-file "$env_file" -f "$compose_file" exec -T nginx nginx -s reload
