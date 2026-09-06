# Broker clock authority audit — closed

The closed adapters do not all establish the intended session economics. This audit used their frozen source and only the `time` column from existing 2024–2025 inputs. No price or trade outcome was materialized, no closed adapter was executed, and no 2026 confirmation, model, runtime or Live change opened.

| Family | Observed implementation | Authority after audit |
| --- | --- | --- |
| 006 opening auction | 965 original complete events reproduce. Nominal broker time puts 334 events two hours early and 631 three hours early. | Adverse output describes the shifted implementation; the declared opening sessions were not tested. |
| 007 AUDCHF transfer | True-UTC scheduled integers directly index broker-wall integers. | Relative cross-market causality may remain, but the declared New York slots were not tested. |
| 008 leveraged ETF close | Helsinki localization differs from the broker nominal convention on 40 development weekdays. | Intended-session economic authority is suspended. Rolling references can propagate the effect beyond those dates. |
| 009 H4 Donchian | Nominal UTC labels change on 1,666 bars. Raw indices, cross-market order, dates, year-boundary membership and raw-server swap timing are unchanged. | Correct labels; retain the adverse development economic conclusion for this specific issue. |
| 010 London fix | Original 514 complete event dates reproduce; 38 are nominally one hour early. | The intended-fix hypothesis was not validly adjudicated; immutable mixed-time outputs remain descriptive. |

The [FP Markets FAQ](https://www.fpmarkets.com/en-au/education/faq/) ties its two seasonal UTC offsets to New York-close daily candles. The historical [29 March 2021 PDS, section 5.4](https://www.fpmarkets.com/wp-content/uploads/2021/03/FP-Markets-Product-Disclosure-Statement-Metatrader-4-29.03.2021.pdf) equates New York-local 17:00 and server midnight. From those sources, the nominal inverse is broker wall time minus seven hours, localized in America/New_York, then converted to UTC. This is an inference from the broker contract, not a fixed UTC offset or a certificate for every historical row.

Raw QQQ/TQQQ first bars are 16:30 server on 494 of 501 observed development dates. Their five 2025-03-10..14 sessions instead run 17:30..23:59 with 390 minutes each. Two other dates start late with fewer rows. Compared with the [Nasdaq regular-session hours](https://www.nasdaq.com/nasdaq-system-hours-of-operation), this is a separate source-session exception. Timestamp-only evidence does not establish whether it is historical labeling, broker quoting hours or another source issue. No manual shift or economic fit is justified. Exact external-session work must resolve its relevant source authority before binding economics.

This audit does not show that any corrected strategy would profit. It does not replace negative numbers, reopen an old family or affect V7R's exact broker-native verification. The durable correction is [the lineage addendum](../../../lineage/CHALLENGE_BROKER_CLOCK_AUTHORITY_CORRECTION_V1.json); all original sources and signed artifacts remain unchanged. Recompare every active macro program before the next declared unit.
