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
        # Ensure SSM policy is attached (harmless if already attached; idempotent).
        aws_cmd_iam iam attach-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore 2>/dev/null || true
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

    # Attach SSM managed-instance-core so `aws ssm start-session` works
    # into the instance for debugging hangs. No extra cost; SSM agent is
    # pre-installed on Amazon Linux 2023.
    aws_cmd_iam iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore

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

echo "--- installing wget (AL2023 ships with curl, not wget) ---"
# Retry up to 5 times in case the package repos aren't ready yet at boot
for attempt in 1 2 3 4 5; do
    if dnf install -y wget; then
        break
    fi
    echo "dnf install attempt $attempt failed, retrying in 10s..."
    sleep 10
done
command -v wget || { echo "FATAL: wget not available after 5 attempts" >&2; exit 1; }

# /tmp on AL2023 is tmpfs (RAM-backed, ~half of RAM = ~2 GB on t3.medium),
# which can't hold LEMON's ~65 GB. Use /data on the root EBS volume.
WORK=/data/lemon
mkdir -p "$WORK"
cd "$WORK"

echo "--- disk sanity before wget ---"
df -h /

echo "--- pulling LEMON RSEEG data from GWDG ($(date -u)) ---"
wget -r -np -nH --cut-dirs=3 -R "index.html*" \
     -A "*.vhdr,*.eeg,*.vmrk" \
     "$EEG_URL"

# wget's --cut-dirs setting determines where files land; easier to
# just find EEG_Raw_BIDS_ID/ wherever it ended up. Robust to any
# future path-depth change on GWDG's side.
EEG_DIR=$(find . -type d -name "EEG_Raw_BIDS_ID" | head -1)
if [ -z "$EEG_DIR" ]; then
    echo "FATAL: wget finished but no EEG_Raw_BIDS_ID/ directory found." >&2
    find . -maxdepth 3 -type d >&2
    exit 1
fi
echo "--- wget done at $(date -u); files in $EEG_DIR ($(du -sh "$EEG_DIR" | cut -f1)) ---"

echo "--- pulling demographics CSV ---"
curl -fsSL -o META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv "$META_CSV_URL"

echo "--- disk after wget ---"
df -h /

# Fail-fast sanity check: if wget got <50 subjects something went wrong.
SUBJECTS=$(ls -d "$EEG_DIR"/sub-* 2>/dev/null | wc -l)
if [ "$SUBJECTS" -lt 50 ]; then
    echo "FATAL: expected ~215 LEMON subjects, got $SUBJECTS. wget or disk likely failed." >&2
    exit 1
fi
echo "--- $SUBJECTS subjects on disk ---"

echo "--- upload to s3://${BUCKET}/mirrors/lemon/ (start $(date -u)) ---"
aws s3 cp META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv \
    "s3://${BUCKET}/mirrors/lemon/" --region "$REGION" --no-progress

aws s3 sync "$EEG_DIR/" \
    "s3://${BUCKET}/mirrors/lemon/" \
    --region "$REGION" --no-progress
echo "--- s3 sync done at $(date -u) ---"

cat > "$WORK/_mirror_complete.json" <<JSON
{
  "dataset": "lemon",
  "finished_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "subjects": ${SUBJECTS}
}
JSON
aws s3 cp "$WORK/_mirror_complete.json" \
    "s3://${BUCKET}/mirrors/lemon/_mirror_complete.json" \
    --region "$REGION" --no-progress

echo "--- done with ${SUBJECTS} subjects; self-terminating ---"
EOT
}

recipe_flanker() {
    cat <<'EOT'
# Flanker ERN (OpenNeuro ds004883) — S3 source, ffa task only.
# ~75 GB for 172 subjects × ffa task .fdt + .set + metadata.
# Uses aws s3 sync with --no-sign-request for the public OpenNeuro bucket.

SOURCE="s3://openneuro.org/ds004883"
DEST="s3://${BUCKET}/mirrors/flanker"

echo "--- mirroring flanker ffa from ${SOURCE} to ${DEST} ---"

# Two-step mirror: download to local disk (anonymous), upload to our bucket (IAM).
# OpenNeuro only allows anonymous reads (--no-sign-request) for ListObjects.
# Our bucket only allows authenticated writes (IAM). Can't do both in one sync.

LOCAL="/data/flanker"
mkdir -p "${LOCAL}"

echo "--- step 1: download from OpenNeuro to local disk ---"
aws s3 sync "${SOURCE}/" "${LOCAL}/" \
    --no-sign-request \
    --region "${REGION}" \
    --exclude "*" \
    --include "sub-*/eeg/*task-ffa*" \
    --include "dataset_description.json" \
    --include "participants.*" \
    --include "README" \
    --no-progress

# Verify download
FDT_COUNT=$(find "${LOCAL}" -name "*task-ffa_eeg.fdt" | wc -l)
echo "--- downloaded ${FDT_COUNT} .fdt files to local disk ---"

if [ "${FDT_COUNT}" -lt 150 ]; then
    echo "FATAL: expected ~172 .fdt files, got ${FDT_COUNT}" >&2
    exit 1
fi

echo "--- step 2: upload to our bucket ---"
aws s3 sync "${LOCAL}/" "${DEST}/" \
    --region "${REGION}" \
    --no-progress

# Verify upload
UPLOADED=$(aws s3 ls "${DEST}/" --recursive --region "${REGION}" | grep "task-ffa_eeg.fdt" | wc -l)
echo "--- uploaded ${UPLOADED} .fdt files to S3 ---"

echo "--- done with ${UPLOADED} subjects; self-terminating ---"
EOT
}

# ── 3. Build user-data + launch ──────────────────────────────────────────

case "$DATASET" in
    lemon)   RECIPE=$(recipe_lemon) ;;
    flanker) RECIPE=$(recipe_flanker) ;;
    *)
        echo "ERROR: no recipe for dataset=$DATASET" >&2
        echo "Supported: lemon, flanker" >&2
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

# Base64-encode the recipe so we don't have to worry about heredoc
# delimiter collisions when embedding it in the outer user-data heredoc.
RECIPE_B64=$(printf '%s' "$RECIPE" | base64)

USER_DATA=$(cat <<EOT
#!/bin/bash
# Mirror-helper user-data. Output goes to cloud-init's capture
# (/var/log/cloud-init-output.log on the instance + EC2 console output
# via \`aws ec2 get-console-output\`). On failure we also upload the
# cloud-init log to S3 for post-mortem and keep the instance alive 30
# minutes so SSM can inspect.

set -x
echo "MIRROR_START ts=\$(date -u +%Y-%m-%dT%H:%M:%SZ)"

export BUCKET="$BUCKET"
export REGION="$REGION"

# Materialize the recipe on disk and execute it. Base64 → file avoids
# any heredoc-nesting or variable-expansion accidents.
echo '$RECIPE_B64' | base64 -d > /tmp/recipe.sh
chmod +x /tmp/recipe.sh

bash -x /tmp/recipe.sh
RC=\$?

if [ "\$RC" -eq 0 ]; then
    echo "MIRROR_DONE ts=\$(date -u +%Y-%m-%dT%H:%M:%SZ)"
else
    echo "MIRROR_FAILED rc=\$RC ts=\$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    # Post-mortem: upload cloud-init output + our recipe for inspection.
    FAIL_STAMP=\$(date -u +%Y%m%dT%H%M%SZ)
    aws s3 cp /var/log/cloud-init-output.log \\
        "s3://$BUCKET/mirrors/$DATASET/_failed_\${FAIL_STAMP}_cloud-init-output.log" \\
        --region "$REGION" --no-progress 2>&1 || true
    aws s3 cp /tmp/recipe.sh \\
        "s3://$BUCKET/mirrors/$DATASET/_failed_\${FAIL_STAMP}_recipe.sh" \\
        --region "$REGION" --no-progress 2>&1 || true
    # Stay alive 30 min so SSM can attach.
    echo "Instance will self-terminate in 30 minutes. SSM in via:"
    echo "  aws ssm start-session --target \$(curl -s http://169.254.169.254/latest/meta-data/instance-id)"
    sleep 1800
fi

# Instance-initiated-shutdown-behavior=terminate, so this terminates.
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
    # Can't use `ec2 wait instance-terminated` — it treats "pending"
    # (the normal early-launch state) as a terminal failure. Poll
    # describe-instances in a loop instead.
    LAST=""
    while true; do
        STATE=$(aws_cmd ec2 describe-instances \
            --instance-ids "$INSTANCE_ID" \
            --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null || echo "?")
        if [[ "$STATE" != "$LAST" ]]; then
            echo "  $(date +%H:%M:%S) state=$STATE"
            LAST="$STATE"
        fi
        case "$STATE" in
            terminated) break ;;
            "?"|"")
                # describe-instances can return empty briefly after termination.
                # Wait once more and recheck; if still empty, assume terminated.
                sleep 10
                STATE=$(aws_cmd ec2 describe-instances --instance-ids "$INSTANCE_ID" \
                    --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null || echo "terminated")
                [[ "$STATE" == "terminated" || -z "$STATE" ]] && break
                ;;
        esac
        sleep 30
    done
    echo "  terminated. Final S3 state:"
    aws $PROFILE_ARG s3 ls "s3://$BUCKET/mirrors/$DATASET/" --recursive --summarize --region "$REGION" | tail -3
fi
