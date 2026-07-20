# XRDBench

[![GitHub stars](https://img.shields.io/github/stars/Asterbin/xrdbench?style=social)](https://github.com/Asterbin/xrdbench/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Asterbin/xrdbench?style=social)](https://github.com/Asterbin/xrdbench/network/members)

**A reproducible benchmark for X-ray diffraction phase identification and refinement.**

[English](../README.md) · [Overview](README.zh-CN.md) · [Japanese](README.ja.md) · [Korean](README.ko.md)

For a browser-friendly walkthrough, open the [HTML getting-started guide](GETTING_STARTED.zh-CN.html).

## Evaluation tracks

| Track | Input | Hidden reference | Metrics |
| --- | --- | --- | --- |
| Single-phase identification | One XRD pattern | One reference CIF | CIF structure match / exact match |
| Multi-phase identification | One mixed XRD pattern | Two or three reference CIFs | Precision, recall, F1, exact match |
| Refinement | Experimental and calculated patterns | No structural answer required | Rp, Rwp, correlation, XRDinspector score |

Every multi-phase sample contains two or three distinct phases, and each phase fraction is at least 10%.

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

Models should submit standard CIF files rather than internal database IDs. XRDBench parses each predicted CIF and structurally matches it against hidden reference CIFs.

```json
{"sample_id":"rruff-single-000000","prediction":{"structure_files":["outputs/cifs/result.cif"]}}
```

Single-phase samples require one CIF. Multi-phase samples require two or three CIFs. The filename and textual CIF formatting do not affect the result. Internal phase IDs remain available only for compatibility and dataset auditing.

See [submission.jsonl examples](../domo/README.zh-CN.md) for CIF paths, pymatgen `Structure` objects, CIF text, and legacy phase-ID submissions.

## Dataset contents

| Source | Type | Contents |
| --- | --- | --- |
| MP500 | Simulated | 10,000 single-phase Cu K-alpha patterns and 30,000 mixtures; structures contain no more than 100 atoms |
| RRUFF | Experimental | 1,282 usable single-phase structure-pattern pairs and 10,000 mixtures |
| opXRD | Experimental | 880 usable single-phase structure-pattern pairs and 10,000 mixtures |

Each dataset package contains `patterns.h5`, `manifest.jsonl`, and `structures/`. The common XRD grid is 10–80 degrees 2-theta with a 0.01-degree step, resulting in 7,001 intensity values per pattern.

## Reproducibility

Manifests record source, pattern location, hidden reference CIF paths, internal audit IDs, and mixture fractions. Releases should also record source snapshots, random seeds, preprocessing configuration, and SHA-256 checksums.
