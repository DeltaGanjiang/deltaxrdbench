import json

import numpy as np

from xrdbench import evaluate


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")


def test_scores_all_three_tasks(tmp_path):
    x = np.linspace(20, 80, 20)
    np.savetxt(tmp_path / "observed.xy", np.c_[x, 3 + np.sin(x)])
    np.savetxt(tmp_path / "calculated.xy", np.c_[x, 3 + np.sin(x)])
    _write_jsonl(tmp_path / "dataset.jsonl", [
        {"sample_id": "single", "task": "identification.single", "input": {}, "ground_truth": {"phase_ids": ["COD:1"]}},
        {"sample_id": "multi", "task": "identification.multi", "input": {}, "ground_truth": {"phase_ids": ["COD:1", "COD:2"]}},
        {"sample_id": "refine", "task": "refinement", "input": {"experimental_pattern": "observed.xy"}, "ground_truth": {}},
    ])
    _write_jsonl(tmp_path / "submission.jsonl", [
        {"sample_id": "single", "prediction": {"phase_ids": ["COD:1"]}},
        {"sample_id": "multi", "prediction": {"phase_ids": ["COD:1"]}},
        {"sample_id": "refine", "prediction": {"calculated_pattern": "calculated.xy"}},
    ])
    report = evaluate(tmp_path / "dataset.jsonl", tmp_path / "submission.jsonl").to_dict()
    assert report["summary"]["identification.single"]["exact_match_rate"] == 1
    assert report["summary"]["identification.multi"]["macro_f1"] == 0.666667
    assert report["summary"]["refinement"]["mean_score"] > 99


def test_missing_predictions_receive_zero_credit(tmp_path):
    _write_jsonl(tmp_path / "dataset.jsonl", [
        {"sample_id": "single", "task": "identification.single", "input": {}, "ground_truth": {"phase_ids": ["COD:1"]}},
    ])
    _write_jsonl(tmp_path / "submission.jsonl", [])
    report = evaluate(tmp_path / "dataset.jsonl", tmp_path / "submission.jsonl").to_dict()
    assert report["samples"][0]["status"] == "missing_prediction"
    assert report["summary"]["identification.single"]["exact_match_rate"] == 0
