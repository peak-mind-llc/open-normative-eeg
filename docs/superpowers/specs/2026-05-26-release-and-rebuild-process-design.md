# Release & Rebuild Process

**Date:** 2026-05-26
**Status:** Approved design → implementation
**Branch:** `feat/release-process`

## Goal

Make cutting a versioned norms release **easy and reproducible**: one script runs the
whole process (rebuild norms → assemble payload → verify), and tagging a release triggers
CI to run it and publish stable artifacts that downstream apps (Coherence Workstation and
others) can pick up by version or "latest".

## What a release is

A semver tag `vX.Y.Z` that pins, under one version, via a `release.json` manifest:

- the **code** that built it — git SHA, git tag, and the GHCR image digest;
- the **dataset set + sources** — which datasets, their source locations, channel count,
  and per-dataset subject counts;
- the **pipeline params** — a hash of `PIPELINE_PARAMS`;
- the **rebuilt norm artifacts** — the cw_payload (`norms_psd.npz`, `npz/` band-level
  split, `MANIFEST.txt`), each with a sha256;
- the **data format versions** — `format_version` (band-level) and `psd_format_version`.

## Scope

- **Datasets:** LEMON + Dortmund, 37-channel (the current shipped product cohort). SRM is
  **out of scope** here — it needs a separate from-raw recompute (loader fix + unit guard
  already merged on `main`).
- **Release contents:** code version + rebuilt norm bundle, tied by one version. **Not**
  PyPI; **not** a GHCR image build (the image already auto-publishes on `main` pushes — the
  release only records its digest).
- **Versioning:** semver for releases, starting `v0.2.0`. The data `format_version` /
  `psd_format_version` stay independent but are recorded in `release.json`.

## Components

| File | Responsibility |
|------|----------------|
| `scripts/release.py` (new) | The one orchestrator. Builds on `cloud_recompute.py` primitives. Runs the whole process; `--publish` uploads artifacts. Single source of truth for both local and CI. |
| `.github/workflows/release.yml` (new) | Tag-triggered (`push: tags: ['v*']`) thin wrapper that runs `release.py <tag> --publish` with AWS OIDC creds. |
| `docs/RELEASE.md` (new) | Runbook + the consumer contract (how apps fetch a release). |
| `CHANGELOG.md` (new) | Keep-a-Changelog format. |
| `tests/test_release.py` (new) | Unit tests for the mechanical pieces (mocked cloud + S3). |

## The script: `scripts/release.py`

One command, optional `--publish`:

```bash
python scripts/release.py v0.2.0            # build + test locally (iterate)
python scripts/release.py v0.2.0 --publish  # also publish artifacts (what CI runs)
python scripts/release.py v0.2.0 --publish --dry-run  # test publish logic, no writes
```

Internal phases (each idempotent; safe to re-run):

1. **validate** — clean git tree; version is valid semver and greater than the current
   `pyproject.toml` version; `aws-config.yaml` present.
2. **bump** — set `pyproject.toml` `version` and `open_normative/__init__.py`
   `__version__` to `X.Y.Z`; scaffold a `CHANGELOG.md` entry from commits since the last
   tag (left for human editing).
3. **rebuild** — for each dataset, submit a `cloud_recompute` job under a release-scoped
   run_id `release-vX.Y.Z-<dataset>-37ch`; submit the merge job. The jobs use the **same
   pipeline flags that produced the current payload** — `--channels 37 --condition both
   --source --ba-connectivity --dk-connectivity --save-psd` — so the merged output carries
   the full scalp + source norms the `npz/` split needs. **Idempotent by run_id:** if a run
   for this version already completed (per its `_submission.json`), skip resubmission and
   reuse it. Poll to completion.
4. **assemble** — download the merged output from S3, build the cw_payload into
   `dist/releases/vX.Y.Z/`: `norms_psd.npz` (already produced by the merge),
   `MANIFEST.txt`, and the **`npz/` band-level split**. NOTE: merge mode was observed
   (2026-05) *not* to rewrite `npz/` — the plan must confirm this and, if so, regenerate
   the split explicitly by calling `open_normative.io.write_norms_npz` on the merged norm
   cells (from `norms.json`). Then compute every file's sha256 and write `release.json`.
5. **verify** (the gate — fails the whole run on any violation, so a bad build never
   publishes):
   - `norms_psd.npz`: `psd_format_version == 2`; `percentile_points` exact; `p50 ≈ mean`
     (median \|p50−mean\| < 0.25 log10) and percentiles monotonic along the last axis;
     **no physiologically impossible magnitudes** (max alpha-band `p97.5` within a sane
     log10(µV²/Hz) range — reuses the unit-guard bounds, catching the SRM-class bug);
   - band-level `npz/metadata.json` present with expected categories and `format_version`;
     `n`-per-cell present and at/above an expected minimum.
6. **publish** (only with `--publish`, only after verify passes):
   - upload `dist/releases/vX.Y.Z/` to immutable `s3://<bucket>/releases/vX.Y.Z/`
     (refuse to overwrite an existing version prefix);
   - write `s3://<bucket>/releases/latest.json`;
   - create GitHub Release `vX.Y.Z` with notes (the CHANGELOG entry) and `release.json` +
     checksums attached.

`--dry-run` performs validate→verify and logs the publish actions without writing to S3
or GitHub.

## CI: `.github/workflows/release.yml`

```yaml
on:
  push:
    tags: ['v*']
permissions:
  id-token: write   # AWS OIDC
  contents: write   # create GitHub Release
```

Steps: checkout the tag → set up Python → configure AWS credentials via OIDC role (no
static keys) → `pip install` → `python scripts/release.py ${GITHUB_REF_NAME} --publish`.
If `verify` fails, the job fails and nothing is published.

**Runner-time note:** the LEMON+Dortmund rebuild on Spot Batch fits within GitHub's 6h job
limit. Idempotency means if you already ran the rebuild locally for that version, the CI
run reuses the completed jobs and only assembles + publishes (fast).

## Consumer contract (how other apps pick up a release)

Documented in `docs/RELEASE.md`. Downstream apps read **`release.json`** as the index:

```jsonc
{
  "version": "v0.2.0",
  "created": "2026-05-26T18:00:00Z",
  "builder": "ci",                       // or "local:<user>"
  "code": { "git_sha": "...", "git_tag": "v0.2.0",
            "image": "ghcr.io/peak-mind-llc/open-normative-eeg@sha256:..." },
  "datasets": [
    { "name": "lemon",    "source": "s3://<bucket>/mirrors/lemon",
      "channels": 37, "run_id": "release-v0.2.0-lemon-37ch",    "n_subjects": 176 },
    { "name": "dortmund", "source": "s3://openneuro.org/ds...",
      "channels": 37, "run_id": "release-v0.2.0-dortmund-37ch", "n_subjects": 1216 }
  ],
  "merge_run_id": "release-v0.2.0-merged-37ch",
  "pipeline_params_sha256": "...",
  "format_versions": { "norms_npz": 2, "psd": 2 },
  "artifacts": [
    { "path": "norms_psd.npz",        "bytes": 5851423, "sha256": "..." },
    { "path": "npz/scalp_power.npz",  "bytes": 6964112, "sha256": "..." }
    // ... every file in the payload
  ],
  "s3_base": "s3://<bucket>/releases/v0.2.0/"
}
```

Fetch options:
- **Pinned:** read `s3://<bucket>/releases/vX.Y.Z/release.json`.
- **Latest:** read `s3://<bucket>/releases/latest.json` → follow to that version's
  `release.json`.
- **GitHub:** download the release assets for `vX.Y.Z`.

In all cases the app verifies each file's sha256 against `release.json` before loading.
Releases are **immutable** — a bad one is superseded by a higher version, never overwritten
(documented rollback = publish a new version and repoint `latest.json`).

## Testing

`tests/test_release.py`, with `cloud_recompute` calls and S3 mocked (`moto`, already a dev
dep):

- version bump writes both `pyproject.toml` and `__init__.py` correctly;
- `release.json` assembly lists every payload file with correct sha256/bytes;
- the **verify gate** passes a good synthetic payload and **fails** a deliberately bad one
  (e.g. a `norms_psd.npz` with inflated p97.5, or missing `psd_format_version`);
- `latest.json` is written/updated on publish;
- idempotency: a completed run_id is reused (rebuild not resubmitted);
- `--dry-run` makes no S3/GitHub writes.

## Out of scope

- PyPI publishing; GHCR image build (auto on `main`; release records the digest only).
- Datasets beyond LEMON+Dortmund (SRM/HBN/MIPDB/TRT/Depress).
- Automated rollback (manual supersede, documented in `RELEASE.md`).
- Changing the norms pipeline or artifact formats.
