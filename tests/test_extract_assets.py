import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.extract_assets import (  # noqa: E402
    assign_wards,
    build_shelters,
    classify,
    main,
    parse_assets,
)

# Shapes match a real `out center tags;` Overpass response: nodes carry lat/lon,
# ways/relations carry a `center`.
OVERPASS_SAMPLE = {
    "elements": [
        {"type": "node", "id": 101, "lat": 13.0678, "lon": 80.2785,
         "tags": {"amenity": "hospital", "name": "Rajiv Gandhi Government General Hospital"}},
        {"type": "way", "id": 202, "center": {"lat": 13.0418, "lon": 80.2341},
         "tags": {"amenity": "school", "name": "Corporation Higher Secondary School"}},
        {"type": "way", "id": 203, "center": {"lat": 13.0420, "lon": 80.2350},
         "tags": {"amenity": "school"}},  # unnamed: an asset, but not a shelter
        {"type": "relation", "id": 303, "center": {"lat": 13.0101, "lon": 80.2354},
         "tags": {"amenity": "university", "name": "Anna University", "name:en": "Anna University"}},
        {"type": "node", "id": 404, "lat": 13.0500, "lon": 80.2600,
         "tags": {"man_made": "pumping_station", "name": "Sewage Pumping Station"}},
        {"type": "node", "id": 101, "lat": 13.0678, "lon": 80.2785,
         "tags": {"amenity": "hospital", "name": "duplicate of 101"}},
        {"type": "node", "id": 505, "lat": 13.0, "lon": 80.2, "tags": {"amenity": "cafe"}},  # not an asset
        {"type": "way", "id": 606, "tags": {"amenity": "police"}},  # no location
        {"type": "node", "id": 707, "lat": 12.5, "lon": 79.5,
         "tags": {"amenity": "fire_station", "name": "Outside the city"}},
    ]
}


def wards_fixture() -> gpd.GeoDataFrame:
    # Two wards covering the sample points, stored in UTM like pipeline/download_wards.py
    gdf = gpd.GeoDataFrame(
        {"ward_id": [1, 2]},
        geometry=[box(80.22, 13.03, 80.30, 13.10), box(80.20, 12.98, 80.30, 13.03)],
        crs="EPSG:4326",
    )
    return gdf.to_crs("EPSG:32644")


def test_classify_known_and_unknown_tags():
    assert classify({"amenity": "hospital"}) == ("hospital", "critical_care")
    assert classify({"power": "substation"}) == ("substation", "power")
    assert classify({"amenity": "cafe"}) is None
    assert classify({}) is None


def test_parse_assets_handles_nodes_ways_relations_and_dedupes():
    assets = parse_assets(OVERPASS_SAMPLE)
    assert sorted(assets["osm_id"]) == [101, 202, 203, 303, 404, 707]
    hospital = assets[assets.osm_id == 101].iloc[0]
    assert hospital["name"] == "Rajiv Gandhi Government General Hospital"
    assert (hospital["latitude"], hospital["longitude"]) == (13.0678, 80.2785)
    assert assets[assets.osm_id == 202].iloc[0]["category"] == "shelter_candidate"
    assert list(assets["asset_id"]) == list(range(1, len(assets) + 1))
    assert assets.crs.to_epsg() == 4326


def test_parse_assets_empty_response():
    assets = parse_assets({"elements": []})
    assert len(assets) == 0
    assert "geometry" in assets.columns


def test_assign_wards_tags_points_and_drops_outside():
    assets = assign_wards(parse_assets(OVERPASS_SAMPLE), wards_fixture())
    by_id = dict(zip(assets["osm_id"], assets["ward_id"]))
    assert by_id[101] == 1
    assert by_id[303] == 2
    assert 707 not in by_id  # outside every ward


def test_assign_wards_without_boundaries_keeps_assets():
    assets = assign_wards(parse_assets(OVERPASS_SAMPLE), None)
    assert len(assets) == 6
    assert assets["ward_id"].isna().all()


def test_build_shelters_matches_api_contract():
    shelters = build_shelters(assign_wards(parse_assets(OVERPASS_SAMPLE), wards_fixture()))
    # only named shelter candidates
    assert sorted(shelters["name"]) == ["Anna University", "Corporation Higher Secondary School"]
    # columns read by model/shelters.py find_nearest_shelters()
    for column in ["shelter_id", "name", "latitude", "longitude", "capacity", "geometry"]:
        assert column in shelters.columns
    assert shelters.set_index("name").loc["Anna University", "capacity"] == 800


def test_main_round_trips_through_parquet(tmp_path, monkeypatch):
    import json

    import pipeline.extract_assets as mod

    sample = tmp_path / "overpass.json"
    sample.write_text(json.dumps(OVERPASS_SAMPLE))
    wards_path = tmp_path / "wards.geojson"
    wards_fixture().to_file(wards_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "WARDS_PATH", wards_path)
    monkeypatch.setattr(mod, "ASSETS_PATH", tmp_path / "assets.parquet")
    monkeypatch.setattr(mod, "SHELTERS_PATH", tmp_path / "shelters.parquet")
    monkeypatch.setattr(mod, "load_wards", lambda path=wards_path: gpd.read_file(path))

    main(["--input", str(sample)])

    assets = gpd.read_parquet(tmp_path / "assets.parquet")
    shelters = gpd.read_parquet(tmp_path / "shelters.parquet")
    assert len(assets) == 5
    assert len(shelters) == 2

    # the API's shelter finder accepts what we wrote
    from model.shelters import find_nearest_shelters

    nearest = find_nearest_shelters(13.04, 80.234, shelters, max_distance_km=5, max_results=1)
    assert nearest[0]["name"] == "Corporation Higher Secondary School"
