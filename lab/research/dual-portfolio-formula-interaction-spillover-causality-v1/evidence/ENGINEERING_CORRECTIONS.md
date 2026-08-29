# Engineering corrections

## EC-01 — family-scoped raw-byte materialization

After declaration commit `c69c217b1f37a42ef7782e984a9434739d48ef1a` reached `origin/main` and before any formula-unseen interaction economics opened, the clean-checkout audit identified that the new Lab family had no explicit raw-byte Git attribute. The committed blobs already contain the declared LF bytes, but `core.autocrlf=true` could materialize different working bytes and make the declaration's raw SHA-256 pins host-dependent.

The correction adds only `/lab/research/dual-portfolio-formula-interaction-spillover-causality-v1/** -text` to the repository `.gitattributes`. Config, analysis code, input data, exact point IDs, parameter payloads, discovery anchors, later intervals, attribution formulas, gates, verdicts and authority are unchanged. No economic process, metric, MT5, Tester, compile, runtime, broker/account query or Live path had opened. This is an unlimited non-economic repository-materialization correction, not a research result or failure.
