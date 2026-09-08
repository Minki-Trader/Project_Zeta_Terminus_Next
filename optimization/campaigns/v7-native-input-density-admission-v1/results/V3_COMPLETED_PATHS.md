# V3 completed paths and the initialization correction

The fixed four-path selection bundle remains **incomplete**. Three paths completed full 2025 at 100% native real ticks; the online path did not complete initialization. It has no economic result. No winner, compounding improvement or family closure is declared.

| Completed path | Actual net, USD | Conservative net, USD | Native equity DD | Robust recovery | Closed trades |
|---|---:|---:|---:|---:|---:|
| Original control cs-v3 | 121.39 | 112.988 | 16.073213873721% | 3.982587546924 | 554 |
| Static ONNX static-v3 | 110.21 | 103.937 | 11.054356941374% | 5.908868675384 | 406 |
| Original control co-v3 | 121.39 | 112.988 | 16.073213873721% | 3.982587546924 | 554 |

Initial capital was USD 100. All three paths preserve all 750 frozen consumed files and the complete twelve historical bar streams, contracts, platform build and symbol database. They finish flat with zero EA faults. The original controls have byte-identical equity, exit, candidate, lifecycle and core event ledgers.

Static ONNX made 942 forecasts, abstained 528 times and recorded 5,260 observations with zero online updates. Both half-years were positive. Its lower DD and better recovery do not compensate for lower actual wealth and failure of the frozen 5% conservative improvement gate. Every original daily volume multiplier stayed at one; these results do not demonstrate the requested compounding effect.

The figure `native-v3-completed-three-paths.png` contains only these three complete paths. The control curves overlap. Plotted drawdown uses available minute marks; the table reports authoritative native intratick DD. Conservative marks include the declared doubled-cost treatment and remove positive financing credits.

## Online initialization and correction

Online-v3 retained its fresh-start marker and runtime ownership lock but produced no initialized learner checkpoint, forecast, update or trade result. Its parent terminal exited after a normal close request. A subsequent scoped termination request returned, but the exact own MetaTester PID 17308 remained alive and held the lock. Windows process/thread wait handles were unsignaled, exit times were zero, and the sole thread waited on a resource. Restart Manager identified that same process as the sole lock owner. The process is not merely a stale list entry.

A subsequent exact-thread Windows CancelSynchronousIo call returned false with ERROR_NOT_FOUND (1168): no cancellable synchronous I/O request was found, and the process remained unsignaled. This scoped attempt changed no file, other process, device or driver. The cause is unresolved; GPU/provider initialization is only a hypothesis. The current source explicitly selects CPU-only ONNX execution and adds a small flushed lifecycle ledger around session creation, each shape assignment, completed initialization and session release. The previous agent subsequently exited and released the exact lock, confirmed by zero own owners and a successful exclusive read. Compile-v5 is now clean for all three roles and installed only in the own runtime. New v4 settings/history and the complete 768-file input freeze are ready; fresh cs-v4 starts the entire new matrix. CPU economics remain unverified.

The graph, 2024 fit, calibration cutoffs, online learning rate and original signal/quantity/risk/stop/exit rules are unchanged. The entire fresh control/static/control/online bundle must complete under that unchanged new input freeze. V3 default-provider results must not be mixed with future CPU results.

All previous compile snapshots, complete V3 native artifacts and original partial online files remain preserved. The separately copied agent log is a whole same-family log, not an exact online-only delta. The locked source file remains in place. The broader archive command was rejected before execution by automatic approval review; narrower explicit evidence copies were allowed. No deletion bypass occurred.

Evidence is in `../evidence/CONTROL_STATIC_NATIVE_V3.json`, `STATIC_NATIVE_V3.json`, `CONTROL_ONLINE_NATIVE_V3.json`, the corresponding `ROOT_*` records, `ROOT_ONNX_CPU_CORRECTION_V1.json`, and `OWN_ONNX_INITIALIZATION_PROCESS_FACTS_V1.json`. Compile-v4 remains attributable through its retained source archive, binaries and logs. Live and Lab remain unchanged.
