#!/usr/bin/env bash
set -euo pipefail

ROOT="${HENGCE_ROOT:-$(pwd)}"
FORMAL_RUNNER="${HENGCE_FORMAL_RUNNER:-$ROOT/RUN_IN_WORK.sh}"
INTRADAY_RUNNER="${HENGCE_INTRADAY_RUNNER:-$ROOT/RUN_INTRADAY_ACTION_BOARD.sh}"
STATE_DIR="${HENGCE_COMPLETE_STATE_DIR:-$ROOT/work_output/complete_run_state}"
RECEIPT="$STATE_DIR/HENGCE_COMPLETE_RUN_RECEIPT.json"
mkdir -p "$STATE_DIR"

write_state() {
  local state="$1" reason="${2:-}"
  python3 - "$RECEIPT" "$state" "$reason" <<'PY'
import json,sys
from datetime import datetime,timezone
p,state,reason=sys.argv[1:]
obj={"schema_version":1,"orchestrator":"RUN_HENGCE_COMPLETE","state":state,"updated_at_utc":datetime.now(timezone.utc).isoformat()}
if reason: obj["reason"]=reason
open(p,"w",encoding="utf-8").write(json.dumps(obj,ensure_ascii=False,indent=2))
PY
}

[[ -f "$FORMAL_RUNNER" ]] || { write_state FAIL_CLOSED "FORMAL_RUNNER_NOT_FOUND:$FORMAL_RUNNER"; exit 2; }
[[ -f "$INTRADAY_RUNNER" ]] || { write_state FAIL_CLOSED "INTRADAY_RUNNER_NOT_FOUND:$INTRADAY_RUNNER"; exit 2; }

write_state FORMAL_RUNNING
set +e
bash "$FORMAL_RUNNER"
formal_rc=$?
set -e
if [[ $formal_rc -ne 0 ]]; then
  write_state FAIL_CLOSED "FORMAL_RUNNER_RC_$formal_rc"
  exit 2
fi

# Process exit 0 is not enough: require an actual formal v2/v3 artifact.
BASE="${HENGCE_FORMAL_BASE_JSON:-}"
if [[ -z "$BASE" ]]; then
  for p in \
    "$ROOT/work_output/formal/production/v2_scan.json" \
    "$ROOT/work_output/formal/production/v3_scan.json" \
    "$ROOT/work_output/formal/v2_scan.json" \
    "$ROOT/work_output/formal/v3_scan.json"; do
    [[ -f "$p" ]] && { BASE="$p"; break; }
  done
fi
if [[ -z "$BASE" ]]; then
  BASE="$(find "$ROOT/work_output" -type f \( -name 'v2_scan.json' -o -name 'v3_scan.json' \) -path '*formal*' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2- || true)"
fi
if [[ -z "$BASE" || ! -f "$BASE" ]]; then
  write_state FAIL_CLOSED "FORMAL_ARTIFACT_NOT_FOUND_AFTER_RUN"
  exit 2
fi

if ! python3 - "$BASE" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
if x.get('formal_scan_allowed') is False:
    raise SystemExit(1)
PY
then
  write_state FAIL_CLOSED "FORMAL_ARTIFACT_DISALLOWED"
  exit 2
fi

write_state INTRADAY_BINDING
set +e
HENGCE_FORMAL_BASE_JSON="$BASE" bash "$INTRADAY_RUNNER"
intra_rc=$?
set -e
if [[ $intra_rc -ne 0 ]]; then
  write_state FAIL_CLOSED "INTRADAY_RUNNER_RC_$intra_rc"
  exit 2
fi

BOARD="${HENGCE_INTRADAY_OUT_DIR:-$ROOT/work_output/intraday_action_board}/HENGCE_INTRADAY_ACTION_BOARD.json"
if ! python3 - "$BOARD" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
assert x.get('ActionLayer')=='INTRADAY_ACTION_BOARD'
assert x.get('binding_status')=='PASS'
PY
then
  write_state FAIL_CLOSED "INTRADAY_BOARD_NOT_PASS"
  exit 2
fi

python3 - "$RECEIPT" "$BASE" "$BOARD" <<'PY'
import json,sys,hashlib
from datetime import datetime,timezone
p,base,board=sys.argv[1:]
def sha(q):
    h=hashlib.sha256()
    with open(q,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
x=json.load(open(board,encoding='utf-8'))
obj={
 "schema_version":1,
 "orchestrator":"RUN_HENGCE_COMPLETE",
 "state":"PASS",
 "formal_base":base,
 "intraday_board":board,
 "LiveSnapshotId":x.get('LiveSnapshotId'),
 "MarketContextState":x.get('MarketContextState'),
 "NewCapitalPolicy":x.get('NewCapitalPolicy'),
 "row_count":len(x.get('rows',[])),
 "sha256":{"formal_base":sha(base),"intraday_board":sha(board)},
 "finished_at_utc":datetime.now(timezone.utc).isoformat(),
}
open(p,'w',encoding='utf-8').write(json.dumps(obj,ensure_ascii=False,indent=2))
print(json.dumps(obj,ensure_ascii=False))
PY

echo "HENGCE_COMPLETE_PASS"
