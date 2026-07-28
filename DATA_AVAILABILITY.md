# Data availability

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
