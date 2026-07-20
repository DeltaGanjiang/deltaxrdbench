# XRDBench

[![GitHub stars](https://img.shields.io/github/stars/Asterbin/xrdbench?style=social)](https://github.com/Asterbin/xrdbench/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Asterbin/xrdbench?style=social)](https://github.com/Asterbin/xrdbench/network/members)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

**A reproducible benchmark for X-ray diffraction phase identification and refinement.**

[English](https://github.com/Asterbin/xrdbench/blob/main/README.md) · [Overview](https://github.com/Asterbin/xrdbench/blob/main/docs/README.zh-CN.md) · [Japanese](https://github.com/Asterbin/xrdbench/blob/main/docs/README.ja.md) · [Korean](https://github.com/Asterbin/xrdbench/blob/main/docs/README.ko.md)

New to the project? Start with the [bilingual step-by-step HTML guide](https://asterbin.github.io/xrdbench/), automatically published through GitHub Pages.

Need to write a model output? See the [submission.jsonl examples](https://github.com/Asterbin/xrdbench/blob/main/domo/README.md).

Want a visual tour of every dataset and both task modes? Open [explore_datasets.ipynb](https://github.com/Asterbin/xrdbench/blob/main/explore_datasets.ipynb) in Jupyter. It displays two single-phase and two multi-phase examples from MP500, RRUFF, and opXRD, including their XRD patterns and reference structures.

## What it evaluates

| Track | Input | Ground truth | Metrics |
| --- | --- | --- | --- |
| Single-phase identification | One XRD pattern | One hidden reference CIF | CIF structure match / exact match |
| Multi-phase identification | One mixed XRD pattern | Set of 2–3 hidden reference CIFs | Precision, recall, F1, exact match |
| Refinement | Experimental and calculated patterns | No structural answer required | Rp, Rwp, correlation, XRDinspector score |

Each multi-phase sample contains two or three distinct phases, with every phase fraction at least 10%.

## Repository layout

```text
xrdbench/
├── xrdbench/          # Benchmark evaluation and dataset preparation package
├── tests/             # Automated tests
├── datasets/          # Generated artifacts (ignored by Git)
└── XRDinspector/      # Pinned upstream dependency repository
```

Raw source data and generated HDF5 datasets are excluded from Git history. See [datasets/README.md](https://github.com/Asterbin/xrdbench/blob/main/datasets/README.md) for artifact conventions.

## Download datasets

Benchmark datasets are published as GitHub Release assets and are **not** included in `git clone`.

[![Download from Releases](https://img.shields.io/badge/Datasets-GitHub%20Releases-2ea44f?logo=github)](https://github.com/Asterbin/xrdbench/releases)

Download the required archive from the [Releases page](https://github.com/Asterbin/xrdbench/releases), extract it into `datasets/`, and preserve the directory names: `mp500`, `rruff`, and `opxrd`.

## Install

```bash
pip install -e ./XRDinspector -e .
```

## Evaluate a model

```bash
xrdbench dataset.jsonl submissions/model-a.jsonl --output report.json
```

The submission interface is model-agnostic: any model writes JSONL records with the correct `sample_id` and one or more predicted CIF paths. XRDBench parses and structurally matches those CIFs to hidden reference structures; models do not need to know database-specific phase IDs.

```json
{"sample_id":"rruff-single-000000","prediction":{"structure_files":["predictions/result.cif"]}}
```

## Dataset sources

| Source | Type | Intended contents |
| --- | --- | --- |
| MP500 | Simulated | 10,000 single-phase Cu Kα patterns and 30,000 mixtures, using structures with ≤100 atoms |
| RRUFF | Experimental | 1,164 usable single-phase structure–pattern pairs and 10,000 mixtures |
| opXRD | Experimental | 880 usable single-phase structure–pattern pairs and 10,000 mixtures |

## Reproducibility

Dataset manifests record source, pattern location, hidden reference CIF paths, internal audit IDs, and mixture fractions. Published releases should additionally record source snapshots, random seeds, preprocessing configuration, and SHA-256 checksums.

## License

Dataset-source licenses and attribution requirements remain with their original providers. Add a project license before public redistribution of code or artifacts.
