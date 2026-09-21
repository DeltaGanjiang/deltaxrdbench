# XRDBench

[![GitHub stars](https://img.shields.io/github/stars/Asterbin/xrdbench?style=social)](https://github.com/Asterbin/xrdbench/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Asterbin/xrdbench?style=social)](https://github.com/Asterbin/xrdbench/network/members)

**A reproducible benchmark for X-ray diffraction phase identification and refinement.**

**[英](../README.md) · [中](./README.zh-CN.md) · [日](./README.ja.md) · [韩](./README.ko.md)**

For a browser-friendly bilingual walkthrough with one-click Chinese/English switching, open the [HTML getting-started guide](https://github.com/Asterbin/xrdbench/blob/main/docs/GETTING_STARTED.zh-CN.html).

## Evaluation tracks

| Track | Input | Hidden reference | Metrics |
| --- | --- | --- | --- |
| Single-phase identification | One XRD pattern | One reference CIF | Top-1、Top-3、Top-5、MRR@5 |
| Multi-phase identification | One mixed XRD pattern | Two or three reference CIFs | Coverage、Exact、宏平均 P/R/F1 |
| Refinement | Experimental and calculated patterns | No structural answer required | Rp, Rwp, correlation, XRDinspector score |

Every multi-phase sample contains two or three distinct phases, and each phase fraction is at least 10%.
XRD-only 与 XRD + composition 两种设置使用相同指标，并分别报告结果。

## Repository layout

```text
xrdbench/
├── xrdbench/          # Evaluation and dataset preparation package
├── domo/              # submission.jsonl examples and helper code
├── tests/             # Automated tests
├── datasets/          # Downloaded artifacts, excluded from Git
└── XRDinspector/      # Pinned upstream scoring dependency
```

## Download datasets

Datasets are published as GitHub Release assets and are not included in `git clone`.

[![Download from Releases](https://img.shields.io/badge/Datasets-GitHub%20Releases-2ea44f?logo=github)](https://github.com/Asterbin/xrdbench/releases)

Download and extract the required archives into `datasets/mp500/`, `datasets/rruff/`, and `datasets/opxrd/`.

## Installation and evaluation

```bash
git clone --recurse-submodules https://github.com/Asterbin/xrdbench.git
cd xrdbench
pip install -e ./XRDinspector -e .
xrdbench evaluation/hidden-test.jsonl outputs/submission.jsonl --data-root . --output outputs/report.json
```

## Model submission

Models should submit standard CIF files rather than internal database IDs. XRDBench parses each predicted CIF and structurally matches it against hidden reference CIFs. 单相预测应按排名提交最多五个结构去重后的 CIF；多相预测应提交无序且去重的 CIF 集合。

```json
{"sample_id":"rruff-single-000000","prediction":{"structure_files":["outputs/cifs/result.cif"]}}
```

所有 identification 汇总指标均以百分比报告。单相 Top-k 判断前 k 个候选中是否首次出现结构匹配，MRR@5 使用首次匹配名次的倒数；候选排名和后处理不得访问隐藏真值。多相 P/R/F1 是 scored mixtures 上逐样本指标的宏平均，Exact 要求预测集合与参考集合完全相同，Coverage 为 `100 * N_scored / N`。显式提交空集合会作为零分样本参与计算；完全省略样本则不进入条件 P/R/F1 平均，并降低 Coverage。Oracle filtering 后没有保留正比例候选的 mixture 也采用后一约定。评测器一次输出一个 run 的百分比，最终表格对三个固定 seed 做无权重平均。文件名和 CIF 文本格式不参与评分；内部 phase ID 只用于兼容和数据审计。

See [submission.jsonl examples](https://github.com/Asterbin/xrdbench/blob/main/domo/README.md) for CIF paths, pymatgen `Structure` objects, CIF text, and legacy phase-ID submissions.

## Dataset contents

| Source | Type | Contents |
| --- | --- | --- |
| MP500 | Simulated | 10,000 single-phase Cu K-alpha patterns and 30,000 mixtures; structures contain no more than 100 atoms |
| RRUFF | Experimental | 1,164 usable single-phase structure-pattern pairs and 10,000 mixtures |
| opXRD | Experimental | 880 usable single-phase structure-pattern pairs and 10,000 mixtures |

Each dataset package contains `patterns.h5`, `manifest.jsonl`, and `structures/`. The common XRD grid is 10–80 degrees 2-theta with a 0.01-degree step, resulting in 7,001 intensity values per pattern.

## Reproducibility

Manifests record source, pattern location, hidden reference CIF paths, internal audit IDs, and mixture fractions. Releases should also record source snapshots, random seeds, preprocessing configuration, and SHA-256 checksums.
