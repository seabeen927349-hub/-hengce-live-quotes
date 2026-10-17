from scripts.hengce_hscore import HScoreInput, compute_hscore, grade, position_comparison


def test_grade_bands():
    assert grade(90) == 'S'
    assert grade(80) == 'A'
    assert grade(70) == 'B'
    assert grade(60) == 'C'
    assert grade(59.9) == 'WEAK'


def test_hscore_weights_sum_to_100():
    r = compute_hscore(HScoreInput(1, 1, 1))
    assert r.hscore == 100.0
    assert r.market_points == 25.0
    assert r.selection_points == 55.0
    assert r.leader_points == 20.0


def test_teacher_is_display_only():
    a = compute_hscore(HScoreInput(.5, .5, .5, -100, 50, -20))
    b = compute_hscore(HScoreInput(.5, .5, .5, 100, -50, 20))
    assert a.hscore == b.hscore
    assert a.teacher_shadow_points == 20.0
    assert a.authority == 'DISPLAY_ONLY'


def test_no_switch_authority():
    x = position_comparison(70, 95)
    assert x['score_gap_vs_position'] == 25.0
    assert x['action'] == 'OBSERVE_ONLY'
    assert x['reason'] == 'HSCORE_HAS_NO_SWITCH_AUTHORITY'


def test_probability_language_guard():
    r = compute_hscore(HScoreInput(.8, .9, .7))
    assert 'not probability' in r.label
