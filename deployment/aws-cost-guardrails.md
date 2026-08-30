# AWS Cost Guardrails

Complete this checklist in the AWS Console before creating or changing production resources. It deliberately does not delete anything automatically.

## Credit verification

1. Open Billing and Cost Management, then **Credits**.
2. Record the extra credit amount, expiry date, and eligible services in a private deployment note.
3. Verify that the Aurora/RDS-specific promotional credit is excluded from the portfolio hosting calculation.
4. Treat credits as runway, not a permanent hosting plan. Alerts notify you; they do not stop an instance automatically.

## Existing resource inventory

Before provisioning, inspect the current AWS account for chargeable resources. In the Console, review EC2 instances, Elastic IP addresses, EBS volumes and snapshots, load balancers, NAT gateways, Route 53 hosted zones, CloudWatch log groups, RDS, and Aurora. Do not delete a resource until its purpose is known.

If the AWS CLI is configured for the correct account and region, these read-only commands provide a second inventory:

```bash
aws sts get-caller-identity
aws ec2 describe-instances
aws ec2 describe-addresses
aws ec2 describe-volumes
aws ec2 describe-snapshots --owner-ids self
aws elbv2 describe-load-balancers
aws ec2 describe-nat-gateways
aws rds describe-db-instances
aws rds describe-db-clusters
```

## Alerts

1. Deploy `deployment/aws/portfolio-cost-budget.yaml` in CloudFormation with your email and a conservative monthly threshold such as USD 5.
2. Confirm every budget email subscription.
3. In Billing and Cost Management, create a **Cost Anomaly Monitor** for AWS services and an email subscription for it. Cost Anomaly Detection is configured separately from the budget template.
4. Add a Billing alarm or review the Billing dashboard weekly while credits are active.

## Smallest intended AWS stack

- One EC2 instance with one EBS root volume.
- One stable public IP only if the final deployment needs it.
- Docker, Nginx, Gunicorn/Flask, and private Ollama on that instance.
- HTTPS through Let's Encrypt after the final `PUBLIC_HOSTNAME` DNS record points at the instance.

Do not add RDS, Aurora, NAT Gateway, a load balancer, or another managed service for this portfolio. The deployment is intentionally portable: the same containers can later move to another suitable VM provider without changing the RAG architecture or frontend.
