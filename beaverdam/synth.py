"""Build the v2 datasets by adding shared dining and study routines to friend pairs.

The prelim generator does not tie friendship to routine, so friends overlap no
more than strangers do. This script starts from the prelim data and, for a
chosen fraction of friend pairs, makes the two friends repeat one meal or one
study block together on two or three days of the week.

For each coupled pair, the steps are as follows.

1. Choose dining or study at random, and choose one friend as the leader.
2. Take one of the leader's existing, unflagged visits in that category as a
   template, which fixes the venue and the time of day.
3. Find up to three days of the same day type (weekday or weekend, because
   opening hours differ) on which neither friend has a class, an existing
   routine, or a planted hangout within 15 minutes of that window.
4. If at least two such days exist, remove any other non-academic visits either
   friend had in that window (and, for dining, any other meal that friend had
   within two hours of it), and then add the shared visit for both friends.

Every pair's choices come from its own random generator, and pairs are processed
in a fixed order, so the weak pairs are a subset of the medium pairs and the
medium pairs are a subset of the strong pairs. All unchanged visits keep their
original check-in rows, and new visits get pings every 15 minutes from start
(inclusive) to end (exclusive), which is the rule the prelim data follows.

Run it with `python -m beaverdam.synth`.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from .data import DEFAULT_DATA_DIR

LEVELS = {"weak": 0.25, "medium": 0.50, "strong": 0.75}
ROUTINE_CATEGORIES = ("dining", "study")
TARGET_DAYS = 3
MIN_DAYS = 2
TRAVEL_BUFFER_MIN = 15
MEAL_REPLACE_WINDOW_MIN = 120
PING_MIN = 15
TZ_SUFFIX = "-04:00"


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _prepare(src: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[tuple[str, str]]]:
    acts = pd.read_csv(src / "activities_full.csv", dtype=str, keep_default_na=False)
    checkins = pd.read_csv(src / "checkins_full.csv", dtype=str, keep_default_na=False)
    acts["start"] = acts["start_time"].map(_minutes)
    acts["end"] = acts["end_time"].map(_minutes)
    acts["dow"] = pd.to_datetime(acts["date"]).dt.dayofweek
    acts["routine_id"] = ""
    flagged = set(checkins.loc[checkins["quality_flag"] != "ok", "event_id"])
    acts["flagged"] = acts["event_id"].isin(flagged)
    f = pd.read_csv(src / "friendships_full.csv", dtype=str)
    edges = [tuple(sorted(p)) for p in zip(f["student_id_1"], f["student_id_2"])]
    return acts, checkins, edges


def _protected(row) -> bool:
    """Classes, routines and planted hangouts are never moved or deleted."""
    return row.activity_category == "academic" or bool(row.routine_id) or bool(row.shared_event_id)


def _overlaps(df: pd.DataFrame, start: int, end: int) -> pd.Series:
    return (df["start"] < end + TRAVEL_BUFFER_MIN) & (df["end"] > start - TRAVEL_BUFFER_MIN)


def _try_couple(acts: pd.DataFrame, pair: tuple[str, str], rng: np.random.Generator,
                routine_id: str, dates_by_dow: dict[int, str]) -> tuple[pd.DataFrame, dict | None]:
    category = str(rng.choice(ROUTINE_CATEGORIES))
    leader = pair[int(rng.integers(2))]
    templates = acts[(acts["student_id"] == leader) & (acts["activity_category"] == category)
                     & ~acts["flagged"] & (acts["routine_id"] == "") & (acts["shared_event_id"] == "")]
    if templates.empty:
        return acts, None

    for t in templates.iloc[rng.permutation(len(templates))].itertuples():
        weekend = t.dow >= 5
        others = [d for d in range(7) if (d >= 5) == weekend and d != t.dow]
        candidate_days = [t.dow] + [others[i] for i in rng.permutation(len(others))]
        days = []
        for d in candidate_days:
            day = acts[(acts["dow"] == d) & acts["student_id"].isin(pair)]
            clash = day[_overlaps(day, t.start, t.end)]
            if not any(_protected(r) for r in clash.itertuples()):
                days.append(d)
            if len(days) == TARGET_DAYS:
                break
        if len(days) < MIN_DAYS:
            continue

        protected = pd.Series([_protected(r) for r in acts.itertuples()], index=acts.index)
        drop = pd.Series(False, index=acts.index)
        for d in days:
            day_mask = (acts["dow"] == d) & acts["student_id"].isin(pair)
            # The feasibility check above guarantees nothing protected is in this window.
            drop |= day_mask & _overlaps(acts, t.start, t.end)
            if category == "dining":
                # Replace the friend's other meal around this time, but never an
                # existing routine or planted hangout.
                near_meal = (acts["activity_category"] == "dining") & (
                    (acts["start"] - t.start).abs() <= MEAL_REPLACE_WINDOW_MIN) & ~protected
                drop |= day_mask & near_meal
        assert not (drop & protected).any()

        new_rows = []
        for d in sorted(days):
            for s in pair:
                new_rows.append({
                    "event_id": f"{routine_id}_{s}_{d}", "student_id": s, "date": dates_by_dow[d],
                    "start_time": _hhmm(t.start), "end_time": _hhmm(t.end),
                    "activity_category": category, "venue_id": t.venue_id, "shared_event_id": "",
                    "start": t.start, "end": t.end, "dow": d, "routine_id": routine_id,
                    "flagged": False,
                })
        acts = pd.concat([acts[~drop], pd.DataFrame(new_rows)], ignore_index=True)
        record = {"routine_id": routine_id, "student_1": pair[0], "student_2": pair[1],
                  "leader": leader, "category": category, "venue_id": t.venue_id,
                  "start_time": _hhmm(t.start), "end_time": _hhmm(t.end),
                  "days": ";".join(dates_by_dow[d] for d in sorted(days)),
                  "removed_visits": int(drop.sum())}
        return acts, record
    return acts, None


def _pings(acts: pd.DataFrame, checkins: pd.DataFrame) -> pd.DataFrame:
    """Keep the original pings for surviving visits and generate pings for new ones."""
    coords = checkins.drop_duplicates("venue_id").set_index("venue_id")[["latitude", "longitude"]]
    kept = checkins[checkins["event_id"].isin(set(acts["event_id"]))]
    rows = []
    for r in acts[acts["routine_id"] != ""].itertuples():
        for i, m in enumerate(range(r.start, r.end, PING_MIN)):
            rows.append({
                "checkin_id": f"C_{r.event_id}_{i:03d}", "student_id": r.student_id,
                "timestamp": f"{r.date}T{_hhmm(m)}:00{TZ_SUFFIX}", "venue_id": r.venue_id,
                "latitude": coords.at[r.venue_id, "latitude"],
                "longitude": coords.at[r.venue_id, "longitude"],
                "activity_category": r.activity_category, "event_id": r.event_id,
                "quality_flag": "ok",
            })
    out = pd.concat([kept, pd.DataFrame(rows, columns=checkins.columns)], ignore_index=True)
    return out.sort_values(["student_id", "timestamp"]).reset_index(drop=True)


def build(src: Path, out: Path, fraction: float, seed: int = 0) -> pd.DataFrame:
    acts, checkins, edges = _prepare(src)
    dates_by_dow = acts.drop_duplicates("dow").set_index("dow")["date"].to_dict()
    order = np.random.default_rng(seed).permutation(len(edges))
    n_target = int(round(fraction * len(edges)))
    records = []
    for rank, e in enumerate(order[:n_target]):
        pair_rng = np.random.default_rng([seed, int(e)])
        acts, rec = _try_couple(acts, edges[e], pair_rng, f"RT{rank:04d}", dates_by_dow)
        if rec is not None:
            records.append(rec)

    out.mkdir(parents=True, exist_ok=True)
    act_cols = ["event_id", "student_id", "date", "start_time", "end_time",
                "activity_category", "venue_id", "shared_event_id", "routine_id"]
    acts = acts.sort_values(["student_id", "date", "start"]).reset_index(drop=True)
    acts[act_cols].to_csv(out / "activities_full.csv", index=False)
    _pings(acts, checkins).to_csv(out / "checkins_full.csv", index=False)
    for name in ("students_nodes.csv", "friendships_full.csv", "friendships.graphml"):
        shutil.copy(src / name, out / name)
    manifest = pd.DataFrame(records)
    manifest.to_csv(out / "routines.csv", index=False)
    return manifest


def validate(src: Path, out: Path) -> list[str]:
    """Return a list of problems with a built dataset (empty when it is clean)."""
    problems = []
    acts = pd.read_csv(out / "activities_full.csv", dtype=str, keep_default_na=False)
    acts["start"], acts["end"] = acts["start_time"].map(_minutes), acts["end_time"].map(_minutes)
    for (s, d), g in acts.sort_values("start").groupby(["student_id", "date"]):
        if (g["start"].to_numpy()[1:] < g["end"].to_numpy()[:-1]).any():
            problems.append(f"overlapping visits for {s} on {d}")
    src_acts = pd.read_csv(src / "activities_full.csv", dtype=str, keep_default_na=False)
    lost = set(src_acts.loc[src_acts["activity_category"] == "academic", "event_id"]) - set(acts["event_id"])
    if lost:
        problems.append(f"{len(lost)} classes were removed")
    lost = set(src_acts.loc[src_acts["shared_event_id"] != "", "event_id"]) - set(acts["event_id"])
    if lost:
        problems.append(f"{len(lost)} planted hangout visits were removed")
    chk = pd.read_csv(out / "checkins_full.csv", dtype=str)
    if set(chk["event_id"]) != set(acts["event_id"]):
        problems.append("check-ins and activities refer to different events")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the v2 datasets with friend routines.")
    ap.add_argument("--src", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--out-base", type=Path, default=DEFAULT_DATA_DIR.parent)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    for level, frac in LEVELS.items():
        out = args.out_base / f"v2_{level}"
        manifest = build(args.src, out, frac, args.seed)
        problems = validate(args.src, out)
        n_target = int(round(frac * len(pd.read_csv(args.src / "friendships_full.csv"))))
        cats = manifest["category"].value_counts().to_dict() if len(manifest) else {}
        print(f"{out.name}: coupled {len(manifest)} of {n_target} targeted friend pairs {cats}, "
              f"removed {manifest['removed_visits'].sum() if len(manifest) else 0} visits, "
              f"problems: {problems or 'none'}")


if __name__ == "__main__":
    main()
