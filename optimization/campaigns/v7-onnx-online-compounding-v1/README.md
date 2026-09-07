# V7 ONNX, online learning and compound growth

This is the sole active Optimization campaign. Exact V7R is physically frozen at `optimization/baseline/NEXT-E03-V7R-RLO1-0bba2ca045fe/`; `evidence/BASELINE_DERIVATION_V1.json` pins all 21 package files. Live-Dev is untouched.

The first bundle compares the exact V7 control, a frozen ONNX risk score with equity-based lot sizing, and the same score with causal online residual updates. `evidence/DECLARATION_V1.json` owns the prospective numeric contract. Python fits a small regularized model from original V7 completed 2024 trades and exports the ONNX graph. The EA materializes the same existing entry features, runs ONNX inference, and updates online state only after its own completed trade label becomes available. Online learning is an explicit residual layer, not a claim that ONNX Runtime trains graph weights.

The initial 2025 offline stage evaluates prediction and risk-weighted original outcome information only. It cannot reproduce a changed stop/volume/admission path or prove compound growth/native DD. An unchanged selected role must run against an adjacent exact-V7 native control on complete real ticks. Fit-year results are not out-of-sample performance. July-August 2026 remains excluded from selection; its known V7 aggregate results are disclosed.

Source, model and small evidence belong here. Physical runtime belongs to `optimization/runtime/v7-onnx-online-compounding-v1-portable/`; large inputs/results belong to `optimization/artifacts/raw/v7-onnx-online-compounding-v1/`. No shared mutable trees, source links, Live runtime, broker context query, external economic datasets or test/checker infrastructure. Keep at least 30 GiB free. Continue serial work until user pause.
