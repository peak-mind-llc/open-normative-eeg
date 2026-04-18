"""CLI entry point: `open-cloud-run` or `python -m open_cloud_run`.

Five subcommands: submit / status / logs / download / list.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Config
from .enumerate import enumerate_units, slice_units
from .submit import submit_run
from .status import get_status, format_status
from .logs import get_logs, DEFAULT_LOG_GROUP
from .download import download_outputs
from .list_runs import list_runs


def _add_config(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--config",
        type=Path,
        default=Path("aws-config.yaml"),
        help="Path to aws-config.yaml (default: ./aws-config.yaml).",
    )


def cmd_submit(args) -> int:
    cfg = Config.load(args.config)

    if args.dry_run:
        units = enumerate_units(args.enumerate, cwd=args.enumerate_cwd)
        slices, per = slice_units(
            units,
            requested_slices=args.slices,
            requested_per_slice=args.per_slice,
            default_slices=cfg.default_slices,
            min_per_slice=cfg.min_units_per_slice,
        )
        print(f"enumerate       : {args.enumerate}")
        print(f"driver          : {args.driver}")
        if args.merge:
            print(f"merge           : {args.merge}")
        print(f"image           : {args.image or cfg.default_image or '<none>'}")
        print(f"n_units         : {len(units)}")
        print(f"slices          : {len(slices)} × per_slice={per}")
        print(f"first 3 units   : {units[:3]}")
        print("(--dry-run; not submitting)")
        return 0

    tags = {}
    for kv in args.tag or []:
        if "=" not in kv:
            sys.exit(f"--tag must be KEY=VALUE, got {kv!r}")
        k, v = kv.split("=", 1)
        tags[k] = v

    run = submit_run(
        cfg,
        enumerate_cmd=args.enumerate,
        driver_cmd=args.driver,
        image=args.image,
        merge_cmd=args.merge,
        outputs_dir=args.outputs,
        slices=args.slices,
        per_slice=args.per_slice,
        run_id_prefix=args.name,
        tags=tags,
        enumerate_cwd=args.enumerate_cwd,
    )
    print(f"run_id          : {run.run_id}")
    print(f"array_job_id    : {run.array_job_id}")
    if run.merge_job_id:
        print(f"merge_job_id    : {run.merge_job_id}")
    print(f"slices          : {run.slices} × per_slice={run.per_slice}  "
          f"(n_units={run.n_units})")
    print(f"outputs         : {run.outputs_s3_uri}")
    print()
    print("Track progress:")
    print(f"  python -m open_cloud_run status {run.run_id}")
    print(f"  python -m open_cloud_run logs   {run.run_id} --follow")
    return 0


def cmd_status(args) -> int:
    cfg = Config.load(args.config)
    if args.run_id:
        st = get_status(cfg, args.run_id)
        if st is None:
            print(f"No submission manifest found for run_id={args.run_id!r}", file=sys.stderr)
            return 1
        print(format_status(st))
        return 0

    # No run_id: list recent runs + their status.
    rows = list_runs(cfg, limit=args.limit)
    if not rows:
        print("(no runs found)")
        return 0
    for i, row in enumerate(rows):
        rid = row["run_id"]
        if "manifest" in row and row["manifest"] is None:
            print(f"{rid}  (no manifest)")
            continue
        st = get_status(cfg, rid)
        if i:
            print("-" * 60)
        if st is None:
            print(f"{rid}  (manifest unreadable)")
        else:
            print(format_status(st))
    return 0


def cmd_logs(args) -> int:
    cfg = Config.load(args.config)
    return get_logs(cfg, args.run_id, log_group=args.log_group, follow=args.follow)


def cmd_download(args) -> int:
    cfg = Config.load(args.config)
    rc = download_outputs(
        cfg, args.run_id, args.output, include_subjects=args.include_subjects,
    )
    if rc == 0:
        # List what landed, abbreviated.
        print("\nFiles:")
        total = 0
        for p in sorted(args.output.rglob("*")):
            if p.is_file():
                print(f"  {p.relative_to(args.output)}  ({p.stat().st_size:,} bytes)")
                total += 1
        if total == 0:
            print("  (empty)")
    return rc


def cmd_list(args) -> int:
    cfg = Config.load(args.config)
    rows = list_runs(cfg, limit=args.limit)
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("(no runs)")
        return 0
    for row in rows:
        if "manifest" in row and row["manifest"] is None:
            print(f"{row['run_id']}  (no manifest)")
            continue
        print(
            f"{row['run_id']}  "
            f"n_units={row.get('n_units','?')}  "
            f"slices={row.get('slices','?')}  "
            f"image={row.get('image','?')}  "
            f"submitted={str(row.get('submitted_at',''))[:19]}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="open-cloud-run",
        description="Generic AWS Batch array-job orchestrator. See docs/open-cloud-run.md.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("submit", help="Submit a new run")
    _add_config(p)
    p.add_argument("--enumerate", required=True,
                   help="Shell command whose stdout lines are work unit IDs.")
    p.add_argument("--driver", required=True,
                   help="Shell command run per unit; $UNIT and $OUT_DIR are set.")
    p.add_argument("--merge", default=None,
                   help="Optional shell command run after all units succeed.")
    p.add_argument("--image", default=None,
                   help="Container image URI (overrides config compute.image).")
    p.add_argument("--outputs", default="/work/out",
                   help="Driver output directory inside the container (default: /work/out).")
    p.add_argument("--slices", type=int, default=None,
                   help="Number of array elements (default from config).")
    p.add_argument("--per-slice", type=int, default=None,
                   help="Units per slice (overrides --slices math).")
    p.add_argument("--name", default=None,
                   help="Run-id prefix (e.g. experiment name).")
    p.add_argument("--tag", action="append", default=None,
                   help="Extra tag KEY=VALUE (repeatable).")
    p.add_argument("--enumerate-cwd", default=None,
                   help="Directory the enumerator runs in.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would be submitted and exit.")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("status", help="Show job status for a run")
    _add_config(p)
    p.add_argument("run_id", nargs="?")
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("logs", help="Tail CloudWatch logs for a run")
    _add_config(p)
    p.add_argument("run_id")
    p.add_argument("--follow", action="store_true")
    p.add_argument("--log-group", default=DEFAULT_LOG_GROUP,
                   help="CloudWatch log group name (default: %(default)s)")
    p.set_defaults(func=cmd_logs)

    p = sub.add_parser("download", help="Sync run outputs locally")
    _add_config(p)
    p.add_argument("run_id")
    p.add_argument("--output", type=Path, default=Path("./run_outputs"),
                   help="Local directory (default: ./run_outputs).")
    p.add_argument("--include-subjects", action="store_true",
                   help="Also sync per-unit outputs (subjects/ tree).")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("list", help="List recent runs in the bucket")
    _add_config(p)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    args = ap.parse_args(argv)
    return args.func(args)
