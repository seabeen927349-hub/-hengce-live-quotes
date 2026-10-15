#!/usr/bin/env bash
set -euo pipefail
ROOT="${HENGCE_ROOT:-$(pwd)}"
STATE_DIR="${HENGCE_LAUNCH_STATE_DIR:-$ROOT/work_output/launcher_state}"
STATUS_FILE="$STATE_DIR/status.json"
PID_FILE="$STATE_DIR/run.pid"

if [[ ! -f "$STATUS_FILE" ]]; then
  echo '{"state":"NO_RUN_STATE"}'
  exit 4
fi

cat "$STATUS_FILE"

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo
    echo "PROCESS_ALIVE pid=$pid"
    exit 10
  fi
fi

state="$(python3 - "$STATUS_FILE" <<'PY'
import json,sys
try:
    x=json.load(open(sys.argv[1],encoding='utf-8'))
    print(x.get('state','UNKNOWN'))
except Exception:
    print('INVALID_STATUS_JSON')
PY
)"

case "$state" in
  PROCESS_COMPLETED) exit 0 ;;
  PROCESS_FAILED|FAIL_CLOSED) exit 2 ;;
  DETACHED|RUNNING|START_REQUESTED) exit 10 ;;
  *) exit 5 ;;
esac
