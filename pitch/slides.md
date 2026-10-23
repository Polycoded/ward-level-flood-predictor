# Pitch: Ward-Level Urban Flood Predictor

Target length: 6 minutes plus Q&A. One idea per slide. Numbers in **[brackets]** must be filled from committed artifacts before presenting; never estimate them on stage.

---

## 1. Title (10 s)

**Which Chennai wards are most at risk from the rain that's coming.**
Ward-level flood risk from a rainfall forecast, in under two seconds.
Team: John · Mit · Ronit

---

## 2. The decision gap (45 s), Criterion 1

- IMD forecasts are city-wide; the Corporation acts **ward by ward** (200 wards).
- Pumps, boats, traffic diversions and relief camps get deployed **after** complaints arrive.
- Residents have no way to know whether *their* ward is at risk tonight.

> Visual: one IMD warning sentence beside a map of 200 ward outlines.

---

## 3. What we built (30 s)

Rainfall in, ward risk out:

1. **Input**: forecast mm (manual, CSV, or live Open-Meteo)
2. **Score**: every ward gets a risk level and a 0–100 index, plus indicative depth and timing bands
3. **Act**: ranked list, English and Tamil alerts, underpass closures, nearest shelters

> Visual: screenshot of the dashboard after a 100 mm run.

---

## 4. Data and features (45 s), Criterion 2

| Layer | Source | Per-ward feature |
| --- | --- | --- |
| Ward boundaries | OpenStreetMap (GCC, admin level 10) | area |
| Elevation | SRTM 30 m | mean / min elevation, slope |
| Land cover | ESA WorldCover 10 m | % built-up, % green, % water |
| Water and roads | OpenStreetMap | distance to river or canal, road density, underpasses |
| Critical assets | OpenStreetMap | hospitals, schools, pumping stations, shelters per ward |

`features.parquet`: [N] wards × [M] features, schema in `docs/data_sources.md`.

---

## 5. The model (45 s), Criterion 3

- A weighted hydrological index, chosen over ML because labels are scarce and officials must be able to **audit** it.
- Weights: elevation 25%, impervious 25%, slope 15%, water proximity 15%, road density 10%, underpasses 10%.
- Rainfall (scaled for storm duration) multiplies the static susceptibility into an uncalibrated 0–1 index.
- Depth and peak bands are display proxies, not hydraulic predictions; say so if asked.
- Every score comes with factual `reasons[]`.

> Visual: the "Why this ward?" bar chart from the app.

---

## 6. Validation: December 2023 (60 s), Criterion 3

Cyclone Michaung, 3–4 Dec 2023. Labels from Sentinel-1 SAR flood extent and news reports ([n] wards).

| Metric | Value |
| --- | --- |
| Precision@20 | **[from Mit's evaluation run; the current validation_metrics.json is a placeholder]** |
| Recall | **[ ]** |
| False positives | **[ ]**: explain one |

> Be explicit about what we missed and why.

---

## 7. Explainability (30 s), Criterion 5

- Factor contributions shown next to the model's reasons for every ward.
- Assumptions documented in `docs/assumptions.md` (shelter capacities, depth bands, rainfall scaling).
- The UI labels its data source (**Live API** vs **Mock data**) and its rainfall provider.

---

## 8. Alerts and the last mile (45 s), Criterion 4

- One click: an SMS-length English and Tamil message, plus a WhatsApp share link.
- The official chooses the recipients; the app never sends to a number from the server.
- Underpass layer for traffic police; nearest shelters with walking time.

---

## 9. Planning scenario (30 s), Criterion 6

- **+15% / +30% built-up** with the same storm: "[N] wards move up a risk level."
- Gives planners a number to argue with before approving more paving.

---

## 10. Adoption (30 s), Criterion 6

- Open data only, so any city with ward boundaries and a DEM can switch it on.
- Runs on free tiers: FastAPI on Render, React on Vercel, CI on GitHub Actions.
- A new rainfall input returns in under 2 s. Works offline in demo mode.
- Next: IMD gridded rainfall feed, Corporation complaint data as labels, more cities.

---

## 11. Close (10 s)

**From "heavy rain over Chennai" to a ward-level priority list: which wards first, which underpasses to watch, which schools to open as shelters.**

---

### Q&A owners

| Topic | Owner |
| --- | --- |
| Data sources, GIS, deployment, CI | John |
| Model, weights, validation, false positives | Mit |
| UI/UX, alert flow, accessibility, security of the frontend | Ronit |
| Scenario and planning | Mit and Ronit |

Likely UI and alert questions, with short answers:

- *Why not send SMS directly?* Twilio is wired on the backend; the dashboard drafts and the official approves. A human stays in the loop for public warnings.
- *How do you stop a malicious link in an alert?* Only number-less https WhatsApp share links are opened; everything else is rebuilt from the message text. Covered by tests.
- *Does it work on a phone?* Yes. The list slides away after Analyze so the map shows first. Lighthouse accessibility scores 100.
- *What if the backend is down mid-demo?* The app switches to a labelled offline mode with the same scoring.
