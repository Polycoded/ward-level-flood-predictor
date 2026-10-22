# Demo script (≈6 min)

Run the live stack (backend + `npm run preview`). If the backend is down, the header says **Mock data**: say so out loud and keep going. Never present mock numbers as real.

Before going on stage:
- [ ] Header shows **Live API**
- [ ] Browser zoom at 100%, window ≥ 1280 px wide, notifications off
- [ ] Open-Meteo reachable (Forecast tab → Fetch works)
- [ ] `validation_metrics.json` committed, so the **Validation** button is visible
- [ ] Phone ready with WhatsApp open, for the share-link moment

---

## Act 1: The decision gap (60 s)

> *(Optional 15-second personal hook, in your own words.)*
>
> "On 4 December 2023, Cyclone Michaung parked over Chennai. IMD's warning said *heavy to extremely heavy rain over Chennai*. That is one sentence for 200 wards. The Corporation still had to decide where pumps and boats go first, and it did that ward by ward, after the WhatsApp complaints came in."

1. Point at the empty map: "This is what an official has before the rain: a city-wide number."
2. Rainfall panel → **100 mm** preset, **3 hours** → **Analyze**.
3. The map re-colours and the ranking fills in. Read the top three wards aloud from the list.
4. "Every ward now has a level, a likely water depth and a peak time. That is the decision we are trying to support."

## Act 2: Why this ward? (60 s)

1. Click the top-ranked ward. The detail drawer opens.
2. Read the risk card: level, *"15–50 cm (knee)"*, *"peak ~4 h from now"*.
3. Scroll to **Why this ward?**: "Each bar is one physical factor, weighted exactly as in our model: low ground, paved surface, flat terrain, distance to the river. Score out of 100, then rainfall scales it."
4. Point at **Model reasons**: "Plain-language reasons an engineer can check against the ground."

## Act 3: Did it work in December 2023? (90 s)

1. Rainfall → **300 · Dec 2023** preset → **Analyze**.
2. Header → **Validation**.
3. Read *precision@20*, *recall* and false positives **from the panel, not from memory**.
4. Name one false positive and why it happened (Mit owns this story; see `docs/validation.md`).
5. "We report our misses, because a tool officials will trust has to show them."

## Act 4: Alerts and the last mile (90 s)

1. With the ward still open → **Draft alerts for this ward**.
2. Toggle **தமிழ் (Tamil)** → **Generate**. Show the SMS character counter and the channel status cards.
3. **Open in WhatsApp** on the phone: "The official picks the group; the link never pre-addresses a number."
4. Sidebar → **Roads & underpasses**: "Traffic police see which underpasses to close first."
5. Sidebar → **Shelters**: nearest named schools and halls from OpenStreetMap, walking time, a directions link.

## Act 5: Planning, not just response (45 s)

1. Map top-right → **+30% built-up**.
2. Read the delta line: *"N wards move up a risk level."*
3. "Same storm, more concrete. This is the conversation a planning department needs before approving the next layout."

## Close (15 s)

> "Open data, runs on a free tier, results in under two seconds. Any Indian city with ward boundaries and an elevation model can switch this on."

---

### If something breaks

| Problem | Say / do |
| --- | --- |
| Header shows **Mock data** | "The backend is offline, so this is our synthetic offline mode; the scoring is identical." Carry on. |
| Validation button missing | Show `docs/validation.md` on screen. |
| Forecast fetch fails | Use the Manual tab; the error message explains it. |
| Map tiles slow | The ranking and detail drawer work without tiles; keep talking over them. |
