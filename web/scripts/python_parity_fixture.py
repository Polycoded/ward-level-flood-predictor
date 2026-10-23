"""Regenerate web/src/test/python_engine_cases.json from model/risk_engine.py.

Run from the repo root:  python web/scripts/python_parity_fixture.py
The frontend test lib/explain.test.ts compares its scoring against these outputs.
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from model.risk_engine import score_ward  # noqa: E402

CASES = [
    dict(elevation_mean=2.2, slope_mean=1.4, impervious_frac=0.78, water_frac=0.13,
         dist_to_water_m=553, road_density_km_per_sqkm=17.3, underpass_count=1),
    dict(elevation_mean=18.0, slope_mean=4.0, impervious_frac=0.35, water_frac=0.02,
         dist_to_water_m=3200, road_density_km_per_sqkm=6.0, underpass_count=0),
    dict(elevation_mean=6.5, slope_mean=0.9, impervious_frac=0.92, water_frac=0.05,
         dist_to_water_m=120, road_density_km_per_sqkm=19.5, underpass_count=2),
]
# (rainfall mm, built-up increase %, duration h)
SCENARIOS = [
    (50, 0, 3), (100, 0, 3), (200, 0, 3), (300, 0, 3), (100, 30, 3),
    (100, 0, 1), (150, 0, 12), (150, 15, 12), (200, 0, 24),
]

out = []
for features in CASES:
    for rainfall_mm, builtup, hours in SCENARIOS:
        score, level, depth, peak, _ = score_ward(pd.Series(features), rainfall_mm, builtup,
                                                  duration_hours=hours)
        out.append(dict(features=features, rainfall_mm=rainfall_mm, builtup=builtup,
                        duration_hours=hours,
                        risk_score=round(float(score), 10), risk_level=level.value,
                        depth_band=depth.value, peak=peak))

target = ROOT / "web/src/test/python_engine_cases.json"
target.write_text(json.dumps(out))
print(f"wrote {len(out)} cases to {target.relative_to(ROOT)}")
