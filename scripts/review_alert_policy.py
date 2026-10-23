"""Reproduce local Exercise evidence without networking or canonical-data writes.

Run from repository root: python -m scripts.review_alert_policy
The fixed output directory is reserved for this package's generated review artifacts.
"""
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import force_2d
from shapely.geometry import box

from model.alert_contract import digest
from model.alert_rules import evaluate_alerts
from model.alerts import exercise_message
from model.cap import generate_cap
from model.forecast_input import aggregate_forecast
from model.ward_lookup import compare_simplification, lookup_ward

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/evidence/mit_alert_policy_review"
NOW = "2000-01-01T00:00:00+00:00"
POLICY = {"version": "artificial-policy-v1", "model_version": "six-feature-source-hash-in-manifest",
          "trigger_score": .25, "release_score": .2, "escalation_score": .6,
          "cooldown_seconds": 3600, "expiry_seconds": 7200, "min_rainfall_mm": 10,
          "max_candidates": 2}
ROW = {"ward_id": 1, "ward_number": "168", "ward_name": "ARTIFICIAL feature fixture",
       "elevation_mean": 10., "slope_mean": 2., "impervious_frac": .5,
       "dist_to_water_m": 1000., "road_density_km_per_sqkm": 5., "underpass_count": 0}


def rain(mm, hours=3):
    end = datetime(2000, 1, 1, tzinfo=UTC) + timedelta(hours=hours)
    return {"kind": "manual_scenario", "source": "artificial:review-only", "rainfall_mm": mm,
            "duration_hours": hours, "interval_start": NOW, "interval_end": end.isoformat()}


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = {}

    def run(name, forcing, *, state=None, now=NOW, rows=None,
            interpretation="Synthetic mechanics scenario; not an observed dry day or historical validation"):
        args = (rows if rows is not None else [ROW], forcing, POLICY, state or {})
        result = evaluate_alerts(*args, now=now)
        assert result == evaluate_alerts(*args, now=now), "Nondeterministic repeat"
        eligible = result["candidates"] + result["overflow"]
        summary = {"candidate_count": len(result["candidates"]), "overflow_count": len(result["overflow"]),
            "suppression_count": len(result["suppressed"]),
            "release_count": sum(e["reason"] == "released" for e in result["lifecycle"]),
            "escalation_count": sum(c["policy_level"] == "escalation" for c in eligible),
            "escalation_transition_count": sum(c["cause"] == "escalation" for c in eligible)}
        cases[name] = {"interpretation": interpretation,
            "input": {"wards": args[0], "rainfall": forcing, "policy": POLICY,
                      "prior_state": args[3], "now": now}, "output": result, "summary": summary}
        return result

    for name, mm, hours in (("dry", 0, 3), ("low", 50, 3), ("trigger", 100, 3),
                             ("heavy", 300, 3), ("short_duration", 100, 1), ("long_duration", 100, 24)):
        run(name, rain(mm, hours))
    state = cases["trigger"]["output"]["proposed_state"]
    run("deduplicated", rain(100), state=state, now="2000-01-01T01:30:00Z")
    run("cooldown", rain(110), state=state, now="2000-01-01T00:30:00Z")
    run("cooldown_elapsed", rain(110), state=state, now="2000-01-01T01:00:00Z")
    run("escalation_bypasses_cooldown", rain(300), state=state, now="2000-01-01T00:01:00Z")
    run("hysteresis", rain(75), state=state)
    released = run("release", rain(50), state=state)
    run("released_reentry", rain(100), state=released["proposed_state"])
    run("expired_reentry", rain(100), state=state, now="2000-01-01T02:00:00Z")
    run("expired_below_trigger", rain(75), state=state, now="2000-01-01T02:00:00Z")
    rows = [{**ROW, "ward_id": i, "ward_number": str(171-i)} for i in (3, 1, 2)]
    overflow = run("overflow", rain(100), rows=rows)
    run("overflow_retry", rain(100), rows=rows, state=overflow["proposed_state"])
    forecast = aggregate_forecast(
        [{"interval_end": f"2000-01-01T0{i}:00:00Z", "precipitation_mm": 40} for i in (1, 2, 3)],
        interval_start=NOW, interval_end="2000-01-01T03:00:00Z", issued_at=NOW, retrieved_at=NOW,
        valid_from=NOW, valid_until="2000-01-01T03:00:00Z", now=NOW,
        source="artificial:preceding-hour", max_age_seconds=3600, max_retrieval_age_seconds=1800)
    run("exact_forecast", forecast)
    features = pd.read_parquet(ROOT / "data/processed/features.parquet")[list(ROW)].copy()
    features["ward_number"] = features["ward_number"].astype(str)
    canonical_rows = features.to_dict("records")
    for name, mm in (("canonical_synthetic_dry", 0), ("canonical_synthetic_low", 5),
                     ("hypothetical_uniform_station_230mm_24h", 230),
                     ("hypothetical_uniform_station_250mm_24h", 250)):
        forcing = rain(mm, 24)
        forcing["source"] = "hypothetical_uniform_sensitivity:not_adopted_ward_rainfall"
        run(name, forcing, rows=canonical_rows,
            interpretation="Existing canonical features; hypothetical uniform rainfall at fixed artificial clock. "
                "230/250 mm are station-candidate sensitivity totals only, not adopted ward rainfall. "
                "0/5 mm are synthetic controls, not observed dry days. No labels or historical validation.")
    write("scenarios.json", {"claim": "Artificial mechanics, not warning effectiveness", "cases": cases})
    write("scenario_summary.json", {
        "claim": "Scenario counts only; no observed negatives, false-alarm rates or historical metrics",
        "count_definitions": {"candidate_count": "Selected pending candidates",
            "overflow_count": "Eligible candidates deferred without state advancement",
            "suppression_count": "Ward suppression decisions",
            "release_count": "Released prior-state lifecycle events, not all-clears",
            "escalation_count": "Selected plus overflow candidates at escalation policy level",
            "escalation_transition_count": "Selected plus overflow candidates bypassing cooldown on active escalation"},
        "cases": {name: {"interpretation": case["interpretation"], **case["summary"]}
                  for name, case in cases.items()}})
    # Reproducible end-to-end example: exact forecast -> pending state -> content -> CAP.
    candidate = cases["exact_forecast"]["output"]["candidates"][0]
    # Synthetic geometry is conspicuously isolated from canonical geographic diagnostics.
    synthetic = gpd.GeoDataFrame({"ward_id": [1], "ward_number": ["168"]},
                                geometry=[box(400000, 1450000, 400100, 1450100)], crs=32644)
    messages = {}
    for language in ("en", "ta"):
        content = exercise_message(candidate, exercise_id="ARTIFICIAL-REVIEW", language=language)
        approval = {"status": "approved", "cancelled": False, "candidate_id": candidate["candidate_id"],
                    "content_digest": digest(content), "approved_by": "ARTIFICIAL reviewer fixture",
                    "approved_at": NOW}
        cap = generate_cap(candidate, content, approval, synthetic, sender="exercise.invalid", sent=NOW, now=NOW)
        if cap["status"] != "exported":
            raise RuntimeError(cap)
        (OUT / f"artificial_{language}.xml").write_text(cap["xml"] + "\n", encoding="utf-8")
        messages[language] = {"content": content, "approval_fixture": approval,
                              "xsd_status": cap["validation"]["status"], "geometry": "ARTIFICIAL rectangle, not ward targeting"}
    write("messages.json", messages)
    full = gpd.read_file(ROOT / "data/processed/wards.geojson")
    crosswalk = pd.read_csv(ROOT / "data/processed/ward_crosswalk.csv", dtype={"ward_number": str})
    identities = crosswalk[["ward_id", "ward_number"]].to_dict("records")
    if "ward_number" not in full:
        full = full.merge(crosswalk[["ward_id", "ward_number"]], on="ward_id", validate="one_to_one")
    full["ward_number"] = full["ward_number"].astype(str)
    original_lookup = lookup_ward(full, full.geometry.iloc[0].representative_point(),
        point_crs=str(full.crs), expected_identities=identities)
    # Explicit diagnostic-only dimension reduction, never a source repair or approval.
    diagnostic_full = full.copy()
    diagnostic_full.geometry = full.geometry.map(force_2d)
    projected = diagnostic_full.to_crs(32644)
    simplified = projected.copy()
    simplified.geometry = projected.geometry.simplify(10, preserve_topology=True)
    diagnostics = {"claim": "Supplied geometry only; no boundary approval or repair",
        "original_geometry_probe": original_lookup,
        "derived_copy": "Explicit in-memory force_2d then EPSG:32644, diagnostic only; canonical inputs unchanged",
        "simplification_10m": compare_simplification(projected, simplified, expected_identities=identities, tolerance_m=10),
        "representative_point_lookups": [], "holed_ward_ids": []}
    for _, row in projected.iterrows():
        parts = [row.geometry] if row.geometry.geom_type == "Polygon" else list(row.geometry.geoms)
        if any(len(p.interiors) for p in parts):
            diagnostics["holed_ward_ids"].append(int(row.ward_id))
        diagnostics["representative_point_lookups"].append({"probe_internal_ward_id": int(row.ward_id),
            "result": lookup_ward(projected, row.geometry.representative_point(), point_crs="EPSG:32644",
                expected_identities=identities)})
    write("lookup_diagnostic.json", diagnostics)
    inputs = [p for folder in ("data/raw", "data/processed", "data/evidence/chennai_2023")
              for p in (ROOT / folder).rglob("*") if p.is_file()]
    inputs += [ROOT / p for p in ("model/risk_engine.py", "model/validation.py", "model/evaluation_runner.py",
                                 "model/alert_rules.py", "model/forecast_input.py", "model/alerts.py",
                                 "model/alert_contract.py", "model/cap.py", "model/ward_lookup.py",
                                 "data/fixtures/cap/CAP-v1.2.xsd", "scripts/review_alert_policy.py")]
    write("manifest.json", {"clock": NOW, "clock_kind": "fixed artificial scenario clock",
        "sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inputs)},
        "reproduction": "python -m scripts.review_alert_policy", "network_required": False})
    print(f"Wrote {len(cases)} deterministic scenarios, messages/CAP and read-only lookup/hash diagnostics to {OUT}")


if __name__ == "__main__":
    main()
