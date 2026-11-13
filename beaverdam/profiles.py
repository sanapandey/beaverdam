"""Disclosure profiles and the disclosure step that runs before any algorithm.

The prelim dataset has no dorm category, so leisure (cafe hangouts) takes the
place of dorms in the proposal's profile ladder (Section 4.1). Every profile
withholds leisure, just as every profile in the proposal withholds dorms.
"""

from __future__ import annotations

import numpy as np

from .data import CAT_INDEX, CATEGORIES

PROFILES: dict[str, frozenset[str]] = {
    "P1_all_but_leisure": frozenset({"academic", "study", "dining", "gym"}),
    "P2_no_dining": frozenset({"academic", "study", "gym"}),
    "P3_no_dining_gym": frozenset({"academic", "study"}),
    "P4_academic_only": frozenset({"academic"}),
}
PROFILE_NAMES: list[str] = list(PROFILES)
FULL_INFORMATION = frozenset(CATEGORIES)


def shares_matrix(profile_per_student: list[frozenset[str]]) -> np.ndarray:
    """Return a bool matrix of shape (n_students, n_categories) where entry
    [u, c] says whether student u shares category c (the set C_u)."""
    S = np.zeros((len(profile_per_student), len(CATEGORIES)), dtype=bool)
    for u, cats in enumerate(profile_per_student):
        for c in cats:
            S[u, CAT_INDEX[c]] = True
    return S


def disclose(X: np.ndarray, slot_cat: np.ndarray, shares: np.ndarray) -> np.ndarray:
    """Remove every withheld slot so that it never reaches the system.

    The output keeps a slot for student u only when u shares that slot's
    category. Algorithms receive this matrix and never see the original.
    """
    return X & shares[:, slot_cat]


def assign_mixed(n_students: int, rng: np.random.Generator) -> list[str]:
    """Assign profiles in near-equal numbers and then shuffle, so that each
    profile has about n/4 students and per-profile metrics are comparable."""
    names = [PROFILE_NAMES[i % len(PROFILE_NAMES)] for i in range(n_students)]
    rng.shuffle(names)
    return names
