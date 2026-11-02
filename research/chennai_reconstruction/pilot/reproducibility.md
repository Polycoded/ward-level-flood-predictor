# Pilot reproducibility

## Environment

- Python 3.11, numpy, pandas, shapely, geopandas, rasterio, matplotlib, PyYAML.
- No paid runtime dependency.
- No credentials are stored in this repository.

## Commands

From the repository root:

```bash
.venv\Scripts\python.exe research/chennai_reconstruction/pilot/run_pilot.py preflight \
  --config research/chennai_reconstruction/pilot/processing_parameters.yaml
```

The command queries the public ASF metadata API, verifies the approved scene IDs,
writes `scene_metadata.csv`, `scene_quality_report.csv`, `coverage_report.csv`,
`preflight_report.md`, and the footprint figures. It does **not** download products.

Download is intentionally gated and was not run:

```bash
# Requires approved Earthdata credentials and explicit approval:
.venv\Scripts\python.exe research/chennai_reconstruction/pilot/run_pilot.py download \
  --config research/chennai_reconstruction/pilot/processing_parameters.yaml \
  --approve-download
```

Processing is intentionally blocked until a reviewed SNAP/pyroSAR toolchain and
parameters are available:

```bash
.venv\Scripts\python.exe research/chennai_reconstruction/pilot/run_pilot.py process \
  --config research/chennai_reconstruction/pilot/processing_parameters.yaml
```

## Data downloaded

**None.** Expected storage if the five approved products are later downloaded:
**4758.7 MB (~4.65 GiB)**.

## Tests

```bash
.venv\Scripts\python.exe -m unittest discover -s research/chennai_reconstruction/pilot/tests -p "test_*.py"
```

Tests are offline and use synthetic payloads/arrays. They do not assert SAR quality.
