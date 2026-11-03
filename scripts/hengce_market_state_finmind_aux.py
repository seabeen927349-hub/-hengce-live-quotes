#!/usr/bin/env python3
"""Compatibility entrypoint for HENGCE FinMind Market State observation.

Legacy helper symbols remain importable, but CLI execution is routed to the
current TWSE + TPEx only observer. Emerging-board equities are excluded from
the active Market State universe by policy.
"""
from hengce_market_state_finmind_aux_legacy_20261103 import *  # noqa: F401,F403
from hengce_market_state_twse_tpex_aux import main as _twse_tpex_main


def main() -> None:
    _twse_tpex_main()


if __name__ == "__main__":
    main()
