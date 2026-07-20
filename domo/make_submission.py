"""Small helpers for writing XRDBench submission.jsonl files.

Copy this file into a model project or import it from the repository root.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Sequence


def write_jsonl(records: Iterable[dict], output: str | Path) -> Path:
    """Write validated-in-shape submission records as UTF-8 JSON Lines."""
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    with destination.open("w", encoding="utf-8") as handle:
        for record in records:
            sample_id = record.get("sample_id")
            if not isinstance(sample_id, str) or not sample_id:
                raise ValueError("every record needs a non-empty sample_id")
            if sample_id in seen:
                raise ValueError(f"duplicate sample_id: {sample_id}")
            if not isinstance(record.get("prediction"), dict):
                raise ValueError(f"{sample_id}: prediction must be an object")
            seen.add(sample_id)
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return destination


def from_cif_paths(sample_id: str, cif_paths: Sequence[str | Path]) -> dict:
    """Create the recommended submission record from existing CIF files."""
    paths = [Path(path) for path in cif_paths]
    if not paths or not all(path.is_file() for path in paths):
        raise ValueError("cif_paths must contain existing CIF files")
    return {"sample_id": sample_id, "prediction": {"structure_files": [str(path) for path in paths]}}


def from_pymatgen_structures(sample_id: str, structures: Sequence, output_directory: str | Path) -> dict:
    """Export pymatgen Structure objects as CIF files and create a record."""
    from pymatgen.io.cif import CifWriter

    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, structure in enumerate(structures, 1):
        path = directory / f"{sample_id}-phase-{index}.cif"
        CifWriter(structure).write_file(path)
        paths.append(path)
    return from_cif_paths(sample_id, paths)


def from_phase_ids(sample_id: str, phase_ids: Sequence[str]) -> dict:
    """Legacy compatibility format when a model knows canonical database IDs."""
    if not phase_ids or len(set(phase_ids)) != len(phase_ids):
        raise ValueError("phase_ids must be non-empty and unique")
    return {"sample_id": sample_id, "prediction": {"phase_ids": list(phase_ids)}}
