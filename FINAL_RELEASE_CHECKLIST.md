# Final repository / submission checklist

## Repository integrity

- [ ] Run `python tools/validate_release.py` and obtain `PASS`.
- [ ] Confirm `RELEASE_MANIFEST_SHA256.txt` matches current files.
- [ ] Confirm no `data/raw/`, `agc2_data/`, virtual environments, caches, or local secrets are staged.
- [ ] Confirm no ThingSpeak write API key appears in tracked files.
- [ ] Confirm the final notebook is `training/Paper_2_CEA_Enhanced_Reproducible_Analysis_v4.ipynb`.
- [ ] Confirm `models/metadata.json` reports Extra Trees / HGB / Ridge and 205 / 202 features.
- [ ] Confirm the definitive Pi benchmark is under `raspberry_pi/results/`.

## Manuscript alignment

- [ ] Production: RMSE 0.1675, MAE 0.1324, R² 0.3360, 11.2% RMSE improvement.
- [ ] EC: HGB, RMSE 0.2879, 32.3% skill over persistence.
- [ ] pH: Ridge α=0.01, RMSE 0.1898, 34.3% skill over persistence.
- [ ] Pi medians: 391.53 ms production, 46.67 ms EC, 11.32 ms pH; RSS ≈160.99 MB.
- [ ] Live HTU outputs are described as advisory/integration evidence, not lettuce validation.
- [ ] Manuscript author byline and CRediT statement list only the confirmed Paper 2 authors: Iman Hindi and Khalid Al-Zaareer.
- [ ] Zenodo record contains the same final notebook/models/results/benchmark files or a new version is published.

## Public-release hygiene

- [ ] Confirm both Paper 2 authors approve the public repository release.
- [ ] Confirm institutional requirements for a software license; add one only after agreement.
- [ ] Inspect Power BI sources for credentials/private channel information.
- [ ] Create a Git tag/release matching the manuscript/repository version.
