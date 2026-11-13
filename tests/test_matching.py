import numpy as np
import pytest

from beaverdam.data import CAT_INDEX, load_checkins, load_slot_data
from beaverdam.matching import gap_aware_scores, overlap_reference_scores, top_k
from beaverdam.profiles import PROFILES, disclose, shares_matrix

A, D, G = CAT_INDEX["academic"], CAT_INDEX["dining"], CAT_INDEX["gym"]
# Four toy slots: two academic and two dining.
SLOT_CAT = np.array([A, A, D, D])


def _shares(*sets):
    return shares_matrix([frozenset(s) for s in sets])


def _scores(X, shares, tau):
    return gap_aware_scores(disclose(X, SLOT_CAT, shares), SLOT_CAT, shares, tau)


def test_hand_computed_example():
    # u visits both academic slots and one dining slot and shares both categories.
    # v visits one academic slot and the same dining slot but withholds dining.
    X = np.array([[1, 1, 1, 0], [1, 0, 1, 0]], dtype=bool)
    S = _shares({"academic", "dining"}, {"academic"})
    # Ω_uv covers only the academic slots, so J = 1/2 and n_uv = 2.
    assert _scores(X, S, tau=1)[0, 1] == pytest.approx(0.5)
    assert _scores(X, S, tau=4)[0, 1] == pytest.approx(0.5 * 2 / 4)
    # The overlap reference treats v's withheld dining slot as unvisited, giving 1/3.
    assert overlap_reference_scores(disclose(X, SLOT_CAT, S))[0, 1] == pytest.approx(1 / 3)


def test_withheld_values_never_affect_scores():
    S = _shares({"academic", "dining"}, {"academic"}, {"academic", "dining"})
    X = np.array([[1, 0, 1, 0], [1, 1, 0, 0], [0, 1, 1, 1]], dtype=bool)
    X_changed = X.copy()
    X_changed[1, 2:] = [True, True]  # alter only user 1's withheld dining visits
    np.testing.assert_array_equal(_scores(X, S, 2), _scores(X_changed, S, 2))
    # Passing the raw matrix by mistake must still ignore withheld categories.
    np.testing.assert_array_equal(
        gap_aware_scores(X_changed, SLOT_CAT, S, 2), _scores(X, S, 2))


def test_shared_withholding_is_not_similarity():
    # Both users withhold dining and have disjoint academic slots. Identical
    # hidden dining visits must not make them look similar.
    S = _shares({"academic"}, {"academic"})
    X = np.array([[1, 0, 1, 1], [0, 1, 1, 1]], dtype=bool)
    assert _scores(X, S, 1)[0, 1] == 0.0


def test_no_shared_categories_matches_no_overlap():
    no_shared = _scores(np.array([[1, 0, 0, 0], [0, 0, 1, 0]], dtype=bool),
                        _shares({"academic"}, {"dining"}), tau=1)[0, 1]
    no_overlap = _scores(np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=bool),
                         _shares({"academic"}, {"academic"}), tau=1)[0, 1]
    assert no_shared == no_overlap == 0.0


def test_tau_downweights_thin_evidence():
    # Both pairs have J = 1, but the second pair has twice as much evidence.
    X = np.array([[1, 0, 0, 0], [1, 0, 0, 0], [1, 1, 0, 0], [1, 1, 0, 0]], dtype=bool)
    S = _shares(*[{"academic"}] * 4)
    s = _scores(X, S, tau=2)
    assert s[0, 1] == pytest.approx(0.5)
    assert s[2, 3] == pytest.approx(1.0)


def test_top_k_skips_self_zero_and_excluded():
    scores = np.array([[0, 0.9, 0.5, 0.0], [0.9, 0, 0.1, 0.2],
                       [0.5, 0.1, 0, 0.3], [0.0, 0.2, 0.3, 0]])
    recs = top_k(scores, k=3, rng=np.random.default_rng(0), exclude=[{1}, set(), set(), set()])
    assert recs[0] == [2]
    assert recs[1] == [0, 3, 2]


def test_top_k_breaks_ties_randomly_but_reproducibly():
    scores = np.zeros((6, 6))
    scores[0, 1:] = 0.5  # five candidates tied for user 0
    first = {tuple(top_k(scores, 2, np.random.default_rng(s))[0]) for s in range(30)}
    assert len(first) > 1  # the order of student IDs does not decide ties
    a = top_k(scores, 2, np.random.default_rng(4))
    b = top_k(scores, 2, np.random.default_rng(4))
    assert a == b


def test_real_data_scores_are_symmetric_and_bounded():
    data = load_slot_data()
    profiles = list(PROFILES.values())
    S = shares_matrix([profiles[i % 4] for i in range(data.n_students)])
    s = gap_aware_scores(disclose(data.X, data.slot_cat, S), data.slot_cat, S, tau=16)
    np.testing.assert_allclose(s, s.T)
    assert np.all(np.diag(s) == 0)
    assert s.min() >= 0 and s.max() <= 1


def test_loading_filters():
    all_rows = load_checkins(drop_flagged=False)
    ok = load_checkins()
    no_shared = load_checkins(drop_shared_events=True)
    assert len(all_rows) - len(ok) == 59
    assert not no_shared["event_id"].str.startswith("SH").any()
    # Exactly the 288 shared-event pings are dropped and nothing else.
    assert len(ok) - len(no_shared) == 288
    assert set(ok["checkin_id"]) - set(no_shared["checkin_id"]) == set(
        ok.loc[ok["event_id"].str.startswith("SH"), "checkin_id"])


def test_normalized_variant_keeps_the_three_guarantees():
    from beaverdam.matching import gap_aware_normalized_scores as norm
    # The third student keeps the population baselines away from zero.
    S = _shares({"academic", "dining"}, {"academic"}, {"academic", "dining"})
    X = np.array([[1, 0, 1, 0], [1, 1, 0, 0], [1, 1, 1, 1]], dtype=bool)
    X_changed = X.copy()
    X_changed[1, 2:] = [True, True]  # alter only withheld dining visits
    base = norm(disclose(X, SLOT_CAT, S), SLOT_CAT, S, 2)
    np.testing.assert_array_equal(base, norm(disclose(X_changed, SLOT_CAT, S), SLOT_CAT, S, 2))
    no_shared = norm(np.array([[1, 0, 0, 0], [0, 0, 1, 0], [1, 0, 1, 0]], dtype=bool), SLOT_CAT,
                     _shares({"academic"}, {"dining"}, {"academic", "dining"}), 1)[0, 1]
    no_overlap = norm(np.array([[1, 0, 0, 0], [0, 1, 0, 0], [1, 1, 0, 0]], dtype=bool), SLOT_CAT,
                      _shares({"academic"}, {"academic"}, {"academic"}), 1)[0, 1]
    assert no_shared == no_overlap == 0.0


def test_v2_datasets_are_valid_and_nested():
    import pandas as pd
    from beaverdam.data import DEFAULT_DATA_DIR
    from beaverdam.synth import validate
    base = DEFAULT_DATA_DIR.parent
    levels = ["v2_weak", "v2_medium", "v2_strong"]
    if not all((base / lvl).exists() for lvl in levels):
        pytest.skip("v2 datasets not built; run python -m beaverdam.synth")
    prev = set()
    for lvl in levels:
        assert validate(DEFAULT_DATA_DIR, base / lvl) == []
        ids = set(pd.read_csv(base / lvl / "routines.csv")["routine_id"])
        assert prev <= ids
        prev = ids
