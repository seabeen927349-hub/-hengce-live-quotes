#!/usr/bin/env python3
import importlib.util
from pathlib import Path

P = Path(__file__).with_name("run_candidate_c_finite.py")
spec = importlib.util.spec_from_file_location("candidate_c", P)
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

base = {"trades": 10, "win_rate": 0.60, "nav": 1.50, "max_drawdown": -0.20}
assert cc.strictly_better({"trades":10,"win_rate":0.70,"nav":1.60,"max_drawdown":-0.15}, base)
assert not cc.strictly_better({"trades":10,"win_rate":0.60,"nav":1.70,"max_drawdown":-0.10}, base)
assert not cc.strictly_better({"trades":10,"win_rate":0.70,"nav":1.40,"max_drawdown":-0.10}, base)
assert not cc.strictly_better({"trades":9,"win_rate":0.70,"nav":1.70,"max_drawdown":-0.10}, base)
assert not cc.strictly_better({"trades":10,"win_rate":0.70,"nav":1.70,"max_drawdown":-0.30}, base)
assert cc.max_drawdown([1.10, 0.99, 1.20]) < 0
print("CANDIDATE_C_UNIT_PASS")
