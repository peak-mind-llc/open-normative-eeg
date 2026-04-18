"""open_cloud_run — generic AWS Batch array-job orchestrator.

A small, opinion-light SDK for submitting per-unit work to AWS Batch,
tracking it via S3 manifests, and retrieving results. Experiment code
stays experiment-owned; the framework only handles enumeration,
slicing, submission, observability, and output sync.

The driver contract lives in docs/open-cloud-run.md. Read it first.

Typical usage:

    from open_cloud_run import Config, submit_run, get_status

    cfg = Config.load("aws-config.yaml")
    run = submit_run(
        cfg,
        enumerate_cmd="python scripts/enumerate.py",
        driver_cmd="python scripts/driver.py",
        image="ghcr.io/example/my-experiment:latest",
        slices=10,
    )
    print(run.run_id)

Or from the CLI:

    python -m open_cloud_run submit \\
        --enumerate "python scripts/enumerate.py" \\
        --driver    "python scripts/driver.py" \\
        --image     ghcr.io/example/my-experiment:latest \\
        --slices 10

See docs/open-cloud-run.md for the full driver contract and worked
examples.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .config import Config
from .manifest import Manifest, submission_key, write_manifest, read_manifest
from .enumerate import enumerate_units
from .submit import SubmittedRun, submit_run
from .status import get_status, format_status
from .logs import get_logs
from .download import download_outputs
from .list_runs import list_runs

__all__ = [
    "Config",
    "Manifest",
    "submission_key",
    "write_manifest",
    "read_manifest",
    "enumerate_units",
    "SubmittedRun",
    "submit_run",
    "get_status",
    "format_status",
    "get_logs",
    "download_outputs",
    "list_runs",
]
