#!/usr/bin/env bash
set -euo pipefail
ROOT="${HENGCE_ROOT:-$(pwd)}"
export HENGCE_ROOT="$ROOT"
RUNNER="$ROOT/work/hengce_unified_runner.py"
if [[ ! -f "$RUNNER" ]]; then
  RUNNER="$ROOT/scripts/hengce_unified_runner.py"
fi
if [[ ! -f "$RUNNER" ]]; then
  # Missing deployment must revoke old output, even before Python imports work.
  python3 - "$ROOT" <<'PY'
import json,os,sys,tempfile
from pathlib import Path
out=Path(os.environ.get('HENGCE_INTRADAY_OUT_DIR',Path(sys.argv[1])/'work_output/intraday_action_board'))
out.mkdir(parents=True,exist_ok=True)
for name in ('HENGCE_INTRADAY_BINDING_RECEIPT.json','HENGCE_INTRADAY_ACTION_BOARD.json','HENGCE_UNIFIED_CANDIDATE_BASE.json'):
    fd,tmp=tempfile.mkstemp(dir=out)
    with os.fdopen(fd,'w') as f:
        json.dump({'system':'HENGCE','binding_status':'FAIL_CLOSED','reason':'UNIFIED_RUNTIME_NOT_INSTALLED','rows':[]},f)
    os.replace(tmp,out/name)
PY
  echo "FAIL_CLOSED: UNIFIED_RUNTIME_NOT_INSTALLED" >&2
  exit 2
fi
exec python3 "$RUNNER"
