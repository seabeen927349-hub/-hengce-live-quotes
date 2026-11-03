#!/usr/bin/env python3
"""Compatibility entrypoint for HENGCE FinMind Market State observation.

Legacy helper symbols remain importable. Active CLI execution monitors current
TWSE-listed ordinary equities only, using the official TWSE current master for
membership and FinMind only for realtime snapshot observations. TPEx and
emerging-board equities are excluded by policy.
"""
from hengce_market_state_finmind_aux_legacy_20261103 import *  # noqa: F401,F403
from hengce_market_state_twse_only_aux import main as _twse_only_main


def main() -> None:
    _twse_only_main()


if __name__ == "__main__":
    main()
