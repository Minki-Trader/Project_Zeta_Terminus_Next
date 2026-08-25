# Risk Capacity Release Window V1

Source-free exploratory diagnostic over the six immutable valid event files from the closed passive-refusal-depth observation matrix.

- Unit: `risk-capacity-release-window-015`
- MQL change: none
- Tester run: none
- Live authority: none

The family asks whether a candidate rejected by the frozen 12% aggregate-risk gate often receives enough natural risk release before its already-recorded decision deadline to justify one later exact-gate retry experiment. It does not alter the cap, extend signal freshness, close an incumbent or infer a skipped trade outcome.

Closed as `INVALID_EVENT_KEY_CONTRACT_NO_DEFERRED_ADMISSION_CANDIDATE`. The declaration incorrectly required `state_sequence` to be event-unique; 76 groups validly contained distinct same-version events. The contract was not repaired after outcomes opened. A non-authoritative sensitivity found only 3 of 78 exact-deadline releases versus the frozen minimum 8, so no key repair, longer-window rescue or retry experiment opened.
