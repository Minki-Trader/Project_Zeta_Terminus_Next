# Independent Live-Dev Optimization

This root owns continuous economic optimization of the exact active Live-Dev behavior. It is physically and logically separate from both `live-dev/` and `lab/`.

## Fixed parent

- Source release: `NEXT-E01-V7-RLO1-b32e7e176f2e`
- Source root at derivation: `live-dev/package/active/`
- Local frozen copy: `baseline/NEXT-E01-V7-RLO1-b32e7e176f2e/`
- Source commit at derivation: `f4e1effb647d5ef81921eddc64fcd6bef2289f57`
- Frozen manifest: `7A968666241AD90629F14ADF48E983AB04A4DD88053F1413EBB209FB51976698`
- Status: exact 20-file baseline frozen; first 15-point risk-cap campaign completed with valid economics

The local baseline is never compiled or executed with Live identity. It is copied once so later campaign work no longer depends on a Live or Lab path.

## Root roles

- `baseline/`: byte-pinned, read-only copy of the active Live package used only for campaign derivation.
- `campaigns/<family>/`: one self-contained active or frozen optimization campaign, including source, configuration and small durable evidence.
- `runtime/<family>-portable/`: Git-ignored dedicated physical MT5 Portable; never the Master, Live or Lab terminal.
- `artifacts/raw/<family>/`: Git-ignored large optimization reports, logs and caches that durable evidence may pin and preserve.
- `artifacts/temp/`: replaceable staging only.

## Operating rules

Only one optimization judgment stream is active. A complete valid economic comparison may judge improvement; missing history, runtime/configuration failure, design defect or engineering defect is corrected and rerun without an arbitrary retry cap and without an economic verdict. The latest two completed months remain isolated from search by default.

Optimization candidates are not Live EA edits and may be economically radical: a campaign may remove or replace strategies, reconstruct portfolio membership or coordination, and run destructive variants. Every such comparison retains an exact Live-derived control, owns separate source/identity/runtime/output, remains distinct from Lab research, and has no Live authority.

One completed campaign does not pause the Goal. After each economic stage, freeze its evidence, choose the next economically distinct optimization stage and continue until the user pauses. A temporary Lab Unit is optional when a new clue needs research or engineering, but it pauses this stream and closes before optimization resumes.

No optimization result changes Live automatically. Any later promotion requires explicit user authorization and a separately named Lab engineering handoff under `docs/OPERATING_DIRECTION.md`.

## Active campaign

`campaigns/portfolio-risk-cap-envelope-v1/` is closed `NO_REPLACEMENT_RETAIN_PARENT_0.04_0.12`. Its 15 selection and 15 isolated-forward passes are preserved without rerun. The same result retained `0.04 / 0.18` as a non-dominated maximum-profit frontier point: selection actual/stressed net `$1,166.89 / $1,085.408`, MT5 equity drawdown `11.3757%`.

`campaigns/dd20-profit-frontier-proxy-v1/` is closed `VALID_PROXY_COMPLETE_NO_MT5_SHORTLIST`. Near-uniform gross leverage almost doubled selection profit, but every frozen role amplified the isolated later loss and exceeded the proxy DD cap; none reached MT5.

The user's prospective objective remains maximum actual and doubled-cost-stressed profit inside a hard `20%` MT5 equity-drawdown budget. `campaigns/dd20-capital-composition-proxy-v1/` is closed `VALID_PROXY_COMPLETE_ONE_MT5_SHORTLIST`: of `29,016` fixed-budget compositions, weights `3.0 / 3.0 / 1.0 / 2.5 / 1.0 / 0.0` were the sole frozen role to turn the isolated later actual/stressed net positive while staying inside the proxy DD cap.

`campaigns/dd20-capital-composition-mt5-v1/` is closed `EXPLOSIVE_PROFIT_CONFIRMED_BUT_SELECTION_MT5_DD_EXCEEDS_20_PERCENT`. Its exact `3 / 3 / 1 / 2.5 / 1 / 0` exposure earned selection actual/stressed `+$2,822.33 / +$2,648.883` and forward `+$36.67 / +$34.6175`, but selection maximum relative MT5 equity DD was `27.072835%`; the valid path is rejected under the user's hard `20%` prospective budget and will not rerun.

`campaigns/dd20-executable-volume-lattice-proxy-v1/` is closed `VALID_PROXY_COMPLETE_SELECTION_WINNER_FAILS_LATER_NO_MT5_SHORTLIST`. Its maximum-profit selection role `3 / 1 / 2.5 / 2 / 1 / 0.5` reached actual/stressed `+$6,976.9515 / +$6,588.5518` at `19.278821%` proxy DD, but the untouched later segment lost `-$9.28 / -$12.808` at `28.019366%` DD. US100-cross supplied `-$37.278` of later stressed net, so the exact winner and its quantized tie close without MT5 or retuning. The next serial stage must use an independent chronological/component-stability proxy before any MT5 shortlist.

`campaigns/dd20-chronological-stability-proxy-v1/` is closed `VALID_PROXY_COMPLETE_JUNE_STABLE_WINNER_FAILS_JULY_NO_MT5_SHORTLIST`. Its June-stable maximum-profit `3 / 1 / 2 / 1.5 / 1 / 0` role earned selection actual/stressed `+$6,532.4496 / +$6,186.2932` at `19.977049%` DD and June `+$8.95 / +$7.284`, but untouched July lost `-$10.25 / -$11.376`; no MT5 ran. The next distinct proxy may require paired June-and-July stability for all candidates before one possible MT5 shortlist.

`campaigns/dd20-paired-month-stability-proxy-v1/` is closed `VALID_PROXY_COMPLETE_ONE_MT5_SHORTLIST`. Of `112,752` compositions, `2,824` passed long selection plus independent June/July gates. Maximum-profit weights `2 / 1.5 / 2 / 2.5 / 1.5 / 0` produced selection actual/stressed `+$5,551.5636 / +$5,237.1427` at `19.423399%` proxy DD, June `+$29.21 / +$27.474`, and July `+$4.10 / +$3.00`. Exactly this one hypothesis may advance to a new dedicated MT5 family.

`campaigns/dd20-paired-month-stability-mt5-v1/` is closed `VALID_MT5_COMPLETE_SELECTION_DD_MISSES_CAP_BY_0_2569_PERCENTAGE_POINTS`. Its exact `2 / 1.5 / 2 / 2.5 / 1.5 / 0` exposure earned selection actual/stressed `+$5,786.63 / +$5,477.524` and full June/July forward `+$32.74 / +$30.626`. Forward DD passed at `18.675302%`, but selection maximum relative MT5 equity DD was `20.256888%`, just `0.256888` percentage points above the hard budget. The highest-profit observed MT5 point is therefore retained as an upper anchor but not a qualifying replacement; it will not rerun.

`campaigns/dd20-mt5-calibrated-exposure-margin-proxy-v1/` is closed `VALID_PROXY_COMPLETE_ONE_MT5_SHORTLIST`. After the outcome-free paired-DD correction, `16,807` candidates completed in `4.13` seconds: `127` passed selection margin, `52` passed full paired forward and June, and `5` passed July. The sole maximum-profit role `1.8 / 1.3 / 1.4 / 2.6 / 1.5 / 0` produced selection actual/stressed `+$4,425.6202 / +$4,176.4760` at calibrated/budgeted DD `19.288409% / 19.788409%`, plus full paired-forward `+$26.42 / +$23.987` at budgeted DD `15.843967%`. Exactly this one hypothesis may advance to a new dedicated MT5 family.

`campaigns/dd20-exposure-margin-mt5-v1/` is closed `VALID_MT5_COMPLETE_SELECTION_DD_MISSES_CAP_AND_CONTINUOUS_JULY_NEGATIVE`. Its sole `1.8 / 1.3 / 1.4 / 2.6 / 1.5 / 0` exposure earned selection actual/stressed `+$4,169.94 / +$3,942.2615`, but native maximum relative equity DD was `20.488349%`, missing the hard budget by `0.488349` percentage points. Full June/July forward passed at `+$27.87 / +$25.9725` and `15.487346%` DD, while the continuous July stressed slice was `-$2.2375`. The exact candidate is closed without rerun; its valid lifecycle/native-cache evidence becomes an anchor for a distinct fast proxy.

`campaigns/dd20-native-gap-july-robustness-proxy-v1/` is closed `VALID_PROXY_COMPLETE_ONE_MT5_SHORTLIST`. Of `49,049` compositions, `1,509` passed selection/full-pair/June, `815` passed raw July and `647` passed the worst observed continuous-July shortfalls plus the additional `$1` reserve. The sole maximum-profit role `1.6 / 0.8 / 0.4 / 3.2 / 1.2 / 0` produced selection actual/stressed `+$1,763.4819 / +$1,693.3221` at raw/calibrated/budgeted DD `17.428221% / 19.210908% / 19.960908%`, full-pair stressed `+$27.236`, and conservative July stressed `+$0.9025`. It is exactly one MT5 hypothesis; no anchor or original combination reran.

`campaigns/dd20-native-gap-july-robustness-mt5-v1/` is closed `VALID_MT5_COMPLETE_ALL_ECONOMIC_GATES_PASS`. Its sole `1.6 / 0.8 / 0.4 / 3.2 / 1.2 / 0` candidate earned selection actual/stressed `+$1,691.54 / +$1,626.26`, beating the preserved comparator by `44.9614% / 49.8294%`; all four selection epochs were positive and native maximum relative equity DD passed at `19.550372%`. The independent full June/July forward earned `+$23.01 / +$21.256` at `12.436759%` DD, with June `+$19.79 / +$18.976` and July `+$3.22 / +$2.280`. This is the first fully qualified DD20 optimization success anchor, not an automatic Live promotion. Continue proxy-first toward more stressed profit through component redistribution; do not rerun this path, any prior candidate or the original 15 combinations.

`campaigns/dd20-qualified-profit-redistribution-proxy-v1/` is closed `VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE`. One `87.9067`-second process evaluated all `184,041` redistributions plus four external anchor rows; every copied-input and proxy/native anchor check passed. Under the global worst selection-profit correction `+$659.7999 / +$615.1109` plus `$50`, the five-anchor DD correction and four positive epochs, selection eligibility was `0`, so all conditional paired/month counts and the MT5 shortlist are also `0`. This valid empty frontier retains the first qualified MT5 anchor and closes without MT5 or any rerun. The next stage must use an economically distinct proxy mechanism rather than repeat this grid.

`campaigns/dd20-local-error-profit-frontier-proxy-v1/` is closed `VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE`. One `97.8265`-second process evaluated all `204,490` new half-step rows plus five external anchors; all copied-input, proxy/native and local-envelope checks passed. Candidate-local selection DD charges ranged `1.148018..5.185475` points and actual/stressed profit charges ranged `$94.2485..$1,968.0084 / $88.6346..$1,900.7276`, but no row simultaneously cleared the corrected qualified-profit floor, native-DD budget and four positive epochs. No MT5 shortlist exists. After two distinct static-weight frontiers, retain the qualified anchor and change the next proxy mechanism to capital-addition-ladder growth rather than another adjacent weight grid.

`campaigns/dd20-capital-addition-ladder-proxy-v1/` is closed `VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE`. One `1.0581`-second process evaluated all `50` new constant addition steps plus the closed `$150` anchor, and every copied lifecycle/native/proxy fact passed. All candidates were positive; `18` passed the conservative qualified-profit floor, `26` passed budgeted DD and `30` passed every epoch, but the full selection intersection was empty. The `$50` explosive endpoint reached proxy stressed `+$44,789.1023` and conservative stressed `+$23,124.1501` at `48.924974%` budgeted DD; the highest-profit DD-eligible `$155` endpoint reached only conservative stressed `+$1,540.0281` at `19.460019%`, below the qualified `+$1,626.26`. The qualified MT5 anchor remains, and the next distinct proxy should cap the day multiplier instead of repeating the constant ladder.

`campaigns/dd20-capped-profit-accelerator-proxy-v1/` is closed `VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE`. One `1.0330`-second process evaluated all `168` new binding `step × cap` paths plus the closed calibration row. Every input, native/proxy anchor and candidate-construction gate passed. All `168` candidates were positive and conservatively exceeded the qualified profit floor, but none passed budgeted DD or every selection epoch. The maximum-profit step `$50`, cap `60` path retained conservative stressed `+$6,988.2869`, yet budgeted DD stayed `48.924974%`. Capping terminal exposure alone therefore cannot repair the too-early low-step ramp; the next distinct proxy must delay acceleration until after a causal stressed-profit buffer.

`campaigns/dd20-deferred-profit-accelerator-proxy-v1/` is declared with economics unopened. Every candidate keeps the qualified `$150` slope until stressed closed profit reaches `$300..$1,350` by `$150`, then changes to a `$25/$50/$75/$100` post-activation step under cap `14/16/18/20/24/30/40/60`. The full `256`-path Cartesian product is causal, every threshold is a baseline-step multiple and every cap preserves baseline headroom at activation. The same conservative profit/DD, four-epoch, paired-forward and June/July gates remain; at most one maximum-profit hypothesis may advance to MT5.
