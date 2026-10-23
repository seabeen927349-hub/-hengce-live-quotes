#!/usr/bin/env bash
set -euo pipefail
ROOT="${HENGCE_ROOT:-$(pwd)}"
export HENGCE_ROOT="$ROOT"
export PYTHONPATH="$ROOT/work:$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
FORMAL_RUNNER="${HENGCE_FORMAL_RUNNER:-$ROOT/RUN_IN_WORK.sh}"
INTRADAY_RUNNER="${HENGCE_INTRADAY_RUNNER:-$ROOT/RUN_INTRADAY_ACTION_BOARD.sh}"
# Runtime overrides may not route around the sole publication coordinator.
if [[ "$INTRADAY_RUNNER" != "$ROOT/RUN_INTRADAY_ACTION_BOARD.sh" ]]; then
  echo 'FAIL_CLOSED: NONCANONICAL_INTRADAY_RUNNER_OVERRIDE' >&2
  exit 2
fi
STATE_DIR="${HENGCE_COMPLETE_STATE_DIR:-$ROOT/work_output/complete_run_state}"
RECEIPT="$STATE_DIR/HENGCE_COMPLETE_RUN_RECEIPT.json"
mkdir -p "$STATE_DIR"
write_state() {
  python3 - "$RECEIPT" "$1" "${2:-}" <<'PY'
import sys
from datetime import datetime,timezone
from hengce_unified_contracts import atomic, ZERO_AUTHORITY
p,state,reason=sys.argv[1:]
atomic(p,{'schema_version':2,'orchestrator':'RUN_HENGCE_COMPLETE','state':state,
          'reason':reason,'updated_at_utc':datetime.now(timezone.utc).isoformat(),**ZERO_AUTHORITY})
PY
}
[[ -f "$FORMAL_RUNNER" ]] || { write_state FAIL_CLOSED FORMAL_RUNNER_NOT_FOUND; exit 2; }
[[ -f "$INTRADAY_RUNNER" ]] || { write_state FAIL_CLOSED INTRADAY_RUNNER_NOT_FOUND; exit 2; }
write_state FORMAL_RUNNING
if ! bash "$FORMAL_RUNNER"; then
  write_state FAIL_CLOSED FORMAL_RUNNER_FAILED
  exit 2
fi
# Artifact admission and selection have ONE implementation, in the runner.
write_state INTRADAY_BINDING
if ! bash "$INTRADAY_RUNNER"; then
  write_state FAIL_CLOSED INTRADAY_RUNNER_FAILED
  exit 2
fi
if ! python3 - "$RECEIPT" <<'PY'
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from hengce_unified_contracts import atomic, ZERO_AUTHORITY
from hengce_unified_runner import locations,NAMES
from hengce_unified_scan_display import build,load
_,out=locations()
x={key:load(out/name) for key,name in NAMES.items()}
now=datetime.now(ZoneInfo('Asia/Taipei'))
result=build(now,x['action'],x['base'],x['receipt'])
if result['binding_status']!='PASS': raise SystemExit(2)
r=x['receipt']
atomic(sys.argv[1],{'schema_version':2,'orchestrator':'RUN_HENGCE_COMPLETE','state':'PASS',
    'transaction_id':r['transaction_id'],'formal_base':r['source_paths']['legacy_base'],
    'source_sha256':r['source_sha256'],'base_hash':r['base_hash'],'action_hash':r['action_hash'],
    'finished_at_utc':now.isoformat(),**ZERO_AUTHORITY})
PY
then
  write_state FAIL_CLOSED INTRADAY_TRANSACTION_NOT_PASS
  exit 2
fi
echo HENGCE_COMPLETE_PASS
