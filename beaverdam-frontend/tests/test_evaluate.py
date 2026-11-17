import numpy as np
import pytest

from beaverdam.data import load_friendships, load_slot_data
from beaverdam.evaluate import (adjacency, fidelity, precision_recall, run_condition,
                                split_edges, summarize)
from beaverdam.profiles import PROFILE_NAMES, assign_mixed


def test_split_is_a_disjoint_partition():
    edges = load_friendships()
    tune, test = split_edges(edges, np.random.default_rng(0))
    assert len(tune) == 48 and len(test) == 191
    assert not set(tune) & set(test)
    assert set(tune) | set(test) == set(edges)


def test_metric_definitions():
    recs = [[1, 2, 3], [], [0]]
    truth = [{1, 4}, set(), {5}]
    prec, rec = precision_recall(recs, truth, k=10)
    assert prec[0] == pytest.approx(1 / 10) and rec[0] == pytest.approx(1 / 2)
    assert np.isnan(prec[1]) and np.isnan(rec[1])
    assert prec[2] == 0 and rec[2] == 0
    assert fidelity([[1, 2], [3]], [[2, 9], []]).tolist()[0] == pytest.approx(0.5)
    assert np.isnan(fidelity([[1, 2], [3]], [[2, 9], []])[1])


def test_tuning_friends_are_never_recommended_at_test_time():
    data = load_slot_data()
    rng = np.random.default_rng(1)
    tune, test = split_edges(load_friendships(), rng)
    tune_adj, test_adj = adjacency(tune, data.students), adjacency(test, data.students)
    rows = run_condition(data, assign_mixed(data.n_students, rng), tune_adj, test_adj, 10, 1)
    assert {r["algorithm"] for r in rows} == {"overlap_reference", "gap_aware",
                                              "gap_aware_normalized"}
    for r in rows:
        assert r["n_recs"] <= 10


def test_fairness_gap_is_paired_by_seed():
    import pandas as pd
    rows = []
    for seed, (p1, p4) in enumerate([(0.3, 0.1), (0.5, 0.2)]):
        for prof, val in ((PROFILE_NAMES[0], p1), (PROFILE_NAMES[-1], p4)):
            rows.append(dict(shared_events="kept", seed=seed, assignment="mixed",
                             algorithm="a", tau=1.0, student=f"{prof}{seed}", profile=prof,
                             n_test_friends=1, n_recs=1, precision=val, recall=val,
                             fidelity=val))
    _, fairness = summarize(pd.DataFrame(rows))
    assert fairness["precision"].iloc[0] == pytest.approx(((0.3 - 0.1) + (0.5 - 0.2)) / 2)


def test_paired_vs_baseline_differences_by_seed():
    import pandas as pd
    from beaverdam.evaluate import paired_vs_baseline
    rows = []
    for seed, (base, alg) in enumerate([(0.10, 0.15), (0.20, 0.18), (0.30, 0.40)]):
        for name, val in (("overlap_reference", base), ("gap_aware", alg)):
            rows.append(dict(shared_events="kept", seed=seed, assignment="mixed",
                             algorithm=name, student="S1", profile=PROFILE_NAMES[0],
                             precision=val, recall=val, fidelity=val))
    out = paired_vs_baseline(pd.DataFrame(rows))
    row = out[out["profile"] == "ALL"].iloc[0]
    assert row["algorithm"] == "gap_aware" and row["n_seeds"] == 3
    assert row["recall"] == pytest.approx((0.05 - 0.02 + 0.10) / 3)
    assert row["recall_seeds_better"] == 2
