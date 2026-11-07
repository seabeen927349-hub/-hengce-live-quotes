# G3 verified code bug fix 001 — S4A result serialization only

Date: 2026-11-07 Asia/Taipei. This is the **one permitted objective code correction** under the G3 study stage. No parameters, variables, sample, horizons, null permutations, significance rule or models changed.

- Original implementation SHA256 `659c84cdb187f298b4e328cafc79fc2fe14fe87d7fffbbbad959d4765cafc215`; original source preserved in Library as prior registered code.
- S4A read the same 2018–2022 G1 retail panel, ran 999 null permutations, then failed **while JSON serialization**: `TypeError: Object of type int64 is not JSON serializable`.
- No numeric results had been returned to the user or used to select a new parameter; the output receipt was not written.
- Correction is **one line only**: the result JSON writer now converts NumPy scalar types to native JSON types via `default=lambda x: x.item() if hasattr(x,'item') else str(x)`.
- Corrected implementation SHA256 `0940ff010139af46d716e76244f6e51ad19e5fcec8b87ed5fa7722a6dc6f0d52`.
- The correction changes **serialization only**, never modifies computed statistic, weights, time-split, investor groups, stock sample, random seed or permutations. S4A rerun uses exactly one pre-registered recipe, not an extra experiment.
- Final S4A data + log will be preserved with original/G1 SHA and this fix reference; if a second significant code defect is discovered, stop and request independent audit instead of endless repair.
