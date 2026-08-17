# Data and code availability

## Public dataset

The quantitative predictive evaluation uses the **Autonomous Greenhouse Challenge, Second Edition (2019)** dataset.

Authorized dataset DOI:

`10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7`

This repository does **not** redistribute the complete AGC dataset. Obtain it from the authorized source under its applicable terms of use.

## Expected local layout

For notebook execution, the preferred local structure is:

```text
agc2_data/
├── AICU/
│   ├── GreenhouseClimate.csv
│   └── Production.csv
├── TheAutomators/
├── Automatoes/
├── Digilog/
├── IUACAAS/
└── Reference/
```

The notebook reads additional source files when present, but `GreenhouseClimate.csv` and `Production.csv` are the primary inputs for the reported predictive workflow.

## Repository data policy

- Raw AGC files are excluded from Git tracking.
- Generated held-out predictions, tables, figures, metadata, and model artifacts required to audit the paper are included.
- `data/sample/live_packet_example.csv` documents an example live packet schema only; it cannot reproduce the reported paper results.
- API keys, passwords, tokens, private channel URLs, local environment folders, and local raw data must not be committed.

## Reproducibility archive

Versioned research-software archive DOI:

`10.5281/zenodo.21645524`

Before a final public release, verify that the Zenodo version contains the same final v4 notebook, selected model artifacts, source-of-truth tables, and final Raspberry Pi benchmark evidence as this repository.
