import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon, box

from model.ward_lookup import compare_simplification, lookup_ward


def layer(geometries):
    return gpd.GeoDataFrame({"ward_id": list(range(1, len(geometries)+1)),
        "ward_number": [str(170-i) for i in range(len(geometries))]}, geometry=geometries, crs=32644)


def lookup(frame, p, **kwargs):
    expected = [{"ward_id": int(r.ward_id), "ward_number": str(r.ward_number)} for _, r in frame.iterrows()]
    return lookup_ward(frame, p, point_crs="EPSG:32644", expected_identities=expected, **kwargs)


@pytest.mark.parametrize("point,status", [(Point(5, 5), "unique"), (Point(10, 5), "ambiguous"),
    (Point(10.1, 5), "ambiguous"), (Point(100, 100), "outside")])
def test_interior_shared_boundary_near_edge_and_outside(point, status):
    result = lookup(layer([box(0, 0, 10, 10), box(10, 0, 20, 10)]), point)
    assert result["status"] == status
    if status == "unique":
        assert result["matches"] == [{"ward_id": 1, "ward_number": "170"}]


def test_overlap_is_ambiguous_not_first_match():
    result = lookup(layer([box(0, 0, 10, 10), box(8, 0, 18, 10)]), Point(9, 5))
    assert result["status"] == "ambiguous"
    assert len(result["matches"]) == 2


def test_holes_and_uncertainty():
    polygon = Polygon(box(0, 0, 20, 20).exterior.coords, [box(5, 5, 15, 15).exterior.coords])
    assert lookup(layer([polygon]), Point(10, 10))["status"] == "outside"
    assert lookup(layer([polygon]), Point(5, 10))["status"] == "ambiguous"
    assert lookup(layer([box(0, 0, 10, 10), box(12, 0, 22, 10)]), Point(8, 5), uncertainty_m=5)["status"] == "ambiguous"


def test_incomplete_invalid_and_identity_mismatch_unavailable():
    full = layer([box(0, 0, 10, 10), box(10, 0, 20, 10)])
    expected = [{"ward_id": 1, "ward_number": "170"}, {"ward_id": 2, "ward_number": "169"}]
    for frame in (full.iloc[:1], full.assign(ward_number=["wrong", "169"]),
                  full.assign(geometry=[None, full.geometry.iloc[1]]), full.set_crs(None, allow_override=True)):
        result = lookup_ward(frame, Point(5, 5), point_crs="EPSG:32644", expected_identities=expected)
        assert result["status"] == "unavailable"
    assert lookup(full, Point(float("inf"), 0))["status"] == "unavailable"


def test_tolerable_simplification_can_still_change_membership():
    full = layer([Polygon([(0, 0), (10, 0), (10, 10), (6, 10), (6, 8), (4, 8), (4, 10), (0, 10)])])
    simplified = layer([box(0, 0, 10, 10)])
    expected = [{"ward_id": 1, "ward_number": "170"}]
    report = compare_simplification(full, simplified, expected_identities=expected, tolerance_m=2)
    assert report["status"] == "within_tolerance"
    assert report["membership_guaranteed"] is False
    assert report["comparisons"][0]["symmetric_difference_m2"] > 0
    p = Point(5, 9)
    assert lookup(full, p, boundary_tolerance_m=0)["status"] == "outside"
    assert lookup(simplified, p, boundary_tolerance_m=0)["status"] == "unique"


def test_metric_crs_and_tolerance_errors_are_explicit():
    full = layer([box(0, 0, 10, 10)])
    assert lookup(full, Point(5, 5), metric_crs="EPSG:4326")["status"] == "unavailable"
    assert lookup(full, Point(5, 5), uncertainty_m=-1)["status"] == "unavailable"


@pytest.mark.parametrize("bad", [True, False, np.bool_(True), float("inf"), float("-inf"),
    float("nan"), 1.5, 0, -1, "1", "bad", None, pd.NA])
@pytest.mark.parametrize("target", ["frame", "expected"])
def test_invalid_ids_return_unavailable_before_conversion(bad, target):
    full = layer([box(0, 0, 10, 10)])
    expected = [{"ward_id": 1, "ward_number": "170"}]
    if target == "frame":
        full["ward_id"] = pd.Series([bad], dtype=object)
    else:
        expected[0]["ward_id"] = bad
    assert lookup_ward(full, Point(5, 5), point_crs="EPSG:32644",
                       expected_identities=expected)["status"] == "unavailable"
    assert compare_simplification(full, full, expected_identities=expected,
                                  tolerance_m=1)["status"] == "unavailable"


@pytest.mark.parametrize("ident", [1, np.int32(1), np.int64(1), np.uint64(1)])
def test_numpy_and_pandas_integer_ids_remain_valid(ident):
    full = layer([box(0, 0, 10, 10)])
    full["ward_id"] = pd.Series([ident], dtype=object)
    expected = [{"ward_id": ident, "ward_number": "170"}]
    assert lookup_ward(full, Point(5, 5), point_crs="EPSG:32644",
                       expected_identities=expected)["status"] == "unique"
    assert compare_simplification(full, full, expected_identities=expected,
                                  tolerance_m=1)["status"] == "within_tolerance"
