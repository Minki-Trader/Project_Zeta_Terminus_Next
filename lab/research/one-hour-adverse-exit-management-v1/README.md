# One-Hour Adverse Exit Management V1

Open serial Tester-only Program 4 / Unit 040 research family for independent elapsed-age adverse position exits.

- Owner root: `lab/research/one-hour-adverse-exit-management-v1/`
- Frozen parent: `lab/engineering/protective-exit-order-reconciliation-v1/mt5/` at commit `0d4032786cecb7d7e8a4c3074609db5b105fa107`
- Declaration: `evidence/ONE_HOUR_ADVERSE_EXIT_MANAGEMENT_DECLARATION_V1.json`, SHA-256 `0FD749028D0D0B22D51C1B85D1B22262F6EE194D3CB60A7E0961C0BAABE11D7B`
- Compile/runtime receipt: `evidence/ONE_HOUR_ADVERSE_EXIT_MANAGEMENT_COMPILE_RECEIPT_V1.json`, SHA-256 `E27427F2DBC63D641CB75BB33F60F290F47302326C106A698A88EC1E17050604`
- Result: `evidence/ONE_HOUR_ADVERSE_EXIT_MANAGEMENT_RESULT_V1.json`, SHA-256 `5379F39F96C118FBC92E96C3147526AEF71F1C81F706B05B55968684903C8DE2`
- Closure: `evidence/ONE_HOUR_ADVERSE_EXIT_MANAGEMENT_CLOSURE_V1.json`, SHA-256 `962A11A069292951751F983D5D82BE70C49CB6E5B19178287A7054CA6578F18F`
- Fixed bundle: frozen control plus post-one-hour full close at executable mark `<= 0.00R`, `<= -0.25R` or `<= -0.50R`
- Runtime: Git-ignored `lab/runtime/oaem40-portable/`
- Boundary: Tester-only exploratory evidence; Program 6 and every Live source, runtime, state, log and broker/account surface are excluded.

Status: `CLOSED_INVALID_P1_ENVIRONMENT_AND_REAL_TICK_GENERATION_NO_ECONOMIC_VERDICT`. P1 control stopped normally and its HTML said 100% real ticks, but detailed generation fallback, market/symbol hash mutation and financing-anchor drift independently failed integrity. The remaining 15 paths were not opened; no threshold candidate or Live authority exists.
