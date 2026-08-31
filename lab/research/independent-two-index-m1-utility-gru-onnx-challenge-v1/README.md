# Independent Two-Index M1 Utility GRU ONNX Challenge V1

This is Independent V8 Challenge Family 005, allocated to Program 1 (`entry_signal_market_structure`) at micro-to-meso height. It asks whether a causal recurrent model of completed US100/US30 M1 price, range, volume and spread paths can rank four actual-cost actions strongly enough to beat V8.

The mandatory architecture is `ONNX + EA`:

- Python owns causal quarterly expanding-window training, deterministic ONNX export and offline frozen-model inference.
- The ONNX model maps one `60 × 15` completed-M1 tensor to utilities for US100 long/short and US30 long/short.
- A self-contained EA must build the exact tensor, invoke the unchanged ONNX schedule, validate freshness and contracts, size and submit the selected action, own protection/recovery and write bounded evidence.
- Python-only or ONNX-only proxy evidence cannot claim a V8 Challenge victory.

Family 001-004 outputs and V1-V8 signals, opportunities, states and economics are excluded. Development is 2024-2025; locked 2026 January-July may confirm at most one unchanged edge role. The authoritative contract is `config/challenge-contract.json`.
