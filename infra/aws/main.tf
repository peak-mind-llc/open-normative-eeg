provider "aws" {
  region  = var.region
  profile = var.profile
  default_tags {
    tags = var.tags
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Use the default VPC + its subnets for simplicity. Batch container
# instances live in private-style placement but can pull from ECR/GHCR
# and reach S3/CloudWatch via default VPC internet routing. Production
# deployments should substitute a dedicated VPC with VPC endpoints.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ---------------------------------------------------------------------------
# S3 bucket for run artifacts + raw-data mirrors
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "runs" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_public_access_block" "runs" {
  bucket                  = aws_s3_bucket.runs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "runs" {
  bucket = aws_s3_bucket.runs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "runs" {
  bucket = aws_s3_bucket.runs.id

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  dynamic "rule" {
    for_each = var.runs_retention_days > 0 ? [1] : []
    content {
      id     = "expire-old-runs"
      status = "Enabled"
      filter {
        prefix = "runs/"
      }
      expiration {
        days = var.runs_retention_days
      }
    }
  }
}

# ---------------------------------------------------------------------------
# IAM — three roles:
#   1. Batch service role: lets the Batch service manage resources on our behalf
#   2. EC2 instance role: attached to the container host, gives it ECS-agent creds
#   3. Job role: assumed by the running container, scoped to our bucket + logs
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "batch_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["batch.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "batch_service" {
  name               = "${var.name_prefix}-batch-service"
  assume_role_policy = data.aws_iam_policy_document.batch_assume.json
}

resource "aws_iam_role_policy_attachment" "batch_service_managed" {
  role       = aws_iam_role.batch_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2_instance" {
  name               = "${var.name_prefix}-ec2-instance"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "ec2_instance_managed" {
  role       = aws_iam_role.ec2_instance.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_instance_profile" "ec2_instance" {
  name = "${var.name_prefix}-ec2-instance"
  role = aws_iam_role.ec2_instance.name
}

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# The "job role" is assumed by the container itself (via the ECS task
# role mechanism under the hood). This is what --checkpoint-sync uses
# when it calls boto3.client("s3").upload_file.
resource "aws_iam_role" "job" {
  name               = "${var.name_prefix}-job"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "job_permissions" {
  statement {
    sid     = "BucketList"
    actions = ["s3:ListBucket"]
    resources = [aws_s3_bucket.runs.arn]
  }

  statement {
    sid = "ObjectRW"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
    ]
    resources = ["${aws_s3_bucket.runs.arn}/*"]
  }

  statement {
    sid = "PublicDatasetRead"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      "arn:aws:s3:::openneuro.org",
      "arn:aws:s3:::openneuro.org/*",
      "arn:aws:s3:::fcp-indi",
      "arn:aws:s3:::fcp-indi/*",
    ]
  }

  statement {
    sid = "Logs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.jobs.arn}:*"]
  }
}

resource "aws_iam_role_policy" "job" {
  name   = "${var.name_prefix}-job"
  role   = aws_iam_role.job.id
  policy = data.aws_iam_policy_document.job_permissions.json
}

# ---------------------------------------------------------------------------
# Security group — allow container instances outbound; no inbound.
# ---------------------------------------------------------------------------

resource "aws_security_group" "batch" {
  name        = "${var.name_prefix}-batch"
  description = "Outbound-only for Batch container instances"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ---------------------------------------------------------------------------
# CloudWatch log group for job output
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "jobs" {
  name              = "/aws/batch/${var.name_prefix}"
  retention_in_days = var.log_retention_days
}

# ---------------------------------------------------------------------------
# Batch compute environment — Spot, capacity-optimized
# ---------------------------------------------------------------------------

resource "aws_batch_compute_environment" "spot" {
  compute_environment_name = "${var.name_prefix}-spot"
  type                     = "MANAGED"
  service_role             = aws_iam_role.batch_service.arn

  compute_resources {
    type                = "SPOT"
    allocation_strategy = "SPOT_CAPACITY_OPTIMIZED"
    min_vcpus           = 0
    max_vcpus           = var.max_vcpus
    # desired_vcpus omitted — Batch auto-scales from 0
    instance_types      = var.instance_types
    subnets             = data.aws_subnets.default.ids
    security_group_ids  = [aws_security_group.batch.id]
    instance_role       = aws_iam_instance_profile.ec2_instance.arn

    # bid_percentage null = pay up to the on-demand price when needed.
    # Set e.g. 60 to cap Spot bids at 60% of on-demand.
    bid_percentage = null
  }

  depends_on = [aws_iam_role_policy_attachment.batch_service_managed]
}

resource "aws_batch_job_queue" "main" {
  name     = "${var.name_prefix}-queue"
  state    = "ENABLED"
  priority = 1
  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.spot.arn
  }
}

# ---------------------------------------------------------------------------
# Job definitions — array worker + merge
# ---------------------------------------------------------------------------

locals {
  common_container_env = [
    # BLAS pinning duplicates the Dockerfile ENV so container overrides
    # at submit-time don't accidentally unset them.
    { name = "OMP_NUM_THREADS", value = "1" },
    { name = "OPENBLAS_NUM_THREADS", value = "1" },
    { name = "MKL_NUM_THREADS", value = "1" },
    { name = "NUMEXPR_NUM_THREADS", value = "1" },
    { name = "VECLIB_MAXIMUM_THREADS", value = "1" },
  ]
}

# Array-worker JD: processes one slice of subjects. cloud_recompute.py
# submits this with arrayProperties.size = N and overrides env vars per-run.
resource "aws_batch_job_definition" "array_worker" {
  name                  = "${var.name_prefix}-jd"
  type                  = "container"
  platform_capabilities = ["EC2"]

  retry_strategy {
    attempts = 5
    evaluate_on_exit {
      on_status_reason = "Host EC2*"
      action           = "RETRY"
    }
    evaluate_on_exit {
      on_reason = "*"
      action    = "EXIT"
    }
  }

  container_properties = jsonencode({
    image            = var.image
    vcpus            = var.array_vcpus
    memory           = var.array_memory_mib
    jobRoleArn       = aws_iam_role.job.arn
    environment      = local.common_container_env
    readonlyRootFilesystem = false
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.jobs.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "array"
      }
    }
  })

  timeout {
    attempt_duration_seconds = 7200 # 2 hours per attempt; slices should finish in minutes
  }
}

# Merge JD: reads all subjects/*.json from S3 and aggregates. Reuses the
# same image but cloud_recompute.py calls it with a containerOverrides
# command that invokes build_norms.py --merge (bypassing the entrypoint's
# array-slicing logic).
resource "aws_batch_job_definition" "merge" {
  name                  = "${var.name_prefix}-merge-jd"
  type                  = "container"
  platform_capabilities = ["EC2"]

  retry_strategy {
    attempts = 3
    evaluate_on_exit {
      on_status_reason = "Host EC2*"
      action           = "RETRY"
    }
    evaluate_on_exit {
      on_reason = "*"
      action    = "EXIT"
    }
  }

  container_properties = jsonencode({
    image            = var.image
    vcpus            = var.merge_vcpus
    memory           = var.merge_memory_mib
    jobRoleArn       = aws_iam_role.job.arn
    environment      = local.common_container_env
    readonlyRootFilesystem = false
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.jobs.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "merge"
      }
    }
  })

  timeout {
    attempt_duration_seconds = 3600 # 1 hour
  }
}
