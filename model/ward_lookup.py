"""Reference full-geometry lookup, not legal geography or resident UI."""
from math import isfinite
from numbers import Integral, Real

import geopandas as gpd
from shapely.geometry import Point

from model.alert_contract import number, text
from model.distance import _validate_crs, _validate_geometry


def _ward_id(value):
    # Validate before int(): bool aliases 1; infinity raises OverflowError; strings
    # and fractional numbers must not be silently coerced. NumPy integers are valid.
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("ward_id must be a positive integral number, not boolean/text")
    if isinstance(value, Integral):
        if value <= 0:
            raise ValueError("ward_id must be positive")
    elif not isfinite(value) or value <= 0 or value % 1 != 0:
        raise ValueError("ward_id must be finite, positive and integral")
    return int(value)


def _wards(frame, identities: list[dict], metric_crs: str):
    _validate_crs(metric_crs, metric=True)
    _validate_crs(frame.crs)
    expected = {}
    for item in identities:
        ident = _ward_id(item.get("ward_id"))
        official = text(item.get("ward_number"), "ward_number")
        if ident in expected or official in expected.values():
            raise ValueError("Duplicate expected identity")
        expected[ident] = official
    if not expected or len(frame) != len(expected) or frame.ward_id.duplicated().any():
        raise ValueError("Incomplete or duplicate ward universe")
    actual = {}
    for _, row in frame.iterrows():
        ident = _ward_id(row.ward_id)
        actual[ident] = str(row.ward_number)
        geom = row.geometry
        if geom is None or geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
            raise ValueError("Missing or nonpolygon geometry")
        _validate_geometry(geom)
    if actual != expected:
        raise ValueError("Official/internal identity mismatch")
    projected = frame.to_crs(metric_crs).copy()
    for geom in projected.geometry:
        _validate_geometry(geom)
    return projected


def lookup_ward(wards, point: Point, *, point_crs: str, expected_identities: list[dict],
                uncertainty_m: float = 0, boundary_tolerance_m: float = 1,
                metric_crs: str = "EPSG:32644") -> dict:
    """unique/ambiguous/outside/unavailable; boundaries never resolved by first match."""
    try:
        projected = _wards(wards, expected_identities, metric_crs)
        _validate_crs(point_crs)
        _validate_geometry(point)
        if point is None or point.is_empty or point.geom_type != "Point":
            raise ValueError("A finite point is required")
        uncertainty = number(uncertainty_m, "uncertainty_m", 0, 100000)
        tolerance = number(boundary_tolerance_m, "boundary_tolerance_m", 0, 100000)
        p = gpd.GeoSeries([point], crs=point_crs).to_crs(metric_crs).iloc[0]
        _validate_geometry(p)
        radius = max(uncertainty, tolerance)
        hits, nearby = [], []
        near_boundary = False
        for _, row in projected.iterrows():
            item = {"ward_id": int(row.ward_id), "ward_number": str(row.ward_number)}
            if row.geometry.covers(p):
                hits.append(item)
            if row.geometry.distance(p) <= radius:
                nearby.append(item)
            if row.geometry.boundary.distance(p) <= radius:
                near_boundary = True
        status = "ambiguous" if near_boundary or len(hits) > 1 or len(nearby) > 1 else "unique" if len(hits) == 1 else "outside"
        return {"status": status, "matches": sorted(hits, key=lambda x: x["ward_id"]),
                "possible_wards": sorted(nearby, key=lambda x: x["ward_id"]),
                "confirmation_required": status == "ambiguous", "reference": "supplied_full_geometry",
                "note": "Outside means outside supplied polygons; source coverage/authenticity not certified."}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        return {"status": "unavailable", "reason": str(exc), "confirmation_required": True}


def compare_simplification(full, simplified, *, expected_identities: list[dict],
                           tolerance_m: float, metric_crs: str = "EPSG:32644") -> dict:
    """Hausdorff tolerance is a diagnostic, never a guarantee of identical membership."""
    try:
        tolerance = number(tolerance_m, "tolerance_m", 0, 1000)
        left = _wards(full, expected_identities, metric_crs).set_index("ward_id")
        right = _wards(simplified, expected_identities, metric_crs).set_index("ward_id")
        comparisons = []
        for ident in sorted(left.index):
            a, b = left.loc[ident].geometry, right.loc[ident].geometry
            comparisons.append({"ward_id": int(ident), "ward_number": str(left.loc[ident].ward_number),
                "hausdorff_m": a.hausdorff_distance(b), "symmetric_difference_m2": a.symmetric_difference(b).area})
        return {"status": "within_tolerance" if all(x["hausdorff_m"] <= tolerance for x in comparisons) else "exceeds_tolerance",
                "comparisons": comparisons, "membership_guaranteed": False,
                "handoff": "Within tolerance is not acceptance. Near simplified boundaries, overlaps, holes or positional uncertainty: use full geometry and require confirmation. Identity mismatch or missing polygons: unavailable."}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        return {"status": "unavailable", "reason": str(exc), "membership_guaranteed": False}
