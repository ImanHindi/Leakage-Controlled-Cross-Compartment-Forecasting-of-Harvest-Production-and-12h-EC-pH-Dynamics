# Power BI dashboard — HTU advisory monitoring

`LiveGreenHouseMonitoring.pbix` is the Power BI resource used in the implemented ThingSpeak monitoring path.

## Role in Paper 2

The dashboard demonstrates that physical HTU NFT measurements and frozen-model outputs can be propagated through the sensing–edge–cloud visualization path. It is **not** used to calculate the manuscript's AICU predictive metrics and does **not** establish lettuce-specific model validity.

## Implemented data path

```text
HTU sensors → ESP32/LoRa P2P → Raspberry Pi → ThingSpeak → Power BI
```

The Raspberry Pi performs local model inference and uploads selected measured/predicted fields. Power BI reads the ThingSpeak feed and presents monitoring visuals.

## Suggested prediction labels

Use labels that preserve the paper's scientific boundary:

- `ProdA advisory prediction`
- `EC forecast (+12 h, advisory)`
- `pH forecast (+12 h, advisory)`
- `AGC-trained model output — not yet validated for lettuce`

Avoid labels such as “validated lettuce yield” or “autonomous AI dosing”.

## Before public use

1. Open **Transform data** in Power BI Desktop.
2. Inspect the Power Query web sources and field mappings.
3. Replace project-specific ThingSpeak channel IDs/read keys where necessary.
4. Remove credentials, private URLs, local paths, or cached sensitive data.
5. Confirm measured EC/pH and predicted EC/pH are clearly distinguishable.
6. Refresh and inspect all visuals.
