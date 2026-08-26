# Pending Reservation Risk Tax V1

This frozen source-free Frontier family tests whether an unfilled Passive limit
order consumes economically material aggregate-risk capacity before it fills or
expires.

The unit reconstructs each `PASSIVE_PLACE` interval from the current-spec P4
event ledger, integrates its recorded planned risk over elapsed server time, and
joins only contemporaneous non-Passive passed-signal rows whose masks prove that
the Passive bit was reserved but not active. A blocked row is reservation-caused
only when subtracting that interval's planned risk would have put the attempted
aggregate risk back within the recorded cap.

No blocked-candidate return, fill, slippage, or later outcome is imputed. The
family does not repair Unit 061's invalid slot sum, change pending accounting,
modify MQL, or touch Tester, broker, account, runtime, or Live surfaces. It
closes after one bounded aggregation and does not automatically open a lifetime,
discount, risk-cap, priority, order-type, or Passive-selector successor.
