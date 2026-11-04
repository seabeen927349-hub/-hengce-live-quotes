#!/usr/bin/env python3
"""Bounded-memory research challenger. Never grants formal or trading authority."""
from collections import deque
from copy import deepcopy
from datetime import date
import math
import HENGCE_ESCAPE_FEATURE_DETECTOR_V1 as detector
import HENGCE_ESCAPE_STATE_ENGINE_V2 as frozen

VERSION = 'HENGCE_ESCAPE_STATE_ENGINE_V3_RESEARCH'
WINDOW = 5  # frozen engineering horizon; never selected using outcomes

class ResearchStateEngine:
    def __init__(self):
        self._recent = deque(maxlen=WINDOW)
        self._level = None
        self._last_date = None
        self._last_index = None

    def evaluate(self, packet):
        """Input only as-of histories; session_index refers to the full exchange calendar.

        Gate assumptions are isolated to exact frozen-code counterfactual execution.
        Actual PIT/universe flags are preserved, never declared passed by this wrapper.
        """
        out = dict(status='UNVERIFIED', engine_version=VERSION,
                   raw_risk_level=None, persistent_state_level=None,
                   formal_escape_state='UNVERIFIED', trading_authority='NONE',
                   source_gates=deepcopy(packet.get('data_gate', {})))
        def fail(reason):
            self._recent.clear()
            return dict(out, reason=reason)
        try:
            day = date.fromisoformat(packet['trade_date'])
            idx = packet['session_index']
            if type(idx) is not int or idx < 0:
                return fail('INVALID_SESSION_INDEX')
            if self._last_date is not None and (day <= self._last_date or idx <= self._last_index):
                return fail('NON_MONOTONIC_OBSERVATION')
            if self._last_index is not None and idx != self._last_index + 1:
                self._recent.clear()
            self._last_date, self._last_index = day, idx
        except (KeyError, ValueError, TypeError):
            return fail('INVALID_DATE_OR_INDEX')
        if packet.get('research_only') is not True or packet.get('source_integrity_verified') is not True:
            return fail('RESEARCH_SCOPE_OR_INTEGRITY_REQUIRED')
        if packet.get('phase') != 'EOD_FORMAL':
            return fail('RESEARCH_EOD_REQUIRED')
        hist = packet.get('metrics_history', {})
        if any(not isinstance(hist.get(m), list) for m in detector.METRICS):
            return fail('MISSING_METRICS')
        if len({len(hist[m]) for m in detector.METRICS}) != 1:
            return fail('MISALIGNED_HISTORY')
        if any(not hist[m] or detector.latest_score(hist[m], detector.METRICS[m][0]) is None for m in detector.METRICS):
            return fail('ALL17_PAST_BASELINES_REQUIRED')
        synthetic = deepcopy(packet)
        synthetic.pop('prior_level', None)
        synthetic['data_gate'] = {k: True for k in ('freshness_pass','integrity_pass','pit_pass','universe_pass')}
        det = detector.detect(synthetic)
        synthetic['detector_output'] = det
        raw = frozen.evaluate(synthetic)
        if raw.get('escape_level') is None:
            return fail('FROZEN_COUNTERFACTUAL_REJECTED')
        level = int(raw['escape_level'])
        previous = self._level
        self._recent.append(level)
        if previous is None:
            self._level = level
        elif level > previous:
            self._level = level
        elif len(self._recent) == WINDOW:
            self._level = max(self._recent)
        # With incomplete confirmation window, retain internal state.
        transition = 'INITIALIZE' if previous is None else 'ESCALATE' if self._level > previous else 'DEESCALATE' if self._level < previous else 'HOLD'
        return dict(out, status='RESEARCH_ONLY_COUNTERFACTUAL', raw_risk_level=level,
                    persistent_state_level=self._level, transition=transition,
                    recovery_to_zero=(previous is not None and previous > 0 and self._level == 0),
                    confirmation_observations=len(self._recent), window=WINDOW,
                    counterfactual_gate_assumptions=True, detector_output=det)
