# BeaverDam — interactive student application + real matching demo

MIT 6.1850 research prototype. The UI is a responsive React/TypeScript app based on Section 3 of the BeaverDam report. A FastAPI demonstration server connects it to the team's original `beaverdam/matching.py`, `profiles.py`, and slot-building code, using **synthetic** V2 datasets. This is a **course prototype, not a production student-tracking system**.

## Quickstart

Requirements: Python 3.10+ and Node.js 20.19+ (or 22.12+).

**Terminal 1 — Python API** (run from the project root):

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

Check the API at http://127.0.0.1:8000/api/v1/health or explore its docs at http://127.0.0.1:8000/docs.

**Terminal 2 — React UI**:

```bash
npm install
cp .env.example .env.local  # Windows: copy .env.example .env.local
npm run dev
```

Open http://localhost:5173. (Use exactly `localhost` on the frontend for the demo CORS configuration.) The `.env.example` contains `VITE_API_URL=http://127.0.0.1:8000`. If it is missing, the frontend intentionally falls back to an *illustrative, disconnected* UI fixture mode; for computed matches **start both servers**.

## Walkthrough for a final presentation

1. Open **Discover** and demonstrate the ten top-ranked candidates from the normalized gap-aware scorer. Only coarse match labels and broad category names are returned; no individual venue, time or exact score appears.
2. Switch between **V2 weak**, **V2 medium**, and **V2 strong** in the visible research-prototype bar. These synthetic datasets were uploaded with the project, and the backend recomputes from each one's actual check-ins.
3. Open **Privacy** and select P1, P2, P3, or P4. Return to Discover to see the newly computed recommendation list. Fine-grained category switches also recompute matches.
4. Open **My routine**. See the selected synthetic student's observed activities. Withhold or remove an existing activity to exclude its matching check-ins. Manually added activities are **personal organizer notes only** until there is check-in evidence and thus do not create synthetic visits.
5. In **Connections**, send a request to a recommended synthetic student. Switch the demo account to the recipient's `S###` ID in the top banner, accept the incoming request, and return to the original student. Both sides now appear mutually connected. Open **Message**, send a note, switch to the other account, and reopen the thread to see and reply to the message. Messages persist in a local demo JSON file; they are **not secure or authenticated production messaging**. Use **Refresh** to fetch new replies (no real-time push).
6. **Privacy → Blind zones** accepts *exact synthetic venue IDs* (e.g. `STUDY_HAYDEN`) or a 24-hour time range `HH:MM–HH:MM`. These filters remove affected check-ins from the matching input for that student in the demo. Ambiguous place names aren't interpreted; these controls are **not a device-local location privacy implementation**.

## Real vs simulated

| Feature | Implementation |
|---|---|
| Score computation | **Real:** original team's `gap_aware_normalized_scores`, disclosed visit matrix, `tau=32` demo configuration |
| Dataset data | **Real synthetic data:** V2 weak / medium / strong `checkins_full.csv`, `activities_full.csv`, friendships and student IDs |
| Profile choices | **Real:** exact P1–P4 category combinations from `profiles.py` |
| Withholding | **Functional within demo:** removes withheld categories/events/exact venue and time zones from the *computed* dataset prior to scoring |
| Existing-friend exclusion | **Real:** friendships in dataset excluded |
| Recommendation labels | **Demo policy:** top ten split into rank bands 3 Strong / 4 Moderate / up to 3 Weak, random order within band; **not** calibrated θ thresholds or an evaluated security mechanism |
| Population baseline | **Real:** original normalized gap-aware algorithm |
| Tau selection | **Fixed at 32 for responsiveness**; not individually tuned on held-out friendship edges |
| Student profile names, interests and years | **Placeholders:** original data contains only `S###` IDs; do not invent personal biographical data |
| Connection requests | **Functional local simulated state:** reciprocation requires two demo account selections; no authentication |
| Messaging | **Functional synthetic messaging:** send, read and persist two-way conversations only after mutual acceptance; locally saved, no push notifications, end-to-end encryption or real authentication |
| Manual routine creation | **UI/personal organizer only**; does not fabricate GPS observations for matching |
| MIT SSO, verified identity, native location filter, secure revocation | **Not implemented** |
| Privacy attacks / exact/category output policy evaluations | **Not implemented by uploaded Python research prototype** |

> **Critical privacy boundary:** This backend holds a full **synthetic** check-in dataset on the server and applies filters to build a safe demonstration *matching input*. The report's intended privacy guarantee is stronger: real devices must filter before uploads, and servers must delete previously permitted records on revocation. Never deploy this API with real user data or expose it to the public internet. The API's "switch student" endpoint is intentionally **not authenticated** for presentation use only.

## Data provenance

`data/v2_weak` uses uploaded `(1)` activities/check-ins, `data/v2_medium` uses `(2)`, and `data/v2_strong` uses `(3)`; shared `students_nodes.csv` and `friendships_full.csv` accompany each dataset. All files are synthetic. The original `prelim` check-in file was **not provided**, so no partial preliminary dataset is presented as complete. Results CSVs are not required for the student interface; they belong to the evaluation workflow.

## Tests

```bash
PYTHONPATH=. pytest -q tests/test_demo_api.py tests/test_messaging.py
PYTHONPATH=. pytest -q tests/test_evaluate.py -k 'metric_definitions or fairness_gap or paired_vs_baseline'
npm run build
```

`npm run build` requires installed Node dependencies. Python tests run against the local FastAPI API via an isolated temporary state file.

## Structure

```text
src/                  React frontend (Discover, Routine, Privacy, Connections)
server.py             Local FastAPI demo adapter and output controller
beaverdam/            Original team data, profiles, matching and evaluation Python modules
data/v2_{weak,medium,strong}/  Original synthetic visits, check-ins and friendships
requirements.txt      Python dependencies
.env.example          Frontend API endpoint
tests/                API + original algorithm tests
```

The demo state (including chat messages) is stored in `.beaverdam-demo-state.json`, which is generated on the API's first mutation and can be deleted to reset all accounts. It stores preferences, connection edges, chat messages and personal organizer notes, not raw check-in uploads. Chat messages are plain text, so **never use this app for real conversations or real user data**. For consistency, switch datasets only as a research operation; the same synthetic student IDs exist across the three variants.
