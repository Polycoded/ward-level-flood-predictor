"""Pure prototype Exercise rules; candidates are pending, never approval or dispatch."""
from copy import deepcopy
from datetime import timedelta

from model.alert_contract import digest, instant, integer, iso, number, scenario_input, text
from model.risk_engine import score_ward


def evaluate_alerts(wards: list[dict], rainfall: dict, policy: dict, prior_state: dict, *, now: str) -> dict:
    """Return candidates, explicit overflow, suppressions, lifecycle and proposed_state.

    Persist state ONLY transactionally with the returned pending candidates. State is not
    approval/sending state. Expiry resets hysteresis/dedup; re-entry requires trigger again.
    Release cancels pending state, not an assertion of all-clear. Escalation bypasses cooldown.
    """
    current = instant(now)
    if not isinstance(policy, dict) or not isinstance(wards, list) or not all(isinstance(row, dict) for row in wards):
        raise ValueError("Policy object and JSON-compatible ward record list required")
    forcing = scenario_input(rainfall)
    if forcing["kind"] == "forecast":
        from model.forecast_input import validate_forecast
        forcing = validate_forecast(forcing, now=now)
    text(policy.get("version"), "policy.version")
    text(policy.get("model_version"), "model_version")
    trigger = number(policy.get("trigger_score"), "trigger_score", 0, 1)
    release = number(policy.get("release_score"), "release_score", 0, 1)
    escalation = number(policy.get("escalation_score"), "escalation_score", 0, 1)
    if not release < trigger < escalation:
        raise ValueError("Require release < trigger < escalation")
    cooldown = number(policy.get("cooldown_seconds"), "cooldown_seconds", 0, 604800)
    expiry = number(policy.get("expiry_seconds"), "expiry_seconds", 1, 604800)
    minimum = number(policy.get("min_rainfall_mm"), "min_rainfall_mm", 0, 500)
    limit = integer(policy.get("max_candidates"), "max_candidates", 1)
    state = deepcopy(prior_state)
    if not isinstance(state, dict):
        raise ValueError("prior_state must be an object keyed by internal ward ID")
    digest(state)
    lifecycle, suppressed, eligible = [], [], []
    for key, previous in state.items():
        if not isinstance(key, str) or not key.isdigit() or int(key) <= 0 or str(int(key)) != key:
            raise ValueError("State keys must be canonical internal ID strings")
        if not isinstance(previous, dict) or type(previous.get("active")) is not bool:
            raise ValueError("Invalid prior state")
        if previous["active"]:
            if previous.get("level") not in ("trigger", "escalation"):
                raise ValueError("Invalid active policy level")
            emitted, expires = instant(previous["last_candidate_at"]), instant(previous["expires_at"])
            if not emitted <= current or not expires > emitted:
                raise ValueError("Invalid state timestamps")
            if previous.get("policy_version") != policy["version"] or previous.get("model_version") != policy["model_version"]:
                raise ValueError("Prior state version mismatch; explicit migration/reset required")
            text(previous.get("fingerprint"), "fingerprint")
            if current >= expires:
                previous["active"] = False
                lifecycle.append({"ward_id": int(key), "reason": "expired", "candidate_id": previous.get("candidate_id")})
    seen, official = set(), set()
    for row in wards:
        ident = integer(row.get("ward_id"), "ward_id", 1)
        ward_number = text(row.get("ward_number"), "ward_number")
        name = text(row.get("ward_name"), "ward_name")
        if ident in seen or ward_number in official:
            raise ValueError("Duplicate internal or official identity")
        seen.add(ident)
        official.add(ward_number)
        score, category, _, _, reasons = score_ward(row, forcing["rainfall_mm"],
            duration_hours=forcing["duration_hours"])
        key = str(ident)
        previous = state.get(key, {"active": False})
        active = previous["active"]
        if active and (score <= release or forcing["rainfall_mm"] < minimum):
            previous["active"] = False
            state[key] = previous
            lifecycle.append({"ward_id": ident, "reason": "released", "candidate_id": previous.get("candidate_id")})
            suppressed.append({"ward_id": ident, "reason": "released"})
            continue
        reason = None
        if forcing["rainfall_mm"] < minimum:
            reason = "minimum_rainfall"
        elif score < trigger:
            reason = "hysteresis_hold" if active else "below_trigger"
        level = "escalation" if score >= escalation else "trigger"
        # An active escalation is latched until release/expiry, even if score dips.
        if active and previous["level"] == "escalation":
            level = "escalation"
        fingerprint = digest({"ward_id": ident, "ward_number": ward_number, "forcing": forcing,
                              "level": level, "policy": policy, "features": {
                                  k: row[k] for k in ("elevation_mean", "slope_mean", "impervious_frac",
                                      "dist_to_water_m", "road_density_km_per_sqkm", "underpass_count")}})
        is_escalation = active and level == "escalation" and previous["level"] != level
        if reason is None and active and not is_escalation:
            if previous["fingerprint"] == fingerprint:
                reason = "deduplicated"
            elif (current - instant(previous["last_candidate_at"])).total_seconds() < cooldown:
                reason = "cooldown"
        if reason:
            suppressed.append({"ward_id": ident, "reason": reason})
            continue
        expiry_at = current + timedelta(seconds=expiry)
        if forcing["kind"] == "forecast":
            expiry_at = min(expiry_at, instant(forcing["valid_until"]))
        candidate = {"candidate_id": digest([fingerprint, iso(current)]), "status": "pending",
            "mode": "Exercise", "ward_id": ident, "ward_number": ward_number, "ward_name": name,
            "score": score, "risk_level": category.value, "policy_level": level, "reasons": reasons,
            "rainfall": forcing, "model_version": policy["model_version"], "policy_version": policy["version"],
            "created_at": iso(current), "expires_at": iso(expiry_at),
            "policy_assumption": "Prototype thresholds, not validated warning levels",
            "fingerprint": fingerprint, "cause": "escalation" if is_escalation else "trigger_or_update"}
        eligible.append(candidate)
    eligible.sort(key=lambda c: (-int(c["policy_level"] == "escalation"), -c["score"], c["ward_id"]))
    selected, overflow = eligible[:limit], eligible[limit:]
    for candidate in selected:
        state[str(candidate["ward_id"])] = {"active": True, "level": candidate["policy_level"],
            "fingerprint": candidate["fingerprint"], "last_candidate_at": candidate["created_at"],
            "expires_at": candidate["expires_at"], "candidate_id": candidate["candidate_id"],
            "policy_version": candidate["policy_version"], "model_version": candidate["model_version"]}
    return {"mode": "Exercise", "candidates": selected, "overflow": overflow,
            "overflow_count": len(overflow), "suppressed": sorted(suppressed, key=lambda x: x["ward_id"]),
            "lifecycle": sorted(lifecycle, key=lambda x: (x["ward_id"], x["reason"])),
            "proposed_state": state}
