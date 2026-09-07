# V7 native learning engine

This campaign adds an actual learning path to an isolated V7 EA. ONNX performs float32 inference; the EA performs explicitly defined online weight updates. The engine begins with zero weights in each fresh Tester pass. It adopts no historical trained model or trading state.

## Entry observation

After an accepted position is durably recorded by the original EA, the learner stores its position identifier, 14 features and the prediction from that moment. The features are six component indicators, six component-gated bounded original signal values, direction, and direction times the previously observed signal direction. No later price, close result or reconstructed counterfactual opportunity enters the entry features.

The embedded graph receives two tensors: features with shape `[1,14]` and current weights with shape `[14,1]`. Its `MatMul` output has shape `[1,1]`. Dynamic weights are model inputs; ONNX Runtime itself is not described as the trainer.

## Matured outcome and update

After a complete own lifecycle closes, the learner records accumulated doubled-cost-stressed net divided by its original admitted entry risk. Raw outcomes remain in evidence. The update label is clipped to `[-2,2]`; forecast error is scored using the stored entry prediction before any corresponding update.

The label is queued at the later of its recorded deal time and the time when the EA observes it. It becomes usable only at a strictly later server second. A close cannot change an entry forecast in that same second. A final label without a later event remains explicitly pending.

For each feature, the fixed update is:

`weight += 0.05 * (clipped_label - stored_prediction) * stored_feature / (1 + sum(stored_features^2))`

Each weight is clipped to `[-2,2]`. There is no learning-rate, feature or clipping search in this campaign.

## Trading and evidence boundary

The learning module has no writes to the original component, portfolio, execution, order or risk state. Its callbacks are observations of completed original core actions. All original V7 sizing, signals, protection and exits remain intact. A model or learning-record failure marks engineering completion invalid while leaving protective trading duties intact.

The own `learning-events.csv` records forecasts, queued labels and applied updates with feature vectors, weights, identifiers and times. Two alternating checkpoint files hold counters, weights, active entry observations and pending labels. Trace capacity is 16 MiB per run; pending-label capacity is 128. This phase makes no live restart or recovery claim.

Source owner: `optimization/campaigns/v7-native-onnx-online-learning-v1/learner/MQL5/Include/ZetaV7MLLearner/Learning/ZetaNativeOnlineLearning.mqh`. Model owner: `optimization/campaigns/v7-native-onnx-online-learning-v1/learner/MQL5/Experts/ZetaV7MLLearner/online-linear.onnx`.

Only a complete native adjacent comparison can establish operation with unchanged V7 economics. Neither adding ONNX nor reducing prediction loss by itself establishes better compound growth. Any later trading use of predictions requires its own prospective economic contract and complete evidence.
