# Independent Two-Index M1 Utility GRU ONNX Challenge V1

This is Independent V8 Challenge Family 005, allocated to Program 1 (`entry_signal_market_structure`) at micro-to-meso height. It asks whether a causal recurrent model of completed US100/US30 M1 price, range, volume and spread paths can rank four actual-cost actions strongly enough to beat V8.

The mandatory architecture is `ONNX + EA`:

- Python owns causal quarterly expanding-window training, deterministic ONNX export and offline frozen-model inference.
- The ONNX model maps one `60 × 15` completed-M1 tensor to utilities for US100 long/short and US30 long/short.
- A self-contained EA must build the exact tensor, invoke the unchanged ONNX schedule, validate freshness and contracts, size and submit the selected action, own protection/recovery and write bounded evidence.
- Python-only or ONNX-only proxy evidence cannot claim a V8 Challenge victory.

Family 001-004 outputs and V1-V8 signals, opportunities, states and economics are excluded. Development is 2024-2025; locked 2026 January-July could have confirmed at most one unchanged edge role. The authoritative contract is `config/challenge-contract.json`.

Status: closed after the one authorized development process. All eight ONNX exports passed PyTorch parity, but only one of 43,072 windows exceeded the loosest `0.10R` edge threshold; that sole US30 long lost actual/stressed `$1.4400 / $1.5520`. The `0.20R` and `0.30R` roles never started. No role passed turnover, breadth, both-year positivity or V8 profit gates, so final fit, locked 2026, EA, compile and MT5 remained unopened. The frozen feature/model/training/threshold/risk/exit bundle has no within-family rescue authority.
