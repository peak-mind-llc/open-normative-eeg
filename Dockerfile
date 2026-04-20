FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# System deps:
#   build-essential: mne-icalabel / picard compile native extensions
#   libgl1 + libglib2.0-0: MNE plot/render pull these even in headless mode
#   curl + unzip: AWS CLI v2 install
#   ca-certificates: HTTPS for S3 + OpenNeuro
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        libglib2.0-0 \
        curl \
        unzip \
        ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# AWS CLI v2 (official binary, not pip). Used by the entrypoint for
# aws s3 sync of raw data mirrors and per-run checkpoint resume.
RUN ARCH=$(dpkg --print-architecture) \
 && case "$ARCH" in \
      amd64) AWSCLI_ARCH=x86_64 ;; \
      arm64) AWSCLI_ARCH=aarch64 ;; \
      *) echo "unsupported arch: $ARCH" >&2; exit 1 ;; \
    esac \
 && curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-${AWSCLI_ARCH}.zip" -o /tmp/awscliv2.zip \
 && unzip -q /tmp/awscliv2.zip -d /tmp \
 && /tmp/aws/install \
 && rm -rf /tmp/aws /tmp/awscliv2.zip

WORKDIR /app

# Install pinned Python deps first so the layer caches independently of
# application code changes.
COPY requirements-pinned.txt /app/requirements-pinned.txt
RUN pip install -r /app/requirements-pinned.txt

# Then copy the project and install it without re-resolving deps.
COPY pyproject.toml README.md LICENSE /app/
COPY open_normative /app/open_normative
COPY scripts /app/scripts
RUN pip install --no-deps -e /app

# Pre-compute Desikan-Killiany + Brodmann surface labels. These aren't
# checked in (gitignored binaries). build_dk_labels.py fetches fsaverage
# (~400 MB) which we remove afterward to keep the image small. Missing these
# pkls silently drops dk_connectivity / ba_connectivity at runtime.
RUN python /app/scripts/build_dk_labels.py \
 && python /app/scripts/build_ba_labels.py \
 && rm -rf /root/mne_data /root/.cache

# BLAS thread pinning is required for cross-machine bit-identity
# (see open_normative/parameters.py). build_norms.py drives parallelism
# via --jobs, not BLAS.
ENV OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    PYTHONPATH=/app

RUN chmod +x /app/scripts/batch_entrypoint.sh

ENTRYPOINT ["/app/scripts/batch_entrypoint.sh"]
