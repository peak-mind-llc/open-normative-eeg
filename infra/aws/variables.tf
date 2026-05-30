variable "region" {
  description = "AWS region. us-east-2 is this project's default (matches aws-config.example.yaml)."
  type        = string
  default     = "us-east-2"
}

variable "profile" {
  description = "Named AWS profile for the provider. Leave null to use AWS_PROFILE / env / instance metadata."
  type        = string
  default     = null
}

variable "name_prefix" {
  description = "Prefix applied to every resource name, so multiple deployments can coexist in one account."
  type        = string
  default     = "norm-recompute"
}

variable "bucket_name" {
  description = <<EOT
Globally-unique S3 bucket name. Stores per-run checkpoints under runs/ and
(optionally) raw-data mirrors under mirrors/.
EOT
  type        = string
}

variable "runs_retention_days" {
  description = "Lifecycle: delete runs/* objects after this many days. Set to 0 to disable."
  type        = number
  default     = 90
}

variable "image" {
  description = "Container image URI used by both job definitions."
  type        = string
  default     = "ghcr.io/peak-mind-llc/open-normative-eeg:latest"
}

variable "instance_types" {
  description = "Spot instance types (ranked by preference) for the array-job + merge compute environment. m-family = 4:1 mem:cpu ratio — LEMON+source peaks >4 GB/worker, c-family's 2:1 ratio OOMs. 2xlarge (8 vCPU / 32 GB) fits the array workers; 4xlarge (16 vCPU / 64 GB) is for the v3 merge job which holds ~3× the cell count in RAM due to sex stratification."
  type        = list(string)
  default     = ["m7i.2xlarge", "m6i.2xlarge", "m5.2xlarge", "m7i.4xlarge", "m6i.4xlarge", "m5.4xlarge"]
}

variable "max_vcpus" {
  description = "Cap on concurrent vCPUs across array elements. 256 = ~32 concurrent c*i.2xlarge containers."
  type        = number
  default     = 256
}

variable "array_vcpus" {
  description = "vCPUs requested per array-job container. 32 matches c*i.8xlarge."
  type        = number
  default     = 8
}

variable "array_memory_mib" {
  description = "Memory (MiB) per array-job container. 28672 = 28 GiB on an m*i.2xlarge (32 GB), leaves ~4 GB for OS/Docker."
  type        = number
  default     = 28672
}

variable "merge_vcpus" {
  description = "vCPUs for the merge job. Merge is mostly single-threaded so small is fine."
  type        = number
  default     = 4
}

variable "merge_memory_mib" {
  description = "Memory (MiB) for the merge job. Full-run aggregation loads all subjects + accumulator (per-(bin,sex,cond,ch,band,metric) value lists) into RAM. v3 sex fan-out (pooled+F+M) roughly triples the cell count vs v2 — Dortmund 1216 subject-conditions × full source connectivity OOM'd at 28 GiB. 61440 = 60 GiB on an m*i.4xlarge (64 GB), leaves ~4 GB for OS/Docker."
  type        = number
  default     = 61440
}

variable "log_retention_days" {
  description = "CloudWatch log retention for job logs."
  type        = number
  default     = 30
}

variable "monthly_budget_usd" {
  description = "AWS Budgets monthly threshold. Notifications fire at 80% and 100%."
  type        = number
  default     = 25
}

variable "notification_email" {
  description = "Optional email address for Budget + job-failure alerts. Leave null to skip SNS/budget notifications."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default = {
    Project   = "open-normative-eeg"
    ManagedBy = "terraform"
  }
}
