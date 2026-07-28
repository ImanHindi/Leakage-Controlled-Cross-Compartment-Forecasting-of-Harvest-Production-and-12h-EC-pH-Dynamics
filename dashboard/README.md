# Power BI dashboard

`LiveGreenHouseMonitoring.pbix` is the Power BI dashboard developed for the
Paper 2 monitoring and forecasting workflow.

## Purpose

The dashboard visualizes greenhouse measurements and model outputs supplied
through ThingSpeak, including:

- air temperature;
- relative humidity;
- CO2 concentration;
- total PAR;
- measured drain EC;
- predicted drain EC at +12 hours;
- measured drain pH;
- predicted drain pH at +12 hours;
- forecast age and, when configured, weekly production prediction.

## Data path

```text
Historical CSV replay or live LoRa P2P sensing
                    |
                    v
             Raspberry Pi
                    |
                    v
            ThingSpeak channels
                    |
                    v
         Power BI / Power Query
                    |
                    v
       monitoring and forecast pages
```

## Opening the dashboard

Use Microsoft Power BI Desktop on Windows and open:

`dashboard/LiveGreenHouseMonitoring.pbix`

## Refresh configuration

The PBIX file may contain local or project-specific ThingSpeak channel
identifiers and web-source settings. Before publishing or demonstrating it:

1. Open **Transform data** in Power BI Desktop.
2. Inspect the Power Query sources.
3. Replace channel IDs and read API keys with public or local values.
4. Confirm that the ThingSpeak field mapping matches the repository README.
5. Select **Refresh** and verify that all visuals load correctly.
6. Remove any private keys, credentials, local paths, or cached sensitive data.

## Public repository warning

ThingSpeak **write API keys must never be embedded** in the PBIX file or
committed configuration files. A read key should also be removed when the
channel is intended to remain private.

GitHub can store PBIX files, but the format is binary and cannot be reviewed
through normal source diffs. For stronger reproducibility, also export:

- screenshots of each report page;
- a PDF version of the dashboard;
- the Power Query M scripts;
- a field-mapping document;
- a PBIP project version when supported by the installed Power BI Desktop.

These additional exports make the dashboard logic easier to inspect and archive.
