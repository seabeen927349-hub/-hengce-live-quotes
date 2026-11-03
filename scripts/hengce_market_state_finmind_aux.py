#!/usr/bin/env python3
"""Compatibility entrypoint for HENGCE FinMind Market State observation.

Legacy helper symbols remain importable. CLI execution uses official current
TWSE and TPEx masters for universe membership, with FinMind used only for the
realtime snapshot. Emerging-board equities are excluded by policy.
"""
from hengce_market_state_finmind_aux_legacy_20261103 import *  # noqa: F401,F403
from hengce_market_state_twse_tpex_official_aux import main as _official_twse_tpex_main


def main() -> None:
    _official_twse_tpex_main()


if __name__ == "__main__":
    main()
