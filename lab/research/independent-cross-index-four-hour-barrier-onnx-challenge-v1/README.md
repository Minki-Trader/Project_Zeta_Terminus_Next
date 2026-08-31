# Independent Cross-Index Four-Hour Barrier ONNX Challenge V1

This is Independent V8 Challenge Family 002, allocated to Program 1 (`entry_signal_market_structure`). It asks whether a temporal model can identify a direction that reaches a favorable barrier before an adverse barrier over the next four H1 bars.

The architecture is mandatory `Python-trained ONNX + EA`:

- Python constructs causal 48-H1 sequences, builds first-barrier labels, trains quarterly temporal convolution models and exports frozen ONNX files.
- ONNX owns the learned decision function. Python and ONNX Runtime must agree within the frozen numeric tolerance before an economic role is valid.
- A separate EA must reproduce the causal feature tensor, invoke the frozen ONNX model, validate risk and symbol contracts, execute, protect, close and persist. A single-EA novel signal or Python-only victory claim is forbidden.

Family 001's features, predictions, decisions, labels and outcomes are not inputs. The three original byte-pinned H1 price sources may be copied only after this declaration reaches `origin/main`. Development is 2024-2025 and locked 2026 January-July may open for at most one unchanged role.

The authoritative contract is `config/challenge-contract.json`. No proxy result can prove a V8 Challenge victory; native ONNX-plus-EA evidence is mandatory.
