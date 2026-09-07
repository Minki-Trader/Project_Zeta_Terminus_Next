# V7 Passive execution quantile result

The complete fixed static/online bundle does not qualify for native execution. It predicts future quote excursions less accurately than the train-only constant reference. No cash-profit, compound-growth or native-DD conclusion follows from this distributional selection.

| 2025 selection | Static ONNX | Online calibrated ONNX |
|---|---:|---:|
| Forecasts / complete labels | 523 / 523 | 523 / 523 |
| Raw pinball loss | 0.532336 | 0.531115 |
| Constant reference loss | 0.476320 | 0.476320 |
| Loss deterioration | 11.7602% | 11.5039% |
| Approximate potential touches | 364 | 373 |
| Original offset potential touches | 456 | 456 |
| Qualifies | No | No |

All 2025 forecasts are retained and have complete labels. Both halves fail the declared loss tolerance. The model fitted 587 complete 2024 labels; two incomplete fit-period windows remain recorded and untrained. The original source session slots with no signal or unavailable original lookback also remain in the population tape.

The fresh ONNX model is 1,067 bytes at `8CE51A3F3C41C82C6D8002252408397DA8FE433A1A973D92544BDFAEEBB77407`. The full forecast, online-update and population tapes are preserved under the own raw root with exact hashes in MODEL_SELECTION_V1. Online calibration applied 518 matured labels before subsequent forecasts; five final-window labels mature after the last forecast and therefore do not affect an earlier decision. They still contribute to the complete predictive score.

This family is closed without a survivor, candidate EA, native run or opened 2026 candidate price/label. No adjacent quantile, horizon, model, clamp or bias repair is authorized by this closure. The broader V7 development continues after a fresh comparison of mechanisms; the separately completed native observational learning engine and original Live V7 remain unchanged.
