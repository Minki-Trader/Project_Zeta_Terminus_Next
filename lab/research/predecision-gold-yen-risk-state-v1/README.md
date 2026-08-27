# Pre-Decision Gold-Yen Risk State V1

This open source-free Frontier family asks whether a causal early-server-day
cross-asset risk state, observed before every native portfolio decision, changes
the current six-component portfolio's signal supply, stressed lifecycle value
and stop burden.

The state uses only XAUUSD and USDJPY H1 prices acquired in one isolated Lab
Portable. `RISK_OFF` requires gold up and USDJPY down from the first physical
bar of the server date through the completed 11:00 bar; `RISK_ON` requires the
opposite signs. Mixed and zero-sign dates are context only. No magnitude
threshold, fitted regime, US-index price transform or scheduled-event window is
used.

The declaration is frozen before the market data is acquired. Acquisition must
be committed and pushed before any CP2 lifecycle outcome is reconstructed. A
pass may retain only one later, independently declared whole-portfolio
risk/lot-treatment question. This unit changes no entry, order, exit, priority,
allocation, lot, risk, slot, component, EA or Live behavior.
