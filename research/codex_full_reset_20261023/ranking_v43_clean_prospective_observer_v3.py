#!/usr/bin/env python3
from __future__ import annotations

# V3 launcher removes any runtime dependency on a repository binary archive.
# The 30 frozen signal dates are identifiers only. Trust still comes from the
# underlying observer independently rebuilding all 30 full event payloads and
# matching their exact frozen SHA-256 before any prospective evidence is used.

import research.codex_full_reset_20261023.ranking_v43_clean_prospective_observer as observer

FROZEN_SIGNAL_DATES = (
    '2024-01-02','2024-02-01','2024-03-14','2024-04-17','2024-05-20',
    '2024-06-20','2024-07-22','2024-08-23','2024-09-25','2024-10-30',
    '2024-12-02','2025-01-02','2025-02-12','2025-03-17','2025-04-18',
    '2025-05-21','2025-06-23','2025-07-23','2025-08-22','2025-09-23',
    '2025-10-29','2025-11-28','2026-01-02','2026-02-03','2026-03-17',
    '2026-04-20','2026-05-21','2026-06-23','2026-07-24','2026-08-25',
)

if len(FROZEN_SIGNAL_DATES) != observer.EXPECTED_PRELOCK_EVENT_COUNT:
    raise SystemExit('FROZEN_SIGNAL_DATE_COUNT_DRIFT')


def _frozen_identifiers_only(_archive_path):
    return [{'signal_date': d} for d in FROZEN_SIGNAL_DATES]

observer.extract_frozen_events = _frozen_identifiers_only

if __name__ == '__main__':
    observer.main()
