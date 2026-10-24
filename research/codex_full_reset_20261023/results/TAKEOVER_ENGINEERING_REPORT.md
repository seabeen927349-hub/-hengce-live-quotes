# Issue #29 takeover: pre-search integrity corrections

Frozen study corpus: `05bf0e35fb6a88473fd4f947952ef1b6875d3f88`.
Working branch: `research/codex-full-reset-run-20261023`.
No production file/model/schedule, main branch, capital, broker or promotion change.

## Data gating

- Original Stage B run 39915764325 failed all 724 dates. Raw MI_INDEX tables
  include alphanumeric preferred-share codes; pinned membership acquisition V2
  independently admits only four-digit numeric security codes.
- Restored that exact input scope predicate. This is independent of the expected
  ticker set; an unexpected ordinary-stock ticker still fails. Missing, duplicate,
  malformed, wrong-date and wrong-sector sources still fail.
- Replacement run 39934293291 had verified passes (2023: 101) but exhausted
  transport retries with HTTP 307 redirects on other dates. No partial mother was
  admitted. Failure evidence remains retained.
- Controlled retry 39936974870: one request worker per year, minimum 1.5-second
  spacing, bounded retries and circuit breaker. Raw official responses are retained
  with hashes; merged rows are revalidated against raw bytes and pinned membership.
- Stage C is bound to that exact run, requires completed/success, complete year
  receipts, correct hashes and all 724 date/ticker sets. No latest-run fallback.

## Reproduced and corrected research defects

1. Selection 2023 included outcomes closing in 2024: now purged entirely.
2. Missing future outcome on rank 1 caused rank 2 substitution: freeze exact TopN
   from signal-time evidence first. Censored baskets are reported and reserve their
   intended holding interval. No future-data-dependent replacement.
3. Missing mother receipt bypassed validation: receipt mandatory, exact sets and
   corpus bindings independently checked on ingest.
4. Ledger was written only at the end using overwrite mode: append STARTED before
   each evaluation and retain results, no-trades, failures, aborts and rejections.
   Hash-chain prefix and duplicate record checks protect the journal. Orphaned
   attempts become explicit ABORTED records when reopening. Unique attempt folders
   prevent failed retries from presenting an old winner as a current result.
5. Trade-end-only drawdown hid within-trade losses: daily-close mark-to-market
   drawdown is reported separately. Insolvent NAV cannot resurrect.

`METHOD_CORRECTIONS_V1.json` freezes these corrections and additional conservative
checks before any real-data Stage C output: stricter .10 discontinuity treatment
without reselecting parameters and quarter-block sign-flip inference with Holm
adjustment across all seven registered families. Sign-flip assumptions are not
proven; reported inference is exploratory historical evidence only. Fewer than six
active quarters is INSUFFICIENT_SAMPLE, not an invented precise p-value.

The unchanged original search plan registers 4,200 configurations per fold, 8,400
selection evaluations total. Validation, neighbor, baseline and quality-attack
simulations are additionally journaled. Pre-search registration is uploaded before
model evaluation. Failed data gates have zero model trials; synthetic tests are
explicitly separate from research trials.

## Historical evidence

Stage A rerun: no hard failures, eight retained historical data failures. Original
Round-2 payload and reconstructed shock payload integrity both remain failed.
Pinned corpus inventory resolves 628 tracked paths and all nine historical refs,
including closed/aborted E2 P2-A and Candidate C. Candidate B is an aggregate
reference, not a privileged champion; event identity remains unproven.

## Limitations

- All 2023–2026 history is exposed, never pristine OOS.
- Official archive retrieval does not prove original publication/first-seen or
  revision history. No adjusted-price or missing-field backfill is fabricated.
- Quarter-block inference assumes block symmetry/independence and cannot erase
  earlier research exposure or unknown historical variant counts.
- The local append journal is fsynced. A GitHub runner host loss can lose its final
  unuploaded journal tail; pre-uploaded registration retains reserved trial scope,
  but cannot manufacture missing metrics. Such runs cannot supply a winner.
- Until Stage B succeeds completely, search is BLOCKED. NO_ROBUST_WINNER due to
  unavailable data would be an evidence limitation, not proof that all strategies
  fail.
