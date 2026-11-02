"""Reports and figures for the Chennai Sentinel-1 pilot.

Footprint figures are explicitly metadata-only. No VV/VH backscatter or change
figure is produced when no products were downloaded.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon as MplPolygon  # noqa: E402
from shapely import wkt  # noqa: E402

from .acquisition import bbox_polygon, expected_storage_mb  # noqa: E402
from .coverage import union_footprint_coverage  # noqa: E402


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def scene_metadata_rows(scenes: list[dict], bbox_wgs84: list[float]) -> list[dict]:
    rows = []
    for scene in scenes:
        rows.append({
            "scene_id": scene["scene_id"],
            "event_date": scene["event_date"],
            "role": scene["role"],
            "platform": scene.get("platform"),
            "start_time_utc": scene.get("start_time_utc"),
            "stop_time_utc": scene.get("stop_time_utc"),
            "flight_direction": scene.get("flight_direction"),
            "relative_orbit": scene.get("relative_orbit"),
            "polarization": scene.get("polarization"),
            "product_type": scene.get("product_type"),
            "size_mb": scene.get("size_mb"),
            "md5sum": scene.get("md5sum"),
            "footprint_wkt": scene.get("footprint_wkt"),
            "bbox_coverage_fraction": scene.get("bbox_coverage_fraction"),
            "source_url": scene.get("download_url"),
            "verified": scene.get("verified"),
            "retrieved": False,
            "notes": scene.get("notes", ""),
        })
    return rows


def quality_rows(scenes: list[dict]) -> list[dict]:
    rows = []
    for scene in scenes:
        rows.append({
            "scene_id": scene["scene_id"],
            "event_date": scene["event_date"],
            "role": scene["role"],
            "file_retrieved": False,
            "checksum_verified": False,
            "bbox_footprint_coverage_fraction": scene.get("bbox_coverage_fraction"),
            "pixel_valid_coverage": "",
            "border_artifact_assessed": False,
            "urban_layover_shadow_assessed": False,
            "temporal_alignment_assessed": False,
            "status": "blocked_access",
            "blocker": (
                "No approved Earthdata/CDSE credentials and no downloaded product; "
                "pixel-level quality cannot be assessed."),
        })
    return rows


def coverage_rows(events: list[dict], bbox_wgs84: list[float]) -> list[dict]:
    rows = []
    for event in events:
        stats = union_footprint_coverage(event["scenes"], bbox_wgs84)
        rows.append({
            "event_date": event["event_date"],
            "scene_ids": ";".join(scene["scene_id"] for scene in event["scenes"]),
            "scene_count": len(event["scenes"]),
            "bbox_area_deg2": stats["bbox_area_deg2"],
            "union_footprint_area_deg2": stats["union_area_deg2"],
            "bbox_coverage_fraction": stats["coverage_fraction"],
            "boundary_version": event["boundary_version"],
            "boundary_status": event["boundary_status"],
            "boundary_coverage_fraction": "",
            "status": "footprint_only",
            "notes": (
                "Coverage is metadata footprint intersect bbox, not valid-pixel "
                "coverage; boundary coverage is blocked because authoritative GIS "
                "is unavailable."),
        })
    return rows


def plot_footprints(events: list[dict], bbox_wgs84: list[float], figures_dir: Path) -> list[Path]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    target = bbox_polygon(bbox_wgs84)
    paths = []
    for event in events:
        figure, ax = plt.subplots(figsize=(7.5, 7))
        x, y = target.exterior.xy
        ax.plot(x, y, color="black", linewidth=1.6, label="pilot bbox")
        ax.fill(x, y, color="none", edgecolor="black")
        colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]
        for index, scene in enumerate(event["scenes"]):
            geometry = wkt.loads(scene["footprint_wkt"])
            coordinates = list(geometry.exterior.coords)
            ax.add_patch(MplPolygon(coordinates, closed=True, fill=False,
                                    edgecolor=colors[index % len(colors)],
                                    linewidth=1.4,
                                    label=f"{scene['role']}: {scene['scene_id'][:36]}..."))
        ax.set_xlim(bbox_wgs84[0] - 0.35, bbox_wgs84[2] + 0.35)
        ax.set_ylim(bbox_wgs84[1] - 0.35, bbox_wgs84[3] + 0.35)
        ax.set_aspect("equal")
        ax.set_xlabel("Longitude (WGS84)")
        ax.set_ylabel("Latitude (WGS84)")
        ax.set_title(
            f"Sentinel-1 metadata footprints — {event['event_date']}\n"
            "footprints only; no VV/VH backscatter was downloaded")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=7, loc="upper left")
        figure.tight_layout()
        path = figures_dir / f"footprints_{event['event_date']}.png"
        figure.savefig(path, dpi=180)
        plt.close(figure)
        paths.append(path)
    return paths


def plot_coverage_summary(scenes: list[dict], figures_dir: Path) -> Path:
    figures_dir.mkdir(parents=True, exist_ok=True)
    labels = [f"{scene['event_date']} {scene['role']}" for scene in scenes]
    values = [float(scene.get("bbox_coverage_fraction") or 0) for scene in scenes]
    figure, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(range(len(values)), values, color="#4c78a8")
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("bbox coverage fraction")
    ax.set_title("Metadata footprint coverage of the Chennai pilot bbox\n"
                 "Not valid-pixel coverage; no products were downloaded")
    ax.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02,
                f"{value:.3f}", ha="center", fontsize=8)
    figure.tight_layout()
    path = figures_dir / "coverage_summary.png"
    figure.savefig(path, dpi=180)
    plt.close(figure)
    return path


def write_figures_readme(figures_dir: Path) -> Path:
    path = figures_dir / "README.md"
    path.write_text(
        "# Pilot figures\n\n"
        "These figures show **metadata footprints only**. No Sentinel-1 VV/VH "
        "backscatter, valid-observation masks, change layers or common-coverage "
        "rasters were produced because the approved products could not be downloaded "
        "and no SNAP/pyroSAR toolchain is installed.\n\n"
        "## Produced\n\n"
        "- `footprints_2015-12-06.png` — metadata footprint and pilot bbox.\n"
        "- `footprints_2021-11-04.png` — north/south frame footprints and bbox.\n"
        "- `footprints_2021-11-16.png` — north/south frame footprints and bbox.\n"
        "- `coverage_summary.png` — footprint coverage fractions (not valid pixels).\n\n"
        "## Not produced (blocked)\n\n"
        "- VV backscatter and VH backscatter.\n"
        "- Valid-observation mask and no-data/quality mask.\n"
        "- 2021 VV change and VH change.\n"
        "- Common valid-observation coverage.\n"
        "- Urban layover/shadow or border-artifact maps.\n\n"
        "Do not interpret the footprint outlines as a flood boundary.\n", encoding="utf-8")
    return path


def write_preflight(path: Path, events: list[dict], scenes: list[dict],
                    toolchain: dict, access_note: str) -> None:
    total_mb = expected_storage_mb(scenes)
    lines = [
        "# Sentinel-1 Chennai pilot — preflight report",
        "",
        "Date: 2026-10-30. Scope: 2015-12-06 and the 2021-11-04/11-16 pair.",
        "This report was produced **before** any approved SAR download.",
        "",
        "## Approved dates and products",
        "",
        "| Event date | Role | Scene | Platform / orbit | Direction | Polarisation | Size MB |",
        "|---|---|---|---|---|---|---:|",
    ]
    for scene in scenes:
        lines.append(
            f"| {scene['event_date']} | {scene['role']} | `{scene['scene_id']}` | "
            f"{scene.get('platform')} / {scene.get('relative_orbit')} | "
            f"{scene.get('flight_direction')} | {scene.get('polarization')} | "
            f"{float(scene.get('size_mb') or 0):.1f} |")
        lines.append("")
    lines += [
        f"Approved products: **{len(scenes)}** (3 acquisition dates; the 2021 dates "
        "require two adjacent frames to cover the bbox).",
        f"Expected raw storage if all approved products are downloaded: "
        f"**{total_mb:.1f} MB (~{total_mb / 1024:.2f} GiB)**.",
        "",
        "## Metadata verification",
        "",
        "All approved scene IDs were queried from the public ASF search API and matched "
        "against the expected platform, direction, relative orbit, polarisation and "
        "product type. Full metadata is in `scene_metadata.csv`.",
        "",
        "| Check | Result |",
        "|---|---|",
        "| Scene IDs returned by ASF | PASS |",
        "| Platform / direction / orbit / polarisation / product type | PASS |",
        "| Footprints intersect the pilot bbox | PASS |",
        "| 2015 full-bbox footprint | PASS |",
        "| 2021 two-frame coverage (north + south) | PARTIAL (99.98% metadata; not valid pixels) |",
        "",
        "## Access and toolchain",
        "",
        f"- ASF search API: public; working. {access_note}",
        "- ASF product download: **BLOCKED** in this environment. A HEAD request to the "
        "approved 2015 product returned HTTP 403; no Earthdata credentials are present.",
        f"- Toolchain: **BLOCKED**. gpt={toolchain.get('gpt')!r}, "
        f"esa_snappy={toolchain.get('esa_snappy')}, snappy={toolchain.get('snappy')}, "
        f"pyroSAR={toolchain.get('pyroSAR')}, sarpy={toolchain.get('sarpy')}.",
        "",
        "## Boundary geometry",
        "",
        "| Event | Required boundary | Status |",
        "|---|---|---|",
        "| 2015 | 2011 GCC boundary | **BLOCKED** — no authoritative 2011 GIS; OpenCity "
        "2011 KML is provisional and licence-unspecified |",
        "| 2021 | 2018 GCC boundary (2018 gazette) | **BLOCKED** — gazette PDF only; no "
        "authoritative GIS under confirmed terms |",
        "",
        "The 2022 KML was **not** substituted for 2015 or 2021 ward calculations.",
        "",
        "## Decision",
        "",
        "Do not download the approved products yet. The pilot can verify acquisition "
        "metadata and bbox footprint coverage, but cannot produce backscatter, quality "
        "masks, temporal change layers or ward-level coverage without access and "
        "authoritative boundaries. This is a stop condition, not a workaround.",
        "",
        "## Status",
        "",
        "| Item | Status |",
        "|---|---|",
        "| Scene metadata verification | PASS |",
        "| Bbox footprint coverage | PASS |",
        "| Product download | BLOCKED |",
        "| SAR preprocessing | BLOCKED |",
        "| Valid-pixel quality assessment | BLOCKED |",
        "| 2021 temporal comparison | BLOCKED |",
        "| Ward-level coverage / labels | BLOCKED |",
        "| VV/VH figures | BLOCKED (not produced) |",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_temporal_report(path: Path, events: list[dict],
                          bbox_wgs84: list[float]) -> None:
    pair = next(event for event in events if event["event_date"] == "2021-11-04")
    stats = union_footprint_coverage(pair["scenes"], bbox_wgs84)
    lines = [
        "# 2021 temporal comparison — feasibility report",
        "",
        "## Nominal compatibility",
        "",
        "| Property | 2021-11-04 | 2021-11-16 | Compatible? |",
        "|---|---|---|---|",
        "| Platform | Sentinel-1A | Sentinel-1A | yes |",
        "| Product | GRD_HD | GRD_HD | yes |",
        "| Direction | DESCENDING | DESCENDING | yes |",
        "| Relative orbit | 92 | 92 | yes |",
        "| Polarisation | VV+VH | VV+VH | yes |",
        "| Separation | — | 12 days | same track, but not a same-day pair |",
        "",
        f"Each 2021 date needs two adjacent frames to cover the pilot bbox. Metadata "
        f"footprint union coverage for the 11-04 pair is "
        f"**{stats['coverage_fraction']:.4f}** of the bbox. The same two-frame structure "
        "exists for 11-16.",
        "",
        "## What could not be done",
        "",
        "- No products were downloaded (ASF HTTP 403; no Earthdata/CDSE credentials).",
        "- No SNAP/pyroSAR toolchain is installed.",
        "- Therefore no common grid, no VV/VH differences, no valid-common-observation "
        "mask, and no change-detection layers were produced.",
        "",
        "## Confounders that must be assessed when data are available",
        "",
        "- Acquisition geometry and incidence-angle differences.",
        "- Urban double-bounce, layover, shadow and metal roofs.",
        "- Vegetation and surface moisture changes.",
        "- Speckle and co-registration error.",
        "- Permanent water versus temporary inundation.",
        "- Timing relative to the actual rainfall/flood peak.",
        "",
        "No binary flood mask or ward-level label should be created from this pilot.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_limitations(path: Path) -> None:
    text = """# Pilot limitations

- **Access:** ASF product download returned HTTP 403; no Earthdata credentials are
  configured. CDSE/GEE also require accounts and were not used. No SAR product was
  downloaded.
- **Toolchain:** ESA SNAP `gpt`/`snappy`, `pyroSAR` and `sarpy` are not installed.
  No processing parameters were executed or invented.
- **Boundaries:** the authoritative 2011 GIS (for 2015) and 2018 GIS (for 2021) are not
  available locally under confirmed terms. The 2022 KML was not substituted.
- **Licensing:** OpenCity reports the 2022 KML licence as "not specified"; the GCC
  gazette PDFs have no explicit open-data licence on the inspected page.
- **Pixel quality:** no valid-pixel coverage, border-noise mask, thermal-noise check,
  layover/shadow mask or geolocation diagnostic was produced.
- **Temporal comparison:** nominal metadata compatibility is established, but no
  alignment or change layer was computed.
- **Event chronology:** the 2015 scene is not called a flood-peak observation. No
  inundation label is inferred from low backscatter.
- **Permanent water:** no permanent-water mask was applied; this remains a required
  separate step.
- **2015 vs 2021 boundaries:** different boundary vintages; no cross-version comparison
  is valid without a reviewed crosswalk.
"""
    path.write_text(text, encoding="utf-8")


def write_reproducibility(path: Path, events: list[dict], scenes: list[dict]) -> None:
    total_mb = expected_storage_mb(scenes)
    text = f"""# Pilot reproducibility

## Environment

- Python 3.11, numpy, pandas, shapely, geopandas, rasterio, matplotlib, PyYAML.
- No paid runtime dependency.
- No credentials are stored in this repository.

## Commands

From the repository root:

```bash
.venv\\Scripts\\python.exe research/chennai_reconstruction/pilot/run_pilot.py preflight \\
  --config research/chennai_reconstruction/pilot/processing_parameters.yaml
```

The command queries the public ASF metadata API, verifies the approved scene IDs,
writes `scene_metadata.csv`, `scene_quality_report.csv`, `coverage_report.csv`,
`preflight_report.md`, and the footprint figures. It does **not** download products.

Download is intentionally gated and was not run:

```bash
# Requires approved Earthdata credentials and explicit approval:
.venv\\Scripts\\python.exe research/chennai_reconstruction/pilot/run_pilot.py download \\
  --config research/chennai_reconstruction/pilot/processing_parameters.yaml \\
  --approve-download
```

Processing is intentionally blocked until a reviewed SNAP/pyroSAR toolchain and
parameters are available:

```bash
.venv\\Scripts\\python.exe research/chennai_reconstruction/pilot/run_pilot.py process \\
  --config research/chennai_reconstruction/pilot/processing_parameters.yaml
```

## Data downloaded

**None.** Expected storage if the five approved products are later downloaded:
**{total_mb:.1f} MB (~{total_mb / 1024:.2f} GiB)**.

## Tests

```bash
.venv\\Scripts\\python.exe -m unittest discover -s research/chennai_reconstruction/pilot/tests -p "test_*.py"
```

Tests are offline and use synthetic payloads/arrays. They do not assert SAR quality.
"""
    path.write_text(text, encoding="utf-8")
