<div align="center">
  <h1>XRDBench</h1>
  <p><strong>A reproducible benchmark for X-ray diffraction phase identification and refinement</strong></p>
  <p>Model-agnostic evaluation across simulated and experimental XRD datasets,<br>with structure-aware scoring against hidden reference CIFs.</p>
  <p>
    <a href="https://www.python.org/"><img alt="Python 3.9+" src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&amp;logoColor=white"></a>
    <a href="https://github.com/Asterbin/xrdbench/releases"><img alt="Datasets" src="https://img.shields.io/badge/Datasets-GitHub_Releases-2ea44f?logo=github"></a>
    <a href="https://asterbin.github.io/xrdbench/"><img alt="Documentation" src="https://img.shields.io/badge/Docs-GitHub_Pages-2563eb?logo=githubpages&amp;logoColor=white"></a>
    <a href="https://github.com/Asterbin/xrdbench/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/Asterbin/xrdbench?style=flat&amp;logo=github"></a>
  </p>
  <p><strong><a href="./README.md">英</a> · <a href="./docs/README.zh-CN.md">中</a> · <a href="./docs/README.ja.md">日</a> · <a href="./docs/README.ko.md">韩</a></strong></p>
  <p><a href="https://asterbin.github.io/xrdbench/">Getting started</a> · <a href="https://github.com/Asterbin/xrdbench/releases">Download datasets</a> · <a href="./domo/README.md">Submission format</a> · <a href="./explore_datasets.ipynb">Dataset notebook</a></p>
</div>

---

## At a glance

| Structure-aware | Model-agnostic | Reproducible | Multimodal |
| :---: | :---: | :---: | :---: |
| Hidden CIF matching | Any model or search system | Fixed manifests and seeds | XRD-only and XRD + composition |

XRDBench evaluates predictions by their parsed crystal structures—not CIF filenames or text formatting. It supports ranked single-phase candidates, unordered multi-phase sets, and pattern-refinement outputs through one JSONL interface.

## Benchmark tracks

| Track | Model input | Hidden reference | Reported metrics |
| --- | --- | --- | --- |
| **Single-phase identification** | XRD or XRD + composition | One reference CIF | Top-1, Top-3, Top-5, MRR@5 |
| **Multi-phase identification** | Mixed XRD or XRD + composition | Set of 2–3 reference CIFs | Coverage, Exact, macro P/R/F1 |
| **Refinement** | Experimental and calculated patterns | No structural answer required | Rp, Rwp, correlation, XRDinspector score |

Every multi-phase sample contains two or three distinct phases, each with a fraction of at least 10%. The XRD-only and XRD + composition settings use the same metrics and are reported separately.

## Quick start

### 1. Install

```bash
git clone --recurse-submodules https://github.com/Asterbin/xrdbench.git
cd xrdbench
pip install -e ./XRDinspector -e .
```

### 2. Download a dataset

Download an archive from [GitHub Releases](https://github.com/Asterbin/xrdbench/releases), then extract it under `datasets/` while preserving the `mp500`, `rruff`, or `opxrd` directory name.

### 3. Evaluate a submission

```bash
xrdbench dataset.jsonl submissions/model-a.jsonl \
  --data-root . \
  --output report.json
```

## Submission format

Each JSONL record pairs a benchmark `sample_id` with model output. Models can submit standard CIF files without knowing database-specific phase IDs.

```json
{"sample_id":"rruff-single-000000","prediction":{"structure_files":["predictions/rank-1.cif","predictions/rank-2.cif"]}}
```

- **Single phase:** submit up to five structurally deduplicated CIFs in rank order.
- **Multi phase:** submit an unordered, structurally deduplicated CIF set.
- **Explicit empty set:** scored as a zero-valued prediction.
- **Omitted sample:** excluded from conditional averages and lowers multi-phase Coverage.

See the [complete submission guide](./domo/README.md) for CIF paths, `pymatgen.Structure` export, legacy phase IDs, and validation details.

<details>
<summary><strong>Metric definitions and aggregation</strong></summary>

Identification summaries are percentages. Single-phase Top-k records whether the first structural match appears by rank k, while MRR@5 averages the reciprocal first-match rank. Candidate ranking and post-processing must be fixed without access to the hidden target.

Multi-phase precision, recall, and F1 are sample-wise macro averages over scored mixtures. Exact requires equality of the predicted and reference sets, and Coverage is `100 × N_scored / N`. Under oracle filtering, mixtures with no retained positive-fraction candidate are omitted from the conditional P/R/F1 averages and reflected through Coverage.

The evaluator reports one run at a time. Benchmark table entries are unweighted means of percentage results from three fixed seeds.

</details>

## Datasets

| Dataset | Pattern source | Single phase | Mixtures | Notes |
| --- | --- | ---: | ---: | --- |
| **MP500** | Simulated | 10,000 | 30,000 | Cu Kα; structures contain ≤100 atoms |
| **RRUFF** | Experimental | 1,164 | 10,000 | Usable structure–pattern pairs |
| **opXRD** | Experimental | 880 | 10,000 | Usable structure–pattern pairs |

Dataset archives are release assets and are intentionally excluded from `git clone`. Artifact layout and conventions are documented in [datasets/README.md](./datasets/README.md).

## Project map

```text
xrdbench/
├── xrdbench/          # Evaluation and dataset preparation package
├── domo/              # Submission examples and helper code
├── tests/             # Automated evaluator tests
├── datasets/          # Downloaded artifacts, excluded from Git
└── XRDinspector/      # Pinned refinement-scoring dependency
```

## Reproducibility

Dataset manifests record source, pattern location, hidden reference CIF paths, internal audit IDs, and mixture fractions. Published releases should also record source snapshots, random seeds, preprocessing configuration, and SHA-256 checksums.

## License

Dataset-source licenses and attribution requirements remain with their original providers. Add a project license before public redistribution of code or artifacts.
