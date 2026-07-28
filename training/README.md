# Training and reproducibility

<<<<<<< HEAD
`Paper_2_Enhanced_AGC2_Reproducible_Analysis_CORRECTED_v3.ipynb` contains the
end-to-end Paper 2 analysis. It covers:

1. authorized data loading and quality control;
2. hourly aggregation and short-gap interpolation;
3. chronological training, validation, and held-out team testing;
4. lag features at 1, 3, 6, 12, 24, and 48 hours;
5. rolling mean, standard deviation, and trend features over 3, 6, 12, 24,
   and 48 hours;
6. Ridge models for 12-hour EC and pH changes;
7. the Extra-Trees weekly production model;
8. persistence and alternative-model comparisons;
9. moving-block bootstrap intervals and leave-one-team-out analysis;
10. model, metadata, figure, table, and prediction export.

## Reproduction

Create the pinned environment from the repository root, place the authorized
source dataset under `data/raw/`, open the notebook, restart the kernel, and run
all cells in order. The checked-in `outputs/` directory contains the current
paper artifacts for comparison.
=======
The training workflow document and export:

1. hourly aggregation of raw greenhouse measurements;
2. short-gap interpolation policy;
3. lag features at 1, 3, 6, 12, 24, and 48 hours;
4. rolling mean, standard deviation, and trend features over 3, 6, 12, 24,
   and 48 hours;
5. chronological train/validation/test partitioning;
6. Ridge models for 12-hour EC and pH changes;
7. the Extra-Trees production model;
8. fitted preprocessing objects;
9. exact ordered feature-name manifests;
10. evaluation tables, plots, predictions, and bootstrap intervals.
>>>>>>> f20272c31159b9f5b07403c4aee6aad7607c46cb
