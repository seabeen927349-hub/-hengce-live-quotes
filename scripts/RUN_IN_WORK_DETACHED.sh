#!/usr/bin/env bash
set -euo pipefail

# HENGCE timeout-safe launcher.
# Does NOT alter model/ranking/production logic. It only detaches the existing
# RUN_IN_WORK.sh so an outer 40s/240s command timeout cannot kill the scan.

ROOT="${HENGCE_ROOT:-$(pwd)}"
RUNNER="${HENGCE_RUNNER:-$ROOT/RUN_IN_WORK.sh}"
STATE_DIR="${HENGCE_LAUNCH_STATE_DIR:-$ROOT/work_output/launcher_state}"
LOG_DIR="$STATE_DIR/logs"
PID_FILE="$STATE_DIR/run.pid"
STATUS_FILE="$STATE_DIR/status.json"
# Key lock by root path so separate HENGCE roots do not block each other.
ROOT_KEY="$(printf '%s' "$ROOT" | sha256sum | cut -c1-16)"
LOCK_FILE="${TMPDIR:-/tmp}/hengce_run_in_work_${ROOT_KEY}.lock"

mkdir -p "$LOG_DIR"

if [[ ! -f "$RUNNER" ]]; then
  python3 - "$STATUS_FILE" "$RUNNER" <<'PY'
import json, os, sys
from datetime import datetime, timezone
p, runner = sys.argv[1:]
os.makedirs(os.path.dirname(p), exist_ok=True)
obj = {
  "schema_version": 1,
  "launcher": "RUN_IN_WORK_DETACHED",
  "state": "FAIL_CLOSED",
  "reason": "RUNNER_NOT_FOUND",
  "runner": runner,
  "finished_at_utc": datetime.now(timezone.utc).isoformat(),
}
open(p,"w",encoding="utf-8").write(json.dumps(obj,ensure_ascii=False,indent=2))
PY
  echo "FAIL_CLOSED: RUN_IN_WORK.sh not found: $RUNNER" >&2
  exit 2
fi

# Parent obtains the lock first. The detached worker INHERITS this exact open
# file descriptor; there is no unlock/re-lock gap, so a second launcher cannot
# slip through while the worker is starting.
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "HENGCE already running; refusing duplicate launch."
  exit 3
fi

# PID is a secondary guard/diagnostic. flock is the authority.
if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "HENGCE already running as PID $old_pid; refusing duplicate launch."
    exit 3
  fi
fi

TS="$(TZ=Asia/Taipei date '+%Y%m%dT%H%M%S%z')"
LOG_FILE="$LOG_DIR/RUN_IN_WORK_${TS}.log"
WRAPPER="$STATE_DIR/worker_${TS}_$$.sh"

python3 - "$STATUS_FILE" "$RUNNER" "$LOG_FILE" <<'PY'
import json, os, sys
from datetime import datetime, timezone
p, runner, log = sys.argv[1:]
os.makedirs(os.path.dirname(p), exist_ok=True)
obj = {
  "schema_version": 1,
  "launcher": "RUN_IN_WORK_DETACHED",
  "state": "START_REQUESTED",
  "runner": runner,
  "log_file": log,
  "requested_at_utc": datetime.now(timezone.utc).isoformat(),
}
open(p,"w",encoding="utf-8").write(json.dumps(obj,ensure_ascii=False,indent=2))
PY

cat > "$WRAPPER" <<'SH'
#!/usr/bin/env bash
set +e
ROOT="$1"
RUNNER="$2"
STATUS_FILE="$3"
LOG_FILE="$4"
PID_FILE="$5"
cd "$ROOT" || exit 97
python3 - "$STATUS_FILE" "$LOG_FILE" "$$" <<'PY'
import json, sys
from datetime import datetime, timezone
p, log, pid = sys.argv[1:]
obj = {
  "schema_version": 1,
  "launcher": "RUN_IN_WORK_DETACHED",
  "state": "RUNNING",
  "pid": int(pid),
  "log_file": log,
  "started_at_utc": datetime.now(timezone.utc).isoformat(),
}
open(p,"w",encoding="utf-8").write(json.dumps(obj,ensure_ascii=False,indent=2))
PY

bash "$RUNNER"
rc=$?

python3 - "$STATUS_FILE" "$LOG_FILE" "$rc" <<'PY'
import json, sys
from datetime import datetime, timezone
p, log, rc = sys.argv[1:]
rc = int(rc)
# Return code describes process completion only. Formal HENGCE PASS/FAIL must
# still be read from formal artifacts and gates; the launcher never invents it.
obj = {
  "schema_version": 1,
  "launcher": "RUN_IN_WORK_DETACHED",
  "state": "PROCESS_COMPLETED" if rc == 0 else "PROCESS_FAILED",
  "return_code": rc,
  "log_file": log,
  "finished_at_utc": datetime.now(timezone.utc).isoformat(),
  "formal_result_must_be_read_from_artifacts": True,
}
open(p,"w",encoding="utf-8").write(json.dumps(obj,ensure_ascii=False,indent=2))
PY
rm -f "$PID_FILE"
exit "$rc"
SH
chmod +x "$WRAPPER"

# Critical detail: fd 9 is inherited by the worker (9>&9). Parent may exit,
# but the worker retains the same flock for its entire lifetime.
nohup "$WRAPPER" "$ROOT" "$RUNNER" "$STATUS_FILE" "$LOG_FILE" "$PID_FILE" \
  9>&9 >"$LOG_FILE" 2>&1 < /dev/null &
pid=$!
echo "$pid" > "$PID_FILE"

echo "HENGCE detached successfully. PID=$pid"
echo "STATUS=$STATUS_FILE"
echo "LOG=$LOG_FILE"
exit 0
