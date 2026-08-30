# Engineering corrections

## Direct GHCNh source completeness

The first outcome-free acquisition targeted NOAA NCEI GHCNh yearly PSV files.
The parser initially looked at `sky_cover_layer_*`, but the LaGuardia routine
METAR representation uses `sky_cover_summation_*`; this was corrected before
any family input was frozen and before any market outcome was loaded.

The corrected direct GHCNh surface then showed a separate source-environment
gap: its 2026 LaGuardia `FM15` sequence ended at `2026-04-13`, leaving P5 June-
July with zero complete four-hour mornings. The provisional raw family artifact
was removed. This produced no economic judgment because acquisition copied the
M15 file byte-for-byte but never parsed its price or spread columns.

The whole weather history, not only the missing tail, was reacquired from the
uniform current NOAA LCDv2 station/year series. LCDv2 derives its hourly
observations from GHCNh and exposes the same routine `FM-15` METAR sky
conditions through the latest period. Its documented local-standard `DATE`
clock is converted through fixed UTC-05:00 to actual America/New_York time,
preventing the summer 08:51 observation from becoming a post-open input.

The corrected source has `43` latest eligible sessions, `15 LONG / 28 SHORT`,
and a minimum `36`-minute lead to the 09:30 entry. This closes the environment
correction without changing the paper rule, market horizon, period, cost model
or any economic gate.
