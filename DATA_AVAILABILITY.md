# Data availability

This repository does not redistribute the full Autonomous Greenhouse Challenge
dataset.

A small synthetic example is included in `data/sample/` only to document the
expected input schema. It must not be used to reproduce the reported results.

The training workflow expects the following hourly greenhouse variables:

- `Tair`
- `Rhair`
- `CO2air`
- `Tot_PAR`
- `EC_drain_PC`
- `pH_drain_PC`
- `Cum_irr`

Researchers should obtain the original dataset from its authorized source and
place it locally under `data/raw/`. The `data/raw/` directory is excluded from
Git tracking.

Recommended public-release approach:

1. Publish only a compact, de-identified sample or schema.
2. Provide the official dataset citation and access instructions.
3. Do not upload proprietary, personal, restricted, or competition-controlled
   data.
4. Record preprocessing assumptions and train/test split rules in the training
   notebook or scripts.
