"""Build an ASE structure database from DeltaXRDbench single-phase CIFs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import warnings
from pathlib import Path

import numpy as np
from ase.db import connect
from ase.io import read


def cif_atom_count(cif: Path) -> int:
    """Return the atom count recorded in a generated reference CIF header."""
    for line in cif.open(encoding="utf-8", errors="replace"):
        if line.lstrip().startswith("_chemical_formula_sum"):
            # The generated CIFs use e.g. ``'Ba4 H12 C8 O8 F2'``.
            return sum(int(count or 1) for _, count in __import__("re").findall(r"([A-Z][a-z]?)(\d*)", line))
    raise ValueError(f"missing _chemical_formula_sum: {cif}")


def records(dataset_root: Path):
    """Yield the source ID, CIF and sample ID for every single-phase record."""
    for source in ("rruff", "opxrd"):
        manifest = dataset_root / source / "manifest.jsonl"
        for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
            entry = json.loads(line)
            if entry.get("task") != "identification.single":
                continue
            phase_ids = entry.get("ground_truth", {}).get("phase_ids", [])
            structure_files = entry.get("ground_truth", {}).get("structure_files", [])
            if len(phase_ids) != 1 or len(structure_files) != 1:
                raise ValueError(f"{manifest}:{line_number}: expected one phase ID and CIF")
            cif = dataset_root / source / structure_files[0]
            if not cif.is_file():
                raise FileNotFoundError(cif)
            yield source, phase_ids[0], cif, entry["sample_id"]


def append_batch(database: Path, dataset_root: Path, batch_size: int, max_atoms: int) -> tuple[int, int]:
    """Append one validated batch, returning the previous and new row counts."""
    all_records = list(records(dataset_root))
    if len(all_records) != 2044 or len({record[1] for record in all_records}) != len(all_records):
        raise ValueError("expected 2,044 unique RRUFF/opXRD single-phase records")
    all_records = [record for record in all_records if cif_atom_count(record[2]) <= max_atoms]
    db = connect(database)
    start = db.count()
    if start > len(all_records):
        raise ValueError("database has more rows than the input dataset")
    if start and max(row.Label for row in db.select()) != start - 1:
        raise ValueError("database Label values are not a contiguous append-only sequence")
    stop = min(start + batch_size, len(all_records))
    warnings.filterwarnings("ignore", category=UserWarning, module="ase.io.cif")
    for label, (source, phase_id, cif, sample_id) in enumerate(all_records[start:stop], start):
        atoms = read(cif, format="cif")
        if (len(atoms) == 0 or atoms.get_volume() <= 0 or not np.isfinite(atoms.cell.array).all()
                or not np.isfinite(atoms.positions).all() or np.any(atoms.numbers <= 0)):
            raise ValueError(f"invalid parsed structure: {phase_id}")
        db.write(
            atoms,
            Label=label,
            cryst_id=phase_id,
            source=source,
            source_id=phase_id,
            sample_id=sample_id,
            cif_filename=cif.name,
            cif_sha256=hashlib.sha256(cif.read_bytes()).hexdigest(),
        )
    return start, db.count()


def verify(database: Path, dataset_root: Path, max_atoms: int) -> None:
    """Verify every ID and ASE round-trip against its source CIF."""
    all_records = [record for record in records(dataset_root) if cif_atom_count(record[2]) <= max_atoms]
    db = connect(database)
    if db.count() != len(all_records):
        raise ValueError(f"row count mismatch: {db.count()} != {len(all_records)}")
    warnings.filterwarnings("ignore", category=UserWarning, module="ase.io.cif")
    for label, (source, phase_id, cif, sample_id) in enumerate(all_records):
        original = read(cif, format="cif")
        row = db.get(Label=label)
        restored = row.toatoms()
        if (row.cryst_id, row.source, row.source_id, row.sample_id, row.cif_filename) != (phase_id, source, phase_id, sample_id, cif.name):
            raise ValueError(f"metadata mismatch: {phase_id}")
        if (len(restored) != len(original) or not np.array_equal(restored.numbers, original.numbers)
                or not np.allclose(restored.positions, original.positions, rtol=0, atol=1e-12)
                or not np.allclose(restored.cell.array, original.cell.array, rtol=0, atol=1e-12)
                or not np.array_equal(restored.pbc, original.pbc)):
            raise ValueError(f"ASE round-trip mismatch: {phase_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--dataset-root", type=Path, default=Path("datasets"))
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--max-atoms", type=int, default=500)
    parser.add_argument("--all", action="store_true", help="append batches until all records are written")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify(args.database, args.dataset_root, args.max_atoms)
        print(f"verified {args.database}")
    else:
        while True:
            start, stop = append_batch(args.database, args.dataset_root, args.batch_size, args.max_atoms)
            print(f"rows: {start} -> {stop}", flush=True)
            if start == stop or stop == 2044 or not args.all:
                break


if __name__ == "__main__":
    main()
