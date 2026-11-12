#!/usr/bin/env python3
"""Research-only gate for triggering the EXISTING HENGCE FinMind monitor.

Schedules are best-effort GitHub events. A completed independent workflow may
wake the existing FinMind job, but must never bypass session/PIT/authority checks.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TW=ZoneInfo("Asia/Taipei")
UPSTREAM="HENGCE Frozen Single-Name Live Quotes"
# Other EXISTING, independently scheduled HENGCE workflows may wake the SAME
# guarded FinMind monitor; no new market collector or source is introduced.
UPSTREAMS={UPSTREAM,"HENGCE Governed SOX VIX Premarket EOD",
           "HENGCE HBA Daily Surveillance Research Sidecar"}


def assess(event, now, repo, payload=None, current_ref=None):
    now=now.astimezone(TW)
    if event=="pull_request":
        # Original workflow only runs no-network regression steps for PR.
        return True,"PR_OFFLINE_ONLY"
    if event in ("push","workflow_dispatch"):
        if current_ref!="refs/heads/main" and event!="push":
            return False,"NON_MAIN_MANUAL_REF"
        if event=="push" and current_ref!="refs/heads/main":
            return False,"NON_MAIN_PUSH"
        return True,"DIRECT_TRUSTED_BRANCH"
    if event not in ("schedule","workflow_run"):
        return False,"UNSUPPORTED_EVENT"
    m=now.hour*60+now.minute
    if not (now.weekday()<5 and 9*60<=m<=13*60+40):
        return False,"OUTSIDE_TWSE_SESSION"
    if event=="schedule":
        return True,"SCHEDULE_TRADING_SESSION"
    if not isinstance(payload,dict):
        return False,"MISSING_UPSTREAM_PAYLOAD"
    source=payload.get("workflow_run") or {}
    if not isinstance(source,dict):
        return False,"INVALID_UPSTREAM_RUN"
    if source.get("name") not in UPSTREAMS or source.get("conclusion")!="success":
        return False,"UPSTREAM_WORKFLOW_OR_CONCLUSION_INVALID"
    if source.get("head_branch")!="main" or (source.get("head_repository") or {}).get("full_name")!=repo:
        return False,"UPSTREAM_REPOSITORY_OR_BRANCH_INVALID"
    if source.get("event") not in ("schedule","workflow_dispatch"):
        return False,"UPSTREAM_NOT_SCHEDULED_OR_MANUAL"
    # Delayed delivery must not revive an old run as a current-session heartbeat.
    finished=source.get("updated_at")
    try:
        stamp=datetime.fromisoformat(finished.replace("Z","+00:00")).astimezone(TW)
    except (TypeError,ValueError,AttributeError):
        return False,"UPSTREAM_COMPLETION_TIME_MISSING"
    age=(now-stamp).total_seconds()
    if age < -120 or age>30*60:
        return False,"UPSTREAM_EVENT_STALE"
    return True,"INDEPENDENT_SCHEDULE_HEARTBEAT"


def main():
    now=datetime.now(TW)
    event=os.environ.get("GITHUB_EVENT_NAME","")
    repo=os.environ.get("GITHUB_REPOSITORY","")
    ref=os.environ.get("GITHUB_REF","")
    payload=None
    if event=="workflow_run":
        try:
            payload=json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        except (OSError,KeyError,ValueError):
            payload=None
    allowed,reason=assess(event,now,repo,payload,ref)
    with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as f:
        f.write("allowed="+str(allowed).lower()+"\n")
        f.write("reason="+reason+"\n")
    print(json.dumps({"event":event,"taipei_now":now.isoformat(),"allowed":allowed,"reason":reason,
                      "role":"SAME_GOVERNED_FINMIND_VESSEL_ONLY"},ensure_ascii=False))
if __name__=="__main__":
    main()
