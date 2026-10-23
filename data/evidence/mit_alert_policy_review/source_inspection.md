# Primary rainfall inspection — not an adopted ward input

Accessed 2026-10-23. IMD All India Weather Summary and Forecast Bulletin:
https://ndrf.nrsc.gov.in/documents/daily_product/weather_forecast_pdf/2023/2023-12-04/2023_12_04_13_36_13_allindianew.pdf

Retrieved PDF: 2,705,719 bytes; 13 pages; SHA-256
`526d1c1fb5bfb16b369510c29521932ea91d76ce96b23c9762302227f1a5a9fd`.
Read using existing `pypdf.PdfReader`, physical pages 1–2 (zero-based indices 0–1).
This was text extraction/inspection, **not visual page verification**. Initial web-fetch
could not process application/pdf; subsequent urllib download and pypdf succeeded.
The PDF remains in temporary working storage, not a canonical dataset.

Page 1: “Monday, December 04, 2023”; “Time of Issue: 1330 hours IST”.
Page 2, Main Weather Observations: “Significant Rainfall recorded (from 0830 hours
IST of yesterday to 0830 hours IST of today): (in cm)”. Entries include
“Alandur (dist Chennai), Chennai (AP) (dist Chennai) 25 each” and
“Chennai (N) (dist Chennai) 23”.

Thus the interval is December 3 08:30 IST to December 4 08:30 IST, 24 hours;
25 cm × 10 = 250 mm and 23 cm × 10 = 230 mm. Preserve published precision.
These are two **station** candidates: no gauge coordinates inferred, no spatial
interpolation, no city/ward-wide adoption, no selection of the larger total as truth.
Issue time is later than the observation interval, not its start/end.

Supplied local research was also read:
`/Users/mitku/Documents/ChatGPT/ZeroShot Hackathon/research/chennai_2023/rainfall_review.md`.
Its station totals and interval agree with this independent primary-text inspection.
Existing incomplete event metadata, unresolved observation candidates and header-only
reviewed labels under `data/evidence/chennai_2023/` were not edited or promoted.

Remaining evidence requirements are enumerated in `historical_status.json`.
Verified rainfall text alone cannot justify running historical accuracy metrics.
