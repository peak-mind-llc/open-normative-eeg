output "bucket" {
  description = "S3 bucket name — paste into aws-config.yaml storage.bucket."
  value       = aws_s3_bucket.runs.id
}

output "region" {
  description = "Region this module was applied in — paste into aws-config.yaml aws.region."
  value       = data.aws_region.current.name
}

output "batch_job_queue" {
  description = "Paste into aws-config.yaml compute.batch_job_queue."
  value       = aws_batch_job_queue.main.name
}

output "batch_job_definition" {
  description = "Array worker JD name (no revision). Paste into aws-config.yaml compute.batch_job_definition."
  value       = aws_batch_job_definition.array_worker.name
}

output "batch_merge_job_definition" {
  description = "Merge JD name. Paste into aws-config.yaml compute.batch_merge_job_definition."
  value       = aws_batch_job_definition.merge.name
}

output "qs_research_job_definition" {
  description = "qs-research JD name. Paste into ~/git/qs-research/aws-config.yaml compute.batch_job_definition."
  value       = aws_batch_job_definition.qs_research.name
}

output "log_group" {
  description = "CloudWatch log group that Batch jobs write to."
  value       = aws_cloudwatch_log_group.jobs.name
}

output "job_role_arn" {
  description = "IAM role assumed by running containers (debug reference)."
  value       = aws_iam_role.job.arn
}

output "aws_config_yaml_snippet" {
  description = "Ready-to-paste aws-config.yaml values. Run `terraform output aws_config_yaml_snippet` after apply."
  value = <<EOT
aws:
  region: ${data.aws_region.current.name}
storage:
  bucket: ${aws_s3_bucket.runs.id}
compute:
  batch_job_queue: ${aws_batch_job_queue.main.name}
  batch_job_definition: ${aws_batch_job_definition.array_worker.name}
  batch_merge_job_definition: ${aws_batch_job_definition.merge.name}
EOT
}
