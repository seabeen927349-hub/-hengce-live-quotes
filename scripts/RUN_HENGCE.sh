#!/usr/bin/env bash
set -euo pipefail
ROOT="${HENGCE_ROOT:-$(pwd)}"
DETACHED="${HENGCE_DETACHED_LAUNCHER:-$ROOT/RUN_IN_WORK_DETACHED.sh}"
COMPLETE="${HENGCE_COMPLETE_RUNNER:-$ROOT/RUN_HENGCE_COMPLETE.sh}"
[[ -f "$DETACHED" ]] || { echo "FAIL_CLOSED: detached launcher not found: $DETACHED" >&2; exit 2; }
[[ -f "$COMPLETE" ]] || { echo "FAIL_CLOSED: complete runner not found: $COMPLETE" >&2; exit 2; }
HENGCE_ROOT="$ROOT" HENGCE_RUNNER="$COMPLETE" bash "$DETACHED"
