# Model card

## Intended use

The models support greenhouse decision analysis by forecasting:

- drain EC 12 hours ahead;
- drain pH 12 hours ahead;
- a weekly production indicator.

## Model families

- Ridge regression for EC and pH change forecasting.
- Extra-Trees ensemble for production prediction.

## Inputs

The principal inputs are greenhouse climate, radiation, irrigation, and drain
nutrient variables, together with lagged and rolling temporal features.

## Important limitations

- The models were trained in the data domain described in Paper 2.
- Application to another crop, greenhouse, season, sensor set, or sampling
  process is an extrapolation until independently validated.
- Legacy LoRa packets may require approximate conversion from TDS to EC, lux to
  PAR, and pump state to cumulative irrigation.
- Predictions are decision-support outputs, not direct dosing prescriptions.
- Model coefficients describe predictive associations and should not be treated
  as causal agronomic effects.
