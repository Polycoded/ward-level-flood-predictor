"""Preprocessing adapter for the Chennai Sentinel-1 pilot.

The pilot does not invent SAR processing parameters or outputs. If no approved
toolchain/data are available the adapter raises ProcessingBlocked with the reason.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

from .acquisition import PilotError


class ProcessingBlocked(PilotError):
    """The approved preprocessing toolchain or input products are unavailable."""


def toolchain_status() -> dict:
    return {
        "gpt": shutil.which("gpt"),
        "snappy": bool(importlib.util.find_spec("snappy")),
        "esa_snappy": bool(importlib.util.find_spec("esa_snappy")),
        "pyroSAR": bool(importlib.util.find_spec("pyroSAR")),
        "sarpy": bool(importlib.util.find_spec("sarpy")),
    }


def available_toolchain() -> str | None:
    status = toolchain_status()
    if status["gpt"]:
        return "ESA_SNAP_gpt"
    if status["esa_snappy"] or status["snappy"]:
        return "ESA_SNAP_snappy"
    if status["pyroSAR"]:
        return "pyroSAR"
    if status["sarpy"]:
        return "sarpy_only"
    return None


def validate_safe_product(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise ProcessingBlocked(f"Product not found: {path}")
    manifest = path / "manifest.safe"
    measurement = list(path.glob("measurement/*"))
    return {
        "path": str(path),
        "manifest_present": manifest.exists(),
        "measurement_files": [item.name for item in measurement],
        "complete_enough_for_review": manifest.exists() and bool(measurement),
    }


def run_workflow(scene_paths: list[Path], config: dict, output_dir: Path) -> dict:
    """Run an approved SNAP/pyroSAR workflow.

    This is intentionally not implemented against a non-existent toolchain. The
    function documents the required preconditions and fails loudly.
    """
    toolchain = available_toolchain()
    if toolchain is None:
        raise ProcessingBlocked(
            "No approved SAR preprocessing toolchain is installed. "
            "Need ESA SNAP gpt/snappy or pyroSAR with a supported backend. "
            f"Toolchain status: {toolchain_status()}")
    if not scene_paths:
        raise ProcessingBlocked("No downloaded scene products were supplied")
    for path in scene_paths:
        validate_safe_product(path)
    raise ProcessingBlocked(
        f"Toolchain {toolchain} is present but no reviewed SNAP graph/parameters "
        "have been approved for this pilot. Do not invent processing parameters.")
