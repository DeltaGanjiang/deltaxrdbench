# 如何把模型预测写成 `submission.jsonl`

XRDBench 的识别评测推荐模型输出 **CIF 晶体结构文件**。你不需要知道 `RRUFF:R120044`、`MP:mp-123` 之类内部编号；评测器会把预测 CIF 与隐藏真解 CIF 做结构匹配。

本目录中的 [make_submission.py](make_submission.py) 是可直接复制到模型项目的 JSONL 写入工具。

## 0. 文件规则

`submission.jsonl` 是 UTF-8 文本，每行一个 JSON 对象。每条记录必须有：

- `sample_id`：与评测样本完全一致的 ID；
- `prediction`：模型预测结果；
- `prediction.structure_files`：推荐字段，值是一个或多个 CIF 文件路径。

单相识别只能交一个 CIF；多相识别交两个或三个 CIF。CIF 至少应包含晶胞参数、元素种类和原子分数坐标。文件名不参与评分。

```text
outputs/
├── submission.jsonl
└── cifs/
    ├── rruff-single-000000-phase-1.cif
    ├── rruff-multi-000000-phase-1.cif
    └── rruff-multi-000000-phase-2.cif
```

## 1. 情形 A：模型已经输出了 CIF 文件（推荐）

例如模型为单相样本输出：

```text
outputs/cifs/single-000000.cif
```

直接写入 JSONL：

```python
from pathlib import Path
from domo.make_submission import from_cif_paths, write_jsonl

records = [
    from_cif_paths(
        sample_id="rruff-single-000000",
        cif_paths=["outputs/cifs/single-000000.cif"],
    ),
    from_cif_paths(
        sample_id="rruff-multi-000000",
        cif_paths=[
            "outputs/cifs/multi-000000-phase-1.cif",
            "outputs/cifs/multi-000000-phase-2.cif",
        ],
    ),
]
write_jsonl(records, "outputs/submission.jsonl")
```

生成的内容：

```json
{"sample_id":"rruff-single-000000","prediction":{"structure_files":["outputs/cifs/single-000000.cif"]}}
{"sample_id":"rruff-multi-000000","prediction":{"structure_files":["outputs/cifs/multi-000000-phase-1.cif","outputs/cifs/multi-000000-phase-2.cif"]}}
```

## 2. 情形 B：模型返回 pymatgen `Structure`

很多模型或数据库搜索程序的结果是 `pymatgen.core.Structure` 对象。先导出标准 CIF，再写入 JSONL：

```python
from domo.make_submission import from_pymatgen_structures, write_jsonl

# single_structure 是一个 pymatgen Structure
# multi_structures 是一个含 2 或 3 个 pymatgen Structure 的列表
records = [
    from_pymatgen_structures(
        "mp500-single-000000",
        [single_structure],
        "outputs/cifs",
    ),
    from_pymatgen_structures(
        "mp500-multi-000000",
        multi_structures,
        "outputs/cifs",
    ),
]
write_jsonl(records, "outputs/submission.jsonl")
```

工具内部使用 `pymatgen.io.cif.CifWriter` 写 CIF。不要把 Python 对象、numpy 数组或 CIF 文本直接放进 JSONL；评测器需要可读取的 CIF 文件路径。

## 3. 情形 C：模型只返回字符串 CIF 内容

将字符串先保存为 UTF-8 的 `.cif` 文件，再按情形 A 提交：

```python
from pathlib import Path
from domo.make_submission import from_cif_paths, write_jsonl

cif_path = Path("outputs/cifs/result.cif")
cif_path.parent.mkdir(parents=True, exist_ok=True)
cif_path.write_text(model_cif_text, encoding="utf-8")

record = from_cif_paths("opxrd-single-000000", [cif_path])
write_jsonl([record], "outputs/submission.jsonl")
```

## 4. 情形 D：模型知道数据库 phase ID（兼容方式）

只有在模型确实能够输出数据集使用的规范 ID 时才使用此接口：

```python
from domo.make_submission import from_phase_ids, write_jsonl

records = [
    from_phase_ids("rruff-single-000000", ["RRUFF:R120044"]),
    from_phase_ids("mp500-multi-000000", ["MP:mp-123", "MP:mp-456"]),
]
write_jsonl(records, "outputs/submission.jsonl")
```

这只是兼容模式。新模型应优先提交 CIF，因为不同数据库往往不共享相 ID。

## 5. 路径如何设置

评测器默认用评测数据清单所在目录解析相对路径。最简单的方式是从仓库根目录运行，并使用 `--data-root .`：

```bash
xrdbench evaluation/hidden-test.jsonl outputs/submission.jsonl \
  --data-root . \
  --output outputs/report.json
```

这样 JSONL 中的 `outputs/cifs/result.cif` 会被正确找到。也可以使用绝对路径，但不建议把包含个人目录的绝对路径提交给线上评测系统。

## 6. 提交前检查

```python
import json
from pathlib import Path

for line in Path("outputs/submission.jsonl").read_text(encoding="utf-8").splitlines():
    record = json.loads(line)
    files = record["prediction"].get("structure_files", [])
    for filename in files:
        assert Path(filename).is_file(), f"CIF does not exist: {filename}"
print("submission paths look valid")
```

评测端会检查：

1. `sample_id` 是否重复或缺失；
2. 单相是否只提交一个 CIF；
3. 多相是否提交 2–3 个 CIF；
4. CIF 是否可被 pymatgen 或 ASE 解析；
5. 预测结构是否与隐藏真解结构一对一匹配。

多报相会降低 precision，漏相会降低 recall。所有预测相与所有真解相一一匹配时，`exact_match` 才为 `true`。
