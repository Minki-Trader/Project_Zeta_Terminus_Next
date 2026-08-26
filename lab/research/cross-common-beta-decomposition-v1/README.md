# Cross Common-Beta Decomposition V1

This source-free Lab family owns Unit 064. It decomposes the exact scheduled four-hour Cross market exposure into the signal's relative component and its unhedged US30/US500 common component, then translates broker lot granularity into a future-capital boundary.

The unit places no trade and does not claim an executable hedge. It uses frozen four-period lifecycle events plus a separately acquired, synchronized three-index H1 bar snapshot and current non-account symbol specifications. Stop and off-grid exits are excluded from the primary price decomposition because H1 opens cannot represent their exact exit tick.

The authoritative design is `evidence/CROSS_COMMON_BETA_DECOMPOSITION_DECLARATION_V1.json`. No MQL source, compilation, Strategy Tester path, reusable analysis CLI, broker/account query, selected hedge parameter, or Live action belongs to this family.

