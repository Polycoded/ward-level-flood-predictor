"""Artificial fixtures for data-loss and identity regressions."""
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from pipeline.build_features import FEATURE_SCHEMA, validate_features
from pipeline.extract_wards_from_kml import main, prepare_wards


def feature():
    values = {key: 0 for key in FEATURE_SCHEMA}
    values.update(ward_id=1, ward_number="168", ward_name="Ward 168", area_sqkm=1,
                  elevation_mean=5, slope_mean=2, impervious_frac=0.5)
    return pd.DataFrame([values])


def test_valid_features_preserve_input_and_genuine_zero():
    frame = feature()
    before = frame.copy(deep=True)
    result = validate_features(frame)
    pd.testing.assert_frame_equal(frame, before)
    assert result.underpass_count.iloc[0] == 0
    assert result.ward_number.iloc[0] == "168"


@pytest.mark.parametrize("field,value", [("slope_mean", np.nan), ("elevation_mean", np.inf),
    ("impervious_frac", 2), ("underpass_count", 1.5), ("ward_id", 0),
    ("dist_to_water_m", True), ("ward_name", ""), ("area_sqkm", 0)])
def test_invalid_measurements_never_become_zero(field, value):
    frame = feature().astype(object)
    frame.loc[0, field] = value
    with pytest.raises((ValueError, TypeError)):
        validate_features(frame)


def test_missing_feature_and_duplicate_identity_rejected():
    with pytest.raises(ValueError, match="Missing"):
        validate_features(feature().drop(columns="slope_mean"))
    with pytest.raises(ValueError, match="unique"):
        validate_features(pd.concat([feature(), feature()]))


def layers():
    # Deliberately reversed official IDs distinguish official number from internal ID.
    wards = gpd.GeoDataFrame({"Name": [str(n) for n in range(200, 0, -1)]},
        geometry=[box(i, 0, i + 0.8, 0.8) for i in range(200)], crs="EPSG:32644")
    zones = gpd.GeoDataFrame({"ZONE": ["Z1"], "ZONE_NAME": ["Fixture"]},
        geometry=[box(-1, -1, 201, 2)], crs=wards.crs)
    return wards, zones


def test_converter_identity_and_crosswalk_columns_agree():
    wards, zones = layers()
    converted, crosswalk = prepare_wards(wards, zones)
    assert converted.iloc[0].ward_id == 1
    assert converted.iloc[0].ward_number == 200
    assert crosswalk.iloc[0].to_dict() == {
        "ward_id": 1, "ward_number": 200, "ward_name": "Ward 200",
        "zone_number": "Z1", "zone_name": "Fixture", "source": "chennai_gcc_kml_2022"}
    assert converted.ward_id.tolist() == crosswalk.ward_id.tolist()


def test_converter_rejects_missing_crs_and_duplicate_numbers():
    wards, zones = layers()
    with pytest.raises(ValueError, match="CRS"):
        prepare_wards(wards.set_crs(None, allow_override=True), zones)
    wards.loc[0, "Name"] = "199"
    with pytest.raises(ValueError, match="unique"):
        prepare_wards(wards, zones)


def test_converter_refuses_existing_output_before_reading_sources(tmp_path):
    output = tmp_path / "wards.geojson"
    output.write_text("preserve")
    with pytest.raises(SystemExit):
        main(["--output-dir", str(tmp_path)])
    assert output.read_text() == "preserve"


def test_feature_storage_overflow_and_duplicate_columns_rejected():
    frame = feature()
    frame["road_count"] = pd.Series([2**63], dtype="uint64")
    with pytest.raises(ValueError, match="storage"):
        validate_features(frame)
    with pytest.raises(ValueError, match="unique"):
        validate_features(pd.concat([feature(), feature()[["slope_mean"]]], axis=1))


def test_legitimate_negative_elevation_and_numeric_csv_values():
    frame = feature()
    frame["elevation_mean"] = -2
    frame["road_count"] = "0"
    result = validate_features(frame)
    assert result.elevation_mean.iloc[0] == -2
    assert result.road_count.iloc[0] == 0


def test_zone_repair_requires_acknowledgement():
    from shapely.geometry import Polygon
    wards, zones = layers()
    zones.geometry = [Polygon([(-1, -1), (201, 2), (-1, 2), (201, -1), (-1, -1)])]
    with pytest.raises(ValueError, match="acknowledge"):
        prepare_wards(wards, zones)


def test_nonpolygon_source_rejected():
    from shapely.geometry import Point
    wards, zones = layers()
    wards.loc[0, "geometry"] = Point(0, 0)
    with pytest.raises(ValueError, match="polygonal"):
        prepare_wards(wards, zones)


def test_explicit_ward_repair_and_input_nonmutation():
    from shapely.geometry import Polygon
    wards, zones = layers()
    wards.loc[0, "geometry"] = Polygon([(0, 0), (0.8, 0.8), (0, 0.8), (0.8, 0), (0, 0)])
    original = wards.geometry.iloc[0].wkb
    with pytest.raises(ValueError, match="acknowledge"):
        prepare_wards(wards, zones)
    converted, _ = prepare_wards(wards, zones, repair_invalid=True)
    assert converted.geometry.is_valid.all()
    assert wards.geometry.iloc[0].wkb == original
