"""Directory contents cannot establish a prior repair acknowledgement."""
import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from scripts import review_chennai_artifacts as review


def test_auditing_directory_does_not_assert_repair_acknowledgement(tmp_path, monkeypatch):
    root = tmp_path / "repository"
    processed = root / "data/processed"
    processed.mkdir(parents=True)
    raw = root / "data/raw"
    raw.mkdir()
    (raw / "Chennai GCC Ward Map - 2022.kml").write_text("artificial fixture only")
    for name in ("wards.geojson", "ward_crosswalk.csv", "features.parquet", "zonal_stats.parquet",
                 "validation_metrics.json", "validation_labels.csv", "roads.gpkg", "water.gpkg",
                 "underpasses.gpkg"):
        (processed / name).write_text("artificial fixture only")
    directory = tmp_path / "unattested-review"
    directory.mkdir()
    wards = gpd.GeoDataFrame({"ward_id": [1], "ward_number": [168], "ZONE": ["XIII"],
                             "ZONE_NAME": ["Artificial"]}, geometry=[box(0, 0, 1, 1)], crs=32644)
    crosswalk = pd.DataFrame({"ward_id": [1], "ward_number": [168],
                              "zone_number": ["XIII"], "zone_name": ["Artificial"]})
    features = pd.DataFrame({"ward_id": [1], "ward_number": [168], "elevation_mean": [1],
                            "slope_mean": [1], "impervious_frac": [0.5], "dist_to_water_m": [0],
                            "road_density_km_per_sqkm": [0], "underpass_count": [0]})
    monkeypatch.setattr(review, "__file__", str(root / "scripts/review_chennai_artifacts.py"))
    monkeypatch.setattr(review.gpd, "read_file", lambda *args, **kwargs: wards.copy())
    monkeypatch.setattr(review.pd, "read_csv", lambda *args, **kwargs: crosswalk.copy())
    monkeypatch.setattr(review.pd, "read_parquet", lambda *args, **kwargs: features.copy())
    result = review.audit(directory)
    assert result["conversion"]["compared_ids"] == 1
    assert result["conversion"]["repair_acknowledged"] is None
    assert result["conversion"]["repair_acknowledgement_status"] == "unverified_from_directory"
