# Pass 3 / Pass 4 numeric promotion-criteria lock

Date: 2026-11-01
Status: PRE-RESULT NUMERIC CRITERIA LOCK

No outcome values from the 778-candidate Pass 3 set have been inspected before this lock.

## Pass 3 family promotion
For each added family, compare on the common held-out scored rows against its immediately preceding model.
A family receives nonzero formal incremental status only if ALL hold:
1. aggregate Brier score is lower;
2. aggregate log loss is lower;
3. expected calibration error (ECE, 10 equal-width probability bins) is not worse by more than 0.02 absolute;
4. in a chronological two-block split of held-out predictions, Brier improves in both blocks OR Brier improves in one block and log loss improves in both blocks;
5. improvement is not solely due to one snapshot date: after removing the single evaluation date contributing the largest favorable Brier delta, aggregate Brier must remain no worse than the predecessor.

If any condition fails, formal incremental weight/status = 0, while diagnostic information may still be reported.

## Pass 4 early-recognition qualification
For each fixed checkpoint h=1,2,3 trading days after t, compare the early model against the frozen Pass-3 BASE probability for the same candidate rows.
A checkpoint qualifies only if ALL hold:
1. aggregate Brier lower than BASE;
2. aggregate log loss lower than BASE;
3. ECE not worse than BASE by more than 0.02 absolute;
4. chronological two-block robustness satisfies the same rule as Pass 3 condition 4;
5. leave-largest-favorable-date-out Brier remains no worse than BASE;
6. at least 30 held-out candidate predictions and at least 5 events from each class are present.

The earliest h satisfying all criteria is the validated recognition point. Recognition-latency gain is measured in remaining trading sessions from that h checkpoint until the next TDCC snapshot's ownership date. If no h qualifies, validated recognition-latency gain is zero / not demonstrated.
