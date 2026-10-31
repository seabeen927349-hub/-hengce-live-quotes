# HENGCE Selection Core — IF-08 New Chat Handoff — 2026-10-31

## Controlling state

- Closed challenger: `IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`
- Formal state: `EXECUTION_SPEC_BLOCKED`
- Blocking stage: `STAGE_B_METADATA_TRANSPORT_MECHANICS`
- Forward returns: `SEALED_NOT_OPENED`
- Validation: `NOT_OPENED`
- Production / trading authority: `NONE`
- This is not `MODEL_FAIL` and not `DATA_BLOCKED`.

## Why IF-07 V0.1 is closed

Formal no-retry Stage B run `41187903523` used the frozen 187-event authority.

Observed:
- 92 events resolved/pass;
- 68 candidate events hit the already-frozen official rate-limit fail-closed rule;
- 16 candidate events hit a 45-second timeout whose duration was not preregistered;
- 11 candidate events hit DNS failure whose permanent-exclusion treatment was not preregistered.

Therefore the legal Stage B sample is not uniquely defined without adding a post-preregistration transport rule.

Run `41185962038` produced a 186-event path but is `INVALID_FOR_FORMAL_RESEARCH_EXECUTION_BUG` because it introduced unfrozen retry/backoff behavior. Its 186-event sample is inadmissible.

N3 random and bootstrap CI mechanics are also under-specified, but they are secondary blockers.

## Hard prohibitions

- Do not open IF-07 V0.1 Discovery or Validation returns.
- Do not use the 92-event or 186-event samples for performance conclusions.
- Do not add timeout/DNS/retry/backoff/N3/bootstrap rules in place to V0.1.
- Do not rescue, retune, reinterpret, or silently version-shift V0.1.
- Do not return to V6/V43 as Selection Core.
- Capital-share migration remains `NOVELTY_GATE_FAIL`.
- Escape remains a risk overlay with zero Selection alpha authority.

## New mainline

Move to `IF-08 EXPECTATION REVISION`.

Do not define a challenger and do not inspect IF-08 forward returns yet.

First perform only:

`DATA_CAPABILITY_AUDIT -> PIT_SAFETY_AUDIT -> NOVELTY_GATE`

Target information must be genuine ex-ante expectation/revision data, e.g. timestamped analyst EPS/revenue consensus revision, forecast/target revision, management guidance revision, or earnings surprise relative to a timestamped prior consensus.

Forbidden substitutes: price, momentum, volume/turnover, institutional flow, margin financing, broker activity, TDCC, or price reaction without an independent expectation measure.

If genuine PIT-safe expectation data are unavailable: `DATA_BLOCKED` or `ONLY_PROXY_AVAILABLE_REJECT`. Do not manufacture a proxy.

If capability and novelty both pass, define exactly one simple challenger and freeze transport failure handling, N3 mechanics, and bootstrap mechanics before preregistration and before any forward return.

## Research stop-loss

Any information family that becomes dominated by bespoke data engineering before a falsifiable return test must be stopped early. Engineering complexity is not evidence of alpha.

## Git authority

Repo: `seabeen927349-hub/-hengce-live-quotes`
Branch: `research/selection-core-rebuild-20261031`
Authority correction commit: `196603fd0cc3f6315dd05e8eee7c275d8501689f`
Previous verified branch head before this package: `2d2cea8914b9403166c04a4361e1d00fab65a3c7`
