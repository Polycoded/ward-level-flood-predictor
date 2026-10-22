"""Artificial coordinates/rasters only: analytical mechanics, not geographic evidence."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from affine import Affine
from rasterio.transform import from_origin
from shapely.geometry import LineString, Point, Polygon, box

from model.distance import (
    compute_feature_distances,
    compute_road_distances,
    compute_ward_water_distances,
    distance_to_nearest,
    point_to_line_distance,
)
from model.slope import NODATA, compute_slope, reproject_raster

METRIC = "EPSG:32644"


def write_dem(path, values, *, crs=METRIC, transform=None, nodata=None,
              mask=None, unit=None, scale=1, count=1):
    if transform is None:
        transform = from_origin(400000, 1450000, 10, 20)
    values = np.asarray(values, dtype="float32")
    with rasterio.open(path, "w", driver="GTiff", width=values.shape[1],
                       height=values.shape[0], count=count, dtype="float32",
                       crs=crs, transform=transform, nodata=nodata) as dst:
        for band in range(1, count + 1):
            dst.write(values, band)
        if mask is not None:
            dst.write_mask(mask)
        if unit is not None:
            dst.set_band_unit(1, unit)
        dst.scales = (scale,) * count


@pytest.mark.parametrize("x_spacing,y_spacing", [(10, 20), (30, 30), (2, 7)])
@pytest.mark.parametrize("gx,gy", [(0, 0), (1, 0), (0.3, 0.4), (0, 1)])
def test_analytical_planar_slopes(tmp_path, x_spacing, y_spacing, gx, gy):
    row, col = np.indices((5, 6))
    transform = from_origin(400000, 1450000, x_spacing, y_spacing)
    dem = 100 + gx * col * x_spacing - gy * row * y_spacing
    source, output = tmp_path / "plane.tif", tmp_path / "slope.tif"
    write_dem(source, dem, transform=transform, unit="m")
    compute_slope(source, output)
    with rasterio.open(output) as dst:
        np.testing.assert_allclose(dst.read(1), np.degrees(np.arctan(np.hypot(gx, gy))), atol=1e-4)
        assert dst.transform == transform
        assert dst.crs.to_epsg() == 32644
        assert dst.nodata == NODATA
        assert dst.units == ("degree",)
        assert dst.dtypes == ("float32",)
        assert dst.shape == (5, 6)


@pytest.mark.parametrize("missing", ["sentinel", "nan", "infinity", "mask"])
def test_missing_cells_invalidate_stencil(tmp_path, missing):
    dem = np.full((5, 5), 10, dtype="float32")
    mask = np.full((5, 5), 255, dtype="uint8")
    if missing == "mask":
        mask[2, 2] = 0
    else:
        dem[2, 2] = {"sentinel": -32768, "nan": np.nan, "infinity": np.inf}[missing]
    source, output = tmp_path / "missing.tif", tmp_path / "slope.tif"
    write_dem(source, dem, nodata=-32768, mask=mask if missing == "mask" else None)
    compute_slope(source, output)
    expected = np.zeros((5, 5), dtype=bool)
    expected[2, 1:4] = True
    expected[1:4, 2] = True
    with rasterio.open(output) as dst:
        actual = dst.read(1, masked=True)
        np.testing.assert_array_equal(actual.mask, expected)
        assert np.isfinite(actual.data).all()  # Unknowns serialized as explicit nodata.
        assert (actual.compressed() == 0).all()


def test_missing_edge_and_all_missing(tmp_path):
    source, output = tmp_path / "edge.tif", tmp_path / "slope.tif"
    dem = np.ones((3, 3))
    dem[0, 0] = np.nan
    write_dem(source, dem)
    compute_slope(source, output)
    with rasterio.open(output) as dst:
        np.testing.assert_array_equal(dst.read_masks(1) == 0,
                                      [[True, True, False], [True, False, False], [False, False, False]])
    write_dem(source, np.full((3, 3), np.nan))
    compute_slope(source, output)
    with rasterio.open(output) as dst:
        assert (dst.read_masks(1) == 0).all()


@pytest.mark.parametrize("kwargs,match", [
    ({"crs": None}, "CRS"),
    ({"crs": "EPSG:4326"}, "reproject"),
    ({"crs": "EPSG:2263"}, "metre"),
    ({"unit": "ft"}, "elevations"),
    ({"scale": 0.1}, "scale/offset"),
    ({"count": 2}, "one band"),
    ({"transform": Affine(10, 1, 400000, 0, -20, 1450000)}, "transform"),
    ({"transform": Affine(10, 0, 400000, 1, -20, 1450000)}, "transform"),
    ({"transform": Affine(10, 0, 400000, 0, 20, 1450000)}, "transform"),
    ({"transform": Affine(-10, 0, 400000, 0, -20, 1450000)}, "transform"),
    # GDAL may lose CRS metadata when writing a singular GeoTIFF transform.
    ({"transform": Affine(0, 0, 400000, 0, -20, 1450000)}, "CRS|transform"),
    ({"transform": Affine(np.nan, 0, 400000, 0, -20, 1450000)}, "transform"),
])
def test_unsupported_dem_metadata(tmp_path, kwargs, match):
    source, output = tmp_path / "unsupported.tif", tmp_path / "slope.tif"
    write_dem(source, np.ones((3, 3)), **kwargs)
    with pytest.raises(ValueError, match=match):
        compute_slope(source, output)
    assert not output.exists()


@pytest.mark.parametrize("shape", [(1, 3), (3, 1)])
def test_insufficient_dimensions(tmp_path, shape):
    source = tmp_path / "small.tif"
    write_dem(source, np.zeros(shape))
    with pytest.raises(ValueError, match="dimensions"):
        compute_slope(source, tmp_path / "slope.tif")


def test_declared_vertical_units(tmp_path):
    source = tmp_path / "dem.tif"
    write_dem(source, np.zeros((3, 3)))
    with pytest.raises(ValueError, match="metres"):
        compute_slope(source, tmp_path / "slope.tif", vertical_units="feet")


def test_reprojection_same_grid_preserves_masks_and_float_elevations(tmp_path):
    source, output = tmp_path / "dem.tif", tmp_path / "warped.tif"
    data = np.full((4, 4), 10.5)
    mask = np.full((4, 4), 255, dtype="uint8")
    mask[1, 1] = 0
    write_dem(source, data, transform=from_origin(400000, 1450000, 10, 10), mask=mask)
    reproject_raster(source, output, resolution=10)
    with rasterio.open(output) as dst:
        assert dst.units == ("m",)
        assert dst.nodata == NODATA
        assert dst.dtypes == ("float32",)
        np.testing.assert_array_equal(dst.read_masks(1), mask)
        np.testing.assert_allclose(dst.read(1, masked=True).compressed(), 10.5)


def test_reprojection_destination_bounds_and_outside_coverage(tmp_path):
    source, output = tmp_path / "dem.tif", tmp_path / "warped.tif"
    write_dem(source, np.full((4, 4), 10.5), transform=from_origin(400000, 1450000, 10, 10))
    extent = (399990, 1449950, 400043, 1450010)
    reproject_raster(source, output, resolution=10, bounds=extent)
    with rasterio.open(output) as dst:
        assert dst.width == 6 and dst.height == 6
        assert dst.bounds.left == extent[0] and dst.bounds.top == extent[3]
        assert dst.bounds.right >= extent[2] and dst.bounds.bottom <= extent[1]
        assert (dst.read_masks(1)[0] == 0).all()
        assert (dst.read_masks(1)[:, 0] == 0).all()
        np.testing.assert_allclose(dst.read(1, masked=True).compressed(), 10.5)


def test_geographic_dem_can_be_warped_before_slope(tmp_path):
    source, output = tmp_path / "degrees.tif", tmp_path / "metres.tif"
    write_dem(source, np.full((5, 5), 42.5), crs="EPSG:4326",
              transform=from_origin(80.1, 13.1, 0.001, 0.001))
    reproject_raster(source, output, resolution=30)
    compute_slope(output, tmp_path / "slope.tif")
    with rasterio.open(output) as dst:
        assert dst.crs.to_epsg() == 32644
        assert dst.transform.a == 30 and dst.transform.e == -30
        np.testing.assert_allclose(dst.read(1, masked=True).compressed(), 42.5)
    with rasterio.open(tmp_path / "slope.tif") as dst:
        np.testing.assert_allclose(dst.read(1, masked=True).compressed(), 0)


@pytest.mark.parametrize("kwargs", [
    {"resolution": 0}, {"resolution": -1}, {"resolution": np.nan},
    {"resolution": True}, {"resolution": "30"}, {"dst_crs": "EPSG:4326"},
    {"bounds": (1, 0, 0, 1)}, {"bounds": (0, 1, 1, 0)},
    {"bounds": (0, 0, np.inf, 1)}, {"bounds": (0, 1)},
    {"bounds": ("0", 0, 10, 10)},
])
def test_invalid_warp_arguments(tmp_path, kwargs):
    source = tmp_path / "dem.tif"
    write_dem(source, np.zeros((3, 3)))
    with pytest.raises(ValueError):
        reproject_raster(source, tmp_path / "warped.tif", **kwargs)


def frame(geometries, crs=METRIC, index=None):
    return gpd.GeoDataFrame(geometry=geometries, crs=crs, index=index)


def test_metric_distance_definition_and_index_alignment():
    wards = frame([box(399990, 1449990, 400010, 1450010),
                   box(400090, 1449990, 400110, 1450010)], index=[42, 7])
    water = frame([box(400030, 1449990, 400050, 1450010)])
    original = wards.copy()
    result = compute_ward_water_distances(wards, water)
    assert isinstance(result, pd.Series) and not isinstance(result, gpd.GeoSeries)
    assert result.dtype == "float64"
    np.testing.assert_allclose(result.to_numpy(), [30, 50])  # Centroids, not ward edges.
    assert result.index.equals(wards.index)
    pd.testing.assert_frame_equal(wards, original)
    pd.testing.assert_series_equal(result, compute_feature_distances(wards, {"water": water})["water"])


@pytest.mark.parametrize("source_crs,target_crs", [
    (METRIC, "EPSG:4326"), ("EPSG:4326", METRIC),
    ("EPSG:4326", "EPSG:4326"), ("EPSG:32643", METRIC),
])
def test_differing_crs_reproject_before_centroids(source_crs, target_crs):
    wards = frame([box(399990, 1449990, 400010, 1450010)]).to_crs(source_crs)
    water = frame([Point(400030, 1450040)]).to_crs(target_crs)
    np.testing.assert_allclose(distance_to_nearest(wards, water), [50], atol=1e-5)


def test_real_zero_and_point_road_compatibility():
    points = frame([Point(400000, 1450000), Point(400003, 1450004)], index=["a", "a"])
    roads = frame([LineString([(399990, 1450000), (400010, 1450000)])])
    result = compute_road_distances(points, roads)
    assert result.index.tolist() == ["a", "a"]
    np.testing.assert_allclose(result, [0, 4])
    assert point_to_line_distance(points.geometry.iloc[1], roads.geometry.iloc[0]) == 4
    assert point_to_line_distance(points.geometry.iloc[1], roads.geometry.iloc[0], crs=METRIC) == 4


@pytest.mark.parametrize("targets", [[], [None], [Polygon()], [Point(400000, 1450000), None]])
def test_unknown_target_coverage_is_unavailable(targets):
    wards = frame([Point(400000, 1450000)], index=[17])
    result = distance_to_nearest(wards, frame(targets))
    assert result.isna().all() and result.index.tolist() == [17]


def test_missing_source_geometry_and_empty_source():
    wards = frame([None, Polygon(), Point(400003, 1450004)], index=[10, 20, 30])
    water = frame([Point(400000, 1450000)])
    result = distance_to_nearest(wards, water)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == 5
    assert distance_to_nearest(wards.iloc[:0], water).empty
    assert np.isnan(point_to_line_distance(None, LineString([(0, 0), (1, 1)])))


@pytest.mark.parametrize("which", ["source", "target", "metric"])
@pytest.mark.parametrize("crs", [None, "EPSG:2263"])
def test_missing_crs_or_unsupported_units(which, crs):
    wards = frame([Point(400000, 1450000)], crs=crs if which == "source" else METRIC)
    water = frame([], crs=crs if which == "target" else METRIC)
    with pytest.raises(ValueError, match="CRS|units"):
        distance_to_nearest(wards, water, metric_crs=crs if which == "metric" else METRIC)


@pytest.mark.parametrize("geometry", [
    Polygon([(0, 0), (2, 2), (0, 2), (2, 0), (0, 0)]),
    Point(np.inf, 0), Point(1, 2, 3),
])
@pytest.mark.parametrize("which", ["source", "target"])
def test_invalid_or_nonfinite_geometry_rejected(geometry, which):
    wards = frame([geometry if which == "source" else Point(400000, 1450000)])
    water = frame([geometry if which == "target" else Point(400000, 1450000)])
    with pytest.raises(ValueError, match="geometry|2D"):
        distance_to_nearest(wards, water)


def test_bilinear_warp_interpolates_plane_without_bridging_mask(tmp_path):
    source, output = tmp_path / "dem.tif", tmp_path / "warped.tif"
    data = np.tile(np.arange(5) * 10.0, (5, 1))
    mask = np.full((5, 5), 255, dtype="uint8")
    mask[2, 2] = 0
    write_dem(source, data, transform=from_origin(400000, 1450000, 10, 10), mask=mask)
    reproject_raster(source, output, resolution=10,
                     bounds=(400005, 1449955, 400045, 1449995))
    with rasterio.open(output) as dst:
        values = dst.read(1, masked=True)
        np.testing.assert_allclose(values[0], [5, 15, 25, 35])
        assert values.mask[1:3, 1:3].all()  # Don't interpolate through missing elevation.


def test_reprojection_nodata_without_internal_mask(tmp_path):
    source, output = tmp_path / "dem.tif", tmp_path / "warped.tif"
    data = np.ones((3, 3))
    data[1, 1] = -32768
    write_dem(source, data, transform=from_origin(400000, 1450000, 10, 10), nodata=-32768)
    reproject_raster(source, output, resolution=10)
    with rasterio.open(output) as dst:
        assert dst.read(1)[1, 1] == NODATA
        assert dst.read(1, masked=True).mask.sum() == 1


def test_reprojection_rejects_missing_crs_and_vertical_units(tmp_path):
    source = tmp_path / "dem.tif"
    write_dem(source, np.ones((3, 3)), crs=None)
    with pytest.raises(ValueError, match="CRS"):
        reproject_raster(source, tmp_path / "warped.tif")
    write_dem(source, np.ones((3, 3)), unit="ft")
    with pytest.raises(ValueError, match="metres"):
        reproject_raster(source, tmp_path / "warped.tif")


def test_explicit_non_chennai_metric_crs():
    # Arbitrary test coordinates in another UTM zone: callers must choose their local CRS.
    sources = frame([Point(400000, 1450000)], crs="EPSG:32643")
    targets = frame([Point(400003, 1450004)], crs="EPSG:32643")
    assert distance_to_nearest(sources, targets, metric_crs="EPSG:32643").iloc[0] == 5
    with pytest.raises(ValueError, match="CRS"):
        point_to_line_distance(Point(0, 0), LineString([(0, 1), (1, 1)]), crs="EPSG:4326")


def test_explicit_mask_does_not_override_declared_nodata(tmp_path):
    source, slope, warped = tmp_path / "dem.tif", tmp_path / "slope.tif", tmp_path / "warp.tif"
    data = np.ones((5, 5))
    data[2, 2] = -32768
    mask = np.full((5, 5), 255, dtype="uint8")
    mask[0, 0] = 0
    write_dem(source, data, nodata=-32768, mask=mask,
              transform=from_origin(400000, 1450000, 10, 10))
    compute_slope(source, slope)
    with rasterio.open(slope) as dst:
        result = dst.read(1, masked=True)
        assert result.mask[0, 0] and result.mask[2, 2]
        assert result.mask[2, 1] and result.mask[1, 2]
    reproject_raster(source, warped, resolution=10)
    with rasterio.open(warped) as dst:
        result = dst.read(1, masked=True)
        assert result.mask.sum() == 2
        assert result.mask[0, 0] and result.mask[2, 2]
