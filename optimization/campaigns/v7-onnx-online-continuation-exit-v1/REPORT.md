# Continuation exit bundle: closed without a survivor

The unchanged 2024 fit used 450 eligible half-hold price states; 98 original positions had already closed and six lacked the complete causal prefix. The 14-input/16-tanh-unit network converged in 33 iterations and exported a 1,591-byte ONNX model.

All 557 original 2025 trades remain in the comparison. There are 479 eligible states, 76 positions already closed and two missing prefixes retained as HOLD. Static ONNX emits zero early closes and therefore exactly retains the control. The online variant closes two positions early in the first half and none in the second half.

| Fixed original-volume proxy | Original V7 / static ONNX | ONNX with online correction |
|---|---:|---:|
| Actual net | $127.8900 | $124.9188 |
| Stressed net | $118.6090 | $115.6294 |
| Closed-balance DD | 15.52% | 15.52% |
| Early closes | 0 | 2 |

Both variants fail improved actual/stressed net and the predeclared early-close supply requirements. The whole bundle closes with no seed or adjacent checkpoint/horizon/model/threshold repair. January-June 2026, recent months, an EA implementation and native paths remain unopened.

These are fixed-source-volume/occupancy proxy results with representative M1 opening spreads, conservative retained costs and no freed-capacity credit. Closed-balance DD is not native equity DD. No changed native trajectory, compound-growth improvement or Live authority is claimed. Preserve the complete original input, source, declarations, model, 479 forecasts and both 557-trade tapes. Free space remains above 56 GiB; Live-Dev is unchanged.
