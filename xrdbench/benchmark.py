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


def _read_jsonl(
    path: str | Path, label: str, *, allow_empty: bool = False
) -> list[dict[str, Any]]:
    source = Path(path)
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        source.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"{label} line {line_number} is not valid JSON: {error.msg}"
            ) from error
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


def _phase_ids(
    value: Any, field: str, sample_id: str, *, allow_empty: bool = False
) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise ValueError(
            f"sample {sample_id}: {field} must be {qualifier} of phase ID strings"
        )
    phase_ids = [_require_string(item, field, sample_id) for item in value]
    if len(set(phase_ids)) != len(value):
        raise ValueError(f"sample {sample_id}: {field} contains duplicate phase IDs")
    return phase_ids


def _resolve_file(value: Any, root: Path, field: str, sample_id: str) -> Path:
    path = Path(_require_string(value, field, sample_id))
    path = path if path.is_absolute() else root / path
    if not path.is_file():
        raise ValueError(f"sample {sample_id}: {field} does not exist: {path}")
    return path


def _structure_files(
    value: Any,
    root: Path,
    field: str,
    sample_id: str,
    *,
    allow_empty: bool = False,
) -> list[Path]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise ValueError(
            f"sample {sample_id}: {field} must be {qualifier} of CIF file paths"
        )
    return [_resolve_file(item, root, field, sample_id) for item in value]


def _structure_match_edges(
    predicted: list[Path],
    reference: list[Path],
    *,
    require_deduplicated: bool = False,
    sample_id: str = "<unknown>",
) -> list[list[int]]:
    """Return candidate-to-reference StructureMatcher edges."""
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

    if require_deduplicated:
        for left, structure in enumerate(predicted_structures):
            for right in range(left):
                if matcher.fit(structure, predicted_structures[right]):
                    raise ValueError(
                        f"sample {sample_id}: prediction.structure_files must be "
                        "structurally deduplicated"
                    )

    return [
        [
            right
            for right, candidate in enumerate(reference_structures)
            if matcher.fit(item, candidate)
        ]
        for item in predicted_structures
    ]


def _maximum_matches(edges: list[list[int]]) -> int:
    """Return the cardinality of a one-to-one maximum match from match edges."""
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

    return sum(assign(left, set()) for left in range(len(edges)))


def _percentage_mean(rows: list[dict[str, Any]], field: str) -> float | None:
    """Return a percentage macro average, or ``None`` for no scored rows."""
    if not rows:
        return None
    return round(100.0 * float(np.mean([row[field] for row in rows])), 6)


def evaluate(
    dataset: str | Path, submission: str | Path, *, data_root: str | Path | None = None
) -> BenchmarkReport:
    """Evaluate a JSONL model submission against a JSONL dataset manifest.

    Single-phase identification uses a ranked list of at most five candidates.
    Multi-phase identification uses an unordered set of candidates. Refinement
    quality is evaluated by :func:`xrdinspector.score_refinement`.
    """
    dataset_path = Path(dataset)
    root = Path(data_root) if data_root is not None else dataset_path.parent
    truth = _read_jsonl(dataset_path, "dataset")
    predictions = _read_jsonl(submission, "submission", allow_empty=True)
    predictions_by_id: dict[str, dict[str, Any]] = {}
    for prediction in predictions:
        sample_id = _require_string(
            prediction.get("sample_id"), "sample_id", "<submission>"
        )
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
            rows.append(
                {"sample_id": sample_id, "task": task, "status": "missing_prediction"}
            )
            continue
        prediction = submitted.get("prediction")
        if not isinstance(prediction, dict):
            raise ValueError(f"sample {sample_id}: prediction must be an object")
        if task in IDENTIFICATION_TASKS:
            ground_truth = item.get("ground_truth", {})
            expected = _phase_ids(
                ground_truth.get("phase_ids"), "ground_truth.phase_ids", sample_id
            )

            if task == "identification.single":
                if len(expected) != 1:
                    raise ValueError(
                        f"sample {sample_id}: a single-phase task requires exactly one reference phase"
                    )
                if "structure_files" in prediction:
                    reference = _structure_files(
                        ground_truth.get("structure_files"),
                        root,
                        "ground_truth.structure_files",
                        sample_id,
                    )
                    if len(reference) != 1:
                        raise ValueError(
                            f"sample {sample_id}: a single-phase task requires exactly one reference CIF"
                        )
                    predicted_files = _structure_files(
                        prediction["structure_files"],
                        root,
                        "prediction.structure_files",
                        sample_id,
                        allow_empty=True,
                    )
                    if len(predicted_files) > 5:
                        raise ValueError(
                            f"sample {sample_id}: a single-phase prediction may contain at most five CIFs"
                        )
                    edges = _structure_match_edges(
                        predicted_files,
                        reference,
                        require_deduplicated=True,
                        sample_id=sample_id,
                    )
                    candidate_matches = [
                        bool(candidate_edges) for candidate_edges in edges
                    ]
                    candidate_count = len(predicted_files)
                    mode = "cif_structure_match"
                else:
                    predicted = _phase_ids(
                        prediction.get("phase_ids"),
                        "prediction.phase_ids",
                        sample_id,
                        allow_empty=True,
                    )
                    if len(predicted) > 5:
                        raise ValueError(
                            f"sample {sample_id}: a single-phase prediction may contain at most five phase IDs"
                        )
                    candidate_matches = [
                        phase_id == expected[0] for phase_id in predicted
                    ]
                    candidate_count = len(predicted)
                    mode = "phase_id"

                match_rank = next(
                    (
                        rank
                        for rank, matched in enumerate(candidate_matches, 1)
                        if matched
                    ),
                    None,
                )
                rows.append(
                    {
                        "sample_id": sample_id,
                        "task": task,
                        "status": "scored",
                        "validation_mode": mode,
                        "candidate_count": candidate_count,
                        "first_match_rank": match_rank,
                        "top_1": match_rank is not None and match_rank <= 1,
                        "top_3": match_rank is not None and match_rank <= 3,
                        "top_5": match_rank is not None and match_rank <= 5,
                        "reciprocal_rank_at_5": (
                            0.0 if match_rank is None else 1.0 / match_rank
                        ),
                    }
                )
            else:
                expected_set = set(expected)
                if "structure_files" in prediction:
                    reference = _structure_files(
                        ground_truth.get("structure_files"),
                        root,
                        "ground_truth.structure_files",
                        sample_id,
                    )
                    predicted_files = _structure_files(
                        prediction["structure_files"],
                        root,
                        "prediction.structure_files",
                        sample_id,
                        allow_empty=True,
                    )
                    edges = _structure_match_edges(
                        predicted_files,
                        reference,
                        require_deduplicated=True,
                        sample_id=sample_id,
                    )
                    true_positive = _maximum_matches(edges)
                    predicted_count = len(predicted_files)
                    truth_count = len(reference)
                    mode = "cif_structure_match"
                else:
                    predicted = _phase_ids(
                        prediction.get("phase_ids"),
                        "prediction.phase_ids",
                        sample_id,
                        allow_empty=True,
                    )
                    predicted_set = set(predicted)
                    true_positive = len(expected_set & predicted_set)
                    predicted_count = len(predicted_set)
                    truth_count = len(expected_set)
                    mode = "phase_id"

                precision = true_positive / predicted_count if predicted_count else 0.0
                recall = true_positive / truth_count
                f1 = (
                    2 * precision * recall / (precision + recall)
                    if precision + recall
                    else 0.0
                )
                rows.append(
                    {
                        "sample_id": sample_id,
                        "task": task,
                        "status": "scored",
                        "validation_mode": mode,
                        "exact_match": true_positive == predicted_count == truth_count,
                        "precision": precision,
                        "recall": recall,
                        "f1": f1,
                        "true_positive": true_positive,
                        "predicted_count": predicted_count,
                        "truth_count": truth_count,
                    }
                )
        else:
            # Keep dataset preparation usable without importing the optional
            # refinement scorer; evaluation installs XRDinspector normally.
            from xrdinspector import score_refinement

            experimental = _resolve_file(
                item.get("input", {}).get("experimental_pattern"),
                root,
                "input.experimental_pattern",
                sample_id,
            )
            calculated = _resolve_file(
                prediction.get("calculated_pattern"),
                root,
                "prediction.calculated_pattern",
                sample_id,
            )
            report = score_refinement(experimental, calculated)
            rows.append(
                {
                    "sample_id": sample_id,
                    "task": task,
                    "status": "scored",
                    **report.to_dict(),
                }
            )

    summary: dict[str, Any] = {
        "total": len(rows),
        "scored": sum(row["status"] == "scored" for row in rows),
        "missing_predictions": sum(
            row["status"] == "missing_prediction" for row in rows
        ),
        "extra_submission_ids": sorted(set(predictions_by_id) - dataset_ids),
    }
    for task in sorted(SUPPORTED_TASKS):
        task_rows = [row for row in rows if row["task"] == task]
        scored = [row for row in task_rows if row["status"] == "scored"]
        if not task_rows:
            continue
        if task == "identification.single":
            summary[task] = {
                "samples": len(task_rows),
                "scored": len(scored),
                "top_1": _percentage_mean(scored, "top_1"),
                "top_3": _percentage_mean(scored, "top_3"),
                "top_5": _percentage_mean(scored, "top_5"),
                "mrr_at_5": _percentage_mean(scored, "reciprocal_rank_at_5"),
            }
        elif task == "identification.multi":
            summary[task] = {
                "samples": len(task_rows),
                "scored": len(scored),
                "coverage": round(100.0 * len(scored) / len(task_rows), 6),
                "exact": _percentage_mean(scored, "exact_match"),
                "macro_precision": _percentage_mean(scored, "precision"),
                "macro_recall": _percentage_mean(scored, "recall"),
                "macro_f1": _percentage_mean(scored, "f1"),
            }
        else:
            summary[task] = {
                "samples": len(task_rows),
                "scored": len(scored),
                "coverage": round(len(scored) / len(task_rows), 6),
                "mean_score": round(
                    float(np.mean([row.get("score", 0.0) for row in task_rows])), 4
                ),
                "mean_rp": (
                    None
                    if not scored
                    else round(float(np.mean([row["rp"] for row in scored])), 6)
                ),
                "mean_rwp": (
                    None
                    if not scored
                    else round(float(np.mean([row["rwp"] for row in scored])), 6)
                ),
                "mean_correlation": (
                    None
                    if not scored
                    else round(
                        float(np.mean([row["correlation"] for row in scored])), 6
                    )
                ),
                "reasonable_rate": round(
                    float(np.mean([row.get("reasonable", False) for row in task_rows])),
                    6,
                ),
            }
    return BenchmarkReport(summary=summary, samples=rows)
