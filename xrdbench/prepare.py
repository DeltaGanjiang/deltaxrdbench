"""Reproducible builders for the MP500, RRUFF, and opXRD datasets."""

from __future__ import annotations

import argparse
import ast
import glob
import json
import re
import warnings
from pathlib import Path
from typing import Iterable

import h5py
import numpy as np
from ase.db import connect
from ase.io import write
from ase.spacegroup import crystal


DEFAULT_GRID = (10.0, 80.0, 0.01)


def _grid(start: float, stop: float, step: float) -> np.ndarray:
    if not start < stop or step <= 0:
        raise ValueError("grid requires start < stop and a positive step")
    return np.arange(start, stop + step / 2, step, dtype=np.float32)


def _normalise_intensity(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    values = np.maximum(values - np.percentile(values, 1), 0)
    area = np.trapz(values)
    if not np.isfinite(area) or area <= 0:
        raise ValueError("pattern has no positive integrated intensity")
    return (values / area).astype(np.float32)


def _interpolate(angle: Iterable[float], intensity: Iterable[float], grid: np.ndarray) -> np.ndarray:
    x, y = np.asarray(angle, dtype=float), np.asarray(intensity, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = x[valid], y[valid]
    order = np.argsort(x)
    x, y = x[order], y[order]
    x, unique = np.unique(x, return_index=True)
    y = y[unique]
    if len(x) < 3:
        raise ValueError("pattern has fewer than three valid points")
    return _normalise_intensity(np.interp(grid, x, y, left=0, right=0))


def _fractions(rng: np.random.Generator, phases: int, minimum: float = 0.10) -> np.ndarray:
    if phases not in (2, 3) or phases * minimum >= 1:
        raise ValueError("only 2- or 3-phase mixtures with feasible minimum fractions are supported")
    return minimum + (1 - phases * minimum) * rng.dirichlet(np.ones(phases))


def _mixtures(patterns: np.ndarray, phase_ids: list[str], count: int, rng: np.random.Generator) -> tuple[np.ndarray, list[list[str]], np.ndarray]:
    if len(patterns) < 3:
        raise ValueError("at least three single-phase patterns are required for mixture generation")
    mixed = np.empty((count, patterns.shape[1]), dtype=np.float32)
    labels: list[list[str]] = []
    fractions = np.empty((count, 3), dtype=np.float32)
    fractions.fill(np.nan)
    for index in range(count):
        phase_count = int(rng.integers(2, 4))
        selected = rng.choice(len(patterns), size=phase_count, replace=False)
        weights = _fractions(rng, phase_count)
        mixed[index] = np.sum(patterns[selected] * weights[:, None], axis=0)
        labels.append([phase_ids[item] for item in selected])
        fractions[index, :phase_count] = weights
    return mixed, labels, fractions


def _simulate_pattern(atoms, grid: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Generate a Cu Kα powder pattern with broadening, background, and noise."""
    from pymatgen.analysis.diffraction.xrd import XRDCalculator
    from pymatgen.io.ase import AseAtomsAdaptor

    pattern = XRDCalculator(wavelength="CuKa").get_pattern(AseAtomsAdaptor.get_structure(atoms), two_theta_range=(float(grid[0]), float(grid[-1])))
    positions, intensities = np.asarray(pattern.x, dtype=float), np.asarray(pattern.y, dtype=float)
    if len(positions) == 0 or np.max(intensities) <= 0:
        raise ValueError("structure has no simulated reflections in the requested range")
    fwhm = rng.uniform(0.08, 0.20)
    sigma = fwhm / 2.35482
    shifted = positions + rng.uniform(-0.03, 0.03)
    signal = np.exp(-0.5 * ((grid[:, None] - shifted[None, :]) / sigma) ** 2) @ intensities
    signal /= signal.max()
    scaled_grid = (grid - grid[0]) / (grid[-1] - grid[0])
    background = rng.uniform(0.002, 0.02) * (1 + rng.uniform(-0.5, 0.5) * scaled_grid)
    noise = rng.normal(0, rng.uniform(0.001, 0.006), size=len(grid)) * np.sqrt(np.maximum(signal + background, 0.02))
    return _normalise_intensity(np.maximum(signal + background + noise, 0))


def _write_dataset(output: Path, source: str, grid: np.ndarray, patterns: np.ndarray, phase_ids: list[str], atoms: list, mixture_count: int, seed: int) -> None:
    if output.exists():
        raise FileExistsError(f"output already exists: {output}; choose a new directory")
    output.mkdir(parents=True)
    structures = output / "structures"
    structures.mkdir()
    from pymatgen.io.ase import AseAtomsAdaptor
    from pymatgen.io.cif import CifWriter

    for phase_id, structure in zip(phase_ids, atoms):
        # Pymatgen-produced CIF files are consumed directly by the evaluator;
        # ASE's CIF writer can emit occupancy records that pymatgen rejects.
        CifWriter(AseAtomsAdaptor.get_structure(structure)).write_file(structures / f"{phase_id.replace(':', '_')}.cif")
    mixed, labels, fractions = _mixtures(patterns, phase_ids, mixture_count, np.random.default_rng(seed))
    utf8 = h5py.string_dtype(encoding="utf-8")
    with h5py.File(output / "patterns.h5", "w") as handle:
        handle.create_dataset("two_theta_deg", data=grid)
        handle.create_dataset("single_intensity", data=patterns, compression="gzip", shuffle=True)
        handle.create_dataset("multi_intensity", data=mixed, compression="gzip", shuffle=True)
        handle.create_dataset("single_phase_id", data=np.asarray(phase_ids, dtype=utf8))
        handle.create_dataset("multi_phase_ids_json", data=np.asarray([json.dumps(ids) for ids in labels], dtype=utf8))
        handle.create_dataset("multi_phase_fractions", data=fractions, compression="gzip")
    with (output / "manifest.jsonl").open("w", encoding="utf-8") as file:
        for index, phase_id in enumerate(phase_ids):
            structure_path = f"structures/{phase_id.replace(':', '_')}.cif"
            file.write(json.dumps({"sample_id": f"{source}-single-{index:06d}", "task": "identification.single", "input": {"archive": "patterns.h5", "dataset": "single_intensity", "index": index}, "ground_truth": {"phase_ids": [phase_id], "structure_files": [structure_path]}, "metadata": {"source": source, "structure": structure_path}}) + "\n")
        for index, ids in enumerate(labels):
            structure_paths = [f"structures/{phase_id.replace(':', '_')}.cif" for phase_id in ids]
            file.write(json.dumps({"sample_id": f"{source}-multi-{index:06d}", "task": "identification.multi", "input": {"archive": "patterns.h5", "dataset": "multi_intensity", "index": index}, "ground_truth": {"phase_ids": ids, "structure_files": structure_paths}, "metadata": {"source": source, "fractions": fractions[index, :len(ids)].round(8).tolist()}}) + "\n")
    (output / "README.md").write_text(f"# {source} dataset\n\n`patterns.h5` holds a common 2θ grid and normalized intensity vectors. `manifest.jsonl` maps each vector to its phase labels. Mixtures contain two or three distinct phases; every stored phase fraction is at least 0.10. Random seed: {seed}.\n", encoding="utf-8")


def build_rruff(database: str | Path, output: str | Path, *, mixtures: int = 10_000, seed: int = 0, grid_spec: tuple[float, float, float] = DEFAULT_GRID) -> None:
    """Build RRUFF experimental single phases and synthetic multi-phase mixtures."""
    grid = _grid(*grid_spec)
    patterns: list[np.ndarray] = []
    labels: list[str] = []
    atoms_list: list = []
    for row in connect(str(database)).select():
        data = row.key_value_pairs
        if not {"RRUFFID", "angle", "intensity"}.issubset(data):
            continue
        try:
            pattern = _interpolate(json.loads(data["angle"]), json.loads(data["intensity"]), grid)
            atoms = row.toatoms()
            if len(atoms) == 0:
                continue
        except (TypeError, ValueError):
            continue
        labels.append(f"RRUFF:{data['RRUFFID']}")
        patterns.append(pattern)
        atoms_list.append(atoms)
    if not patterns:
        raise ValueError("no usable RRUFF structure-pattern pairs found")
    _write_dataset(Path(output), "rruff", grid, np.stack(patterns), labels, atoms_list, mixtures, seed)


def _rruff_key(path: Path) -> str:
    """Return the shared sample key in RRUFF DIF and XY_RAW filenames."""
    return path.name.split("__Powder__", 1)[0]


def _rruff_atoms_from_dif(filename: Path):
    """Parse a RRUFF DIF crystal label into an ASE structure.

    DIF files that only contain a calculated peak list intentionally return
    ``None``: they do not provide a usable crystal-structure label.
    """
    text = filename.read_text(encoding="utf-8", errors="replace")
    cell_match = re.search(
        r"CELL PARAMETERS:\s*([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)",
        text,
    )
    group_match = re.search(r"(?:SPACE GROUP|ALTERNATE SETTING FOR SPACE GROUP):\s*([^\r\n]+)", text)
    atom_rows = re.findall(
        r"^\s*([A-Z][a-z]?)\S*\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+([0-9.]+)",
        text,
        flags=re.MULTILINE,
    )
    if not cell_match or not group_match or not atom_rows:
        return None
    cellpar = [float(value) for value in cell_match.groups()]
    symbols = [row[0] for row in atom_rows]
    basis = [[float(value) for value in row[1:4]] for row in atom_rows]
    occupancies = [float(row[4]) for row in atom_rows]
    spacegroup = group_match.group(1).strip().split()[0].replace("_", "")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            return crystal(symbols, basis=basis, spacegroup=spacegroup, cellpar=cellpar, occupancies=occupancies)
    except Exception:  # RRUFF includes non-standard Hermann--Mauguin settings.
        return None


def _rruff_xy_pattern(filename: Path, grid: np.ndarray) -> np.ndarray:
    points: list[tuple[float, float]] = []
    for line in filename.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = re.split(r"[\s,]+", line.strip())
        if len(fields) < 2:
            continue
        try:
            points.append((float(fields[0]), float(fields[1])))
        except ValueError:
            continue
    if len(points) < 3:
        raise ValueError("pattern has fewer than three numeric points")
    angle, intensity = zip(*points)
    return _interpolate(angle, intensity, grid)


def build_rruff_directory(source_directory: str | Path, output: str | Path, *, mixtures: int = 10_000, seed: int = 0, grid_spec: tuple[float, float, float] = DEFAULT_GRID) -> None:
    """Build RRUFF from the raw DIF/XY_RAW release directory.

    Only XY_RAW spectra with a matching DIF file that contains a complete
    crystal label (cell, space group, and atom positions) are retained.
    """
    source = Path(source_directory)
    grid = _grid(*grid_spec)
    dif_files = {_rruff_key(path): path for path in (source / "DIF").glob("*.txt")}
    patterns: list[np.ndarray] = []
    labels: list[str] = []
    atoms_list: list = []
    for xy_file in sorted((source / "XY_RAW").glob("*.txt")):
        key = _rruff_key(xy_file)
        dif_file = dif_files.get(key)
        if dif_file is None:
            continue
        try:
            atoms = _rruff_atoms_from_dif(dif_file)
            if atoms is None or len(atoms) == 0:
                continue
            pattern = _rruff_xy_pattern(xy_file, grid)
        except (OSError, TypeError, ValueError, np.linalg.LinAlgError):
            continue
        rruff_id = key.split("__")[-1]
        labels.append(f"RRUFF:{rruff_id}")
        patterns.append(pattern)
        atoms_list.append(atoms)
    if not patterns:
        raise ValueError("no usable RRUFF XY_RAW spectra with crystal labels found")
    _write_dataset(Path(output), "rruff", grid, np.stack(patterns), labels, atoms_list, mixtures, seed)


def build_opxrd(database: str | Path, output: str | Path, *, id_key: str, angle_key: str, intensity_key: str, mixtures: int = 10_000, seed: int = 0, grid_spec: tuple[float, float, float] = DEFAULT_GRID) -> None:
    """Build an experimental opXRD dataset from an ASE database.

    The key names are explicit because opXRD releases may use different names
    for their sample identifier and diffraction arrays.
    """
    grid = _grid(*grid_spec)
    patterns: list[np.ndarray] = []
    labels: list[str] = []
    atoms_list: list = []
    for row in connect(str(database)).select():
        data = row.key_value_pairs
        if not {id_key, angle_key, intensity_key}.issubset(data):
            continue
        try:
            angle = data[angle_key]
            intensity = data[intensity_key]
            pattern = _interpolate(json.loads(angle) if isinstance(angle, str) else angle, json.loads(intensity) if isinstance(intensity, str) else intensity, grid)
            atoms = row.toatoms()
            if len(atoms) == 0:
                continue
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        labels.append(f"OPXRD:{data[id_key]}")
        patterns.append(pattern)
        atoms_list.append(atoms)
    if not patterns:
        raise ValueError("no usable opXRD structure-pattern pairs found; check --id-key, --angle-key, and --intensity-key")
    _write_dataset(Path(output), "opxrd", grid, np.stack(patterns), labels, atoms_list, mixtures, seed)


def build_opxrd_json(source_directory: str | Path, output: str | Path, *, mixtures: int = 10_000, seed: int = 0, grid_spec: tuple[float, float, float] = DEFAULT_GRID) -> None:
    """Build opXRD from its directory of XRDPattern JSON records."""
    from pymatgen.core import Lattice, Structure
    from pymatgen.io.ase import AseAtomsAdaptor

    grid = _grid(*grid_spec)
    patterns: list[np.ndarray] = []
    labels: list[str] = []
    atoms_list: list = []
    for filename in sorted(glob.glob(str(Path(source_directory) / "*" / "pattern_*.json"))):
        try:
            record = json.loads(Path(filename).read_text(encoding="utf-8"))
            label = json.loads(record["label"])
            if len(label.get("phases", [])) != 1:
                continue
            phase = json.loads(label["phases"][0])
            if phase.get("lattice") in (None, "None") or phase.get("basis") in (None, "None"):
                continue
            lattice = ast.literal_eval(phase["lattice"])
            sites = [json.loads(site) if isinstance(site, str) else site for site in json.loads(phase["basis"])]
            structure = Structure(Lattice.from_parameters(*lattice), [site["symbol"] for site in sites], [[site["x"], site["y"], site["z"]] for site in sites], coords_are_cartesian=False)
            atoms = AseAtomsAdaptor.get_atoms(structure)
            pattern = _interpolate(record["two_theta_values"], record["intensities"], grid)
        except (KeyError, TypeError, ValueError, SyntaxError, json.JSONDecodeError):
            continue
        source = Path(filename).parent.name
        labels.append(f"OPXRD:{source}:{Path(filename).stem.removeprefix('pattern_')}")
        patterns.append(pattern)
        atoms_list.append(atoms)
    if not patterns:
        raise ValueError("no usable single-phase structure-pattern pairs found in opXRD JSON files")
    _write_dataset(Path(output), "opxrd", grid, np.stack(patterns), labels, atoms_list, mixtures, seed)


def build_mp500(database: str | Path, output: str | Path, *, single_count: int = 10_000, mixtures: int = 30_000, seed: int = 0, grid_spec: tuple[float, float, float] = DEFAULT_GRID) -> None:
    """Sample MP500 structures with ≤100 atoms and simulate realistic Cu Kα patterns."""
    grid = _grid(*grid_spec)
    rng = np.random.default_rng(seed)
    database_handle = connect(str(database))
    candidates = [row.id for row in database_handle.select("natoms>0, natoms<=100")]
    if len(candidates) < single_count:
        raise ValueError(f"MP500 has only {len(candidates)} eligible structures; requested {single_count}")
    # Over-sample candidates so failed diffraction calculations do not bias the
    # selection or prevent reaching the requested count.
    selected = rng.permutation(candidates)
    output_path = Path(output)
    if output_path.exists():
        raise FileExistsError(f"output already exists: {output_path}; choose a new directory")
    output_path.mkdir(parents=True)
    structures = output_path / "structures"
    structures.mkdir()
    labels: list[str] = []
    seen_labels: set[str] = set()
    utf8 = h5py.string_dtype(encoding="utf-8")
    with h5py.File(output_path / "patterns.h5", "w") as handle:
        handle.create_dataset("two_theta_deg", data=grid)
        single = handle.create_dataset("single_intensity", shape=(single_count, len(grid)), dtype="f4", chunks=(1, len(grid)), compression="gzip", shuffle=True)
        index = 0
        for row_id in selected:
            if index == single_count:
                break
            row = database_handle.get(id=int(row_id))
            raw_id = row.key_value_pairs.get("mpid")
            if not raw_id:
                continue
            phase_id = f"MP:{str(raw_id).removesuffix('.cif')}"
            if phase_id in seen_labels:
                continue
            try:
                atoms = row.toatoms()
                single[index] = _simulate_pattern(atoms, grid, rng)
            except (ValueError, TypeError, np.linalg.LinAlgError):
                continue
            write(structures / f"{phase_id.replace(':', '_')}.cif", atoms)
            labels.append(phase_id)
            seen_labels.add(phase_id)
            index += 1
        if index != single_count:
            raise RuntimeError(f"only simulated {index} eligible MP500 structures")
        handle.create_dataset("single_phase_id", data=np.asarray(labels, dtype=utf8))
        multi = handle.create_dataset("multi_intensity", shape=(mixtures, len(grid)), dtype="f4", chunks=(1, len(grid)), compression="gzip", shuffle=True)
        multi_ids = handle.create_dataset("multi_phase_ids_json", shape=(mixtures,), dtype=utf8)
        multi_fractions = handle.create_dataset("multi_phase_fractions", shape=(mixtures, 3), dtype="f4", compression="gzip")
        mixture_labels: list[list[str]] = []
        fractions = np.full((mixtures, 3), np.nan, dtype=np.float32)
        for index in range(mixtures):
            phase_count = int(rng.integers(2, 4))
            selected_indices = rng.choice(single_count, size=phase_count, replace=False)
            weights = _fractions(rng, phase_count)
            multi[index] = sum(weight * single[int(item)] for item, weight in zip(selected_indices, weights))
            ids = [labels[int(item)] for item in selected_indices]
            mixture_labels.append(ids)
            multi_ids[index] = json.dumps(ids)
            fractions[index, :phase_count] = weights
        multi_fractions[:] = fractions
    with (output_path / "manifest.jsonl").open("w", encoding="utf-8") as file:
        for index, phase_id in enumerate(labels):
            file.write(json.dumps({"sample_id": f"mp500-single-{index:06d}", "task": "identification.single", "input": {"archive": "patterns.h5", "dataset": "single_intensity", "index": index}, "ground_truth": {"phase_ids": [phase_id]}, "metadata": {"source": "mp500", "structure": f"structures/{phase_id.replace(':', '_')}.cif"}}) + "\n")
        for index, ids in enumerate(mixture_labels):
            file.write(json.dumps({"sample_id": f"mp500-multi-{index:06d}", "task": "identification.multi", "input": {"archive": "patterns.h5", "dataset": "multi_intensity", "index": index}, "ground_truth": {"phase_ids": ids}, "metadata": {"source": "mp500", "fractions": fractions[index, :len(ids)].round(8).tolist()}}) + "\n")
    (output_path / "README.md").write_text(f"# mp500 dataset\n\n`patterns.h5` holds a common 2θ grid and normalized intensity vectors. `manifest.jsonl` maps each vector to its phase labels. Mixtures contain two or three distinct phases; every stored phase fraction is at least 0.10. Random seed: {seed}.\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build standardized XRDBench datasets")
    command = parser.add_subparsers(dest="source", required=True)
    rruff = command.add_parser("rruff", help="Build RRUFF experimental patterns and mixtures")
    rruff.add_argument("database")
    rruff.add_argument("output")
    rruff.add_argument("--mixtures", type=int, default=10_000)
    rruff.add_argument("--seed", type=int, default=0)
    rruff.add_argument("--grid-start", type=float, default=DEFAULT_GRID[0])
    rruff.add_argument("--grid-stop", type=float, default=DEFAULT_GRID[1])
    rruff.add_argument("--grid-step", type=float, default=DEFAULT_GRID[2])
    rruff_raw = command.add_parser("rruff-raw", help="Build RRUFF from raw DIF and XY_RAW directories")
    rruff_raw.add_argument("directory")
    rruff_raw.add_argument("output")
    rruff_raw.add_argument("--mixtures", type=int, default=10_000)
    rruff_raw.add_argument("--seed", type=int, default=0)
    rruff_raw.add_argument("--grid-start", type=float, default=DEFAULT_GRID[0])
    rruff_raw.add_argument("--grid-stop", type=float, default=DEFAULT_GRID[1])
    rruff_raw.add_argument("--grid-step", type=float, default=DEFAULT_GRID[2])
    mp500 = command.add_parser("mp500", help="Build simulated MP500 patterns and mixtures")
    mp500.add_argument("database")
    mp500.add_argument("output")
    mp500.add_argument("--single-count", type=int, default=10_000)
    mp500.add_argument("--mixtures", type=int, default=30_000)
    mp500.add_argument("--seed", type=int, default=0)
    mp500.add_argument("--grid-start", type=float, default=DEFAULT_GRID[0])
    mp500.add_argument("--grid-stop", type=float, default=DEFAULT_GRID[1])
    mp500.add_argument("--grid-step", type=float, default=DEFAULT_GRID[2])
    opxrd = command.add_parser("opxrd", help="Build experimental opXRD patterns and mixtures")
    opxrd.add_argument("database")
    opxrd.add_argument("output")
    opxrd.add_argument("--id-key", required=True)
    opxrd.add_argument("--angle-key", required=True)
    opxrd.add_argument("--intensity-key", required=True)
    opxrd.add_argument("--mixtures", type=int, default=10_000)
    opxrd.add_argument("--seed", type=int, default=0)
    opxrd.add_argument("--grid-start", type=float, default=DEFAULT_GRID[0])
    opxrd.add_argument("--grid-stop", type=float, default=DEFAULT_GRID[1])
    opxrd.add_argument("--grid-step", type=float, default=DEFAULT_GRID[2])
    opxrd_json = command.add_parser("opxrd-json", help="Build opXRD JSON patterns and mixtures")
    opxrd_json.add_argument("directory")
    opxrd_json.add_argument("output")
    opxrd_json.add_argument("--mixtures", type=int, default=10_000)
    opxrd_json.add_argument("--seed", type=int, default=0)
    opxrd_json.add_argument("--grid-start", type=float, default=DEFAULT_GRID[0])
    opxrd_json.add_argument("--grid-stop", type=float, default=DEFAULT_GRID[1])
    opxrd_json.add_argument("--grid-step", type=float, default=DEFAULT_GRID[2])
    args = parser.parse_args()
    grid_spec = (args.grid_start, args.grid_stop, args.grid_step)
    if args.source == "rruff":
        build_rruff(args.database, args.output, mixtures=args.mixtures, seed=args.seed, grid_spec=grid_spec)
    elif args.source == "rruff-raw":
        build_rruff_directory(args.directory, args.output, mixtures=args.mixtures, seed=args.seed, grid_spec=grid_spec)
    elif args.source == "mp500":
        build_mp500(args.database, args.output, single_count=args.single_count, mixtures=args.mixtures, seed=args.seed, grid_spec=grid_spec)
    elif args.source == "opxrd":
        build_opxrd(args.database, args.output, id_key=args.id_key, angle_key=args.angle_key, intensity_key=args.intensity_key, mixtures=args.mixtures, seed=args.seed, grid_spec=grid_spec)
    else:
        build_opxrd_json(args.directory, args.output, mixtures=args.mixtures, seed=args.seed, grid_spec=grid_spec)


if __name__ == "__main__":
    main()
