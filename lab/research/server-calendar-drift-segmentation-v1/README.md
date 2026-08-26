# Server-Calendar Drift Segmentation V1

This source-free Lab family owns active Program 2 / Unit 071. It asks whether the existing same-server-day portfolio structurally omits most positive index drift because that drift occurs between one server date's last observed H1 open and the next date's first, rather than inside the current decision/hold envelope.

The single finite bundle decomposes every eligible US30, US100 and US500 server-calendar transition into gap and intraday log return, then splits intraday at the exact 13:00 open. Short gaps of at most six hours are distinguished from weekend/holiday long gaps so an apparent overnight effect cannot automatically imply an implementable nightly sleeve.

The authoritative pre-outcome contract is `evidence/SERVER_CALENDAR_DRIFT_SEGMENTATION_DECLARATION_V1.json`, SHA-256 `B5AB83C3E9390910B957F27AA6DF4222FDC63BD05CB9E084963ADE1F0BF7DD1B`. The unit uses only the immutable 24,417-row H1-open export and Unit 018's already-frozen same-day lifecycle fact. It adds no data, runtime, MQL, Tester, broker/account query or Live action.
