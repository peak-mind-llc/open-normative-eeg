# IAM role assumed by GitHub Actions (via OIDC) for the release workflow.
# Lets .github/workflows/release.yml run `scripts/release.py --publish`
# with no static AWS keys. Trust is restricted to this repo on tag pushes
# matching v*, so arbitrary branches/PRs cannot assume this role.
#
# After `terraform apply`, paste the `release_role_arn` output into the
# GitHub repo secret AWS_RELEASE_ROLE_ARN.

variable "github_repo" {
  description = "GitHub repo (OWNER/NAME) allowed to assume the release role."
  type        = string
  default     = "peak-mind-llc/open-normative-eeg"
}

# One-time-per-account OIDC provider for GitHub Actions.
# If your account already has one for token.actions.githubusercontent.com,
# `terraform import aws_iam_openid_connect_provider.github <existing-arn>`
# before applying, otherwise this resource will fail with EntityAlreadyExists.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # GitHub's well-known thumbprints. AWS no longer validates these for
  # github.com (it uses JWKS), but the field is still required.
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
  tags = var.tags
}

data "aws_iam_policy_document" "release_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Only the configured repo's v* tag pushes may assume this role.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/tags/v*"]
    }
  }
}

data "aws_iam_policy_document" "release_permissions" {
  # S3: list bucket, read runs/<id>/* (for download), write releases/<v>/* (publish).
  statement {
    sid       = "BucketList"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.runs.arn]
  }
  statement {
    sid     = "ReadRunsReleasesMirrors"
    actions = ["s3:GetObject"]
    resources = [
      "${aws_s3_bucket.runs.arn}/runs/*",
      "${aws_s3_bucket.runs.arn}/releases/*",
      # mirrors/ needed by cloud_recompute.py's _stage_s3_mirror_layout so the
      # release workflow can enumerate LEMON subjects from our S3 mirror
      # without any local data on the runner. Read-only here; mirrors are
      # populated out of band by operators.
      "${aws_s3_bucket.runs.arn}/mirrors/*",
    ]
  }
  statement {
    sid       = "WriteReleases"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.runs.arn}/releases/*"]
  }

  # Batch: submit (the rebuild), describe (the --follow poll), queue checks.
  statement {
    sid = "BatchSubmitAndDescribe"
    actions = [
      "batch:SubmitJob",
      "batch:DescribeJobs",
      "batch:DescribeJobQueues",
      "batch:DescribeJobDefinitions",
      "batch:ListJobs",
      "batch:TagResource",
    ]
    resources = ["*"]
  }

  # SubmitJob with a pre-registered JD needs PassRole on the role baked into
  # the JD (the per-job container role).
  statement {
    sid       = "PassJobRole"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.job.arn]
  }

  # CloudWatch Logs: cloud_recompute's `logs` subcommand reads here.
  statement {
    sid = "LogsRead"
    actions = [
      "logs:DescribeLogStreams",
      "logs:GetLogEvents",
      "logs:FilterLogEvents",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role" "release" {
  name               = "${var.name_prefix}-release"
  description        = "Assumed by GitHub Actions release.yml via OIDC (tag pushes only)."
  assume_role_policy = data.aws_iam_policy_document.release_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy" "release" {
  name   = "${var.name_prefix}-release-permissions"
  role   = aws_iam_role.release.id
  policy = data.aws_iam_policy_document.release_permissions.json
}

output "release_role_arn" {
  description = "Paste into GitHub repo secret AWS_RELEASE_ROLE_ARN."
  value       = aws_iam_role.release.arn
}
