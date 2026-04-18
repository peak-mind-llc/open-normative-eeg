"""Configuration loading for the cloud-run orchestrator.

One YAML file per user, typically `aws-config.yaml` at the project root.
Gitignored; each user fills it in with their own bucket / queue / JDs
(populated by `terraform output`) plus experiment-specific overrides.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Flattened view of aws-config.yaml.

    Mandatory: aws.region, storage.bucket, compute.batch_job_queue,
    compute.batch_job_definition (array worker JD).

    Optional: aws.profile, compute.batch_merge_job_definition (for
    experiments with a merge step), compute.image, per-experiment
    overrides under experiment.<name>.

    Any other keys in the YAML are ignored — extending the schema
    later won't break older orchestrator versions.
    """

    # AWS
    profile: str | None
    region: str

    # S3
    bucket: str
    runs_prefix: str
    mirrors_prefix: str

    # Batch
    job_queue: str
    array_jd: str
    merge_jd: str | None
    default_image: str | None

    # Per-slice work tuning
    workers_per_slice: int
    default_slices: int
    min_units_per_slice: int

    # Raw YAML kept in case a caller wants experiment-specific overrides
    raw: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str) -> "Config":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"Config not found: {path}\n"
                f"Copy the example file (aws-config.example.yaml) to "
                f"{path.name} and fill in your values."
            )
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required: pip install 'open-cloud-run[cli]' "
                "or pip install pyyaml"
            ) from exc
        data = yaml.safe_load(path.read_text()) or {}
        try:
            aws = data.get("aws") or {}
            storage = data.get("storage") or {}
            compute = data.get("compute") or {}
            slicing = data.get("slicing") or {}
            return cls(
                profile=aws.get("profile"),
                region=aws["region"],
                bucket=storage["bucket"],
                runs_prefix=(storage.get("runs_prefix") or "runs/").rstrip("/") + "/",
                mirrors_prefix=(storage.get("mirrors_prefix") or "mirrors/").rstrip("/") + "/",
                job_queue=compute["batch_job_queue"],
                array_jd=compute["batch_job_definition"],
                merge_jd=compute.get("batch_merge_job_definition"),
                default_image=compute.get("image"),
                workers_per_slice=int(compute.get("workers_per_slice", 1)),
                default_slices=int(slicing.get("default_slices", 10)),
                min_units_per_slice=int(slicing.get("min_units_per_slice", 1)),
                raw=data,
            )
        except KeyError as exc:
            sys.exit(f"{path.name} is missing required key: {exc}")

    def runs_s3_uri(self, run_id: str) -> str:
        return f"s3://{self.bucket}/{self.runs_prefix}{run_id}/"

    def out_s3_uri(self, run_id: str) -> str:
        return self.runs_s3_uri(run_id) + "out/"
