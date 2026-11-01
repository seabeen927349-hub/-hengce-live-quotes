# Pass 3 model-class lock — before full forward-label evaluation

Date: 2026-11-01
Parent execution-lock commit: 16c0af5291ad686846bf3eaa3ef399201a6c3970
Status: PRE-RESULT MODEL CLASS LOCK

The current100 frozen candidate screen yields 778 candidate intervals across 38 snapshot dates before applying any outcome value.

For all four Pass 3 feature-family variants, use the same fixed classifier class and parameters:
- `HistGradientBoostingClassifier`
- `learning_rate=0.1`
- `max_iter=100`
- `max_leaf_nodes=31`
- `min_samples_leaf=20`
- `l2_regularization=0.0`
- `random_state=20261101`

No feature-family-specific hyperparameter search is allowed.

Missing numeric inputs are left as NaN for native HGB handling. Binary interaction flags are deterministic from the frozen execution lock / Pass 3 preregistration.

Probability calibration is chronological Platt scaling: for each evaluation date, eligible prior labeled candidates are split by time into an earlier model-fit block and a later calibration block; the calibration block must contain both classes. The HGB is fit only on the earlier block, its raw probabilities on the calibration block are logit-transformed, and a one-variable `LogisticRegression(C=1.0, penalty='l2', solver='lbfgs', max_iter=1000, random_state=20261101)` maps raw logits to calibrated probability. If either fit or calibration block lacks both classes, that evaluation date abstains.

The chronological calibration split is fixed at the latest 25% of eligible prior snapshot dates as calibration, with a minimum of two snapshot dates; the earlier 75% is model-fit. No split adjustment after outcomes are inspected.

Primary evaluation begins at 2026-06-26, as already frozen. Training eligibility requires the candidate's t+2 ownership label to have become observable strictly before the evaluation snapshot date.
