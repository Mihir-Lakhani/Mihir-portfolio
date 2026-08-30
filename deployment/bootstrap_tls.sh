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

for variable in PUBLIC_HOSTNAME CERTBOT_EMAIL; do
  if [[ -z "${!variable:-}" ]]; then
    echo "Missing required value in $env_file: $variable" >&2
    exit 1
  fi
done

docker compose --env-file "$env_file" -f "$compose_file" stop nginx || true
docker compose --env-file "$env_file" -f "$compose_file" --profile maintenance up -d nginx-bootstrap

cleanup() {
  docker compose --env-file "$env_file" -f "$compose_file" --profile maintenance stop nginx-bootstrap || true
}
trap cleanup EXIT

docker compose --env-file "$env_file" -f "$compose_file" --profile maintenance run --rm certbot \
  certonly --webroot --webroot-path /var/www/certbot \
  --email "$CERTBOT_EMAIL" --agree-tos --no-eff-email \
  --cert-name portfolio --keep-until-expiring -d "$PUBLIC_HOSTNAME"

cleanup
trap - EXIT
docker compose --env-file "$env_file" -f "$compose_file" up -d nginx
echo "HTTPS certificate installed for $PUBLIC_HOSTNAME."
