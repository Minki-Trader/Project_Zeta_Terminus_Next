# Cross Common-Beta Decomposition V1

This frozen source-free Lab family owns closed Unit 064. It decomposes the exact scheduled four-hour Cross market exposure into the signal's relative component and its unhedged US30/US500 common component, then translates broker lot granularity into a future-capital boundary.

The unit places no trade and does not claim an executable hedge. It uses frozen four-period lifecycle events plus a separately acquired, synchronized three-index H1 bar snapshot and current non-account symbol specifications. Stop and off-grid exits are excluded from the primary price decomposition because H1 opens cannot represent their exact exit tick.

The authoritative design is `evidence/CROSS_COMMON_BETA_DECOMPOSITION_DECLARATION_V1.json`. The synchronized H1 and non-account symbol-spec boundary is frozen by `evidence/CROSS_COMMON_BETA_DECOMPOSITION_ACQUISITION_RECEIPT_V1.json`; all 756 scheduled lifecycles have exact three-index entry and exit marks before outcomes open.

The sole aggregation closed `NO_MATERIAL_CROSS_COMMON_BETA_DILUTION`. Common variance was large and lot granularity was feasible at higher capital, but the common path was not near-zero mean and removing it reduced quality in every period and both directions. The existing directional US100 Cross is preserved; no hedge seed or candidate survives.

No MQL source, compilation, Strategy Tester path, reusable analysis CLI, broker/account query, selected hedge parameter, or Live action belongs to this family.
