import json

import numpy as np
import pytest

from xrdbench import evaluate


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")


def test_scores_all_three_tasks(tmp_path):
    x = np.linspace(20, 80, 20)
    np.savetxt(tmp_path / "observed.xy", np.c_[x, 3 + np.sin(x)])
    np.savetxt(tmp_path / "calculated.xy", np.c_[x, 3 + np.sin(x)])
    _write_jsonl(
        tmp_path / "dataset.jsonl",
        [
            {
                "sample_id": "single",
                "task": "identification.single",
                "input": {},
                "ground_truth": {"phase_ids": ["COD:1"]},
            },
            {
                "sample_id": "multi",
                "task": "identification.multi",
                "input": {},
                "ground_truth": {"phase_ids": ["COD:1", "COD:2"]},
            },
            {
                "sample_id": "refine",
                "task": "refinement",
                "input": {"experimental_pattern": "observed.xy"},
                "ground_truth": {},
            },
        ],
    )
    _write_jsonl(
        tmp_path / "submission.jsonl",
        [
            {"sample_id": "single", "prediction": {"phase_ids": ["COD:1"]}},
            {"sample_id": "multi", "prediction": {"phase_ids": ["COD:1"]}},
            {
                "sample_id": "refine",
                "prediction": {"calculated_pattern": "calculated.xy"},
            },
        ],
    )
    report = evaluate(
        tmp_path / "dataset.jsonl", tmp_path / "submission.jsonl"
    ).to_dict()
    assert report["summary"]["identification.single"]["top_1"] == 100
    assert report["summary"]["identification.single"]["mrr_at_5"] == 100
    assert report["summary"]["identification.multi"]["coverage"] == 100
    assert report["summary"]["identification.multi"]["macro_f1"] == 66.666667
    assert report["summary"]["refinement"]["mean_score"] > 99


def test_missing_single_phase_prediction_is_not_scored(tmp_path):
    _write_jsonl(
        tmp_path / "dataset.jsonl",
        [
            {
                "sample_id": "single",
                "task": "identification.single",
                "input": {},
                "ground_truth": {"phase_ids": ["COD:1"]},
            },
        ],
    )
    _write_jsonl(tmp_path / "submission.jsonl", [])
    report = evaluate(
        tmp_path / "dataset.jsonl", tmp_path / "submission.jsonl"
    ).to_dict()
    assert report["samples"][0]["status"] == "missing_prediction"
    assert report["summary"]["identification.single"]["scored"] == 0
    assert report["summary"]["identification.single"]["top_1"] is None


def test_single_phase_ranked_metrics(tmp_path):
    _write_jsonl(
        tmp_path / "dataset.jsonl",
        [
            {
                "sample_id": "single",
                "task": "identification.single",
                "input": {},
                "ground_truth": {"phase_ids": ["COD:3"]},
            },
        ],
    )
    _write_jsonl(
        tmp_path / "submission.jsonl",
        [
            {
                "sample_id": "single",
                "prediction": {"phase_ids": ["COD:1", "COD:2", "COD:3"]},
            },
        ],
    )

    report = evaluate(
        tmp_path / "dataset.jsonl", tmp_path / "submission.jsonl"
    ).to_dict()
    row = report["samples"][0]
    summary = report["summary"]["identification.single"]
    assert row["first_match_rank"] == 3
    assert row["top_1"] is False
    assert row["top_3"] is True
    assert summary["top_1"] == 0
    assert summary["top_3"] == 100
    assert summary["top_5"] == 100
    assert summary["mrr_at_5"] == 33.333333


def test_single_phase_rejects_more_than_five_candidates(tmp_path):
    _write_jsonl(
        tmp_path / "dataset.jsonl",
        [
            {
                "sample_id": "single",
                "task": "identification.single",
                "input": {},
                "ground_truth": {"phase_ids": ["COD:1"]},
            },
        ],
    )
    _write_jsonl(
        tmp_path / "submission.jsonl",
        [
            {
                "sample_id": "single",
                "prediction": {"phase_ids": [f"COD:{index}" for index in range(6)]},
            },
        ],
    )

    with pytest.raises(ValueError, match="at most five"):
        evaluate(tmp_path / "dataset.jsonl", tmp_path / "submission.jsonl")


def test_multiphase_metrics_are_conditional_on_scored_samples(tmp_path):
    _write_jsonl(
        tmp_path / "dataset.jsonl",
        [
            {
                "sample_id": "correct",
                "task": "identification.multi",
                "input": {},
                "ground_truth": {"phase_ids": ["COD:1", "COD:2"]},
            },
            {
                "sample_id": "empty",
                "task": "identification.multi",
                "input": {},
                "ground_truth": {"phase_ids": ["COD:1", "COD:2"]},
            },
            {
                "sample_id": "missing",
                "task": "identification.multi",
                "input": {},
                "ground_truth": {"phase_ids": ["COD:1", "COD:2"]},
            },
        ],
    )
    _write_jsonl(
        tmp_path / "submission.jsonl",
        [
            {"sample_id": "correct", "prediction": {"phase_ids": ["COD:1", "COD:2"]}},
            {"sample_id": "empty", "prediction": {"phase_ids": []}},
        ],
    )

    report = evaluate(
        tmp_path / "dataset.jsonl", tmp_path / "submission.jsonl"
    ).to_dict()
    summary = report["summary"]["identification.multi"]
    assert summary["coverage"] == 66.666667
    assert summary["exact"] == 50
    assert summary["macro_precision"] == 50
    assert summary["macro_recall"] == 50
    assert summary["macro_f1"] == 50


def test_cif_submission_is_matched_without_phase_id(tmp_path):
    cif = """data_test
_cell_length_a 4
_cell_length_b 4
_cell_length_c 4
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P 1'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Si1 Si 0 0 0
"""
    (tmp_path / "reference.cif").write_text(cif)
    (tmp_path / "prediction.cif").write_text(cif)
    _write_jsonl(
        tmp_path / "dataset.jsonl",
        [
            {
                "sample_id": "single",
                "task": "identification.single",
                "input": {},
                "ground_truth": {
                    "phase_ids": ["INTERNAL:1"],
                    "structure_files": ["reference.cif"],
                },
            }
        ],
    )
    _write_jsonl(
        tmp_path / "submission.jsonl",
        [
            {
                "sample_id": "single",
                "prediction": {"structure_files": ["prediction.cif"]},
            }
        ],
    )
    report = evaluate(
        tmp_path / "dataset.jsonl", tmp_path / "submission.jsonl"
    ).to_dict()
    assert report["samples"][0]["validation_mode"] == "cif_structure_match"
    assert report["samples"][0]["first_match_rank"] == 1
    assert report["summary"]["identification.single"]["top_1"] == 100


def test_single_phase_cif_candidates_must_be_structurally_deduplicated(tmp_path):
    cif = """data_test
_cell_length_a 4
_cell_length_b 4
_cell_length_c 4
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P 1'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Si1 Si 0 0 0
"""
    (tmp_path / "reference.cif").write_text(cif)
    (tmp_path / "prediction-1.cif").write_text(cif)
    (tmp_path / "prediction-2.cif").write_text(cif)
    _write_jsonl(
        tmp_path / "dataset.jsonl",
        [
            {
                "sample_id": "single",
                "task": "identification.single",
                "input": {},
                "ground_truth": {
                    "phase_ids": ["INTERNAL:1"],
                    "structure_files": ["reference.cif"],
                },
            }
        ],
    )
    _write_jsonl(
        tmp_path / "submission.jsonl",
        [
            {
                "sample_id": "single",
                "prediction": {
                    "structure_files": ["prediction-1.cif", "prediction-2.cif"]
                },
            }
        ],
    )

    with pytest.raises(ValueError, match="structurally deduplicated"):
        evaluate(tmp_path / "dataset.jsonl", tmp_path / "submission.jsonl")
