"""Load the prelim dataset and turn GPS check-ins into (venue, hour-of-week) slots.

A slot is keyed by (venue, hour_of_week, category). The category is part of the
key because three cafes are tagged "dining" on some visits and "leisure" on
others, and the gap-aware method needs every slot to belong to exactly one
category (kappa(s) in the proposal).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

CATEGORIES: tuple[str, ...] = ("academic", "study", "dining", "gym", "leisure")
CAT_INDEX = {c: i for i, c in enumerate(CATEGORIES)}

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "prelim"


@dataclass(frozen=True)
class SlotData:
    """Full-information visit matrix for every student.

    X[u, s] is True when student u was observed in slot s. slot_cat[s] is the
    index into CATEGORIES of slot s. This object holds everything, including
    categories a student will later withhold, so it must only be passed to an
    algorithm after `disclose` has been applied.
    """

    students: list[str]
    slots: list[tuple[str, int, str]]
    X: np.ndarray  # bool, shape (n_students, n_slots)
    slot_cat: np.ndarray  # int, shape (n_slots,)

    @property
    def n_students(self) -> int:
        return len(self.students)


def _hour_of_week(ts: str) -> int:
    t = datetime.fromisoformat(ts)
    return t.weekday() * 24 + t.hour


def load_checkins(data_dir: Path = DEFAULT_DATA_DIR, *, drop_flagged: bool = True,
                  drop_shared_events: bool = False) -> pd.DataFrame:
    """Read check-ins, optionally dropping implausible pings and planted hangouts.

    Shared events are identified by joining each check-in's event_id against the
    activities file, whose shared_event_id column marks the planted friend
    hangouts.
    """
    df = pd.read_csv(data_dir / "checkins_full.csv")
    if drop_flagged:
        df = df[df["quality_flag"] == "ok"]
    if drop_shared_events:
        acts = pd.read_csv(data_dir / "activities_full.csv")
        shared_ids = set(acts.loc[acts["shared_event_id"].notna(), "event_id"])
        df = df[~df["event_id"].isin(shared_ids)]
    unknown = set(df["activity_category"]) - set(CATEGORIES)
    if unknown:
        raise ValueError(f"unexpected categories in check-ins: {sorted(unknown)}")
    return df.reset_index(drop=True)


def load_students(data_dir: Path = DEFAULT_DATA_DIR) -> list[str]:
    return sorted(pd.read_csv(data_dir / "students_nodes.csv")["student_id"])


def load_friendships(data_dir: Path = DEFAULT_DATA_DIR) -> list[tuple[str, str]]:
    df = pd.read_csv(data_dir / "friendships_full.csv")
    return [tuple(sorted(p)) for p in zip(df["student_id_1"], df["student_id_2"])]


def build_slots(checkins: pd.DataFrame, students: list[str]) -> SlotData:
    how = checkins["timestamp"].map(_hour_of_week)
    keys = list(zip(checkins["venue_id"], how, checkins["activity_category"]))
    slots = sorted(set(keys))
    slot_index = {k: i for i, k in enumerate(slots)}
    stu_index = {s: i for i, s in enumerate(students)}

    X = np.zeros((len(students), len(slots)), dtype=bool)
    rows = checkins["student_id"].map(stu_index).to_numpy()
    cols = np.fromiter((slot_index[k] for k in keys), dtype=int, count=len(keys))
    X[rows, cols] = True
    slot_cat = np.array([CAT_INDEX[cat] for _, _, cat in slots], dtype=int)
    return SlotData(students=students, slots=slots, X=X, slot_cat=slot_cat)


def load_slot_data(data_dir: Path = DEFAULT_DATA_DIR, *, drop_shared_events: bool = False) -> SlotData:
    students = load_students(data_dir)
    checkins = load_checkins(data_dir, drop_shared_events=drop_shared_events)
    return build_slots(checkins, students)
