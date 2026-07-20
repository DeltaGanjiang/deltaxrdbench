"""A model-agnostic benchmark protocol for XRD tasks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np


IDENTIFICATION_TASKS = {"identification.single", "identification.multi"}
REFINEMENT_TASK = "refinement"
SUPPORTED_TASKS = IDENTIFICATION_TASKS | {REFINEMENT_TASK}


@dataclass(frozen=True)
class BenchmarkReport:
    """A portable result containing aggregate metrics and sample-level evidence."""

    summary: dict[str, Any]
    samples: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_jsonl(path: str | Path, label: str, *, allow_empty: bool = False) -> list[dict[str, Any]]:
    source = Path(path)
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{label} line {line_number} is not valid JSON: {error.msg}") from error
        if not isinstance(record, dict):
            raise ValueError(f"{label} line {line_number} must be a JSON object")
        records.append(record)
    if not records and not allow_empty:
        raise ValueError(f"{label} is empty")
    return records


def _require_string(value: Any, field: str, sample_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"sample {sample_id}: {field} must be a non-empty string")
    return value


def _phase_ids(value: Any, field: str, sample_id: str) -> set[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"sample {sample_id}: {field} must be a non-empty list of phase ID strings")
    phase_ids = {_require_string(item, field, sample_id) for item in value}
    if len(phase_ids) != len(value):
        raise ValueError(f"sample {sample_id}: {field} contains duplicate phase IDs")
    return phase_ids


def _resolve_file(value: Any, root: Path, field: str, sample_id: str) -> Path:
    path = Path(_require_string(value, field, sample_id))
    path = path if path.is_absolute() else root / path
    if not path.is_file():
        raise ValueError(f"sample {sample_id}: {field} does not exist: {path}")
    return path


def _structure_files(value: Any, root: Path, field: str, sample_id: str) -> list[Path]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"sample {sample_id}: {field} must be a non-empty list of CIF file paths")
    return [_resolve_file(item, root, field, sample_id) for item in value]


def _maximum_structure_matches(predicted: list[Path], reference: list[Path]) -> int:
    """Return a one-to-one maximum CIF match count using pymatgen."""
    from ase.io import read
    from pymatgen.analysis.structure_matcher import StructureMatcher
    from pymatgen.core import Structure
    from pymatgen.io.ase import AseAtomsAdaptor

    matcher = StructureMatcher(ltol=0.2, stol=0.3, angle_tol=5)

    def load(path: Path):
        try:
            return Structure.from_file(path)
        except ValueError:
            # Some legacy ASE CIF exports encode site multiplicities as
            # occupancies. ASE can recover these files reliably.
            return AseAtomsAdaptor.get_structure(read(path))

    predicted_structures = [load(path) for path in predicted]
    reference_structures = [load(path) for path in reference]
    edges = [[right for right, candidate in enumerate(reference_structures) if matcher.fit(item, candidate)] for item in predicted_structures]
    assigned: dict[int, int] = {}

    def assign(left: int, visited: set[int]) -> bool:
        for right in edges[left]:
            if right in visited:
                continue
            visited.add(right)
            if right not in assigned or assign(assigned[right], visited):
                assigned[right] = left
                return True
        return False

    return sum(assign(left, set()) for left in range(len(predicted)))


def evaluate(dataset: str | Path, submission: str | Path, *, data_root: str | Path | None = None) -> BenchmarkReport:
    """Evaluate a JSONL model submission against a JSONL dataset manifest.

    Identification is scored as exact sets of canonical phase IDs. Refinement
    quality is evaluated by :func:`xrdinspector.score_refinement`.
    """
    dataset_path = Path(dataset)
    root = Path(data_root) if data_root is not None else dataset_path.parent
    truth = _read_jsonl(dataset_path, "dataset")
    predictions = _read_jsonl(submission, "submission", allow_empty=True)
    predictions_by_id: dict[str, dict[str, Any]] = {}
    for prediction in predictions:
        sample_id = _require_string(prediction.get("sample_id"), "sample_id", "<submission>")
        if sample_id in predictions_by_id:
            raise ValueError(f"submission contains duplicate sample_id: {sample_id}")
        predictions_by_id[sample_id] = prediction

    rows: list[dict[str, Any]] = []
    dataset_ids: set[str] = set()
    for item in truth:
        sample_id = _require_string(item.get("sample_id"), "sample_id", "<dataset>")
        if sample_id in dataset_ids:
            raise ValueError(f"dataset contains duplicate sample_id: {sample_id}")
        dataset_ids.add(sample_id)
        task = item.get("task")
        if task not in SUPPORTED_TASKS:
            raise ValueError(f"sample {sample_id}: unsupported task {task!r}")
        submitted = predictions_by_id.get(sample_id)
        if submitted is None:
            rows.append({"sample_id": sample_id, "task": task, "status": "missing_prediction"})
            continue
        prediction = submitted.get("prediction")
        if not isinstance(prediction, dict):
            raise ValueError(f"sample {sample_id}: prediction must be an object")
        if task in IDENTIFICATION_TASKS:
            truth = item.get("ground_truth", {})
            expected = _phase_ids(truth.get("phase_ids"), "ground_truth.phase_ids", sample_id)
            if "structure_files" in prediction:
                reference = _structure_files(truth.get("structure_files"), root, "ground_truth.structure_files", sample_id)
                predicted_files = _structure_files(prediction["structure_files"], root, "prediction.structure_files", sample_id)
                if task == "identification.single" and (len(reference) != 1 or len(predicted_files) != 1):
                    raise ValueError(f"sample {sample_id}: a single-phase task requires exactly one CIF")
                true_positive = _maximum_structure_matches(predicted_files, reference)
                predicted_count = len(predicted_files)
                truth_count = len(reference)
                mode = "cif_structure_match"
            else:
                predicted = _phase_ids(prediction.get("phase_ids"), "prediction.phase_ids", sample_id)
                if task == "identification.single" and (len(expected) != 1 or len(predicted) != 1):
                    raise ValueError(f"sample {sample_id}: a single-phase task requires exactly one phase ID")
                true_positive = len(expected & predicted)
                predicted_count = len(predicted)
                truth_count = len(expected)
                mode = "phase_id"
            precision = true_positive / predicted_count
            recall = true_positive / truth_count
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            rows.append({
                "sample_id": sample_id, "task": task, "status": "scored",
                "validation_mode": mode, "exact_match": true_positive == predicted_count == truth_count, "precision": round(precision, 6),
                "recall": round(recall, 6), "f1": round(f1, 6),
                "true_positive": true_positive, "predicted_count": predicted_count, "truth_count": truth_count,
            })
        else:
            # Keep dataset preparation usable without importing the optional
            # refinement scorer; evaluation installs XRDinspector normally.
            from xrdinspector import score_refinement
            experimental = _resolve_file(item.get("input", {}).get("experimental_pattern"), root, "input.experimental_pattern", sample_id)
            calculated = _resolve_file(prediction.get("calculated_pattern"), root, "prediction.calculated_pattern", sample_id)
            report = score_refinement(experimental, calculated)
            rows.append({"sample_id": sample_id, "task": task, "status": "scored", **report.to_dict()})

    summary: dict[str, Any] = {"total": len(rows), "scored": sum(row["status"] == "scored" for row in rows), "missing_predictions": sum(row["status"] == "missing_prediction" for row in rows), "extra_submission_ids": sorted(set(predictions_by_id) - dataset_ids)}
    for task in sorted(SUPPORTED_TASKS):
        task_rows = [row for row in rows if row["task"] == task]
        scored = [row for row in task_rows if row["status"] == "scored"]
        if not task_rows:
            continue
        if task in IDENTIFICATION_TASKS:
            summary[task] = {"samples": len(task_rows), "scored": len(scored), "coverage": round(len(scored) / len(task_rows), 6), "exact_match_rate": round(float(np.mean([row.get("exact_match", False) for row in task_rows])), 6), "macro_precision": round(float(np.mean([row.get("precision", 0.0) for row in task_rows])), 6), "macro_recall": round(float(np.mean([row.get("recall", 0.0) for row in task_rows])), 6), "macro_f1": round(float(np.mean([row.get("f1", 0.0) for row in task_rows])), 6)}
        else:
            summary[task] = {"samples": len(task_rows), "scored": len(scored), "coverage": round(len(scored) / len(task_rows), 6), "mean_score": round(float(np.mean([row.get("score", 0.0) for row in task_rows])), 4), "mean_rp": None if not scored else round(float(np.mean([row["rp"] for row in scored])), 6), "mean_rwp": None if not scored else round(float(np.mean([row["rwp"] for row in scored])), 6), "mean_correlation": None if not scored else round(float(np.mean([row["correlation"] for row in scored])), 6), "reasonable_rate": round(float(np.mean([row.get("reasonable", False) for row in task_rows])), 6)}
    return BenchmarkReport(summary=summary, samples=rows)
