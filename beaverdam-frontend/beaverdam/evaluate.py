"""Evaluate gap-aware matching against the overlap reference (proposal Section 4.5).

For each seed, the protocol works as follows.

1. Friendship edges are split so that 20% are used to tune tau and 80% are
   held out for testing. Neither algorithm consumes friendships as input, so
   all of the week's behaviour stays visible to both.
2. Disclosure profiles are assigned in a mixed run (about 25 students per
   profile) and in four homogeneous runs where everyone has the same profile.
3. For gap-aware matching, tau is chosen from TAU_GRID to maximise mean
   recall@k on the tuning edges.
4. On the test edges, precision@k and recall@k are computed after removing
   each user's tuning-split friends from the candidate list, since a deployed
   recommender would not suggest people who are already friends.
5. Fidelity is the fraction of a user's full-information top-k, where every
   student shares all five categories, that survives under the policy. The
   full-information list uses the same algorithm with tau tuned under full
   information, so it is the same reference for every policy within a seed.

The whole protocol runs twice, once keeping the planted shared-event hangouts
and once dropping them.

Run it with `python -m beaverdam.evaluate` (use `--help` for options). It prints a
short summary and writes these tables to `results/`:

- `summary_mixed.csv` gives the mean and 95% CI of each metric for every
  dataset, algorithm and profile in the mixed-profile runs.
- `paired_vs_baseline.csv` gives each algorithm's per-seed difference from
  the overlap reference, which is the right test for "is it better", because
  every algorithm sees the same splits and profile assignments in a seed.
- `fairness_gap.csv` gives the P1 minus P4 difference in each metric.
- `<dataset>/` holds the same tables for one dataset, plus the homogeneous
  runs and `per_user.csv`, the raw per-student rows (large and not committed).
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

from .data import DEFAULT_DATA_DIR, SlotData, load_friendships, load_slot_data
from .matching import (gap_aware_normalized_scores, gap_aware_scores,
                       overlap_reference_scores, top_k)
from .profiles import (FULL_INFORMATION, PROFILE_NAMES, PROFILES, assign_mixed,
                       disclose, shares_matrix)

TAU_GRID = (1, 2, 4, 8, 16, 32, 64, 128)
TUNE_FRAC = 0.2
DEFAULT_K = 10
DEFAULT_SEEDS = 20

ScoreFn = Callable[[np.ndarray, np.ndarray, np.ndarray, float], np.ndarray]

# To add an algorithm, write a function with the signature
# (X_disclosed, slot_cat, shares, tau) -> (n x n) score matrix and register it
# here. The boolean says whether tau should be tuned for it.
ALGORITHMS: dict[str, tuple[ScoreFn, bool]] = {
    "overlap_reference": (lambda X, cat, S, tau: overlap_reference_scores(X), False),
    "gap_aware": (gap_aware_scores, True),
    "gap_aware_normalized": (gap_aware_normalized_scores, True),
}
BASELINE = "overlap_reference"
DATASETS = ("prelim", "v2_weak", "v2_medium", "v2_strong")
METRICS = ["precision", "recall", "fidelity"]


def split_edges(edges: list[tuple[str, str]], rng: np.random.Generator,
                tune_frac: float = TUNE_FRAC) -> tuple[list, list]:
    perm = rng.permutation(len(edges))
    n_tune = int(round(tune_frac * len(edges)))
    tune = [edges[i] for i in perm[:n_tune]]
    test = [edges[i] for i in perm[n_tune:]]
    return tune, test


def adjacency(edges: list[tuple[str, str]], students: list[str]) -> list[set[int]]:
    idx = {s: i for i, s in enumerate(students)}
    adj: list[set[int]] = [set() for _ in students]
    for a, b in edges:
        adj[idx[a]].add(idx[b])
        adj[idx[b]].add(idx[a])
    return adj


def precision_recall(recs: list[list[int]], truth: list[set[int]], k: int):
    """Compute per-user precision@k and recall@k, with NaN for users who have
    no ground-truth friends. Precision divides by k even when a list is shorter
    than k, so that a short list is not rewarded for being short."""
    prec = np.full(len(recs), np.nan)
    rec = np.full(len(recs), np.nan)
    for u, (r, t) in enumerate(zip(recs, truth)):
        if t:
            hits = len(set(r) & t)
            prec[u] = hits / k
            rec[u] = hits / len(t)
    return prec, rec


def fidelity(recs: list[list[int]], full_recs: list[list[int]]) -> np.ndarray:
    out = np.full(len(recs), np.nan)
    for u, (r, f) in enumerate(zip(recs, full_recs)):
        if f:
            out[u] = len(set(r) & set(f)) / len(f)
    return out


def _tie_rng(seed: int) -> np.random.Generator:
    # A fresh generator per call gives both algorithms identical tie-breaking.
    return np.random.default_rng([seed, 7919])


def tune_tau(score_fn: ScoreFn, data: SlotData, X_disc: np.ndarray, shares: np.ndarray,
             tune_adj: list[set[int]], k: int, seed: int) -> float:
    best_tau, best_recall = TAU_GRID[0], -1.0
    for tau in TAU_GRID:
        scores = score_fn(X_disc, data.slot_cat, shares, tau)
        recs = top_k(scores, k, _tie_rng(seed))
        _, rec = precision_recall(recs, tune_adj, k)
        mean_rec = float(np.nanmean(rec))
        if mean_rec > best_recall:  # strict ">" keeps the smallest tau on ties
            best_tau, best_recall = tau, mean_rec
    return float(best_tau)


def run_condition(data: SlotData, profiles: list[str], tune_adj, test_adj, k: int,
                  seed: int) -> list[dict]:
    shares = shares_matrix([PROFILES[p] for p in profiles])
    X_disc = disclose(data.X, data.slot_cat, shares)
    full_shares = shares_matrix([FULL_INFORMATION] * data.n_students)
    X_full = disclose(data.X, data.slot_cat, full_shares)

    rows = []
    for alg, (score_fn, uses_tau) in ALGORITHMS.items():
        tau = tune_tau(score_fn, data, X_disc, shares, tune_adj, k, seed) if uses_tau else np.nan

        scores = score_fn(X_disc, data.slot_cat, shares, tau)
        test_recs = top_k(scores, k, _tie_rng(seed), exclude=tune_adj)
        prec, rec = precision_recall(test_recs, test_adj, k)

        policy_recs = top_k(scores, k, _tie_rng(seed))
        # The full-information reference gets its own tau, tuned under full
        # information, so that the reference list does not move with the policy.
        full_tau = (tune_tau(score_fn, data, X_full, full_shares, tune_adj, k, seed)
                    if uses_tau else np.nan)
        full_scores = score_fn(X_full, data.slot_cat, full_shares, full_tau)
        full_recs = top_k(full_scores, k, _tie_rng(seed))
        fid = fidelity(policy_recs, full_recs)

        for u, student in enumerate(data.students):
            rows.append({
                "algorithm": alg, "tau": tau, "student": student, "profile": profiles[u],
                "n_test_friends": len(test_adj[u]), "n_recs": len(test_recs[u]),
                "precision": prec[u], "recall": rec[u], "fidelity": fid[u],
            })
    return rows


def run_all(data_dir: Path = DEFAULT_DATA_DIR, seeds: int = DEFAULT_SEEDS,
            k: int = DEFAULT_K) -> pd.DataFrame:
    edges = load_friendships(data_dir)
    rows = []
    for shared_events in ("kept", "dropped"):
        data = load_slot_data(data_dir, drop_shared_events=(shared_events == "dropped"))
        for seed in range(seeds):
            rng = np.random.default_rng(seed)
            tune, test = split_edges(edges, rng)
            tune_adj = adjacency(tune, data.students)
            test_adj = adjacency(test, data.students)
            assignments = {"mixed": assign_mixed(data.n_students, rng)}
            for p in PROFILE_NAMES:
                assignments[f"all_{p}"] = [p] * data.n_students
            for assignment, profiles in assignments.items():
                for r in run_condition(data, profiles, tune_adj, test_adj, k, seed):
                    r.update(shared_events=shared_events, seed=seed, assignment=assignment)
                    rows.append(r)
    cols = ["shared_events", "seed", "assignment", "algorithm", "tau", "student", "profile",
            "n_test_friends", "n_recs", "precision", "recall", "fidelity"]
    return pd.DataFrame(rows)[cols]


def _t_crit(n: int) -> float:
    return float(student_t.ppf(0.975, n - 1)) if n > 1 else np.nan


def _ci(per_seed: pd.DataFrame, keys: list[str], metrics: list[str]) -> pd.DataFrame:
    """Return the mean and the half-width of a t-based 95% CI across seeds."""
    g = per_seed.groupby(keys)[metrics]
    mean, sd, n = g.mean(), g.std(ddof=1), g.count()
    out = mean.copy()
    for m in metrics:
        half = sd[m] / np.sqrt(n[m]) * n[m].map(_t_crit)
        out[f"{m}_ci95"] = half
    return out[[c for m in metrics for c in (m, f"{m}_ci95")]].reset_index()


def paired_vs_baseline(per_user: pd.DataFrame, baseline: str = BASELINE) -> pd.DataFrame:
    """Compare each algorithm with the baseline seed by seed in the mixed runs.

    For every seed, the per-user mean of each metric is differenced against the
    baseline's mean in the same seed, and the table reports the mean
    difference, its 95% CI, and how many seeds favoured the algorithm. A
    difference is clear when its magnitude exceeds its CI half-width.
    """
    mixed = per_user[per_user["assignment"] == "mixed"]
    both = pd.concat([mixed.assign(profile="ALL"), mixed])
    keys = ["shared_events", "profile", "seed"]
    per_seed = both.groupby(["algorithm"] + keys)[METRICS].mean()
    base = per_seed.xs(baseline, level="algorithm")
    tables = []
    for alg in per_seed.index.get_level_values("algorithm").unique():
        if alg == baseline:
            continue
        diff = (per_seed.xs(alg, level="algorithm") - base).reset_index()
        stats = _ci(diff, keys[:-1], METRICS)
        wins = diff.groupby(keys[:-1])[METRICS].agg(lambda s: int((s > 0).sum()))
        wins.columns = [f"{m}_seeds_better" for m in METRICS]
        n_seeds = diff.groupby(keys[:-1])["seed"].nunique().rename("n_seeds")
        stats = stats.merge(wins.reset_index(), on=keys[:-1]).merge(
            n_seeds.reset_index(), on=keys[:-1])
        tables.append(stats.assign(algorithm=alg, baseline=baseline))
    out = pd.concat(tables)
    first = ["shared_events", "algorithm", "baseline", "profile"]
    return out[first + [c for c in out if c not in first]].reset_index(drop=True)


def summarize(per_user: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Average users within each seed, then report the mean ± 95% CI across seeds.

    Returns the summary table and the fairness-gap table (P1 minus P4, paired
    by seed, in the mixed runs).
    """
    metrics = METRICS
    base = ["shared_events", "assignment", "algorithm"]

    overall = per_user.assign(profile="ALL")
    both = pd.concat([overall, per_user])
    per_seed = both.groupby(base + ["profile", "seed"])[metrics].mean().reset_index()
    taus = per_user.groupby(base)["tau"].agg(lambda s: ",".join(
        f"{t:g}" for t in sorted(set(s.dropna())))).rename("taus_chosen").reset_index()
    summary = _ci(per_seed, base + ["profile"], metrics).merge(taus, on=base)
    # The homogeneous runs have only one profile, so their "ALL" row duplicates it.
    summary = summary[(summary["assignment"] == "mixed") | (summary["profile"] == "ALL")]

    mixed = per_seed[(per_seed["assignment"] == "mixed")]
    p1 = mixed[mixed["profile"] == PROFILE_NAMES[0]].set_index(base + ["seed"])[metrics]
    p4 = mixed[mixed["profile"] == PROFILE_NAMES[-1]].set_index(base + ["seed"])[metrics]
    gap = (p1 - p4).reset_index()
    fairness = _ci(gap, base, metrics)
    return summary.reset_index(drop=True), fairness


def _first(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return df[cols + [c for c in df if c not in cols]]


def _print_grid(df: pd.DataFrame, metric: str, title: str, signed: bool = False) -> None:
    """Print a dataset-by-algorithm grid of 'mean ± ci' for one metric."""
    fmt = "{:+.3f} ± {:.3f}" if signed else "{:.3f} ± {:.3f}"
    cells = df.assign(cell=[fmt.format(m, c) for m, c in zip(df[metric], df[f"{metric}_ci95"])])
    grid = cells.pivot(index="dataset", columns="algorithm", values="cell")
    grid = grid.reindex([d for d in DATASETS if d in grid.index]
                        + [d for d in grid.index if d not in DATASETS])
    print(f"\n{title}\n")
    print(grid.to_string())


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Evaluate the matching algorithms on one or more datasets.")
    ap.add_argument("--datasets", nargs="+", default=list(DATASETS),
                    help="dataset folder names under --data-root (default: all four)")
    ap.add_argument("--seeds", type=int, default=DEFAULT_SEEDS,
                    help=f"number of random seeds (default: {DEFAULT_SEEDS}; use 5 for a quick run)")
    ap.add_argument("-k", type=int, default=DEFAULT_K, help="length of each recommendation list")
    ap.add_argument("--data-root", type=Path, default=DEFAULT_DATA_DIR.parent)
    ap.add_argument("--out-dir", type=Path,
                    default=Path(__file__).resolve().parent.parent / "results")
    args = ap.parse_args()

    summaries, gaps, paired = [], [], []
    for name in args.datasets:
        print(f"Evaluating {name} with {args.seeds} seeds...")
        per_user = run_all(args.data_root / name, args.seeds, args.k)
        summary, fairness = summarize(per_user)
        vs_base = paired_vs_baseline(per_user)
        out = args.out_dir / name
        out.mkdir(parents=True, exist_ok=True)
        per_user.to_csv(out / "per_user.csv", index=False)
        summary.to_csv(out / "summary.csv", index=False)
        fairness.to_csv(out / "fairness_gap.csv", index=False)
        vs_base.to_csv(out / "paired_vs_baseline.csv", index=False)
        summaries.append(summary[summary["assignment"] == "mixed"].assign(dataset=name))
        gaps.append(fairness.assign(dataset=name))
        paired.append(vs_base.assign(dataset=name))

    summary_all = _first(pd.concat(summaries).drop(columns="assignment"),
                         ["dataset", "shared_events", "algorithm", "profile"])
    gaps_all = _first(pd.concat(gaps).drop(columns="assignment"), ["dataset"])
    paired_all = _first(pd.concat(paired), ["dataset"])
    summary_all.to_csv(args.out_dir / "summary_mixed.csv", index=False)
    gaps_all.to_csv(args.out_dir / "fairness_gap.csv", index=False)
    paired_all.to_csv(args.out_dir / "paired_vs_baseline.csv", index=False)

    # The console shows the headline view: mixed profiles, planted hangouts
    # kept, all students together. Everything else is in the CSVs.
    kept_all = summary_all[(summary_all["shared_events"] == "kept")
                           & (summary_all["profile"] == "ALL")]
    print(f"\nMixed profiles, planted hangouts kept, k={args.k}, "
          f"mean ± 95% CI over {args.seeds} seeds.")
    _print_grid(kept_all, "recall", "Recall@k")
    _print_grid(kept_all, "fidelity", "Fidelity")
    _print_grid(paired_all[(paired_all["shared_events"] == "kept")
                           & (paired_all["profile"] == "ALL")],
                "recall", f"Recall@k difference from {BASELINE}, paired by seed", signed=True)
    _print_grid(gaps_all[gaps_all["shared_events"] == "kept"], "recall",
                f"Fairness gap in recall@k ({PROFILE_NAMES[0]} minus {PROFILE_NAMES[-1]})",
                signed=True)
    print(f"\nFull tables are in {args.out_dir}/")


if __name__ == "__main__":
    main()
