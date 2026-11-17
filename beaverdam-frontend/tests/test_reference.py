"""Check the vectorized scorers against a literal, set-based reading of the formulas.

The reference functions below deliberately share no code with
beaverdam.matching. They follow the definitions in Section 4.3 of the proposal
one pair at a time using Python sets, so any disagreement points to a bug in the
fast implementation (or in the reading of the spec).
"""

from itertools import combinations

import numpy as np
import pytest

from beaverdam.data import DEFAULT_DATA_DIR, load_slot_data
from beaverdam.matching import (gap_aware_normalized_scores, gap_aware_scores,
                                overlap_reference_scores)
from beaverdam.profiles import PROFILES, disclose, shares_matrix

DATASETS = ["prelim", "v2_weak", "v2_strong"]


def _visible_sets(X, slot_cat, C):
    """A_u is the set of slots u visits in a category u shares."""
    return [{s for s in np.flatnonzero(X[u]) if slot_cat[s] in C[u]} for u in range(len(C))]


def ref_gap_aware(X, slot_cat, C, tau):
    A = _visible_sets(X, slot_cat, C)
    n = len(C)
    out = np.zeros((n, n))
    for u, v in combinations(range(n), 2):
        shared = C[u] & C[v]
        if not shared:
            continue
        Au = {s for s in A[u] if slot_cat[s] in shared}
        Av = {s for s in A[v] if slot_cat[s] in shared}
        n_uv = len(Au | Av)
        J = len(Au & Av) / n_uv if n_uv else 0.0
        out[u, v] = out[v, u] = J * min(n_uv, tau) / tau
    return out


def ref_overlap(X, slot_cat, C):
    A = _visible_sets(X, slot_cat, C)
    n = len(C)
    out = np.zeros((n, n))
    for u, v in combinations(range(n), 2):
        union = len(A[u] | A[v])
        out[u, v] = out[v, u] = len(A[u] & A[v]) / union if union else 0.0
    return out


def ref_normalized(X, slot_cat, C, tau):
    A = _visible_sets(X, slot_cat, C)
    n = len(C)

    def jaccard_on(u, v, cats):
        Au = {s for s in A[u] if slot_cat[s] in cats}
        Av = {s for s in A[v] if slot_cat[s] in cats}
        union = len(Au | Av)
        return (len(Au & Av) / union if union else 0.0), union

    baselines = {}
    out = np.zeros((n, n))
    for u, v in combinations(range(n), 2):
        M = frozenset(C[u] & C[v])
        if not M:
            continue
        if M not in baselines:
            vals = [jaccard_on(x, y, M)[0] for x, y in combinations(range(n), 2)
                    if M <= (C[x] & C[y])]
            baselines[M] = sum(vals) / len(vals)
        J, n_uv = jaccard_on(u, v, M)
        mu = baselines[M]
        lift = J / mu if mu > 0 else 0.0
        out[u, v] = out[v, u] = lift * min(n_uv, tau) / tau
    return out


@pytest.fixture(scope="module", params=DATASETS)
def mixed(request):
    path = DEFAULT_DATA_DIR.parent / request.param
    if not path.exists():
        pytest.skip(f"{request.param} not built; run python -m beaverdam.synth")
    data = load_slot_data(path)
    rng = np.random.default_rng(3)
    names = list(PROFILES)
    profiles = [PROFILES[names[i]] for i in rng.integers(0, len(names), data.n_students)]
    cat_names = ["academic", "study", "dining", "gym", "leisure"]
    C = [{cat_names.index(c) for c in p} for p in profiles]
    S = shares_matrix(profiles)
    return data, C, S, disclose(data.X, data.slot_cat, S)


@pytest.mark.parametrize("tau", [1, 7, 40, 500])
def test_gap_aware_matches_reference(mixed, tau):
    data, C, S, X_disc = mixed
    np.testing.assert_allclose(gap_aware_scores(X_disc, data.slot_cat, S, tau),
                               ref_gap_aware(data.X, data.slot_cat, C, tau), atol=1e-12)


def test_overlap_matches_reference(mixed):
    data, C, S, X_disc = mixed
    np.testing.assert_allclose(overlap_reference_scores(X_disc),
                               ref_overlap(data.X, data.slot_cat, C), atol=1e-12)


@pytest.mark.parametrize("tau", [1, 40])
def test_normalized_matches_reference(mixed, tau):
    data, C, S, X_disc = mixed
    np.testing.assert_allclose(gap_aware_normalized_scores(X_disc, data.slot_cat, S, tau),
                               ref_normalized(data.X, data.slot_cat, C, tau), atol=1e-9)
