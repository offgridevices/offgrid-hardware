#!/bin/sh
# Run one product's CI on this machine exactly as .github/workflows/ci.yml
# does: the image its tools/ci.json pins (amd64, emulated on an ARM Mac), as
# root, tools/ci-setup.sh and then tools/ci.sh, from the product's folder.
#
#   tools/ci/local.sh products/print-hub
#
# It builds in this checkout, as the product's own make.py does: the outputs
# it writes are the ones CI compares against HEAD, so commit first, and
# expect only the files CI also rewrites (Ridge 3's VERIFICATION.md) to
# change.  The repository is mounted at its own path, and a worktree's .git
# beside it, so git works inside the container.
set -eu
[ $# -eq 1 ] || { echo "usage: $0 products/<product>" >&2; exit 2; }
ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
GIT=$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)
case "$GIT" in "$ROOT"/*) OUTSIDE= ;; *) OUTSIDE=1 ;; esac
P=${1%/}
[ -f "$ROOT/$P/tools/ci.json" ] || { echo "$P has no tools/ci.json" >&2; exit 2; }
IMAGE=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["image"])' "$ROOT/$P/tools/ci.json")
exec docker run --rm --platform linux/amd64 -u root -e HOME=/tmp -e PYTHONHASHSEED=0 \
  -v "$ROOT:$ROOT" ${OUTSIDE:+-v} ${OUTSIDE:+"$GIT:$GIT"} -w "$ROOT/$P" "$IMAGE" sh -c '
  if command -v git > /dev/null; then git config --global --add safe.directory "*"; fi
  tools/ci-setup.sh && tools/ci.sh'
