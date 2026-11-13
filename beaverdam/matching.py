"""Gap-aware matching (proposal Section 4.3) and the overlap reference baseline.

Both functions take the *disclosed* visit matrix, which means withheld slots
have already been removed by `profiles.disclose`. They return a symmetric
(n x n) score matrix with a zero diagonal.
"""

from __future__ import annotations

import numpy as np


def _jaccard_parts(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return the pairwise intersection and union sizes of the rows of X."""
    Xf = X.astype(np.float64)
    inter = Xf @ Xf.T
    sizes = Xf.sum(axis=1)
    union = sizes[:, None] + sizes[None, :] - inter
    return inter, union


def _safe_div(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    out = np.zeros_like(num, dtype=np.float64)
    np.divide(num, den, out=out, where=den > 0)
    return out


def overlap_reference_scores(X_disclosed: np.ndarray) -> np.ndarray:
    """Plain Jaccard over all disclosed slots.

    A withheld slot looks exactly like an unvisited one, so a student who shares
    more categories has a larger union and therefore a lower score against a
    student who shares fewer.
    """
    inter, union = _jaccard_parts(X_disclosed)
    J = _safe_div(inter, union)
    np.fill_diagonal(J, 0.0)
    return J


def _per_category_parts(X_disclosed: np.ndarray, slot_cat: np.ndarray,
                        shares: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return per-category intersection and union sizes, each of shape (C, n, n).

    Entry [c, u, v] counts only slots of category c, and it is zero unless both
    u and v share c. Because Ω_uv is a union of whole categories, any Jaccard
    restricted to Ω_uv can be assembled by summing these over categories.
    """
    n, n_cats = X_disclosed.shape[0], shares.shape[1]
    inter = np.zeros((n_cats, n, n))
    union = np.zeros((n_cats, n, n))
    for c in range(n_cats):
        cols = slot_cat == c
        if not cols.any():
            continue
        both_share = np.outer(shares[:, c], shares[:, c]).astype(np.float64)
        # Masking by shares here as well as in `disclose` guarantees that a
        # slot from a withheld category can never contribute to a score, even
        # if a caller passes an undisclosed matrix by mistake.
        Xc = X_disclosed[:, cols] & shares[:, [c]]
        i_c, u_c = _jaccard_parts(Xc)
        inter[c] = both_share * i_c
        union[c] = both_share * u_c
    return inter, union


def gap_aware_components(X_disclosed: np.ndarray, slot_cat: np.ndarray,
                         shares: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute |A_u ∩ A_v ∩ Ω_uv| and n_uv = |(A_u ∪ A_v) ∩ Ω_uv| for every pair,
    where Ω_uv is the set of slots whose category is in C_u ∩ C_v."""
    inter, union = _per_category_parts(X_disclosed, slot_cat, shares)
    return inter.sum(axis=0), union.sum(axis=0)


def gap_aware_scores(X_disclosed: np.ndarray, slot_cat: np.ndarray, shares: np.ndarray,
                     tau: float) -> np.ndarray:
    """score_uv = J_uv * min(n_uv, tau) / tau, computed only over Ω_uv.

    The method never estimates withheld values. It does not reward two users
    for withholding the same category, because a category that either user
    withholds is dropped from Ω_uv entirely. A pair with no shared categories
    and a pair with no overlap both score exactly zero, so the output does not
    reveal which of the two cases applies.
    """
    if tau <= 0:
        raise ValueError("tau must be positive")
    inter, n_uv = gap_aware_components(X_disclosed, slot_cat, shares)
    J = _safe_div(inter, n_uv)
    score = J * np.minimum(n_uv, tau) / tau
    np.fill_diagonal(score, 0.0)
    return score


def gap_aware_normalized_scores(X_disclosed: np.ndarray, slot_cat: np.ndarray,
                                shares: np.ndarray, tau: float) -> np.ndarray:
    """Gap-aware score with J_uv replaced by its lift over the population baseline.

    This variant is not in the proposal. It addresses the fact that a Jaccard
    computed over academic slots alone is systematically higher than one
    computed over several categories, which makes raw gap-aware scores
    incomparable across pairs whose Ω_uv differ. For a pair whose shared
    category set is M, the baseline mu(M) is the mean Jaccard restricted to the
    categories in M, taken over every pair of distinct students who both share
    all of M. The score is (J_uv / mu(M)) * min(n_uv, tau) / tau.

    The three properties of the original method still hold, because the score
    is still built only from slots in Ω_uv, and a pair with no shared category
    or no overlap still scores exactly zero. mu(M) is a population statistic and
    reveals nothing about any individual.
    """
    if tau <= 0:
        raise ValueError("tau must be positive")
    inter_c, union_c = _per_category_parts(X_disclosed, slot_cat, shares)
    n = X_disclosed.shape[0]
    bits = shares.astype(np.int64) @ (1 << np.arange(shares.shape[1]))
    pair_mask = bits[:, None] & bits[None, :]
    off_diag = ~np.eye(n, dtype=bool)
    upper = np.triu(np.ones((n, n), dtype=bool), k=1)

    J = np.zeros((n, n))
    n_uv = union_c.sum(axis=0)
    for m in np.unique(pair_mask[off_diag]):
        if m == 0:
            continue
        cats = [c for c in range(shares.shape[1]) if m >> c & 1]
        J_m = _safe_div(inter_c[cats].sum(axis=0), union_c[cats].sum(axis=0))
        eligible = ((pair_mask & m) == m) & upper
        mu = J_m[eligible].mean()
        target = (pair_mask == m) & off_diag
        if mu > 0:
            J[target] = J_m[target] / mu
    score = J * np.minimum(n_uv, tau) / tau
    np.fill_diagonal(score, 0.0)
    return score


def top_k(scores: np.ndarray, k: int, rng: np.random.Generator,
          exclude: list[set[int]] | None = None) -> list[list[int]]:
    """Return each user's top-k candidates, best first.

    Candidates with a score of zero are never recommended, so a list can be
    shorter than k. Ties are broken randomly using `rng` so that the order of
    student IDs cannot influence results.
    """
    n = scores.shape[0]
    jitter = rng.random(scores.shape)
    out: list[list[int]] = []
    for u in range(n):
        s = scores[u].copy()
        s[u] = 0.0
        if exclude is not None:
            for v in exclude[u]:
                s[v] = 0.0
        order = np.lexsort((jitter[u], -s))
        out.append([int(v) for v in order[:k] if s[v] > 0])
    return out
