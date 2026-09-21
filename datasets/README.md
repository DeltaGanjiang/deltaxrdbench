# Dataset artifacts

Generated datasets are intentionally excluded from Git because the pattern archives are large. Download the published archives from the [DeltaXRDbench Releases page](https://github.com/Asterbin/xrdbench/releases), then place each source under this directory:

```text
datasets/
  mp500/
  rruff/
  opxrd/
```

Every source directory contains:

- `patterns.h5`: shared 2θ grid and single/multi-phase intensities;
- `manifest.jsonl`: labels, HDF5 locations, mixture fractions, and metadata;
- `structures/`: reference CIF files for the single-phase records.

Use an artifact store, release asset, or DOI-backed archive for published dataset versions. Record the source snapshot, random seed, grid, preprocessing parameters, and checksums with every release.
