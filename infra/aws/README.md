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
# Edit terraform.tfvars — at minimum set a globally-unique bucket_name.
# If you want budget email alerts, also set notification_email here NOW
# (changing it later is fine, but adding it after the first apply means
# AWS sends a confirmation email you'll need to click).

terraform init
terraform plan    # review what will be created
terraform apply   # create everything
```

On completion:

```bash
terraform output aws_config_yaml_snippet
# Paste these values into ../../aws-config.yaml (top-level, merge with existing keys).
```

> **Don't lose `terraform.tfstate`.** The state file in this directory is
> the only record of what Terraform created. If it gets deleted (or you run
> apply from a different machine without it), Terraform will try to recreate
> everything and fail with "already exists" errors on the bucket, IAM roles,
> log group, etc. See *Recovering from missing state* below if this happens.

## Recovering from missing state ("already exists" errors)

If `terraform apply` fails with a wall of `BucketAlreadyExists` /
`EntityAlreadyExists` / `DuplicateRecordException` / `ResourceAlreadyExistsException`
errors, your local state is empty but the AWS resources still exist. Don't
destroy them — import them back into state.

Quick diagnostic:

```bash
terraform state list   # if this shows only `data.*` entries, state is empty
```

Run these imports (one at a time — Terraform serializes state writes anyway).
Substitute your account ID, region, bucket name, and security-group / launch-template IDs
(grab those from the AWS console or `aws ec2 describe-...`):

```bash
ACCT=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1
BUCKET=<your-bucket-name>
PREFIX=norm-recompute   # var.name_prefix, change if you customized it

terraform import aws_s3_bucket.runs "$BUCKET"
terraform import aws_s3_bucket_public_access_block.runs "$BUCKET"
terraform import aws_s3_bucket_server_side_encryption_configuration.runs "$BUCKET"
terraform import aws_s3_bucket_lifecycle_configuration.runs "$BUCKET"

terraform import aws_iam_role.ec2_instance "${PREFIX}-ec2-instance"
terraform import aws_iam_role_policy_attachment.ec2_instance_managed \
  "${PREFIX}-ec2-instance/arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
terraform import aws_iam_instance_profile.ec2_instance "${PREFIX}-ec2-instance"
terraform import aws_iam_role.job "${PREFIX}-job"
terraform import aws_iam_role_policy.job "${PREFIX}-job:${PREFIX}-job"

SG_ID=$(aws ec2 describe-security-groups --filters Name=group-name,Values=${PREFIX}-batch \
  --query 'SecurityGroups[0].GroupId' --output text)
terraform import aws_security_group.batch "$SG_ID"

terraform import aws_cloudwatch_log_group.jobs "/aws/batch/${PREFIX}"

LT_ID=$(aws ec2 describe-launch-templates --launch-template-names ${PREFIX}-batch-instance \
  --query 'LaunchTemplates[0].LaunchTemplateId' --output text)
terraform import aws_launch_template.batch_instance "$LT_ID"

terraform import aws_batch_compute_environment.spot \
  "arn:aws:batch:${REGION}:${ACCT}:compute-environment/${PREFIX}-spot"
terraform import aws_batch_job_queue.main \
  "arn:aws:batch:${REGION}:${ACCT}:job-queue/${PREFIX}-queue"

# Job definitions are versioned — find the active revision number first
JD_REV=$(aws batch describe-job-definitions --job-definition-name ${PREFIX}-jd --status ACTIVE \
  --query 'jobDefinitions[0].revision' --output text)
MERGE_REV=$(aws batch describe-job-definitions --job-definition-name ${PREFIX}-merge-jd --status ACTIVE \
  --query 'jobDefinitions[0].revision' --output text)
terraform import aws_batch_job_definition.array_worker \
  "arn:aws:batch:${REGION}:${ACCT}:job-definition/${PREFIX}-jd:${JD_REV}"
terraform import aws_batch_job_definition.merge \
  "arn:aws:batch:${REGION}:${ACCT}:job-definition/${PREFIX}-merge-jd:${MERGE_REV}"
# Optional: if qs-research-jd exists in your account
# QS_REV=$(aws batch describe-job-definitions --job-definition-name qs-research-jd --status ACTIVE \
#   --query 'jobDefinitions[0].revision' --output text)
# terraform import aws_batch_job_definition.qs_research \
#   "arn:aws:batch:${REGION}:${ACCT}:job-definition/qs-research-jd:${QS_REV}"

terraform import aws_budgets_budget.monthly "${ACCT}:${PREFIX}-monthly"

# Only if you had set notification_email previously:
# terraform import 'aws_sns_topic.alerts[0]' \
#   "arn:aws:sns:${REGION}:${ACCT}:${PREFIX}-alerts"
```

After the imports finish, run `terraform plan`. You should see at most
in-place updates for schema housekeeping (e.g., the Batch job queue
migrating its deprecated `compute_environments` attribute). Real "to add"
or "to destroy" lines mean either: (a) you missed an import, or (b) your
`terraform.tfvars` doesn't match what's deployed (e.g., budget amount,
notification_email). Reconcile tfvars to AWS rather than letting apply
overwrite it, unless you actually want to change the deployment.

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

## Troubleshooting

- **`already exists` errors on apply** — see *Recovering from missing state* above.
- **Email subscription stays "pending"** — AWS sends a confirmation link to
  the address in `notification_email`. Click it (subject: "AWS Notification —
  Subscription Confirmation"); until you do, the budget can't actually email you.
- **Plan keeps showing the same trivial drift after every apply** — usually the
  AWS API returns a default that wasn't in your config. Add the block explicitly
  to `main.tf` to silence it (e.g., the Batch CE `update_policy` block).
- **`ecs:DescribeClusters` denied on the Batch CE** — don't define a custom
  `service_role` on `aws_batch_compute_environment`. AWS now uses the
  `AWSServiceRoleForBatch` service-linked role automatically.
- **Bucket name collision** — S3 bucket names are globally unique across all
  AWS accounts. Pick something with your org or a date suffix.
