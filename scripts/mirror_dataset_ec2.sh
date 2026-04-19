#!/usr/bin/env bash
# Spin up a one-shot EC2 instance that pulls a dataset from its public
# source (FTP/HTTPS) and mirrors it into your S3 bucket. Self-terminates
# when done. Cleaner than uploading 60+ GB from a laptop.
#
# Currently supports:
#   lemon   — GWDG FTP → s3://<bucket>/mirrors/lemon/ (RSEEG only, ~65 GB)
#
# Adding a new dataset = add a `recipe_<name>()` function below + one
# case in the dispatcher.
#
# Usage:
#   bash scripts/mirror_dataset_ec2.sh lemon
#   bash scripts/mirror_dataset_ec2.sh lemon --wait       # block until EC2 terminates
#
# Env overrides:
#   BUCKET=<name>           target S3 bucket (default: value from aws-config.yaml,
#                           else fails)
#   AWS_PROFILE=<name>      profile for API calls
#   REGION=<region>         AWS region (default: us-east-1)
#   INSTANCE_TYPE=<type>    EC2 instance type (default: t3.medium)
#   DISK_GB=<int>           EBS root volume size in GB (default: 100)
#
# The script creates a minimal IAM instance profile on first run:
#   role:    open-normative-eeg-mirror-helper
#   policy:  s3:PutObject + s3:ListBucket on <bucket>/mirrors/*
#
# That role is NOT deleted between runs — re-use is cheap, the role costs
# nothing when no instances are using it.

set -euo pipefail

DATASET="${1:-}"
WAIT_FLAG=""
if [[ "${2:-}" == "--wait" ]]; then
    WAIT_FLAG="yes"
fi

if [[ -z "$DATASET" ]]; then
    cat <<EOT >&2
Usage: $0 <dataset> [--wait]

Supported datasets: lemon
Add more by editing scripts/mirror_dataset_ec2.sh (recipe_<name>).
EOT
    exit 2
fi

# ── Defaults / config ────────────────────────────────────────────────────
REGION="${REGION:-us-east-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.medium}"
DISK_GB="${DISK_GB:-100}"
PROFILE_ARG=""
if [[ -n "${AWS_PROFILE:-}" ]]; then
    PROFILE_ARG="--profile $AWS_PROFILE"
fi

# Resolve BUCKET from aws-config.yaml if not set explicitly.
# Looks for a line like `  bucket: <name>` under the storage section.
if [[ -z "${BUCKET:-}" ]]; then
    CFG="$(cd "$(dirname "$0")/.." && pwd)/aws-config.yaml"
    if [[ -f "$CFG" ]]; then
        BUCKET=$(grep -E '^[[:space:]]+bucket:' "$CFG" | head -1 | awk '{print $2}')
    fi
fi
if [[ -z "${BUCKET:-}" ]]; then
    echo "ERROR: BUCKET not set; pass BUCKET=... or put it in aws-config.yaml" >&2
    exit 1
fi

ROLE_NAME="open-normative-eeg-mirror-helper"
PROFILE_NAME="$ROLE_NAME"
TAG_BASE="mirror-${DATASET}-$(date +%Y%m%dT%H%M%SZ)"

echo "=== mirror_dataset_ec2 ==="
echo "  dataset        : $DATASET"
echo "  bucket         : $BUCKET"
echo "  region         : $REGION"
echo "  instance type  : $INSTANCE_TYPE"
echo "  disk size      : ${DISK_GB} GB"
echo "  iam role       : $ROLE_NAME"
echo "  aws profile    : ${AWS_PROFILE:-default}"
echo ""

aws_cmd() { aws $PROFILE_ARG --region "$REGION" "$@"; }
aws_cmd_iam() { aws $PROFILE_ARG "$@"; }   # IAM is global; no region

# ── 1. Ensure IAM instance profile exists ────────────────────────────────

ensure_iam() {
    if aws_cmd_iam iam get-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null 2>&1; then
        echo "  (iam) instance profile $PROFILE_NAME already exists — reusing"
        return
    fi
    echo "  (iam) creating role + instance profile ..."

    TRUST_DOC=$(cat <<'EOT'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ec2.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOT
)
    POLICY_DOC=$(cat <<EOT
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::${BUCKET}"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:AbortMultipartUpload", "s3:GetObject"],
      "Resource": "arn:aws:s3:::${BUCKET}/mirrors/*"
    }
  ]
}
EOT
)

    aws_cmd_iam iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document "$TRUST_DOC" \
        --description "EC2 instance profile used by scripts/mirror_dataset_ec2.sh" \
        >/dev/null

    aws_cmd_iam iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "mirror-s3-write" \
        --policy-document "$POLICY_DOC"

    aws_cmd_iam iam create-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null
    aws_cmd_iam iam add-role-to-instance-profile \
        --instance-profile-name "$PROFILE_NAME" \
        --role-name "$ROLE_NAME"

    # IAM propagation is eventually consistent; wait before launching.
    echo "  (iam) waiting ~15s for propagation..."
    sleep 15
}

# ── 2. Dataset recipes ───────────────────────────────────────────────────
# Each recipe prints a shell script (to stdout) that will be run on the
# EC2 via user-data. The script must end by `shutdown -h now` (not shown
# here; appended by the dispatcher).

recipe_lemon() {
    cat <<'EOT'
# LEMON — resting-state EEG only, served over HTTPS from GWDG.
# Filters by file extension so we don't pull the full multimodal dataset.
FTP_BASE="https://ftp.gwdg.de/pub/misc/MPI-Leipzig_Mind-Brain-Body-LEMON"
EEG_URL="${FTP_BASE}/EEG_MPILMBB_LEMON/EEG_Raw_BIDS_ID/"
META_CSV_URL="${FTP_BASE}/Behavioural_Data_MPILMBB_LEMON/META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv"

yum install -y -q wget

cd /tmp
mkdir -p lemon
cd lemon

echo "=== pulling LEMON RSEEG data from GWDG ($(date -u)) ==="
wget -r -np -nH --cut-dirs=3 -R "index.html*" \
     -A "*.vhdr,*.eeg,*.vmrk" \
     -q --show-progress \
     "$EEG_URL"

echo "=== pulling demographics CSV ==="
wget -q -O META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv "$META_CSV_URL"

echo "=== upload to s3://${BUCKET}/mirrors/lemon/ ==="
aws s3 cp META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv \
    "s3://${BUCKET}/mirrors/lemon/" --region "$REGION" --no-progress

aws s3 sync ./EEG_Raw_BIDS_ID/ \
    "s3://${BUCKET}/mirrors/lemon/" \
    --region "$REGION" --no-progress

# Done marker for monitoring
echo "{\"dataset\":\"lemon\",\"finished_at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"subjects\":$(ls -d EEG_Raw_BIDS_ID/sub-* 2>/dev/null | wc -l)}" \
    > /tmp/_mirror_complete.json
aws s3 cp /tmp/_mirror_complete.json \
    "s3://${BUCKET}/mirrors/lemon/_mirror_complete.json" \
    --region "$REGION" --no-progress

echo "=== done; self-terminating ==="
EOT
}

# ── 3. Build user-data + launch ──────────────────────────────────────────

case "$DATASET" in
    lemon) RECIPE=$(recipe_lemon) ;;
    *)
        echo "ERROR: no recipe for dataset=$DATASET" >&2
        echo "Supported: lemon" >&2
        echo "Add a recipe_${DATASET}() function in $0 to extend." >&2
        exit 2
        ;;
esac

ensure_iam

# Find the most recent Amazon Linux 2023 AMI for the region.
echo "=== resolving Amazon Linux 2023 AMI ==="
AMI_ID=$(aws_cmd ec2 describe-images \
    --owners amazon \
    --filters "Name=name,Values=al2023-ami-*-x86_64" \
              "Name=state,Values=available" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' --output text)
echo "  ami: $AMI_ID"

USER_DATA=$(cat <<EOT
#!/bin/bash
set -e
exec > /var/log/mirror.log 2>&1

# Env available inside the recipe
export BUCKET="$BUCKET"
export REGION="$REGION"

$RECIPE

# Self-terminate. Instance was launched with
# --instance-initiated-shutdown-behavior terminate so `shutdown -h now`
# actually terminates (vs. just stopping).
shutdown -h now
EOT
)

echo ""
echo "=== launching EC2 ($INSTANCE_TYPE, ${DISK_GB} GB root) ==="

INSTANCE_ID=$(aws_cmd ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --iam-instance-profile "Name=$PROFILE_NAME" \
    --user-data "$USER_DATA" \
    --block-device-mappings "[{\"DeviceName\":\"/dev/xvda\",\"Ebs\":{\"VolumeSize\":${DISK_GB},\"DeleteOnTermination\":true,\"VolumeType\":\"gp3\"}}]" \
    --instance-initiated-shutdown-behavior terminate \
    --metadata-options "HttpTokens=required,HttpEndpoint=enabled,HttpPutResponseHopLimit=2" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$TAG_BASE},{Key=Purpose,Value=dataset-mirror},{Key=Dataset,Value=$DATASET}]" \
    --query 'Instances[0].InstanceId' --output text)

echo "  instance id: $INSTANCE_ID"
echo ""
cat <<EOT
=== launched; monitor with ===

  # console-view of user-data stdout (takes ~2 min to populate):
  aws $PROFILE_ARG --region $REGION ec2 get-console-output \\
      --instance-id $INSTANCE_ID --latest --output text

  # progress via S3 size:
  aws $PROFILE_ARG s3 ls s3://$BUCKET/mirrors/$DATASET/ \\
      --recursive --summarize --region $REGION | tail -3

  # instance state (running → shutting-down → terminated):
  aws $PROFILE_ARG --region $REGION ec2 describe-instances \\
      --instance-ids $INSTANCE_ID \\
      --query 'Reservations[0].Instances[0].State.Name' --output text

  # completion marker:
  aws $PROFILE_ARG s3 ls s3://$BUCKET/mirrors/$DATASET/_mirror_complete.json

Cost so far: ~\$0.05 per hour of the $INSTANCE_TYPE ($DISK_GB GB EBS = ~\$0.01/hr).
EOT

if [[ -n "$WAIT_FLAG" ]]; then
    echo ""
    echo "=== waiting for instance termination (--wait) ==="
    aws_cmd ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"
    echo "  terminated. Final S3 state:"
    aws $PROFILE_ARG s3 ls "s3://$BUCKET/mirrors/$DATASET/" --recursive --summarize --region "$REGION" | tail -3
fi
