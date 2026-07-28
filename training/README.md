# Training and reproducibility

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