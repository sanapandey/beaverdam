# BeaverDam: gap-aware private friend recommendation

This repository implements the gap-aware matching method from Section 4.3 of our
6.1850 proposal and evaluates it against the overlap reference baseline using
the quality metrics from Section 4.5. Everything runs on synthetic data for 100
students over one week, and a full evaluation takes under a minute on a laptop.

## Quickstart

```bash
pip install -e ".[dev]"          # installs numpy, pandas, scipy and pytest
python -m pytest                 # runs the 37 tests in a few seconds
python -m beaverdam.evaluate     # re-runs every experiment and rewrites results/
```

`python -m beaverdam.evaluate --datasets v2_strong --seeds 5` gives a quicker run
on one dataset while you iterate. `python -m beaverdam.synth` rebuilds the v2
datasets from the prelim data, which you only need to do if you change the
generator.

## What is where

```
beaverdam/
  data.py        loads check-ins and turns them into (venue, hour-of-week) slots
  profiles.py    the four disclosure profiles and the step that removes withheld data
  matching.py    the three scoring algorithms and top-k selection
  evaluate.py    the evaluation protocol, statistics and command-line entry point
  synth.py       builds the v2 datasets by giving friend pairs shared routines
data/            the prelim dataset and three v2 variants (see data/README.md)
results/         summary tables from the last full run (see "Reading the results")
tests/           unit tests, a slow reference implementation, and evaluation tests
```

## The algorithms

Each student's week becomes a set of slots, where a slot is a venue in a given
hour of the week, such as Maseeh dining hall on Tuesday from 12:00 to 13:00.
Every slot belongs to one category: academic, study, dining, gym, or leisure.
Each student shares some categories and withholds the rest, and withheld slots
are removed before any algorithm sees the data.

The **overlap reference** (`overlap_reference_scores`) scores a pair by the
Jaccard overlap of their visible slots. A withheld slot looks exactly like an
unvisited one, so a student who shares more categories looks less similar to a
student who shares fewer.

**Gap-aware matching** (`gap_aware_scores`) compares two students only on the
categories both of them share. With Ω_uv as the slots in those shared
categories, J_uv is the Jaccard overlap restricted to Ω_uv, and n_uv is the
number of slots in Ω_uv that either student visited. The score is
J_uv · min(n_uv, τ) / τ, where the second factor down-weights pairs with little
comparable evidence and τ is tuned. The three guarantees from the proposal are
each tested. Withheld data never changes a score, two students hiding the same
category does not make them look similar, and "no shared categories" scores
exactly the same as "no overlap", namely zero.

**Normalized gap-aware** (`gap_aware_normalized_scores`) is 
not in the proposal. Overlaps computed over different category sets are not on
a common scale. Academic-only overlaps average about 0.33, while overlaps across
four categories average about 0.12, so plain gap-aware fills the lists of
students who share a lot with academic-only students. This variant divides each
pair's J_uv by the average J over all pairs who share the same categories, and
then applies the same τ factor. It keeps all three guarantees.

## The evaluation

The four disclosure profiles adapt the proposal's ladder to this dataset, which
has no dorm category, so leisure takes the place of dorms. P1 shares everything
except leisure, P2 also withholds dining, P3 also withholds gym, and P4 shares
academic locations only.

Each seed randomly splits the friendships into 20% for tuning τ and 80% for
testing, and it assigns profiles so that about 25 students have each one. Each
algorithm recommends 10 people to every student, excluding friends from the
tuning split. Three metrics are measured. Recall@10 is the fraction of a
student's test friends who appear in their list, and precision@10 is the
fraction of the list who are test friends. Fidelity is the fraction of the list
the student would have received under full information that survives under
their profile. Every number is a mean over 20 seeds with a 95% confidence
interval. The evaluation also runs each profile on its own, and it runs
everything with and without the 43 planted hangouts in the data.

## Main results

These numbers come from the committed `results/` folder (mixed profiles, planted
hangouts kept, 20 seeds). Recall@10 at chance is about 0.10.

| Dataset | Overlap reference | Gap-aware | Normalized gap-aware |
|---|---|---|---|
| prelim | 0.104 ± 0.009 | 0.116 ± 0.008 | 0.114 ± 0.008 |
| v2_weak | 0.113 ± 0.006 | 0.124 ± 0.010 | 0.128 ± 0.010 |
| v2_medium | 0.130 ± 0.007 | 0.150 ± 0.010 | 0.144 ± 0.009 |
| v2_strong | 0.143 ± 0.008 | 0.164 ± 0.011 | 0.163 ± 0.011 |

Four findings stand out.

1. Gap-aware matching beats the overlap reference on recall on every dataset,
   by 0.01 to 0.02. Because every algorithm sees the same splits within a seed,
   the right test is the paired difference, and its 95% interval excludes zero
   on every dataset.
2. The gain goes almost entirely to students who withhold categories. On every
   dataset, academic-only students have recall of about 0.10 to 0.11 under the
   overlap reference and about 0.14 under gap-aware matching, while students who share
   nearly everything see no change. On v2_strong, the recall gap between P1 and
   P4 students shrinks from 0.073 to 0.044.
3. Plain gap-aware matching keeps less of the full-information list than the
   overlap reference on prelim and v2_weak (fidelity of 0.443 against 0.500 on
   prelim). The normalized variant fixes this (0.515) without losing recall.
4. The prelim data alone cannot show any of this clearly, because friendship is
   not tied to routines there. That is why the v2 datasets exist.

All recall values are low in absolute terms, even on v2_strong, because each
friend pair shares only one routine on two or three days.

## Reading the results

| File | Contents |
|---|---|
| `results/summary_mixed.csv` | This has the mean and CI of every metric for each dataset, algorithm, profile, and hangout setting. Rows with `profile` set to `ALL` cover every student. |
| `results/paired_vs_baseline.csv` | This has each algorithm's difference from the overlap reference, paired by seed, plus how many seeds favoured it. A difference is clear when its magnitude exceeds `*_ci95`. |
| `results/fairness_gap.csv` | This has the P1 minus P4 difference in each metric. A positive value means students who share more get better recommendations. |
| `results/<dataset>/` | This has the same tables for one dataset, including the runs where every student has the same profile. |
| `results/<dataset>/per_user.csv` | This has the raw per-student rows. It is not committed, but running the evaluation recreates it. |

## Common tasks

**Adding an algorithm.** Write a function in `matching.py` that takes
`(X_disclosed, slot_cat, shares, tau)` and returns an n × n score matrix, and
register it in `ALGORITHMS` at the top of `evaluate.py`. It will then appear in
every table. Adding a literal reference version to `tests/test_reference.py` is
the easiest way to make sure the fast version is right.

**Changing the disclosure profiles.** Edit `PROFILES` in `profiles.py`. The
fairness gap always compares the first profile with the last one.

**Adding a dataset.** Put a folder with the same files under `data/` and pass its
name to `--datasets`.

## Decisions worth knowing about

Slots are built from the GPS check-ins rather than the clean schedule, because
that is what a deployed app would see, and the 59 pings flagged as physically
implausible are dropped. Category is part of the slot key, because three cafes
are logged as dining on some visits and leisure on others. As a result, 16 cafe
venue-hours appear under both labels, and two students recorded under different
labels there are not counted as co-located.

There is only one week of data, so the proposal's split by weeks is replaced by
a split of friendship edges. Neither algorithm uses friendships as input, so the
split only affects tuning and scoring.

Tuning τ mostly chooses between two behaviours. Any τ smaller than a pair's
n_uv leaves the score equal to plain Jaccard, while a large τ turns it into a
count of shared slots. For plain gap-aware matching, tuning picks τ = 1 in about
half of the prelim seeds, and it picks 32 to 128 in 19 of the 20 v2_strong seeds.

The planted hangouts carry little signal. Each is a single 45-minute visit, 28 of
the 43 are in leisure or dining, which most profiles withhold, and keeping or
dropping them barely changes any result.

The privacy attacks from Section 4.4 and the exact and category output policies
from Section 4.2 are not implemented yet.
