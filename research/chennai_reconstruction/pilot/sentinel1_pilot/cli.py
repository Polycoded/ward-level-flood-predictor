"""Command-line entry point for the Chennai Sentinel-1 technical pilot."""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

from .acquisition import (
    AccessBlocked,
    download_scene,
    expected_storage_mb,
    footprint_coverage,
    query_asf,
    resolve_credentials,
    select_scenes,
    verify_scene,
)
from .coverage import boundary_coverage
from .preprocessing import ProcessingBlocked, available_toolchain, run_workflow, toolchain_status
from .reporting import (
    coverage_rows,
    plot_coverage_summary,
    plot_footprints,
    quality_rows,
    scene_metadata_rows,
    write_csv,
    write_figures_readme,
    write_limitations,
    write_preflight,
    write_reproducibility,
    write_temporal_report,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]


def load_config(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "pilot" not in data:
        raise ValueError("Config must contain a top-level 'pilot' mapping")
    pilot = data["pilot"]
    if not pilot.get("bbox_wgs84") or len(pilot["bbox_wgs84"]) != 4:
        raise ValueError("pilot.bbox_wgs84 must be [west, south, east, north]")
    if not pilot.get("scenes"):
        raise ValueError("pilot.scenes must not be empty")
    return pilot


def _group_events(pilot: dict) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for spec in pilot["scenes"]:
        event_date = spec["event_date"]
        if hasattr(event_date, "isoformat"):
            event_date = event_date.isoformat()
        event_date = str(event_date)
        grouped.setdefault(event_date, []).append(spec)
    events = []
    for event_date, specs in grouped.items():
        year = event_date[:4]
        policy_map = {str(key): value
                      for key, value in pilot.get("boundary_policy", {}).items()}
        policy = policy_map.get(year, {})
        events.append({
            "event_date": event_date,
            "boundary_version": policy.get("boundary_version", "unknown"),
            "boundary_status": policy.get("status", "blocked"),
            "specs": specs,
        })
    return events


def _date_window(event_date: str) -> tuple[str, str]:
    start = date.fromisoformat(event_date)
    end = start + timedelta(days=1)
    return f"{start.isoformat()}T00:00:00Z", f"{end.isoformat()}T00:00:00Z"


def run_preflight(config_path: Path) -> int:
    pilot = load_config(config_path)
    bbox = pilot["bbox_wgs84"]
    events = _group_events(pilot)
    scenes = []
    failures = []
    for event in events:
        start, end = _date_window(event["event_date"])
        available = query_asf(start, end, bbox,
                              processing_level=pilot["acquisition"].get("processing_level", "GRD_HD"))
        specs = {spec["scene_id"]: spec for spec in event["specs"]}
        selected = select_scenes(available, list(specs))
        for scene_id, item in selected.items():
            spec = specs[scene_id]
            errors = verify_scene(item, spec)
            if errors:
                failures.extend(f"{scene_id}: {error}" for error in errors)
            scene = {
                "scene_id": scene_id,
                "event_date": event["event_date"],
                "role": spec["role"],
                "platform": item.get("platform"),
                "start_time_utc": item.get("startTime"),
                "stop_time_utc": item.get("stopTime"),
                "flight_direction": item.get("flightDirection"),
                "relative_orbit": item.get("relativeOrbit"),
                "polarization": item.get("polarization"),
                "product_type": item.get("processingLevel"),
                "size_mb": item.get("sizeMB"),
                "md5sum": item.get("md5sum"),
                "footprint_wkt": item.get("stringFootprint"),
                "stringFootprint": item.get("stringFootprint"),
                "bbox_coverage_fraction": footprint_coverage(item, bbox),
                "download_url": item.get("downloadUrl"),
                "verified": not errors,
                "notes": "; ".join(errors),
            }
            scenes.append(scene)
    scene_by_event: dict[str, list[dict]] = {}
    for scene in scenes:
        scene_by_event.setdefault(scene["event_date"], []).append(scene)
    events = [event | {"scenes": scene_by_event[event["event_date"]]} for event in events]

    out = pilot["outputs"]
    base = REPO_ROOT
    metadata_path = base / out["scene_metadata_csv"]
    quality_path = base / out["quality_csv"]
    coverage_path = base / out["coverage_csv"]
    preflight_path = base / out["preflight_report"]
    temporal_path = base / out["temporal_report"]
    figures_dir = base / out["figures_dir"]

    write_csv(metadata_path, scene_metadata_rows(scenes, bbox),
              list(scene_metadata_rows(scenes, bbox)[0].keys()))
    write_csv(quality_path, quality_rows(scenes), list(quality_rows(scenes)[0].keys()))
    write_csv(coverage_path, coverage_rows(events, bbox),
              list(coverage_rows(events, bbox)[0].keys()))
    access_note = (
        "A product download HEAD request returned HTTP 403; no Earthdata credentials "
        "are present in this environment.")
    write_preflight(preflight_path, events, scenes, toolchain_status(), access_note)
    write_temporal_report(temporal_path, events, bbox)
    write_limitations(base / "research/chennai_reconstruction/pilot/limitations.md")
    write_reproducibility(base / "research/chennai_reconstruction/pilot/reproducibility.md",
                          events, scenes)
    plot_footprints(events, bbox, figures_dir)
    plot_coverage_summary(scenes, figures_dir)
    write_figures_readme(figures_dir)

    boundary_results = {}
    for event in events:
        boundary_path = pilot.get("boundary_paths", {}).get(event["event_date"])
        if boundary_path:
            boundary_results[event["event_date"]] = boundary_coverage(
                base / boundary_path, event["scenes"])
    print(f"Preflight wrote {len(scenes)} approved products for {len(events)} dates")
    print(f"Expected raw storage: {expected_storage_mb(scenes):.1f} MB")
    print(f"Metadata failures: {len(failures)}")
    print(f"Toolchain: {toolchain_status()}")
    return 0 if not failures else 1


def run_download(config_path: Path, approve: bool) -> int:
    if not approve:
        print("Refusing to download without --approve-download")
        return 2
    pilot = load_config(config_path)
    credentials = resolve_credentials()
    if credentials is None:
        print("BLOCKED: no EARTHDATA_USERNAME/EARTHDATA_PASSWORD or .netrc credentials")
        return 2
    out_dir = REPO_ROOT / pilot["acquisition"]["storage"]["raw"]
    # Re-query metadata so IDs rather than stale URLs are used.
    bbox = pilot["bbox_wgs84"]
    events = _group_events(pilot)
    downloaded = []
    for event in events:
        start, end = _date_window(event["event_date"])
        available = query_asf(start, end, bbox,
                              processing_level=pilot["acquisition"].get("processing_level", "GRD_HD"))
        specs = {spec["scene_id"]: spec for spec in event["specs"]}
        selected = select_scenes(available, list(specs))
        for scene_id, item in selected.items():
            destination = out_dir / f"{scene_id}.zip"
            if destination.exists():
                print(f"SKIP existing {destination.name}")
                continue
            print(f"Downloading {scene_id} ...")
            try:
                download_scene(item["downloadUrl"], destination,
                               expected_md5=item.get("md5sum"), credentials=credentials)
            except AccessBlocked as exc:
                print(f"BLOCKED: {exc}")
                return 2
            downloaded.append(destination)
    print(f"Downloaded {len(downloaded)} products to {out_dir}")
    return 0


def run_process(config_path: Path) -> int:
    pilot = load_config(config_path)
    raw_dir = REPO_ROOT / pilot["acquisition"]["storage"]["raw"]
    scene_paths = sorted(raw_dir.glob("*.SAFE")) + sorted(raw_dir.glob("*.zip"))
    toolchain = available_toolchain()
    if toolchain is None:
        print("BLOCKED: no approved SAR preprocessing toolchain")
        print(toolchain_status())
        return 2
    try:
        run_workflow(scene_paths, pilot, REPO_ROOT / pilot["acquisition"]["storage"]["processed"])
    except ProcessingBlocked as exc:
        print(f"BLOCKED: {exc}")
        return 2
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "download", "process"])
    parser.add_argument("--config", type=Path,
                        default=Path("research/chennai_reconstruction/pilot/processing_parameters.yaml"))
    parser.add_argument("--approve-download", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "preflight":
        return run_preflight(args.config)
    if args.command == "download":
        return run_download(args.config, args.approve_download)
    return run_process(args.config)


if __name__ == "__main__":
    sys.exit(main())
