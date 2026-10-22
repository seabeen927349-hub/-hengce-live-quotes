#!/usr/bin/env python3
"""Only this collector uses the live API; evaluator/tests consume local manifests."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from hengce_system_health import ZERO, POLICY, validate_policy


def collect(policy, repository, now, fetch_page):
    validate_policy(policy)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('INVALID_REPOSITORY')
    start=now.astimezone(timezone.utc)-timedelta(hours=48)
    output=dict(schema_version=1,collected_at_utc=now.isoformat(),coverage_start_utc=start.isoformat(),
        coverage_end_utc=now.isoformat(),complete=True,errors=[],runs=[],**ZERO)
    for w in policy['workflows']:
        if not w['crons_utc']:
            continue
        try:
            for page in range(1,11):
                query=urlencode(dict(event='schedule',branch='main',created='>='+start.isoformat(),per_page=100,page=page))
                url=f'https://api.github.com/repos/{repository}/actions/workflows/{quote(w["file"],safe="")}/runs?{query}'
                payload=fetch_page(url)
                if not isinstance(payload,dict) or not isinstance(payload.get('workflow_runs'),list):
                    raise ValueError('INVALID_API_RESPONSE')
                rows=payload['workflow_runs']
                for r in rows:
                    output['runs'].append(dict(id=r['id'],workflow_file=w['file'],event=r['event'],
                        head_branch=r['head_branch'],created_at=r['created_at'],
                        run_started_at=r.get('run_started_at'),status=r['status'],conclusion=r.get('conclusion')))
                if len(rows)<100:
                    break
            else:
                raise ValueError('PAGINATION_TRUNCATED')
        except Exception as exc:
            # No tokens, URLs with credentials or raw API error bodies are logged.
            output['complete']=False
            output['errors'].append(dict(workflow_file=w['file'],reason=type(exc).__name__))
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy',type=Path,default=POLICY)
    parser.add_argument('--repository',default=os.environ.get('GITHUB_REPOSITORY'))
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    token=os.environ.get('GH_TOKEN')
    def fetch(url):
        if not token:
            raise RuntimeError('ACTIONS_READ_TOKEN_UNAVAILABLE')
        req=Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
            'X-GitHub-Api-Version':'2022-11-28','User-Agent':'HENGCE-health-metadata-only'})
        with urlopen(req,timeout=20) as response:
            return json.load(response)
    result=collect(json.loads(args.policy.read_text()),args.repository,datetime.now(timezone.utc),fetch)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(complete=result['complete'],run_count=len(result['runs']),errors=result['errors'])))


if __name__=='__main__':
    main()
