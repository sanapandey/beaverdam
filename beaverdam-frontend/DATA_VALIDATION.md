# Dataset validation — V2 synthetic datasets

Validation performed on the included CSVs. All three datasets passed these checks:
- Required student/event/check-in identifiers and referenced students exist.
- Unique event IDs, check-in IDs, and undirected friendship edges; no self-friendship links.
- Activity and check-in event IDs match exactly, and event ownership, venue and category agree.
- Valid activity date/time windows and check-in timestamps; every ping falls inside its event's date and half-open time window.
- No overlapping scheduled activities for the same student/day.
- Activity categories are within academic, study, dining, gym, leisure.
- The bundled `beaverdam.synth.validate()` also returned no problems for each V2 dataset.

| Dataset | Students | Friendships | Activities | GPS check-ins | Flagged GPS pings | Issues |
|---|---:|---:|---:|---:|---:|---|
| v2_weak | 100 | 239 | 3,342 | 13,880 | 59 | None found |
| v2_medium | 100 | 239 | 3,398 | 14,192 | 55 | None found |
| v2_strong | 100 | 239 | 3,437 | 14,408 | 55 | None found |

Flagged pings are present by design and skipped by the data loader (`quality_flag != "ok"`). These validations establish internal structure, **not** empirical representativeness, realistic causal assumptions, data privacy, or prediction quality.

The *preliminary* activities file was uploaded, but not a complete preliminary check-in file, so prelim is not bundled as a selectable working dataset.

The V2 weak activity CSV does not have a `routine_id` column (unlike medium and strong), but the matcher and frontend use the event, category and venue fields and do not require `routine_id`. Its presence/absence should be addressed if you want to use all versions with a uniform routines-manifest analysis.
