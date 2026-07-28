# Power BI Dashboard

`LiveGreenHouseMonitoring.pbix` is the Power BI dashboard developed for the
Paper 2 greenhouse monitoring and forecasting workflow.

## Purpose

The dashboard visualizes greenhouse measurements and model outputs delivered
through ThingSpeak. Depending on the configured channel fields, the report may
include:

- air temperature;
- relative humidity;
- carbon-dioxide concentration;
- total photosynthetically active radiation;
- measured drain electrical conductivity;
- predicted drain electrical conductivity at +12 hours;
- measured drain pH;
- predicted drain pH at +12 hours;
- forecast age;
- communication-quality indicators;
- weekly production-indicator prediction, when configured.

The dashboard is intended for research, demonstration, and decision-support
visualization. It is not a deterministic industrial SCADA system.

## Data flow

```text
Historical CSV replay or live LoRa P2P sensing
                    │
                    ▼
             Raspberry Pi
                    │
                    ▼
            ThingSpeak channels
                    │
                    ▼
         Power BI / Power Query
                    │
                    ▼
      Monitoring and forecast pages
```

## Open the dashboard

Use Microsoft Power BI Desktop on Windows and open:

```text
dashboard/LiveGreenHouseMonitoring.pbix
```

## ThingSpeak field mapping

The dashboard should follow the field mappings documented in the main
repository README.

### Channel A — greenhouse measurements

| Field | Variable |
|---:|---|
| 1 | `Tair` |
| 2 | `Rhair` |
| 3 | `CO2air` |
| 4 | `Tot_PAR` |
| 5 | `EC_drain_PC` |
| 6 | `pH_drain_PC` |
| 7 | `Cum_irr` |

### Channel B — measurements, predictions, and communication quality

| Field | Variable |
|---:|---|
| 1 | Measured EC |
| 2 | Predicted EC at +12 h |
| 3 | Measured pH |
| 4 | Predicted pH at +12 h |
| 5 | Weekly production indicator |
| 6 | Forecast age in minutes |
| 7 | RSSI |
| 8 | SNR |

## Refresh configuration

The PBIX file may contain local or project-specific ThingSpeak channel
identifiers and web-source settings. Before publishing, demonstrating, or
refreshing the dashboard:

1. Open **Transform data** in Power BI Desktop.
2. Inspect every Power Query source.
3. Replace project-specific channel IDs and read API keys with valid values.
4. Confirm that the ThingSpeak field mapping matches the repository README.
5. update private credentials, write keys, local paths.
6. Select **Refresh** and verify that all queries and visuals load successfully.
7. Check time-zone handling and timestamp formatting.
8. Confirm that prediction timestamps and forecast-age calculations remain
   consistent with the Raspberry Pi and replay scripts.

ThingSpeak write API keys must be changed in the PBIX file.


## Limitations

- The dashboard reflects the quality and update frequency of the connected
  ThingSpeak feeds.
- Temporary communication interruptions may produce missing or delayed values.
- Forecast visualizations depend on the model and feature-generation pipeline
  described elsewhere in the repository.
- Live production output should be treated as an experimental indicator when
  the complete training feature set is unavailable.
- The dashboard should not be used as the sole basis for autonomous nutrient or
  chemical dosing.
