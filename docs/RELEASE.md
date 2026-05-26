# Cutting a release

## TL;DR
```bash
python scripts/release.py v0.2.0          # build + test locally; inspect dist/releases/v0.2.0
git tag v0.2.0 && git push origin v0.2.0  # CI runs release.py --publish and publishes
```

## What happens
1. `release.py` bumps the version, rebuilds norms on AWS (LEMON+Dortmund, 37ch, `--source`),
   downloads the merged output, assembles the cw_payload (incl. regenerating the `npz/`
   split), and runs the **verify gate** (percentile self-checks, unit-magnitude bound,
   format versions, band-level metadata). A failed gate aborts — nothing publishes.
2. On a `v*` tag, CI runs the same script with `--publish`, uploading to immutable
   `s3://<bucket>/releases/<version>/` and updating `releases/latest.json`, then creates a
   GitHub Release.

## Consumer contract
Downstream apps read `release.json` (pinned at `releases/<version>/release.json`, or follow
`releases/latest.json`). It lists every artifact with `sha256`; verify hashes before loading.
Releases are **immutable** — to fix a bad release, publish a higher version (CI refuses to
overwrite an existing version prefix) and `latest.json` repoints automatically.

## Prerequisites
- `aws-config.yaml` present (see `aws-config.example.yaml`).
- CI secret `AWS_RELEASE_ROLE_ARN` (OIDC role with S3 + Batch access).
