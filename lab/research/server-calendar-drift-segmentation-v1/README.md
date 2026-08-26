# Server-Calendar Drift Segmentation V1

This frozen source-free Lab family owns closed Program 2 / Unit 071. It asked whether the existing same-server-day portfolio structurally omits most positive index drift because that drift occurs between one server date's last observed H1 open and the next date's first, rather than inside the current decision/hold envelope.

The single finite bundle decomposes every eligible US30, US100 and US500 server-calendar transition into gap and intraday log return, then splits intraday at the exact 13:00 open. Short gaps of at most six hours are distinguished from weekend/holiday long gaps so an apparent overnight effect cannot automatically imply an implementable nightly sleeve.

The frozen verdict is `NO_MATERIAL_OVERNIGHT_DRIFT_OMISSION_INTRADAY_DOMINATES`. Gap return was only `16.96%` of positive pooled calendar drift while intraday return carried `83.04%`, with intraday dominance in `4/4` periods and `3/3` symbols. Ordinary short gaps carried `94.92%` of the small positive gap channel, but that implementability fact cannot rescue a non-dominant economic opportunity. Preserve the current same-day orientation and retain no overnight sleeve, boundary, allocation, EA or Live candidate.

Declaration/result/closure SHA-256 values are `B5AB83C3E9390910B957F27AA6DF4222FDC63BD05CB9E084963ADE1F0BF7DD1B` / `F6182E21FEF2688EC940B36B0473E5629CDA266C11D959896629D73A2A403230` / `4B8E9E6330484C0BDC997279426D517491A67B52C30DF790758C4A81300E7A3A`. One successful aggregation, zero correction and zero rerun; no data, runtime, MQL, Tester, broker/account query or Live action occurred.
