#!/usr/bin/env python3
"""Compatibility entrypoint for the HENGCE Market State FinMind shadow observer.

The active broad-market implementation is TWSE + TPEx only. Emerging-board
equities are intentionally excluded from the HENGCE Market State universe.
"""
from hengce_market_state_twse_tpex_aux import main


if __name__ == "__main__":
    main()
