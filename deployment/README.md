# Portable Production Deployment

This directory deploys the current optimized portfolio only. The local `C:\Backup\Documents\Websume` directory remains a backup and is not part of this release flow.

The production stack is intentionally small:

- Nginx is the only public container and owns ports 80 and 443.
- Gunicorn serves Flask privately on the Docker network.
- Ollama serves `nomic-embed-text` privately on the Docker network.
- A named Docker volume holds the validated local RAG index.
- Gemini credentials and the final hostname live only in `deployment/.env` on the server.

No database, NAT Gateway, load balancer, RDS, or Aurora is required.

## Before provisioning

1. Follow [AWS cost guardrails](aws-cost-guardrails.md), including credit verification and a read-only resource inventory.
2. Create and confirm the Budget alerts and Cost Anomaly Detection email subscription.
3. Create the smallest suitable Ubuntu EC2 VM and an EBS root volume. Restrict SSH to your own IP address; allow ports 80 and 443 publicly only when ready for HTTPS.
4. Assign a stable public IP only if you need one. Point the actual final DNS hostname at that IP before issuing a certificate.

The AWS credit balance and eligibility must be confirmed in the Billing console immediately before provisioning. Do not include the Aurora/RDS-only promotion in the hosting estimate.

## Server preparation

On the VM, install Docker Engine with the Docker Compose plugin, clone the optimized repository, then create the private environment file:

```bash
cd /opt/mihir-portfolio
cp deployment/.env.example deployment/.env
chmod 600 deployment/.env
chmod +x deployment/deploy.sh deployment/bootstrap_tls.sh deployment/renew_tls.sh
```

Set `GEMINI_API_KEY`, `PUBLIC_HOSTNAME`, `PUBLIC_ORIGIN`, and `CERTBOT_EMAIL` in `deployment/.env`. `PUBLIC_ORIGIN` must be the final public origin, such as `https://your-real-domain`; the repository never assumes a hostname.

Keep `RAG_RETRIEVAL_MODE=local_hybrid` for the default production path. Do not expose Ollama, port 11434, or Gunicorn port 8000 in an EC2 security group.

## Configuration validation

Before starting containers, validate the Compose configuration without using a
real API key. From the repository root, point the Compose interpolation variable
at the committed sample file:

```bash
PORTFOLIO_ENV_FILE="$(pwd)/deployment/.env.example" \
  docker compose --env-file deployment/.env.example -f deployment/compose.yaml config
```

The actual VM deployment uses `deployment/.env`, which remains private and is
selected automatically by the deployment scripts.

## First deployment

Run the index-aware application deployment:

```bash
./deployment/deploy.sh
```

For local hybrid mode, the script starts Ollama, pulls `nomic-embed-text`, rebuilds the index from only `knowledge/sources.json`, starts Gunicorn, and waits for `/healthz`. It does not start the TLS Nginx gateway until a certificate exists.

After DNS for `PUBLIC_HOSTNAME` resolves to this VM and port 80 is reachable, issue the first certificate:

```bash
./deployment/bootstrap_tls.sh
```

Then verify from another machine:

```bash
curl -fsS https://your-real-domain/healthz
curl -I https://your-real-domain/
```

The health endpoint returns only `ok` or `unready` plus the retrieval mode. It never reveals keys, paths, source records, or provider failures.

## Ongoing maintenance

Rebuild the local index after any approved source change:

```bash
docker compose --env-file deployment/.env -f deployment/compose.yaml --profile maintenance run --rm indexer
docker compose --env-file deployment/.env -f deployment/compose.yaml restart portfolio
```

Renew certificates monthly through cron or a systemd timer:

```bash
./deployment/renew_tls.sh
```

Use the following when debugging without exposing secrets in shell history:

```bash
docker compose --env-file deployment/.env -f deployment/compose.yaml ps
docker compose --env-file deployment/.env -f deployment/compose.yaml logs --tail=200 portfolio
docker compose --env-file deployment/.env -f deployment/compose.yaml logs --tail=200 nginx
```

## File Search alternative

`gemini_file_search` remains supported but must point to a separate, current store that exactly matches every enabled source in `knowledge/sources.json`. Do not repurpose the old store. Build a new approved store through the explicit admin command, validate it, then set its ID only in `deployment/.env` before changing `RAG_RETRIEVAL_MODE`.

## Portability

The server has no AWS-specific application dependency. If AWS credits stop being viable, copy the optimized repository and `deployment/.env` securely to another Linux VM, transfer only the necessary Docker volumes or rebuild the local index, update DNS, and run the same deployment scripts. Never copy a real `.env` file into Git.
