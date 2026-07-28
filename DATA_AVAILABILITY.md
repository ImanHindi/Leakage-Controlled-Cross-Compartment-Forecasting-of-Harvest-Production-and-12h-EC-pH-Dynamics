# Data availability

<<<<<<< HEAD
The full Autonomous Greenhouse Challenge, Second Edition (2019) dataset is not
redistributed in this repository. It is identified in the training metadata by
DOI `10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7` and should be obtained
from its authorized source under the applicable terms of use.

A small synthetic file in `data/sample/` documents the live input schema only;
it cannot reproduce the reported paper results. After obtaining the original
data, place it under `data/raw/` and run the notebook in `training/`.

The repository does include derived, non-raw research artifacts under
`outputs/`, including manuscript figures, evaluation tables, coefficients, and
held-out predictions. These artifacts are provided for transparency and do not
replace the source dataset.
=======
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
>>>>>>> f20272c31159b9f5b07403c4aee6aad7607c46cb
