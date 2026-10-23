# Honest screening demo — manual sequence

Start the backend from the repository root (`uvicorn api.main:app --port 8000`) and
the web dev server (`cd web && npm run dev`) using the existing environment. Confirm
the header says **Live API**. If it says **Mock data**, disclose synthetic grid wards;
do not present them as Chennai measurements. Network services may be unavailable.

1. Choose Manual → **100** mm, **3 h**, then Analyze. Explain that this is a hypothetical
   uniform accumulation, not a measured city-wide event. The **300 · Hypothetical** preset
   is another manual sensitivity input, not December 2023 attribution.
2. Read the ward index/category and shared model reasons. Explain the hand-chosen weights
   and uncalibrated duration heuristic. No flood probability, physical depth or peak time
   is established. Ward/internal IDs differ from official ward numbers.
3. Repeat 100 mm at **12 h**, Analyze, then draft alerts for a selected ward. Generate a
   preview and show **100mm/12h** in the message. Generation is not delivery: SMS, voice
   and LiveKit require separately verified integrations. WhatsApp is a user-mediated
   share action, not proof of recipient delivery. Tamil wording needs native review.
4. Open Validation. Current canonical mock metrics must render **unavailable**, not
   accuracy percentages. Partial/evaluated schema-2 results describe observed-sample
   eligibility/coverage, not independently verified representative accuracy. No historical
   labels or completed evaluation are claimed. Research station candidates remain separate.
5. Open Roads & underpasses: show **uncalibrated screening**, requiring human review,
   not an automatic closure/diversion or water-depth prediction. The road endpoint currently
   retains its own default rainfall-duration behavior; do not equate road screening to a
   duration-aware hydraulic forecast.
6. Optionally open Shelters. Presence, capacity, opening status and route safety are not
   certified. An empty live layer is legitimate. Do not promise available accommodation
   or validated walking times based on this demo.
7. Compare +15%/+30% built-up with the same rainfall/duration for planning sensitivity.
   Alert drafts remain baseline land use, not that built-up scenario. Return to baseline
   before comparing alert categories with map categories.

Close: this is transparent prioritization mechanics and an evidence-review workflow,
not a validated emergency-warning system. Do not claim historical metrics, measured latency,
production notification delivery or plug-and-play accuracy in another city.

If tiles/network/forecast fail, use manual inputs and disclose the failure. Automated tests
and a successful build do not establish live-browser, source-quality or safety acceptance.
