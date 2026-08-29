# Paired-Month versus Active Live-Control Native Quality Recomparison V1

This source-free Optimization campaign keeps `dd20-paired-month-stability-mt5-v1` unchanged and compares its already-complete native MT5 selection and forward reports with the exact active Live-derived `0.04 / 0.12` pass-4 optimization rows. It asks whether the candidate's much higher profit density is also native PF, Recovery Factor and Sharpe dominance.

No candidate grid, parameter change, MQL or SET edit, compile, MT5 run, broker query or Live/Lab action occurred. Candidate PF is reconstructed from native gross profit/loss, Recovery Factor from net divided by maximal equity drawdown dollars, and both must round back to the displayed native values. Candidate Sharpe is authoritative only at its displayed two-decimal precision; control XML precision is retained.

Selection is economically mixed. Candidate PF is `1.49547` versus control `1.413892`, a `5.77%` advantage, and expected payoff remains `8.72x`. But candidate Recovery Factor is `8.69634` versus `10.965367`, a `20.69%` shortfall, while displayed Sharpe is `5.35` versus `5.625108`, a `4.89%` shortfall. This is consistent with the already-disclosed late compounding-dollar DD: the candidate has superior net per relative-DD point but not superior native dollar recovery or smoothness.

Untouched forward is dominant: candidate PF `1.32038` versus `0.984324`, Recovery Factor `1.17054` versus `-0.055472`, and Sharpe `5.57` versus `-0.340238`. Ratios against the nonpositive control forward Recovery Factor and Sharpe are deliberately omitted.

The verdict is `VALID_FIXED_DEVELOPMENT_CANDIDATE_NATIVE_QUALITY_TRADEOFF_SELECTION_MIXED_FORWARD_DOMINANT`. It preserves a real long-path quality cost while strengthening forward replacement evidence. It neither changes nor rejects the fixed candidate and grants no MT5 or Live authority.
