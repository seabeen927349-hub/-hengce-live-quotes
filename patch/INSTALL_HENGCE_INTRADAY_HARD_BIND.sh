#!/usr/bin/env bash
set -euo pipefail

PATCH_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_ROOT="$(cd "$PATCH_DIR/.." && pwd)"
TARGET="${1:-${HENGCE_ROOT:-$(pwd)}}"
EXPECTED_MODEL_SHA="e4bf778d98ffa588901034a5322954631b8e43d173bb80847dde664068752e30"
STAMP="$(TZ=Asia/Taipei date '+%Y%m%dT%H%M%S%z')"
BACKUP="$TARGET/work_output/patch_backups/INTRADAY_HARD_BIND_$STAMP"
RECEIPT="$TARGET/work_output/HENGCE_INTRADAY_HARD_BIND_INSTALL_RECEIPT.json"
mkdir -p "$BACKUP" "$(dirname "$RECEIPT")" "$TARGET/work" "$TARGET/governance"

fail(){ echo "FAIL_CLOSED: $*" >&2; exit 2; }
[[ -d "$TARGET" ]] || fail "TARGET_NOT_FOUND:$TARGET"
[[ -f "$TARGET/RUN_IN_WORK.sh" ]] || fail "RUN_IN_WORK_NOT_FOUND:$TARGET/RUN_IN_WORK.sh"

BEFORE_MODELS="$(mktemp)"; AFTER_MODELS="$(mktemp)"
trap 'rm -f "$BEFORE_MODELS" "$AFTER_MODELS"' EXIT
python3 - "$TARGET" "$BEFORE_MODELS" <<'PY'
import os,sys,hashlib,json
root,out=sys.argv[1:];rows=[]
for dp,_,fs in os.walk(root):
    for f in fs:
        if f.endswith('.joblib'):
            p=os.path.join(dp,f);h=hashlib.sha256()
            with open(p,'rb') as z:
                for b in iter(lambda:z.read(1024*1024),b''):h.update(b)
            rows.append([os.path.relpath(p,root),h.hexdigest()])
json.dump(sorted(rows),open(out,'w'),indent=2)
PY

copy_one(){
  local src="$1" dst="$2"
  [[ -f "$src" ]] || fail "PATCH_PAYLOAD_MISSING:$src"
  if [[ -f "$dst" ]]; then
    mkdir -p "$BACKUP/$(dirname "${dst#$TARGET/}")"
    cp -p "$dst" "$BACKUP/${dst#$TARGET/}"
  fi
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
}

copy_one "$BUNDLE_ROOT/scripts/hengce_intraday_action_board.py" "$TARGET/work/hengce_intraday_action_board.py"
for module in hengce_unified_contracts hengce_unified_candidate_adapter hengce_unified_q017_admission hengce_q017_structure_exit hengce_unified_action_board hengce_unified_runner hengce_unified_scan_display hengce_scan_once_router hengce_twse_calendar; do
  copy_one "$BUNDLE_ROOT/scripts/$module.py" "$TARGET/work/$module.py"
done
copy_one "$BUNDLE_ROOT/hengce/q017_radar/data/twse_electronics_history_2026.csv" "$TARGET/hengce/q017_radar/data/twse_electronics_history_2026.csv"
copy_one "$BUNDLE_ROOT/scripts/RUN_INTRADAY_ACTION_BOARD.sh" "$TARGET/RUN_INTRADAY_ACTION_BOARD.sh"
copy_one "$BUNDLE_ROOT/scripts/RUN_HENGCE_COMPLETE.sh" "$TARGET/RUN_HENGCE_COMPLETE.sh"
copy_one "$BUNDLE_ROOT/scripts/RUN_IN_WORK_DETACHED.sh" "$TARGET/RUN_IN_WORK_DETACHED.sh"
copy_one "$BUNDLE_ROOT/scripts/CHECK_HENGCE_RUN.sh" "$TARGET/CHECK_HENGCE_RUN.sh"
copy_one "$BUNDLE_ROOT/scripts/RUN_HENGCE.sh" "$TARGET/RUN_HENGCE.sh"
copy_one "$BUNDLE_ROOT/hengce/HENGCE_INTRADAY_ACTION_BOARD_CONTRACT_v1_0_20261015.json" "$TARGET/governance/HENGCE_INTRADAY_ACTION_BOARD_CONTRACT_v1_0_20261015.json"
copy_one "$BUNDLE_ROOT/hengce/calendar/TWSE_TRADING_CALENDAR_2026_v1.json" "$TARGET/governance/TWSE_TRADING_CALENDAR_2026_v1.json"
copy_one "$BUNDLE_ROOT/hengce/calendar/TWSE_EXTRAORDINARY_CLOSURES_2026_v1.json" "$TARGET/governance/TWSE_EXTRAORDINARY_CLOSURES_2026_v1.json"
chmod +x "$TARGET/RUN_INTRADAY_ACTION_BOARD.sh" "$TARGET/RUN_HENGCE_COMPLETE.sh" "$TARGET/RUN_IN_WORK_DETACHED.sh" "$TARGET/CHECK_HENGCE_RUN.sh" "$TARGET/RUN_HENGCE.sh"

bash -n "$TARGET/RUN_INTRADAY_ACTION_BOARD.sh"
bash -n "$TARGET/RUN_HENGCE_COMPLETE.sh"
bash -n "$TARGET/RUN_IN_WORK_DETACHED.sh"
bash -n "$TARGET/CHECK_HENGCE_RUN.sh"
bash -n "$TARGET/RUN_HENGCE.sh"
python3 "$TARGET/work/hengce_intraday_action_board.py" --self-test >/dev/null
HENGCE_ROOT="$TARGET" PYTHONPATH="$TARGET/work" python3 - <<'PY'
import hengce_twse_calendar as c
m,p,_=c.load_manifest()
assert p.name==c.MANIFEST_NAME
assert not c.is_trading_day('2026-10-23',m)
assert c.next_trading_day('2026-10-22',m)=='2026-10-27'
c.validate_next_session('2026-10-22','2026-10-27',m)
print('TWSE_EFFECTIVE_CALENDAR_INSTALL_PASS')
PY

python3 - "$TARGET" "$AFTER_MODELS" <<'PY'
import os,sys,hashlib,json
root,out=sys.argv[1:];rows=[]
for dp,_,fs in os.walk(root):
    for f in fs:
        if f.endswith('.joblib'):
            p=os.path.join(dp,f);h=hashlib.sha256()
            with open(p,'rb') as z:
                for b in iter(lambda:z.read(1024*1024),b''):h.update(b)
            rows.append([os.path.relpath(p,root),h.hexdigest()])
json.dump(sorted(rows),open(out,'w'),indent=2)
PY
cmp -s "$BEFORE_MODELS" "$AFTER_MODELS" || fail "MODEL_HASH_SET_CHANGED"

MODEL_EXPECTED_PRESENT="$(python3 - "$AFTER_MODELS" "$EXPECTED_MODEL_SHA" <<'PY'
import json,sys
rows=json.load(open(sys.argv[1])); exp=sys.argv[2]
print('true' if any(h==exp for _,h in rows) else 'false')
PY
)"

python3 - "$TARGET" "$BACKUP" "$RECEIPT" "$AFTER_MODELS" "$MODEL_EXPECTED_PRESENT" <<'PY'
import sys,os,json,hashlib
from datetime import datetime,timezone
root,backup,receipt,models,expected_present=sys.argv[1:]
rels=[
 'work/hengce_unified_contracts.py','work/hengce_unified_candidate_adapter.py','work/hengce_unified_q017_admission.py',
 'work/hengce_q017_structure_exit.py','work/hengce_unified_action_board.py','work/hengce_unified_runner.py','work/hengce_unified_scan_display.py','work/hengce_scan_once_router.py',
 'work/hengce_twse_calendar.py','work/hengce_intraday_action_board.py','hengce/q017_radar/data/twse_electronics_history_2026.csv',
 'RUN_INTRADAY_ACTION_BOARD.sh','RUN_HENGCE_COMPLETE.sh','RUN_IN_WORK_DETACHED.sh','CHECK_HENGCE_RUN.sh','RUN_HENGCE.sh',
 'governance/HENGCE_INTRADAY_ACTION_BOARD_CONTRACT_v1_0_20261015.json',
 'governance/TWSE_TRADING_CALENDAR_2026_v1.json','governance/TWSE_EXTRAORDINARY_CLOSURES_2026_v1.json']
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
obj={'schema_version':1,'patch':'HENGCE_INTRADAY_HARD_BIND','status':'PASS','target':root,'backup_dir':backup,
 'installed_at_utc':datetime.now(timezone.utc).isoformat(),'installed_files':{r:sha(os.path.join(root,r)) for r in rels},
 'all_joblib_hashes_after':json.load(open(models)),'expected_frozen_model_hash_present':expected_present=='true',
 'expected_frozen_model_sha256':'e4bf778d98ffa588901034a5322954631b8e43d173bb80847dde664068752e30',
 'production_model_mutated_by_patch':False,'entrypoint':'RUN_HENGCE.sh'}
open(receipt,'w',encoding='utf-8').write(json.dumps(obj,ensure_ascii=False,indent=2));print(json.dumps(obj,ensure_ascii=False))
PY

echo "INSTALL_PASS: $RECEIPT"
echo "NEW_ENTRYPOINT: $TARGET/RUN_HENGCE.sh"
