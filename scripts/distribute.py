#!/usr/bin/env python3
"""Distributed normative EEG processing across multiple machines.

Orchestrates build_norms.py across machines via SSH, using an NFS share
for data and checkpoints.

Usage:
    # Configure machines in distribute.yaml (see --init for a template)
    python scripts/distribute.py --init > distribute.yaml

    # Preview the work split without running anything
    python scripts/distribute.py run --dry-run

    # Launch distributed processing
    python scripts/distribute.py run

    # Check progress across all machines
    python scripts/distribute.py status

    # Merge results from all machines into final norms
    python scripts/distribute.py merge
"""

import argparse
import json
import logging
import shlex
import subprocess
import sys
import time
from pathlib import Path

import yaml

logger = logging.getLogger("distribute")


# ── Configuration ─────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "machines": {
        "mac-mini": {
            "host": "localhost",
            "user": "",
            "jobs": 4,
            "data_root": "/Volumes/dev",
            "python": "python3",
        },
        "linux-fast": {
            "host": "linux-fast.local",
            "user": "hiro",
            "jobs": 6,
            "data_root": "/mnt/dev",
            "python": "python3",
        },
        "linux-slow": {
            "host": "linux-slow.local",
            "user": "hiro",
            "jobs": 3,
            "data_root": "/mnt/dev",
            "python": "python3",
        },
    },
    "project": {
        "repo_path": "open-normative-eeg/open-normative-eeg",
        "output_base": "norms_output",
        "dataset_path": "datasets/lemon",
    },
    "defaults": {
        "dataset": "lemon",
        "condition": "both",
        "channels": 19,
        "skip_connectivity": False,
        "ba_connectivity": False,
        "extra_args": "",
    },
}


def load_config(config_path: str) -> dict:
    """Load and validate the distribute.yaml configuration."""
    path = Path(config_path)
    if not path.exists():
        logger.error(f"Config file not found: {path}")
        logger.error("Run: python scripts/distribute.py --init > distribute.yaml")
        sys.exit(1)

    with open(path) as f:
        cfg = yaml.safe_load(f)

    # Validate required fields
    if "machines" not in cfg or not cfg["machines"]:
        logger.error("Config must define at least one machine")
        sys.exit(1)

    for name, machine in cfg["machines"].items():
        for key in ("host", "data_root", "python"):
            if key not in machine:
                logger.error(f"Machine '{name}' missing required field: {key}")
                sys.exit(1)
        # Defaults
        machine.setdefault("user", "")
        machine.setdefault("jobs", 1)
        machine.setdefault("enabled", True)

    cfg.setdefault("project", {})
    cfg["project"].setdefault("repo_path", "open-normative-eeg/open-normative-eeg")
    cfg["project"].setdefault("output_base", "norms_output")
    cfg["project"].setdefault("dataset_path", "")

    cfg.setdefault("defaults", {})
    cfg["defaults"].setdefault("dataset", "lemon")
    cfg["defaults"].setdefault("condition", "both")
    cfg["defaults"].setdefault("channels", 19)
    cfg["defaults"].setdefault("skip_connectivity", False)
    cfg["defaults"].setdefault("ba_connectivity", False)
    cfg["defaults"].setdefault("extra_args", "")

    return cfg


# ── Path helpers ──────────────────────────────────────────────────────────

def remote_path(machine: dict, relative: str) -> str:
    """Construct a full path on the remote machine."""
    return f"{machine['data_root']}/{relative}"


def ssh_prefix(machine: dict) -> list[str]:
    """Build SSH command prefix for a machine. Empty list for localhost."""
    if machine["host"] in ("localhost", "127.0.0.1", ""):
        return []
    user_host = machine["host"]
    if machine.get("user"):
        user_host = f"{machine['user']}@{machine['host']}"
    return ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", user_host]


def run_remote(machine: dict, cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command on a remote machine (or locally)."""
    prefix = ssh_prefix(machine)
    if prefix:
        full_cmd = prefix + [cmd]
    else:
        full_cmd = ["bash", "-c", cmd]
    return subprocess.run(full_cmd, capture_output=True, text=True, check=check)


# ── Subject counting ─────────────────────────────────────────────────────

def count_eligible_subjects(cfg: dict) -> int:
    """Count eligible subjects by running a quick dry-scan on localhost."""
    # Find a localhost machine, or use the first one
    local_machine = None
    for name, m in cfg["machines"].items():
        if m["host"] in ("localhost", "127.0.0.1", ""):
            local_machine = m
            break

    if local_machine is None:
        logger.warning(
            "No localhost machine in config. Cannot auto-count subjects. "
            "Specify --total-subjects manually."
        )
        return 0

    project = cfg["project"]
    repo = remote_path(local_machine, project["repo_path"])
    defaults = cfg["defaults"]
    dataset = defaults["dataset"]
    dataset_paths = cfg.get("dataset_paths", {})
    if dataset_paths and dataset in dataset_paths:
        data_dir = remote_path(local_machine, dataset_paths[dataset])
    elif project.get("dataset_path"):
        data_dir = remote_path(local_machine, project["dataset_path"])
    else:
        data_dir = ""

    cmd = (
        f"cd {shlex.quote(repo)} && "
        f"{local_machine['python']} scripts/build_norms.py "
        f"{shlex.quote(data_dir)} "
        f"--dataset {defaults['dataset']} "
        f"--condition {defaults['condition']} "
        f"--channels {defaults['channels']} "
        f"--max-subjects 0 "
        f"--output /tmp/_distribute_scan "
        f"2>&1 | grep -oP '(?<=Found )\\d+(?= subjects)'"
    )
    # This is fragile; a better approach is to add a --count-only flag.
    # For now, we'll just estimate from the file scan.
    logger.info("Counting subjects (this may take a moment)...")
    result = run_remote(local_machine, cmd, check=False)
    try:
        return int(result.stdout.strip())
    except (ValueError, AttributeError):
        return 0


def split_ranges(total: int, machines: dict) -> dict[str, tuple[int, int]]:
    """Split subjects across machines proportional to their job count."""
    enabled = {n: m for n, m in machines.items() if m.get("enabled", True)}
    total_jobs = sum(m["jobs"] for m in enabled.values())
    if total_jobs == 0:
        return {}

    ranges = {}
    start = 0
    names = sorted(enabled.keys())
    for i, name in enumerate(names):
        m = enabled[name]
        if i == len(names) - 1:
            # Last machine gets the remainder
            count = total - start
        else:
            count = round(total * m["jobs"] / total_jobs)
        ranges[name] = (start, start + count)
        start += count

    return ranges


# ── Commands ──────────────────────────────────────────────────────────────

def cmd_run(cfg: dict, args: argparse.Namespace):
    """Launch build_norms.py on each machine for its assigned subject range."""
    total = args.total_subjects
    if total <= 0:
        total = count_eligible_subjects(cfg)
    if total <= 0:
        logger.error("Could not determine subject count. Use --total-subjects N.")
        sys.exit(1)

    enabled_machines = {n: m for n, m in cfg["machines"].items() if m.get("enabled", True)}
    ranges = split_ranges(total, enabled_machines)

    project = cfg["project"]
    defaults = cfg["defaults"]

    logger.info(f"Total subjects: {total}")
    logger.info(f"Machines: {len(enabled_machines)}")
    for name, (start, end) in ranges.items():
        m = enabled_machines[name]
        logger.info(f"  {name}: subjects [{start}:{end}) ({end - start} subjects, {m['jobs']} workers)")

    if args.dry_run:
        logger.info("\nDry run — commands that would be executed:")
        for name, (start, end) in ranges.items():
            m = enabled_machines[name]
            cmd = _build_command(m, project, defaults, name, start, end, cfg.get("dataset_paths"))
            prefix = " ".join(ssh_prefix(m)) + " " if ssh_prefix(m) else ""
            logger.info(f"\n  [{name}] {prefix}{cmd}")
        return

    # Launch all machines
    processes = {}
    for name, (start, end) in ranges.items():
        if end <= start:
            continue
        m = enabled_machines[name]
        cmd = _build_command(m, project, defaults, name, start, end, cfg.get("dataset_paths"))

        prefix = ssh_prefix(m)
        if prefix:
            full_cmd = prefix + [cmd]
        else:
            full_cmd = ["bash", "-c", cmd]

        logger.info(f"Launching {name} [{start}:{end})...")
        proc = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        processes[name] = {
            "proc": proc,
            "range": (start, end),
            "machine": m,
        }

    # Monitor and log output
    logger.info(f"\n{len(processes)} machines running. Monitoring...")

    # Find a local machine for writing logs (use its data_root)
    output_base = project.get("output_base", "norms_output")
    local_root = None
    for m in enabled_machines.values():
        if m["host"] in ("localhost", "127.0.0.1", ""):
            local_root = m["data_root"]
            break

    # Wait for all to complete
    for name, info in processes.items():
        proc = info["proc"]
        stdout, _ = proc.communicate()

        # Write logs using the local NFS mount path
        if local_root:
            log_path = Path(f"{local_root}/{output_base}") / name / "run.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(stdout or "")

        if proc.returncode == 0:
            logger.info(f"  {name}: DONE")
        else:
            logger.error(f"  {name}: FAILED (exit code {proc.returncode})")
            logger.error(f"  Last output: {stdout[-500:] if stdout else '(none)'}")

    logger.info("\nAll machines finished. Run 'distribute.py merge' to combine results.")


def _build_command(
    machine: dict, project: dict, defaults: dict,
    machine_name: str, start: int, end: int,
    dataset_paths: dict | None = None,
) -> str:
    """Build the build_norms.py command string for a machine."""
    repo = remote_path(machine, project["repo_path"])

    # Resolve dataset path from dataset_paths map or fallback to project.dataset_path
    dataset = defaults["dataset"]
    if dataset_paths and dataset in dataset_paths:
        data_dir = remote_path(machine, dataset_paths[dataset])
    elif project.get("dataset_path"):
        data_dir = remote_path(machine, project["dataset_path"])
    else:
        data_dir = ""

    output = remote_path(machine, project["output_base"]) + f"/{machine_name}"

    parts = [
        f"cd {shlex.quote(repo)}",
        "&&",
        machine["python"],
        "scripts/build_norms.py",
        shlex.quote(data_dir),
        f"--dataset {defaults['dataset']}",
        f"--condition {defaults['condition']}",
        f"--channels {defaults['channels']}",
        f"--output {shlex.quote(output)}",
        f"-j {machine['jobs']}",
        f"--subject-range {start}:{end}",
    ]

    if defaults.get("skip_connectivity"):
        parts.append("--skip-connectivity")
    if defaults.get("ba_connectivity"):
        parts.append("--ba-connectivity")
    if defaults.get("save_psd"):
        parts.append("--save-psd")

    extra = defaults.get("extra_args", "").strip()
    if extra:
        parts.append(extra)

    return " ".join(parts)


def cmd_status(cfg: dict, args: argparse.Namespace):
    """Check progress by counting checkpoint files on each machine."""
    project = cfg["project"]
    output_base = project.get("output_base", "norms_output")

    logger.info("Checking progress across machines...\n")

    total_checkpoints = 0
    for name, machine in cfg["machines"].items():
        if not machine.get("enabled", True):
            continue

        subjects_dir = remote_path(machine, output_base) + f"/{name}/subjects"
        cmd = f"ls -1 {shlex.quote(subjects_dir)}/*.json 2>/dev/null | wc -l"

        result = run_remote(machine, cmd, check=False)
        count = 0
        try:
            count = int(result.stdout.strip())
        except (ValueError, AttributeError):
            pass

        # Check if process is still running
        pid_cmd = f"pgrep -f 'build_norms.*--subject-range' 2>/dev/null | head -1"
        pid_result = run_remote(machine, pid_cmd, check=False)
        running = bool(pid_result.stdout.strip())

        status = "RUNNING" if running else "idle"
        logger.info(f"  {name:20s}  {count:5d} checkpoints  [{status}]")
        total_checkpoints += count

    logger.info(f"\n  {'TOTAL':20s}  {total_checkpoints:5d} checkpoints")


def cmd_merge(cfg: dict, args: argparse.Namespace):
    """Merge results from all machines into a single normative database."""
    project = cfg["project"]
    defaults = cfg["defaults"]
    output_base = project.get("output_base", "norms_output")

    # Find a local machine for running merge
    local_machine = None
    for name, m in cfg["machines"].items():
        if m["host"] in ("localhost", "127.0.0.1", ""):
            local_machine = m
            break

    if local_machine is None:
        logger.error("Merge must be run on a local machine (host: localhost)")
        sys.exit(1)

    # Collect all subjects/ directories
    merge_dirs = []
    for name, machine in cfg["machines"].items():
        if not machine.get("enabled", True):
            continue
        # Use local paths (NFS is mounted locally)
        subjects_dir = Path(remote_path(local_machine, output_base)) / name / "subjects"
        if subjects_dir.exists():
            n_files = len(list(subjects_dir.glob("*.json")))
            if n_files > 0:
                merge_dirs.append(subjects_dir)
                logger.info(f"  {name}: {n_files} checkpoints in {subjects_dir}")

    if not merge_dirs:
        logger.error("No checkpoint directories found to merge")
        sys.exit(1)

    merged_output = Path(remote_path(local_machine, output_base)) / "merged"
    repo = remote_path(local_machine, project["repo_path"])

    merge_args = " ".join(f"--merge-dir {shlex.quote(str(d))}" for d in merge_dirs)
    cmd = (
        f"cd {shlex.quote(repo)} && "
        f"{local_machine['python']} scripts/build_norms.py "
        f"--merge {merge_args} "
        f"--output {shlex.quote(str(merged_output))} "
        f"--channels {defaults['channels']}"
    )

    if defaults.get("save_psd"):
        cmd += " --save-psd"

    logger.info(f"\nMerging {len(merge_dirs)} directories into {merged_output}...")
    result = subprocess.run(
        ["bash", "-c", cmd],
        text=True,
    )

    if result.returncode == 0:
        logger.info(f"\nMerge complete. Output: {merged_output}")
    else:
        logger.error(f"\nMerge failed (exit code {result.returncode})")
        sys.exit(1)


def cmd_setup(cfg: dict, args: argparse.Namespace):
    """Set up Python environments on remote machines.

    Creates a shared venv on the NFS share (install once, all machines use it),
    or per-machine venvs if data_root differs. Then verifies each machine can
    import the required packages.
    """
    env_cfg = cfg.get("env", {})
    venv_dir = env_cfg.get("venv_dir", "~/.eeg-normative-env")
    requirements = env_cfg.get("requirements", "Data/EEG/eeg-env/requirements.txt")
    system_python = env_cfg.get("system_python", "python3")

    done_hosts = set()

    for name, machine in cfg["machines"].items():
        if not machine.get("enabled", True):
            continue

        host = machine["host"]
        root = machine["data_root"]
        full_reqs = f"{root}/{requirements}"

        # Expand ~ for the venv path (local to each machine's home dir)
        if machine["host"] in ("localhost", "127.0.0.1", ""):
            import os
            expanded_venv = os.path.expanduser(venv_dir)
        else:
            # Let the remote shell expand ~
            expanded_venv = venv_dir

        python_bin = f"{expanded_venv}/bin/python"

        # Skip if we already set up this host
        if host in done_hosts:
            logger.info(f"  {name}: same host as another machine, skipping")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"Setting up {name} ({host})")
        logger.info(f"{'='*60}")

        # Step 1: Create venv
        logger.info(f"  Creating venv at {venv_dir}...")
        result = run_remote(machine, f"{system_python} -m venv {venv_dir}", check=False)
        if result.returncode != 0:
            logger.error(f"  Failed to create venv: {result.stderr}")
            continue

        # Step 2: Install requirements from NFS
        logger.info(f"  Installing packages from {full_reqs}...")
        pip = f"{expanded_venv}/bin/pip"
        result = run_remote(
            machine,
            f"{pip} install -r {shlex.quote(full_reqs)} 2>&1 | tail -5",
            check=False,
        )
        if result.returncode != 0:
            logger.error(f"  pip install failed: {result.stderr}")
            continue
        logger.info(f"  {result.stdout.strip()}")

        # Step 3: Install the project in editable mode
        repo = remote_path(machine, cfg["project"]["repo_path"])
        logger.info(f"  Installing open-normative-eeg from {repo}...")
        result = run_remote(
            machine,
            f"{pip} install -e {shlex.quote(repo)} 2>&1 | tail -3",
            check=False,
        )
        if result.returncode != 0:
            logger.warning(f"  Editable install failed: {result.stderr.strip()[:200]}")

        done_hosts.add(host)

        # Step 4: Verify
        _verify_machine(name, machine, python_bin)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("Setup complete. Update distribute.yaml python paths:")
    for name, machine in cfg["machines"].items():
        if not machine.get("enabled", True):
            continue
        if machine["host"] in ("localhost", "127.0.0.1", ""):
            import os
            venv = os.path.expanduser(venv_dir)
        else:
            venv = venv_dir
        logger.info(f"  {name}: python: {venv}/bin/python")
    logger.info(f"{'='*60}")


def _verify_machine(name: str, machine: dict, python_bin: str):
    """Verify a machine can import the required packages."""
    verify_cmd = (
        f"{python_bin} -c \""
        "import mne; import mne_connectivity; import specparam; "
        "from open_normative.source import ROI_NAMES; "
        f"print(f'OK: MNE {{mne.__version__}}, {{len(ROI_NAMES)}} ROIs')\""
    )
    result = run_remote(machine, verify_cmd, check=False)
    if result.returncode == 0:
        logger.info(f"  {name}: {result.stdout.strip()}")
    else:
        logger.error(f"  {name}: verification FAILED")
        if result.stderr:
            logger.error(f"    {result.stderr.strip()[:200]}")


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Distributed normative EEG processing across machines.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-c", "--config",
        default="distribute.yaml",
        help="Path to distribute.yaml config file (default: distribute.yaml)",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Print a template distribute.yaml config and exit",
    )

    subparsers = parser.add_subparsers(dest="command")

    # run
    run_parser = subparsers.add_parser("run", help="Launch distributed processing")
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the plan without executing",
    )
    run_parser.add_argument(
        "--total-subjects",
        type=int,
        default=0,
        help="Total subject count (auto-detected if 0)",
    )

    # setup
    subparsers.add_parser("setup", help="Set up Python environments on all machines")

    # status
    subparsers.add_parser("status", help="Check progress on all machines")

    # merge
    subparsers.add_parser("merge", help="Merge results from all machines")

    args = parser.parse_args()

    # Logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    if args.init:
        yaml.dump(DEFAULT_CONFIG, sys.stdout, default_flow_style=False, sort_keys=False)
        return

    if not args.command:
        parser.print_help()
        return

    cfg = load_config(args.config)

    if args.command == "setup":
        cmd_setup(cfg, args)
    elif args.command == "run":
        cmd_run(cfg, args)
    elif args.command == "status":
        cmd_status(cfg, args)
    elif args.command == "merge":
        cmd_merge(cfg, args)


if __name__ == "__main__":
    main()
