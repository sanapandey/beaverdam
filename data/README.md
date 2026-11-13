# Datasets

Every dataset folder describes the same 100 synthetic students (S001 to S100) over
one week, from Monday 2026-10-05 to Sunday 2026-10-11, and all of them share the
same friendship graph of 239 undirected edges.

| Folder | What it is |
|---|---|
| `prelim/` | This is the team's preliminary dataset, copied unchanged from `beaverdam-prelim-dataset-100students-1week`. In it, friends overlap no more than strangers do in any category that a profile discloses. |
| `v2_weak/` | This is prelim plus shared routines for 56 friend pairs, out of the 60 targeted (25% of friendships). |
| `v2_medium/` | This is prelim plus shared routines for 111 of the 120 targeted friend pairs (50%). |
| `v2_strong/` | This is prelim plus shared routines for 159 of the 179 targeted friend pairs (75%). |

Do not edit the v2 folders by hand, because `python -m beaverdam.synth` rebuilds
them from `prelim/`.

## Files

`students_nodes.csv` has a single column, `student_id`, that lists every student.

`friendships_full.csv` has one row per friendship, with columns `student_id_1`
and `student_id_2`. `friendships.graphml` is the same graph in GraphML format, so
it can be opened in tools like NetworkX or Gephi.

`activities_full.csv` is the clean schedule, with one row per visit. Its columns
are listed below.

| Column | Meaning |
|---|---|
| `event_id` | This is a unique visit ID. IDs starting with `A_` are classes, `L_` are other activities, `SH` are planted hangouts, and `RT` are v2 routines. |
| `student_id` | This is the student who made the visit. |
| `date`, `start_time`, `end_time` | These give the local date and time (Eastern, UTC-4), with the end time exclusive. |
| `activity_category` | This is one of `academic`, `study`, `dining`, `gym`, or `leisure`. |
| `venue_id` | This is one of 30 venues, such as `ROOM_1-190`, `DINING_MASEEH`, `STUDY_HAYDEN`, `GYM_ZESIGER`, or `CAFE_TEADO`. |
| `shared_event_id` | This is set only for the 43 planted hangouts, and the two friends at a hangout share the same ID. |
| `routine_id` | This column exists only in v2. It is set for visits added as a shared friend routine, and it matches `routines.csv`. |

`checkins_full.csv` holds the GPS pings that a deployed app would collect, and it
is what the algorithms actually read. Each visit produces one ping every 15
minutes from its start time, stopping before its end time. Its columns are
`checkin_id`, `student_id`, `timestamp` (ISO 8601 with the offset), `venue_id`,
`latitude`, `longitude`, `activity_category`, `event_id` (which links back to
`activities_full.csv`), and `quality_flag`. The flag is `ok` for 13,821 of the
13,880 prelim pings. The rest are marked `outside_opening_hours` or
`insufficient_travel_time`, and the loader drops them as implausible.

`routines.csv` exists only in v2 and lists every shared routine that was added.
Each row gives the two friends, which friend's existing visit was used as the
template (`leader`), the category, the venue, the time, the days, and how many
clashing visits were removed to make room.

## How the v2 routines are added

For each targeted friend pair, the generator chooses dining or study at random
and takes one of the leader's existing visits in that category as a template.
It then looks for up to three days of the same day type (weekday or weekend) on
which neither friend has a class, an existing routine, or a planted hangout
within 15 minutes of that time. If it finds at least two such days, it removes
any other non-academic visits either friend had in that window, and for dining
it also removes any other meal within two hours. Then it adds the shared visit
for both friends on those days. Pairs with fewer than two free days are skipped,
which is why slightly fewer pairs are coupled than are targeted.

Pairs are processed in a fixed random order, so the weak pairs are a subset of
the medium pairs, which are in turn a subset of the strong pairs. Classes and
planted hangouts are never moved, no visits overlap, and every unchanged visit
keeps its original pings. `tests/test_matching.py` checks all of these
properties.
