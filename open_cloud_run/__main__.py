"""Enable `python -m open_cloud_run <subcommand>`."""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
