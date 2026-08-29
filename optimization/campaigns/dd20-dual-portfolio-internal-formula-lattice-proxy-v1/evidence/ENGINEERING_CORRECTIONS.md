# Engineering corrections

## Market acquisition attempt 01

The first M1 export inherited `MaxBars=400000` and therefore truncated the requested history. It is preserved under `optimization/artifacts/raw/dd20-dual-portfolio-internal-formula-lattice-proxy-v1/market-invalid-attempt-01/`. This was an environment correction, not an economic result. The dedicated Optimization runtime was changed to `MaxBars=3000000`, and the final acquisition receipt covers all eight declared series through `2026-07-31`.

## Economic anchor corrections

The feature proxy initially aligned the Cross inputs by historical timestamps. Source inspection showed that the native formula checks only the latest H1 synchronization and then reads the three symbol histories positionally. The proxy was corrected to that exact behavior. The final feature anchor matches all `5,085 / 5,085` observed rows within `1e-8`.

Native stressed lifecycle evidence also showed that stress uses the larger of entry and exit spread, not entry spread alone. Component calibration was corrected to the same exact lifecycle pairs and `max(entry, exit)` M1 spread. Near-zero native forward net is normalized only for the engineering anchor by the larger of the native net, five percent of matching proxy turnover, or USD 5. Candidate selection still uses complete unnormalized economic dollars and drawdown.

## Invalid neighborhood attempt 01

The first full surface completed but its local-plateau verdict is invalid and has no research-failure status. It is preserved under `optimization/artifacts/raw/dd20-dual-portfolio-internal-formula-lattice-proxy-v1/output-invalid-neighborhood-attempt-01/`.

That implementation treated all 59 level indexes as one continuous Euclidean topology and selected the 32 globally nearest points. This was not a valid local robustness geometry:

- categorical modes, the ARC ordinal profile and Return overlap were treated as if adjacent integer labels represented small formula changes;
- the replacement contract's economically inert Passive axes contributed to geometric distance;
- a post-selection plateau neighbor could become a nominee without owning an unopened neighborhood;
- each 64-point basin mixed simultaneous changes across as many as eight axes, so its DD quantile measured a bundle jump rather than a local formula perturbation;
- all eight medoids came from the paired preliminary order, leaving no guaranteed contract-specific basin coverage.

Before the corrected rerun, the following replacement was frozen:

- eight unique broad medoids when available: four paired-transfer, two Live-control ceiling and two fixed-replacement ceiling roles;
- exactly 64 one-axis ordered/numeric perturbations per medoid, using only the already-declared normalized offsets; categorical regimes remain unchanged;
- the medoid and its 64 owned neighbors are the only local plateau population;
- only an original broad medoid can be nominated; a neighbor cannot be promoted without a new unopened campaign;
- the same predeclared economic gates remain unchanged: E1-E3 actual and stressed positivity, sample/breadth/concentration limits, the 20.5% anchor-proportional DD boundary, positive local stressed-net tenth percentile and local DD ninetieth percentile at or below 20.5%.

No E4, June 2026 or July 2026 number from invalid attempt 01 may select or replace a corrected nominee.

## Invalid neighborhood attempt 02

The first one-axis correction is preserved under `optimization/artifacts/raw/dd20-dual-portfolio-internal-formula-lattice-proxy-v1/output-invalid-neighborhood-attempt-02/` and also has no research-failure status. The exact baseline's one-axis variants were already present in the broad atlas. The implementation correctly refused to add duplicate rows, but incorrectly failed to attach those existing rows to the baseline medoid. The baseline was consequently judged from a one-point “neighborhood” and became a false robust nominee.

The corrected ownership map now reuses a matching broad or previously generated formula point as an owned neighbor. A medoid must own exactly 64 distinct non-self neighbors before it can pass the robust gate. These changes do not alter any formula level, economic gate, selection interval, ranking field or later-data boundary.

## Invalid reporting attempt 03

The corrected 64-neighbor economics are valid, but the first result serialization conflated a contract-specific economic ceiling with a robust nominee. It therefore wrote the fixed-replacement ceiling as `null` when that contract had no robust point. This output is preserved under `optimization/artifacts/raw/dd20-dual-portfolio-internal-formula-lattice-proxy-v1/output-invalid-reporting-attempt-03/`; only its reporting/freeze completeness is invalid.

The final implementation records the best E1-E3 expanded medoid satisfying the contract's core and point-DD gates as a descriptive ceiling even when its local plateau fails. `robust_eligible=false` remains explicit, later data cannot promote or rescue that ceiling, and only a robust paired nominee can receive the one MT5 priority. This correction does not change any economic number, rank order or gate.
