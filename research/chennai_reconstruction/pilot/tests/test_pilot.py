import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box

PILOT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PILOT_ROOT))

from sentinel1_pilot.acquisition import (  # noqa: E402
    Credentials,
    bbox_polygon,
    credentials_from_env,
    dedupe_scenes,
    expected_storage_mb,
    footprint_coverage,
    parse_asf_payload,
    part_path,
    select_scenes,
    union_coverage,
    verify_scene,
)
from sentinel1_pilot.coverage import (  # noqa: E402
    border_mask,
    boundary_coverage,
    common_valid_mask,
    coverage_stats,
    reproject_to_grid,
    valid_mask,
)
from sentinel1_pilot.preprocessing import (  # noqa: E402
    ProcessingBlocked,
    available_toolchain,
    toolchain_status,
)

BBOX = [80.10, 12.80, 80.35, 13.25]


def make_scene(scene_id="S1A_TEST", footprint=None, **overrides):
    geometry = footprint or Polygon([
        (80.10, 12.80), (80.35, 12.80), (80.35, 13.25), (80.10, 13.25)
    ])
    item = {
        "sceneId": scene_id,
        "platform": "Sentinel-1A",
        "flightDirection": "DESCENDING",
        "relativeOrbit": 92,
        "polarization": "VV+VH",
        "processingLevel": "GRD_HD",
        "stringFootprint": geometry.wkt,
        "downloadUrl": "https://example.invalid/test.zip",
        "startTime": "2021-11-04T00:31:47Z",
        "stopTime": "2021-11-04T00:32:12Z",
        "sizeMB": 900.0,
        "md5sum": "abc123",
    }
    item.update(overrides)
    return item


class AcquisitionTests(unittest.TestCase):
    def test_parse_nested_asf_payload(self):
        payload = [[make_scene("A"), make_scene("B")]]
        parsed = parse_asf_payload(payload)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["sceneId"], "A")

    def test_dedupe_rejects_conflicting_checksums(self):
        with self.assertRaises(Exception):
            dedupe_scenes([make_scene("A", md5sum="a"), make_scene("A", md5sum="b")])

    def test_select_scenes_reports_missing(self):
        with self.assertRaises(Exception):
            select_scenes({"A": make_scene("A")}, ["A", "MISSING"])

    def test_verify_scene_matches_and_reports_mismatch(self):
        spec = {
            "expected_platform": "Sentinel-1A",
            "expected_direction": "DESCENDING",
            "expected_relative_orbit": 92,
            "expected_polarization": "VV+VH",
            "expected_product_type": "GRD_HD",
        }
        self.assertEqual(verify_scene(make_scene(), spec), [])
        errors = verify_scene(make_scene(platform="Sentinel-1B"), spec)
        self.assertTrue(any("platform" in error for error in errors))

    def test_footprint_coverage_exact_and_partial(self):
        self.assertAlmostEqual(footprint_coverage(make_scene(), BBOX), 1.0)
        half = Polygon([(80.10, 12.80), (80.225, 12.80),
                        (80.225, 13.25), (80.10, 13.25)])
        self.assertAlmostEqual(footprint_coverage(make_scene(footprint=half), BBOX), 0.5)

    def test_union_coverage_two_frames(self):
        south = Polygon([(80.10, 12.80), (80.35, 12.80),
                         (80.35, 13.0), (80.10, 13.0)])
        north = Polygon([(80.10, 13.0), (80.35, 13.0),
                         (80.35, 13.25), (80.10, 13.25)])
        self.assertAlmostEqual(union_coverage([
            make_scene(footprint=south), make_scene(footprint=north)
        ], BBOX), 1.0)

    def test_storage_and_part_path(self):
        scene = make_scene(sizeMB=100.0)
        self.assertEqual(expected_storage_mb([scene, scene]), 200.0)
        self.assertEqual(part_path(Path("a.zip")).name, "a.zip.part")

    def test_credentials_not_hardcoded(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(credentials_from_env())
        with patch.dict(os.environ, {"EARTHDATA_USERNAME": "u",
                                     "EARTHDATA_PASSWORD": "p"}, clear=True):
            self.assertEqual(credentials_from_env(), Credentials("u", "p"))

    def test_bbox_polygon(self):
        self.assertAlmostEqual(bbox_polygon(BBOX).area, box(*BBOX).area)


class CoverageTests(unittest.TestCase):
    def test_valid_mask_and_stats(self):
        array = np.array([[1.0, np.nan], [-9999.0, 2.0]])
        mask = valid_mask(array, nodata=-9999.0)
        self.assertEqual(mask.tolist(), [[True, False], [False, True]])
        self.assertEqual(coverage_stats(mask), {
            "pixels_total": 4, "pixels_valid": 2,
            "pixels_nodata": 2, "valid_fraction": 0.5})

    def test_border_mask(self):
        valid = np.ones((5, 5), dtype=bool)
        border = border_mask(valid, border_px=1)
        self.assertTrue(border[0, :].all())
        self.assertTrue(border[:, 0].all())
        self.assertFalse(border[2, 2])
        self.assertEqual(int(border.sum()), 16)

    def test_common_valid_mask_rejects_shape_mismatch(self):
        with self.assertRaises(ValueError):
            common_valid_mask([np.ones((2, 2), dtype=bool),
                               np.ones((3, 3), dtype=bool)])

    def test_common_valid_mask(self):
        left = np.array([[True, False], [True, True]])
        right = np.array([[True, True], [False, True]])
        self.assertEqual(common_valid_mask([left, right]).tolist(),
                         [[True, False], [False, True]])

    def test_reproject_identity_grid(self):
        source = np.array([[1.0, 2.0], [3.0, 4.0]], dtype="float32")
        transform = from_origin(0, 2, 1, 1)
        output = reproject_to_grid(source, transform, "EPSG:32644",
                                   (2, 2), transform, "EPSG:32644")
        self.assertEqual(output.shape, (2, 2))
        self.assertTrue(np.allclose(output, source))

    def test_missing_boundary_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = boundary_coverage(Path(tmp) / "missing.geojson", [make_scene()])
            self.assertEqual(result["status"], "blocked")
            self.assertIsNone(result["coverage_fraction"])


class PreprocessingTests(unittest.TestCase):
    def test_toolchain_status_shape(self):
        status = toolchain_status()
        self.assertIn("gpt", status)
        self.assertIn("pyroSAR", status)
        self.assertIn("sarpy", status)

    def test_available_toolchain_is_optional(self):
        result = available_toolchain()
        self.assertTrue(result is None or isinstance(result, str))

    def test_no_fake_processing_when_blocked(self):
        if available_toolchain() is None:
            from sentinel1_pilot.preprocessing import run_workflow
            with self.assertRaises(ProcessingBlocked):
                run_workflow([], {}, Path("."))


class ConfigTests(unittest.TestCase):
    def test_config_has_five_unique_scene_ids(self):
        import yaml
        config = yaml.safe_load(
            (PILOT_ROOT / "processing_parameters.yaml").read_text(encoding="utf-8"))
        scenes = config["pilot"]["scenes"]
        self.assertEqual(len(scenes), 5)
        self.assertEqual(len({scene["scene_id"] for scene in scenes}), 5)
        self.assertEqual(config["pilot"]["bbox_wgs84"], BBOX)

    def test_config_does_not_store_credentials(self):
        import yaml
        config = yaml.safe_load(
            (PILOT_ROOT / "processing_parameters.yaml").read_text(encoding="utf-8"))
        credentials = config["pilot"]["acquisition"]["credentials"]
        self.assertNotIn("username", credentials)
        self.assertNotIn("password", credentials)
        self.assertEqual(credentials["env_username"], "EARTHDATA_USERNAME")


if __name__ == "__main__":
    unittest.main()
