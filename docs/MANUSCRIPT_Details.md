
Associated manuscript title:

**Leakage-Controlled Cross-Compartment Forecasting of Harvest Production and 12-Hour EC/pH Dynamics with Edge Computing Benchmarking**


| Manuscript component | Repository evidence |
|---|---|
| Six-compartment split; AICU untouched | `models/metadata.json`, training notebook |
| 110 development / 23 AICU harvest events | `results/v4/tables/production_event_audit.csv` |
| Extra Trees final production model | `models/production_model.joblib`, model comparison tables |
| Production RMSE 0.1675; 11.2% improvement | `results/v4/tables/production_results.csv`, source-of-truth CSV |
| 19,265 development / 3,538 AICU hourly samples | `results/v4/tables/hourly_sample_audit.csv` |
| EC final family = HGB | `models/ec_12h_model.joblib`, `metadata.json`, model-family tables |
| pH final family = Ridge α=0.01 | `models/ph_12h_model.joblib`, `metadata.json` |
| EC/pH 12-h skill over persistence | `results/v4/tables/forecast_skill_12h.csv` |
| Paired bootstrap skill intervals | `results/v4/tables/CEA_paired_skill_bootstrap.json` |
| Horizon sensitivity | `results/v4/tables/CEA_multi_horizon_heldout.csv` |
| Feature-group ablation | `results/v4/tables/CEA_feature_group_ablation_12h.csv` |
| Regime-specific behavior | `results/v4/tables/CEA_regime_error_analysis.csv` |
| Production stage-proxy ablation | `results/v4/tables/CEA_production_stage_ablation.csv` |
| Target-device benchmark | `raspberry_pi/results/raspberry_pi_benchmark_v4.csv` and JSON |
| Target-device environment | `raspberry_pi/results/raspberry_pi_environment_v4.json` |
| Live HTU advisory path | `raspberry_pi/live_lora_p2p_models_to_thingspeak.py`, dashboard resource |

## Final quantitative boundary

Quantitative predictive validity is established only within the AGC domain using the untouched AICU compartment. The HTU NFT execution establishes target-device feasibility and systems integration only; it does not establish lettuce-specific forecast accuracy or autonomous dosing performance.
