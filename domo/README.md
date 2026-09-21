# Writing `submission.jsonl`

For XRDBench identification evaluation, models should submit **CIF crystal-structure files**. You do not need to know internal identifiers such as `RRUFF:R120044` or `MP:mp-123`: the evaluator structurally matches each predicted CIF against a hidden reference CIF.

This directory includes [make_submission.py](https://github.com/Asterbin/xrdbench/blob/main/domo/make_submission.py), a small JSONL-writing helper that can be copied into a model project.

## File contract

`submission.jsonl` is UTF-8 text with one JSON object per line. Every record requires:

- `sample_id`: exactly matches the benchmark sample ID;
- `prediction`: the model prediction object;
- `prediction.structure_files`: the recommended field, containing CIF file paths.

For a single-phase task, submit a ranked list of zero to five structurally deduplicated CIF candidates; list order determines Top-1, Top-3, Top-5, and MRR@5. For a multi-phase task, submit an unordered, structurally deduplicated CIF set. An empty submitted set is a scored prediction with zero precision, recall, and F1. Omit the entire sample only when it should be outside the conditional scored set; doing so lowers multi-phase coverage. A CIF must include cell parameters, species, and fractional atomic coordinates. File names are not scored.

```text
outputs/
├── submission.jsonl
└── cifs/
    ├── rruff-single-000000-phase-1.cif
    ├── rruff-multi-000000-phase-1.cif
    └── rruff-multi-000000-phase-2.cif
```

## Case A: the model already writes CIF files (recommended)

For example, if a model writes `outputs/cifs/single-000000.cif`, add it to JSONL directly:

```python
from domo.make_submission import from_cif_paths, write_jsonl

records = [
    from_cif_paths(
        "rruff-single-000000",
        ["outputs/cifs/single-000000-rank-1.cif", "outputs/cifs/single-000000-rank-2.cif"],
    ),
    from_cif_paths(
        "rruff-multi-000000",
        [
            "outputs/cifs/multi-000000-phase-1.cif",
            "outputs/cifs/multi-000000-phase-2.cif",
        ],
    ),
]
write_jsonl(records, "outputs/submission.jsonl")
```

The output is:

```json
{"sample_id":"rruff-single-000000","prediction":{"structure_files":["outputs/cifs/single-000000-rank-1.cif","outputs/cifs/single-000000-rank-2.cif"]}}
{"sample_id":"rruff-multi-000000","prediction":{"structure_files":["outputs/cifs/multi-000000-phase-1.cif","outputs/cifs/multi-000000-phase-2.cif"]}}
```

## Case B: the model returns pymatgen `Structure` objects

Export standard CIF files before writing the submission:

```python
from domo.make_submission import from_pymatgen_structures, write_jsonl

records = [
    from_pymatgen_structures("mp500-single-000000", [single_structure], "outputs/cifs"),
    from_pymatgen_structures("mp500-multi-000000", multi_structures, "outputs/cifs"),
]
write_jsonl(records, "outputs/submission.jsonl")
```

`make_submission.py` uses `pymatgen.io.cif.CifWriter`. Do not place Python objects, NumPy arrays, or raw CIF text in JSONL: the evaluator needs readable CIF file paths.

## Case C: the model returns CIF text

Save the string as a UTF-8 `.cif` file, then use Case A:

```python
from pathlib import Path
from domo.make_submission import from_cif_paths, write_jsonl

cif_path = Path("outputs/cifs/result.cif")
cif_path.parent.mkdir(parents=True, exist_ok=True)
cif_path.write_text(model_cif_text, encoding="utf-8")
write_jsonl([from_cif_paths("opxrd-single-000000", [cif_path])], "outputs/submission.jsonl")
```

## Case D: the model knows benchmark phase IDs (legacy compatibility)

Use this only when a model genuinely produces the dataset's canonical IDs:

```python
from domo.make_submission import from_phase_ids, write_jsonl

records = [
    from_phase_ids("rruff-single-000000", ["RRUFF:R120044"]),
    from_phase_ids("mp500-multi-000000", ["MP:mp-123", "MP:mp-456"]),
]
write_jsonl(records, "outputs/submission.jsonl")
```

New models should submit CIFs, because phase IDs are not shared across databases.

## Path resolution and evaluation

The evaluator resolves relative paths from the dataset manifest directory. The simplest approach is to run it from the repository root with `--data-root .`:

```bash
xrdbench evaluation/hidden-test.jsonl outputs/submission.jsonl \
  --data-root . \
  --output outputs/report.json
```

Avoid submitting absolute paths that include a personal machine directory.

## Preflight check

```python
import json
from pathlib import Path

for line in Path("outputs/submission.jsonl").read_text(encoding="utf-8").splitlines():
    record = json.loads(line)
    for filename in record["prediction"].get("structure_files", []):
        assert Path(filename).is_file(), f"CIF does not exist: {filename}"
print("submission paths look valid")
```

The evaluator checks duplicate or missing sample IDs, the five-candidate single-phase limit, structural deduplication, CIF readability, and one-to-one structure matches. Identification summary metrics are percentages. For multi-phase samples, extra phases lower precision, missing phases lower recall, and `exact_match` is true only when the predicted and reference sets are equal.
