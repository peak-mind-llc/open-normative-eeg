# infra/aws

Terraform module that provisions everything `scripts/cloud_recompute.py` needs:

- S3 bucket (`runs/`, `mirrors/`) with lifecycle rules
- CloudWatch log group
- Batch compute environment (EC2 Spot, capacity-optimized)
- Batch job queue
- Two job definitions (array worker + merge)
- IAM roles (Batch service, EC2 instance, container job role)
- Security group (outbound-only)
- AWS Budgets alert (optional email)
- SNS topic for alerts (optional email)

## Prerequisites

- Terraform ≥ 1.5 (`brew install terraform`)
- AWS credentials resolvable via the standard chain (env, `~/.aws/credentials`, SSO)
- Permission to create IAM roles, S3 buckets, Batch resources, Budgets
  (`AdministratorAccess` is sufficient; a tighter custom policy also works)

## First-time apply

```bash
cd infra/aws
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — at minimum set a globally-unique bucket_name

terraform init
terraform plan    # review
terraform apply   # create everything
```

On completion:

```bash
terraform output aws_config_yaml_snippet
# Paste these values into ../../aws-config.yaml (top-level, merge with existing keys).
```

## Tearing down

```bash
# Delete any data in the bucket first — the bucket is not force-destroyed.
aws s3 rm s3://<your-bucket>/ --recursive --profile <your-profile>

terraform destroy
```

## Common overrides (terraform.tfvars)

```hcl
region             = "us-east-1"   # if you prefer Virginia
notification_email = "you@example.com"
monthly_budget_usd = 50
instance_types     = ["c7i.2xlarge"]  # restrict to one family for CPU homogeneity
max_vcpus          = 512              # allow more parallelism
```

## What this module intentionally does NOT provision

- **Dedicated VPC**: uses the default VPC. Production-grade setups should
  replace this with a private VPC + VPC endpoints for S3/Logs to avoid
  NAT Gateway charges.
- **ECR repo**: we publish container images to GHCR (public), not ECR.
  If you fork and want a private registry, add `aws_ecr_repository`.
- **KMS key**: S3 uses SSE-S3 (AES256). Substitute SSE-KMS for stricter
  compliance requirements.

## Cost sanity

Idle cost is ~$1–2/month for the bucket + CloudWatch log group. Batch
compute environment and job queue are free until jobs run (scale-to-zero).
The $25 budget alert fires well before runaway spend.
