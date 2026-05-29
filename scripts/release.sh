#!/usr/bin/env bash
# Cut a versioned norms release.
#
# Usage:
#   scripts/release.sh v0.3.0
#
# This is the LOCAL wrapper a human runs to kick off a release.
# It does not run the heavy rebuild itself — it bumps the version,
# updates the CHANGELOG, commits, tags, and pushes. The tag push
# triggers .github/workflows/release.yml, which runs
# `python scripts/release.py <version> --publish` on the
# self-hosted runner (the actual cloud rebuild + S3 publish).
#
# Preflight checks (refuses to release if any fail):
#   - on main with a clean working tree
#   - main is up to date with origin
#   - tests pass
#   - tag does not already exist
#   - CHANGELOG.md has an [Unreleased] section to convert
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <version>   (e.g. $0 v0.3.0)" >&2
    exit 2
fi

VERSION_INPUT="$1"
VERSION_TAG="${VERSION_INPUT#v}"     # strip leading v if present
VERSION_TAG="v${VERSION_TAG}"        # re-add so we always have "vX.Y.Z"
VERSION="${VERSION_TAG#v}"           # bare X.Y.Z for pyproject

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Version must be MAJOR.MINOR.PATCH (got: $VERSION)" >&2
    exit 2
fi

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

# --- preflight ---------------------------------------------------------

BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "main" ]; then
    echo "Refusing to release: not on main (on '$BRANCH')." >&2
    exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Refusing to release: working tree is dirty." >&2
    git status --short >&2
    exit 1
fi

git fetch origin main --quiet
LOCAL=$(git rev-parse main)
REMOTE=$(git rev-parse origin/main)
if [ "$LOCAL" != "$REMOTE" ]; then
    echo "Refusing to release: main is not in sync with origin/main." >&2
    echo "  local:  $LOCAL" >&2
    echo "  remote: $REMOTE" >&2
    exit 1
fi

if git rev-parse "$VERSION_TAG" >/dev/null 2>&1; then
    echo "Refusing to release: tag $VERSION_TAG already exists." >&2
    exit 1
fi

if ! grep -q '^## \[Unreleased\]' CHANGELOG.md; then
    echo "Refusing to release: CHANGELOG.md has no [Unreleased] section." >&2
    exit 1
fi

echo "Running tests..."
if [ -f .venv/bin/activate ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi
python -m pytest tests/ \
    --ignore=tests/test_pipeline.py \
    --ignore=tests/test_preprocessing.py -q

# --- bump version + CHANGELOG -----------------------------------------

TODAY=$(date -u +%Y-%m-%d)

echo "Bumping pyproject.toml: -> $VERSION"
python - "$VERSION" <<'PY'
import re, sys, pathlib
version = sys.argv[1]
p = pathlib.Path("pyproject.toml")
text = p.read_text()
new = re.sub(r'^version\s*=\s*"[^"]+"',
             f'version = "{version}"', text, count=1, flags=re.M)
if new == text:
    sys.exit("pyproject.toml: no version line replaced")
p.write_text(new)
PY

echo "Updating CHANGELOG: [Unreleased] -> [$VERSION] - $TODAY"
python - "$VERSION" "$TODAY" <<'PY'
import sys, pathlib
version, today = sys.argv[1], sys.argv[2]
p = pathlib.Path("CHANGELOG.md")
text = p.read_text()
target = "## [Unreleased]"
if target not in text:
    sys.exit("CHANGELOG.md: no [Unreleased] section")
# Move the Unreleased contents under a versioned header; restart an empty
# Unreleased block at the top so the next release has a place to land.
new = text.replace(
    target,
    f"## [Unreleased]\n\n## [{version}] - {today}",
    1,
)
p.write_text(new)
PY

# --- commit, tag, push ------------------------------------------------

git add pyproject.toml CHANGELOG.md
git commit -m "release: $VERSION_TAG"
git tag -a "$VERSION_TAG" -m "$VERSION_TAG"

echo
echo "Local release commit + tag prepared:"
git --no-pager log -1 --oneline
git --no-pager show "$VERSION_TAG" --stat --no-patch | head -10
echo
read -r -p "Push to origin and trigger release.yml? [y/N] " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Not pushed. Undo with:"
    echo "  git tag -d $VERSION_TAG && git reset --hard HEAD~1"
    exit 0
fi

git push origin main
git push origin "$VERSION_TAG"

echo
echo "Pushed $VERSION_TAG. Release workflow will start on the self-hosted runner."
echo "Watch: gh run watch  (or https://github.com/peak-mind-llc/open-normative-eeg/actions)"
