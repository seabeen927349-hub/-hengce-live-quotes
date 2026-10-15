#!/usr/bin/env bash
set -euo pipefail

ROOT="${HENGCE_ROOT:-$(pwd)}"
PY="${HENGCE_INTRADAY_BRIDGE:-$ROOT/work/hengce_intraday_action_board.py}"
OUT_DIR="${HENGCE_INTRADAY_OUT_DIR:-$ROOT/work_output/intraday_action_board}"
OUT="$OUT_DIR/HENGCE_INTRADAY_ACTION_BOARD.json"
RECEIPT="$OUT_DIR/HENGCE_INTRADAY_BINDING_RECEIPT.json"
LIVE_LOCAL="$OUT_DIR/live_active.json"
RAW_LIVE_URL="${HENGCE_LIVE_RAW_URL:-https://raw.githubusercontent.com/seabeen927349-hub/-hengce-live-quotes/main/live/active.json}"
mkdir -p "$OUT_DIR"

fail_closed() {
  local reason="$1"
  python3 - "$RECEIPT" "$reason" <<'PY'
import json,sys
from datetime import datetime, timezone
p,reason=sys.argv[1:]
obj={
  "schema_version":1,
  "ActionLayer":"INTRADAY_ACTION_BOARD",
  "binding_status":"FAIL_CLOSED",
  "reason":reason,
  "generated_at_utc":datetime.now(timezone.utc).isoformat(),
}
open(p,"w",encoding="utf-8").write(json.dumps(obj,ensure_ascii=False,indent=2))
PY
  echo "FAIL_CLOSED: $reason" >&2
  exit 2
}

[[ -f "$PY" ]] || fail_closed "BRIDGE_NOT_FOUND:$PY"

# 1) Formal base: explicit override first, then deterministic preferred paths,
# then newest formal v2/v3 artifact. Never use arbitrary chat-side data.
BASE="${HENGCE_FORMAL_BASE_JSON:-}"
if [[ -z "$BASE" ]]; then
  for p in \
    "$ROOT/work_output/formal/production/v2_scan.json" \
    "$ROOT/work_output/formal/production/v3_scan.json" \
    "$ROOT/work_output/formal/v2_scan.json" \
    "$ROOT/work_output/formal/v3_scan.json"; do
    if [[ -f "$p" ]]; then BASE="$p"; break; fi
  done
fi
if [[ -z "$BASE" ]]; then
  BASE="$(find "$ROOT/work_output" -type f \( -name 'v2_scan.json' -o -name 'v3_scan.json' \) -path '*formal*' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2- || true)"
fi
[[ -n "$BASE" && -f "$BASE" ]] || fail_closed "FORMAL_BASE_NOT_FOUND"

# Reject a base that explicitly says formal scan is disallowed.
python3 - "$BASE" <<'PY' || exit 21
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
if x.get('formal_scan_allowed') is False:
    raise SystemExit(1)
PY
[[ $? -eq 0 ]] || fail_closed "FORMAL_BASE_DISALLOWED"

# 2) Market Context: explicit override first. Otherwise newest JSON containing
# MarketContextState/NewCapitalPolicy. Missing context is never neutral.
CTX="${HENGCE_MARKET_CONTEXT_JSON:-}"
if [[ -z "$CTX" ]]; then
  while IFS= read -r p; do
    if python3 - "$p" <<'PY' >/dev/null 2>&1
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
assert isinstance(x,dict)
assert ('MarketContextState' in x or 'market_context_state' in x or 'NewCapitalPolicy' in x or 'new_capital_policy' in x)
PY
    then CTX="$p"; break; fi
  done < <(find "$ROOT/work_output" -type f -name '*.json' -printf '%T@ %p\n' 2>/dev/null | sort -nr | cut -d' ' -f2-)
fi
[[ -n "$CTX" && -f "$CTX" ]] || fail_closed "MARKET_CONTEXT_NOT_FOUND"

# 3) Fresh live snapshot: explicit local override or public GitHub transport.
if [[ -n "${HENGCE_LIVE_JSON:-}" ]]; then
  [[ -f "$HENGCE_LIVE_JSON" ]] || fail_closed "LIVE_OVERRIDE_NOT_FOUND:$HENGCE_LIVE_JSON"
  cp "$HENGCE_LIVE_JSON" "$LIVE_LOCAL"
else
  tmp="$LIVE_LOCAL.tmp.$$"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --connect-timeout 8 --max-time 20 "$RAW_LIVE_URL" -o "$tmp" || fail_closed "LIVE_TRANSPORT_FETCH_FAILED"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -T 20 -O "$tmp" "$RAW_LIVE_URL" || fail_closed "LIVE_TRANSPORT_FETCH_FAILED"
  else
    fail_closed "NO_HTTP_CLIENT_FOR_LIVE_TRANSPORT"
  fi
  mv "$tmp" "$LIVE_LOCAL"
fi

TRADE_DATE="$(python3 - "$LIVE_LOCAL" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
ds={str(r.get('quote_date')) for r in x.get('data',[]) if r.get('quote_date')}
print(next(iter(ds)) if len(ds)==1 else '')
PY
)"
[[ -n "$TRADE_DATE" ]] || fail_closed "LIVE_TRADE_DATE_UNRESOLVED"

set +e
python3 "$PY" \
  --base "$BASE" \
  --live "$LIVE_LOCAL" \
  --context "$CTX" \
  --output "$OUT" \
  --trade-date "$TRADE_DATE" \
  --max-age-seconds "${HENGCE_LIVE_MAX_AGE_SECONDS:-480}"
rc=$?
set -e
[[ $rc -eq 0 ]] || fail_closed "INTRADAY_BRIDGE_FAIL_CLOSED_RC_$rc"

python3 - "$OUT" "$RECEIPT" "$BASE" "$CTX" "$LIVE_LOCAL" <<'PY'
import json,sys,hashlib,os
from datetime import datetime, timezone
outp,receipt,base,ctx,live=sys.argv[1:]
x=json.load(open(outp,encoding='utf-8'))
if x.get('ActionLayer')!='INTRADAY_ACTION_BOARD' or x.get('binding_status')!='PASS':
    raise SystemExit(2)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
obj={
  "schema_version":1,
  "ActionLayer":"INTRADAY_ACTION_BOARD",
  "binding_status":"PASS",
  "base":base,
  "context":ctx,
  "live":live,
  "output":outp,
  "LiveSnapshotId":x.get('LiveSnapshotId'),
  "MarketContextState":x.get('MarketContextState'),
  "NewCapitalPolicy":x.get('NewCapitalPolicy'),
  "row_count":len(x.get('rows',[])),
  "sha256":{"base":sha(base),"context":sha(ctx),"live":sha(live),"output":sha(outp)},
  "generated_at_utc":datetime.now(timezone.utc).isoformat(),
}
open(receipt,'w',encoding='utf-8').write(json.dumps(obj,ensure_ascii=False,indent=2))
print(json.dumps(obj,ensure_ascii=False))
PY

echo "INTRADAY_ACTION_BOARD_PASS: $OUT"
