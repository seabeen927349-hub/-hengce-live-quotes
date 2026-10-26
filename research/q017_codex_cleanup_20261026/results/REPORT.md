# Q017 cleanup engineering report

Final state: **PASS_ENGINEERING_OPTIMIZATION_NO_SEMANTIC_CHANGE**.

The formal output boundary now requires original current-session schema-5 Q017 evidence. The router checks the complete hash-bound, fresh publication rather than a few flags. Public display cannot promote legacy candidates or the distinct daily canonical model. Monitor score/gate/universe tampering is rejected. Retired E2 remains explicitly research-only. Stale latest pointers cannot override current dated authority.

The original schema-5 observation/compute/ranking file is byte-for-byte unchanged. Exact replay covers preserved 2026-10-21 (GO, three qualified buys, 155 ranked candidates) and 2026-10-22 (CASH, zero buys, 221 ranked candidates). Full rankings, serialized numeric values, original timestamps, observation/universe bindings, decision hashes and original rejection outcomes match. No field normalization or score tolerance is used. Replays are separate test artifacts; original formal evidence is never overwritten.

Guard hash work fell from eight to six canonical hash calls per validation. Original observation reads/parses remain one per guard invocation; network calls in the offline replay remain zero. Timing samples and unchanged capture-lane limitations are recorded in `PERFORMANCE_BEFORE_AFTER.json`; no guaranteed wall-clock speedup is claimed.

The old daily top1/H20/no-DXY bridge has a different contract and lacks schema-5 observation/decision bindings. Its formal action publication remains fail closed. This cleanup does not synthesize bindings, convert its ranking into schema-5 output or grant new trading authority. Schema-5 validated diagnostic/display output is preserved.

## Reproduce offline

Install the existing import dependencies once, then disable external access if desired:

```sh
python -m venv /tmp/q017-audit-venv
/tmp/q017-audit-venv/bin/pip install requests==2.32.5 openpyxl==3.1.5 PyYAML==6.0.3
/tmp/q017-audit-venv/bin/python -B tests/engineering/q017_cleanup_audit.py
```

The audit actively rejects socket, requests and urllib network access. It exports the fixed starting commit to a disposable directory and replays the working tree separately. It fails on any exact semantic difference and runs the frozen-source, resilience, original gate and authority attack regressions. It writes only separate result reports. Full history is required (`fetch-depth: 0` in CI).

For a committed comparison (also used by the existing engineering CI):

```sh
python -B tests/engineering/q017_cleanup_audit.py --before BASE_COMMIT --after HEAD --report /tmp/q017-audit.json
```

`--before` is compared against the fixed cleanup baseline as well as `--after`; neither revision can weaken the model baseline. The original observations/decisions are pinned independently of the revision under test. No retired engine is needed for this model audit.

Additional inventory and broad checks:

```sh
python -B tests/engineering/q017_cleanup_inventory.py
python -B -m unittest discover -s tests/engineering -p 'test_*.py' -v
```

`EQUIVALENCE_TEST_REPORT.json`, `SCRIPT_REGRESSIONS.json`, `ENGINEERING_REGRESSIONS.txt` and `FINAL_AUDIT.json` record the completed validation. All ten requested deliverables are in this directory. Static inventory includes all code/workflows and preserves uncertain dead-code candidates. The changes are confined to the requested branch; no production merge or deployment is authorized by this report.
