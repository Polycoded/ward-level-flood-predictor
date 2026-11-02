"""Small, reproducible Sentinel-1 acquisition helpers for the Chennai pilot.

No credentials are stored here. Downloads require an approved route and are gated by
the CLI. The ASF search endpoint is public; product download is authenticated.
"""

from __future__ import annotations

import base64
import hashlib
import json
import netrc
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from shapely import wkt
from shapely.geometry import box
from shapely.ops import unary_union

ASF_SEARCH_URL = "https://api.daac.asf.alaska.edu/services/search/param"


class PilotError(RuntimeError):
    """Base class for pilot failures."""


class AccessBlocked(PilotError):
    """The approved download route is unavailable or not authorized."""


class SceneVerificationError(PilotError):
    """ASF metadata does not match the approved scene specification."""


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str


def credentials_from_env() -> Credentials | None:
    username = os.environ.get("EARTHDATA_USERNAME")
    password = os.environ.get("EARTHDATA_PASSWORD")
    if username and password:
        return Credentials(username, password)
    return None


def credentials_from_netrc(host: str = "urs.earthdata.nasa.gov") -> Credentials | None:
    path = Path.home() / ".netrc"
    if not path.exists():
        return None
    try:
        auth = netrc.netrc(path).authenticators(host)
    except (OSError, netrc.NetrcParseError):
        return None
    if not auth:
        return None
    login, _account, password = auth
    if login and password:
        return Credentials(login, password)
    return None


def resolve_credentials() -> Credentials | None:
    return credentials_from_env() or credentials_from_netrc()


def _asf_request(params: dict) -> dict:
    url = ASF_SEARCH_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise PilotError(f"ASF metadata query failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise PilotError(f"ASF metadata query failed: {exc.reason}") from exc


def parse_asf_payload(payload) -> list[dict]:
    """ASF returns either a list of products or a nested one-element list."""
    results = payload
    while isinstance(results, list) and len(results) == 1 and isinstance(results[0], list):
        results = results[0]
    if isinstance(results, dict):
        results = [results]
    if not isinstance(results, list):
        raise PilotError(f"Unexpected ASF payload type: {type(results)!r}")
    return [item for item in results if isinstance(item, dict)]


def dedupe_scenes(items: list[dict]) -> dict[str, dict]:
    scenes: dict[str, dict] = {}
    for item in items:
        scene_id = item.get("sceneId")
        if not scene_id:
            continue
        if scene_id in scenes:
            existing = scenes[scene_id]
            for key in ("md5sum", "downloadUrl", "startTime", "stringFootprint"):
                if existing.get(key) and item.get(key) and existing[key] != item[key]:
                    raise PilotError(f"Conflicting ASF metadata for {scene_id}: {key}")
            continue
        scenes[scene_id] = item
    return scenes


def query_asf(start_iso: str, end_iso: str, bbox_wgs84: list[float],
              processing_level: str = "GRD_HD") -> dict[str, dict]:
    params = {
        "platform": "Sentinel-1",
        "processingLevel": processing_level,
        "start": start_iso,
        "end": end_iso,
        "bbox": ",".join(f"{value:.6f}" for value in bbox_wgs84),
        "output": "json",
        "maxResults": "100",
    }
    return dedupe_scenes(parse_asf_payload(_asf_request(params)))


def select_scenes(items: dict[str, dict], scene_ids: list[str]) -> dict[str, dict]:
    selected = {}
    missing = []
    for scene_id in scene_ids:
        if scene_id not in items:
            missing.append(scene_id)
        else:
            selected[scene_id] = items[scene_id]
    if missing:
        raise PilotError(f"Approved scenes not returned by ASF: {missing}")
    return selected


def verify_scene(item: dict, spec: dict) -> list[str]:
    checks = {
        "platform": spec.get("expected_platform"),
        "flightDirection": spec.get("expected_direction"),
        "relativeOrbit": spec.get("expected_relative_orbit"),
        "polarization": spec.get("expected_polarization"),
        "processingLevel": spec.get("expected_product_type"),
    }
    errors = []
    for key, expected in checks.items():
        if expected is None:
            continue
        observed = item.get(key)
        if str(observed).upper() != str(expected).upper():
            errors.append(f"{key}: expected {expected!r}, found {observed!r}")
    if not item.get("stringFootprint"):
        errors.append("missing stringFootprint")
    if not item.get("downloadUrl"):
        errors.append("missing downloadUrl")
    return errors


def footprint_box(item: dict):
    return wkt.loads(item["stringFootprint"])


def bbox_polygon(bbox_wgs84: list[float]):
    west, south, east, north = bbox_wgs84
    return box(west, south, east, north)


def footprint_coverage(item: dict, bbox_wgs84: list[float]) -> float:
    target = bbox_polygon(bbox_wgs84)
    footprint = footprint_box(item)
    if target.area <= 0:
        raise PilotError("bbox has zero area")
    return float(footprint.intersection(target).area / target.area)


def union_coverage(items: list[dict], bbox_wgs84: list[float]) -> float:
    if not items:
        return 0.0
    target = bbox_polygon(bbox_wgs84)
    union = unary_union([footprint_box(item) for item in items])
    return float(union.intersection(target).area / target.area)


def expected_storage_mb(items: list[dict]) -> float:
    return float(sum(float(item.get("sizeMB") or item.get("size_mb") or 0)
                     for item in items))


def part_path(destination: Path) -> Path:
    return destination.with_name(destination.name + ".part")


def needs_download(destination: Path) -> bool:
    return not destination.exists()


def _auth_header(credentials: Credentials) -> str:
    token = base64.b64encode(
        f"{credentials.username}:{credentials.password}".encode()).decode("ascii")
    return f"Basic {token}"


def download_scene(url: str, destination: Path, expected_md5: str | None = None,
                   credentials: Credentials | None = None,
                   chunk_size: int = 1024 * 1024) -> Path:
    """Download one approved scene, resuming a partial file when possible."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = part_path(destination)
    headers = {"User-Agent": "chennai-s1-pilot/0.1"}
    if credentials is not None:
        headers["Authorization"] = _auth_header(credentials)
    existing = partial.stat().st_size if partial.exists() else 0
    if existing:
        headers["Range"] = f"bytes={existing}-"
    request = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=120)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise AccessBlocked(
                "Sentinel-1 download requires an approved Earthdata/CDSE login; "
                f"HTTP {exc.code} from {url}") from exc
        raise PilotError(f"Download failed: HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise PilotError(f"Download failed: {exc.reason}") from exc
    mode = "ab" if existing and response.status == 206 else "wb"
    with response, partial.open(mode) as handle:
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            handle.write(chunk)
    if expected_md5:
        digest = hashlib.md5()
        with partial.open("rb") as handle:
            for chunk in iter(lambda: handle.read(chunk_size), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != expected_md5.lower():
            raise PilotError(f"MD5 mismatch for {destination.name}")
    partial.replace(destination)
    return destination
