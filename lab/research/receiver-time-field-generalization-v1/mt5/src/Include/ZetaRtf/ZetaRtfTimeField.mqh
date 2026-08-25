#ifndef ZETA_RTF_TIME_FIELD_MQH
#define ZETA_RTF_TIME_FIELD_MQH

// Frozen receiver-time-field-generalization V1 mechanism.

const int RTF_RETURN_CONTRACTION_KIND = 1;
const int RTF_RECEIVER_TIME_FIELD_KIND = 2;
#define RTF_AFTERIMAGE_CAPACITY 64
const int RTF_HALF_LIFE_MINUTES = 2880;
const int RTF_MAXIMUM_AGE_MINUTES = 8 * RTF_HALF_LIFE_MINUTES;
const int RTF_CROSS_LOOKBACK_MINUTES = 2880;

struct RtfExpiredPassiveAfterimage
  {
   datetime observed_server;
   int direction;
  };

RtfExpiredPassiveAfterimage rtf_afterimages[RTF_AFTERIMAGE_CAPACITY];
int rtf_afterimage_count = 0;
long rtf_observed_expirations = 0;
long rtf_afterimage_capacity_faults = 0;

ulong rtf_return_lifecycle_identifier = 0;
bool rtf_return_lifecycle_qualified = false;
bool rtf_return_release_recorded = false;
long rtf_return_qualified_signals = 0;
long rtf_return_qualified_lifecycles = 0;
long rtf_return_three_bar_releases = 0;

ulong rtf_cross_lifecycle_identifier = 0;
bool rtf_cross_lifecycle_qualified = false;
bool rtf_cross_maturity_decided = false;
bool rtf_cross_extended = false;
bool rtf_cross_close_recorded = false;
long rtf_cross_qualified_signals = 0;
long rtf_cross_qualified_lifecycles = 0;
long rtf_cross_maturity_decisions = 0;
long rtf_cross_extensions = 0;
long rtf_cross_native_maturities = 0;
long rtf_cross_extended_closes = 0;
long rtf_cross_native_closes = 0;


void RtfResetState()
  {
   for(int index = 0; index < RTF_AFTERIMAGE_CAPACITY; ++index)
     {
      rtf_afterimages[index].observed_server = 0;
      rtf_afterimages[index].direction = 0;
     }
   rtf_afterimage_count = 0;
   rtf_observed_expirations = 0;
   rtf_afterimage_capacity_faults = 0;

   rtf_return_lifecycle_identifier = 0;
   rtf_return_lifecycle_qualified = false;
   rtf_return_release_recorded = false;
   rtf_return_qualified_signals = 0;
   rtf_return_qualified_lifecycles = 0;
   rtf_return_three_bar_releases = 0;

   rtf_cross_lifecycle_identifier = 0;
   rtf_cross_lifecycle_qualified = false;
   rtf_cross_maturity_decided = false;
   rtf_cross_extended = false;
   rtf_cross_close_recorded = false;
   rtf_cross_qualified_signals = 0;
   rtf_cross_qualified_lifecycles = 0;
   rtf_cross_maturity_decisions = 0;
   rtf_cross_extensions = 0;
   rtf_cross_native_maturities = 0;
   rtf_cross_extended_closes = 0;
   rtf_cross_native_closes = 0;
  }


void RtfPruneAfterimages(const datetime now)
  {
   int write_index = 0;
   const long maximum_age_seconds =
      (long)RTF_MAXIMUM_AGE_MINUTES * 60;
   for(int read_index = 0;
       read_index < rtf_afterimage_count;
       ++read_index)
     {
      const datetime observed =
         rtf_afterimages[read_index].observed_server;
      const long age_seconds = (long)now - (long)observed;
      if(observed <= 0 || age_seconds < 0 ||
         age_seconds > maximum_age_seconds)
         continue;
      if(write_index != read_index)
         rtf_afterimages[write_index] = rtf_afterimages[read_index];
      ++write_index;
     }
   for(int index = write_index; index < rtf_afterimage_count; ++index)
     {
      rtf_afterimages[index].observed_server = 0;
      rtf_afterimages[index].direction = 0;
     }
   rtf_afterimage_count = write_index;
  }


bool RtfObserveExpiredPassive(const int direction,
                              const datetime observed_server)
  {
   if(RTF_PATH_KIND == 0)
      return(true);
   if(MathAbs(direction) != 1 || observed_server <= 0)
     {
      ++rtf_afterimage_capacity_faults;
      EngageSafetyStop("invalid Passive afterimage observation");
      RecordEvent(US100_PASSIVE_LIMIT,
                  "RTF_AFTERIMAGE_FAULT",
                  (double)direction,
                  (double)observed_server,
                  "invalid direction or server time");
      return(false);
     }
   RtfPruneAfterimages(observed_server);
   if(rtf_afterimage_count >= RTF_AFTERIMAGE_CAPACITY)
     {
      ++rtf_afterimage_capacity_faults;
      EngageSafetyStop("receiver-time-field afterimage capacity exceeded");
      RecordEvent(US100_PASSIVE_LIMIT,
                  "RTF_AFTERIMAGE_FAULT",
                  (double)rtf_afterimage_count,
                  (double)RTF_AFTERIMAGE_CAPACITY,
                  "live emitter capacity exceeded");
      return(false);
     }
   rtf_afterimages[rtf_afterimage_count].observed_server = observed_server;
   rtf_afterimages[rtf_afterimage_count].direction = direction;
   ++rtf_afterimage_count;
   ++rtf_observed_expirations;
   RecordEvent(US100_PASSIVE_LIMIT,
               "RTF_PASSIVE_EXPIRE",
               (double)direction,
               (double)rtf_afterimage_count,
               StringFormat("observed=%s",
                            TimeToString(observed_server,
                                         TIME_DATE | TIME_SECONDS)));
   return(true);
  }


bool RtfReturnQualifies(const int receiver_direction,
                        const datetime decision_server,
                        double &energy,
                        double &dominance)
  {
   energy = 0.0;
   dominance = 0.0;
   if(RTF_PATH_KIND < RTF_RETURN_CONTRACTION_KIND ||
      MathAbs(receiver_direction) != 1 || decision_server <= 0)
      return(false);
   RtfPruneAfterimages(decision_server);
   double signed_energy = 0.0;
   for(int index = 0; index < rtf_afterimage_count; ++index)
     {
      const datetime observed = rtf_afterimages[index].observed_server;
      if(observed <= 0 || observed >= decision_server)
         continue;
      const double age_minutes =
         (double)((long)decision_server - (long)observed) / 60.0;
      if(age_minutes > (double)RTF_MAXIMUM_AGE_MINUTES)
         continue;
      const double weight =
         MathPow(0.5, age_minutes / (double)RTF_HALF_LIFE_MINUTES);
      const int relation =
         (rtf_afterimages[index].direction == receiver_direction ? 1 : -1);
      energy += weight;
      signed_energy += weight * (double)relation;
     }
   if(energy > 0.0)
      dominance = signed_energy / energy;
   return(energy >= 0.25 && dominance >= 0.25);
  }


bool RtfCrossQualifies(const int receiver_direction,
                       const datetime decision_server,
                       int &matching_emitters)
  {
   matching_emitters = 0;
   if(RTF_PATH_KIND < RTF_RECEIVER_TIME_FIELD_KIND ||
      MathAbs(receiver_direction) != 1 || decision_server <= 0)
      return(false);
   RtfPruneAfterimages(decision_server);
   const long lookback_seconds =
      (long)RTF_CROSS_LOOKBACK_MINUTES * 60;
   for(int index = 0; index < rtf_afterimage_count; ++index)
     {
      const datetime observed = rtf_afterimages[index].observed_server;
      if(observed <= 0 || observed >= decision_server)
         continue;
      const long age_seconds =
         (long)decision_server - (long)observed;
      if(age_seconds <= lookback_seconds &&
         rtf_afterimages[index].direction == receiver_direction)
         ++matching_emitters;
     }
   return(matching_emitters >= 1);
  }


void RtfNoteReturnSignal(const bool qualified,
                         const double energy,
                         const double dominance)
  {
   if(!qualified)
      return;
   ++rtf_return_qualified_signals;
   RecordEvent(US30_RETURN_REV_LONG,
               "RTF_RETURN_QUALIFY",
               energy,
               dominance,
               StringFormat("signal=%I64d", rtf_return_qualified_signals));
  }


void RtfAdoptReturnLifecycle(const bool qualified,
                             const double energy,
                             const double dominance)
  {
   const ulong identifier =
      component_states[US30_RETURN_REV_LONG].position_identifier;
   if(identifier == 0)
     {
      rtf_return_lifecycle_identifier = 0;
      rtf_return_lifecycle_qualified = false;
      rtf_return_release_recorded = false;
      return;
     }
   rtf_return_lifecycle_identifier = identifier;
   rtf_return_lifecycle_qualified = qualified;
   rtf_return_release_recorded = false;
   if(!qualified)
      return;
   ++rtf_return_qualified_lifecycles;
   RecordEvent(US30_RETURN_REV_LONG,
               "RTF_RETURN_ARM",
               energy,
               dominance,
               StringFormat("identifier=%I64u", identifier));
  }


int RtfReturnHoldBars(const ulong identifier,
                      const int native_hold_bars)
  {
   if(RTF_PATH_KIND >= RTF_RETURN_CONTRACTION_KIND &&
      identifier > 0 &&
      identifier == rtf_return_lifecycle_identifier &&
      rtf_return_lifecycle_qualified)
      return(3);
   return(native_hold_bars);
  }


void RtfRecordReturnRelease(const ulong identifier)
  {
   if(identifier == 0 ||
      identifier != rtf_return_lifecycle_identifier ||
      !rtf_return_lifecycle_qualified || rtf_return_release_recorded)
      return;
   rtf_return_release_recorded = true;
   ++rtf_return_three_bar_releases;
   RecordEvent(US30_RETURN_REV_LONG,
               "RTF_RETURN_RELEASE",
               3.0,
               (double)rtf_return_three_bar_releases,
               StringFormat("identifier=%I64u", identifier));
  }


void RtfNoteCrossSignal(const bool qualified,
                        const int matching_emitters)
  {
   if(!qualified)
      return;
   ++rtf_cross_qualified_signals;
   RecordEvent(US100_CROSS,
               "RTF_CROSS_QUALIFY",
               (double)matching_emitters,
               (double)rtf_cross_qualified_signals,
               "same-direction expired Passive within 2880 minutes");
  }


void RtfAdoptCrossLifecycle(const bool qualified,
                            const int matching_emitters)
  {
   const ulong identifier =
      component_states[US100_CROSS].position_identifier;
   if(identifier == 0)
     {
      rtf_cross_lifecycle_identifier = 0;
      rtf_cross_lifecycle_qualified = false;
      rtf_cross_maturity_decided = false;
      rtf_cross_extended = false;
      rtf_cross_close_recorded = false;
      return;
     }
   rtf_cross_lifecycle_identifier = identifier;
   rtf_cross_lifecycle_qualified = qualified;
   rtf_cross_maturity_decided = false;
   rtf_cross_extended = false;
   rtf_cross_close_recorded = false;
   if(!qualified)
      return;
   ++rtf_cross_qualified_lifecycles;
   RecordEvent(US100_CROSS,
               "RTF_CROSS_ARM",
               (double)matching_emitters,
               (double)rtf_cross_qualified_lifecycles,
               StringFormat("identifier=%I64u", identifier));
  }


bool RtfCrossEffectiveHoldBars(const ulong ticket,
                               const ulong identifier,
                               const int held_bars,
                               const int native_hold_bars,
                               int &effective_hold_bars)
  {
   effective_hold_bars = native_hold_bars;
   if(RTF_PATH_KIND < RTF_RECEIVER_TIME_FIELD_KIND ||
      identifier == 0 || identifier != rtf_cross_lifecycle_identifier ||
      !rtf_cross_lifecycle_qualified)
      return(true);
   if(held_bars < native_hold_bars)
      return(true);
   if(!rtf_cross_maturity_decided)
     {
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         return(false);
      const double floating_profit =
         PositionGetDouble(POSITION_PROFIT);
      if(!MathIsValidNumber(floating_profit))
         return(false);
      rtf_cross_maturity_decided = true;
      rtf_cross_extended = (floating_profit > 0.0);
      ++rtf_cross_maturity_decisions;
      if(rtf_cross_extended)
         ++rtf_cross_extensions;
      else
         ++rtf_cross_native_maturities;
      RecordEvent(US100_CROSS,
                  "RTF_CROSS_MATURITY",
                  floating_profit,
                  (rtf_cross_extended ? 6.0 : 4.0),
                  StringFormat("identifier=%I64u extended=%d",
                               identifier,
                               (int)rtf_cross_extended));
     }
   effective_hold_bars = (rtf_cross_extended ? 6 : native_hold_bars);
   return(true);
  }


void RtfRecordCrossClose(const ulong identifier)
  {
   if(identifier == 0 || identifier != rtf_cross_lifecycle_identifier ||
      !rtf_cross_lifecycle_qualified || !rtf_cross_maturity_decided ||
      rtf_cross_close_recorded)
      return;
   rtf_cross_close_recorded = true;
   if(rtf_cross_extended)
      ++rtf_cross_extended_closes;
   else
      ++rtf_cross_native_closes;
   RecordEvent(US100_CROSS,
               "RTF_CROSS_CLOSE",
               (rtf_cross_extended ? 6.0 : 4.0),
               (double)(rtf_cross_extended
                        ? rtf_cross_extended_closes
                        : rtf_cross_native_closes),
               StringFormat("identifier=%I64u extended=%d",
                            identifier,
                            (int)rtf_cross_extended));
  }


void RtfPrintFinalTelemetry()
  {
   PrintFormat("%s receiver_time_field path=%s kind=%d afterimages=%d "
               "observed_expirations=%I64d capacity_faults=%I64d "
               "return_qualified_signals=%I64d return_qualified_lifecycles=%I64d "
               "return_three_bar_releases=%I64d cross_qualified_signals=%I64d "
               "cross_qualified_lifecycles=%I64d cross_maturity_decisions=%I64d "
               "cross_extensions=%I64d cross_native_maturities=%I64d "
               "cross_extended_closes=%I64d cross_native_closes=%I64d",
               EXECUTION_VERSION,
               RTF_PATH_LABEL,
               RTF_PATH_KIND,
               rtf_afterimage_count,
               rtf_observed_expirations,
               rtf_afterimage_capacity_faults,
               rtf_return_qualified_signals,
               rtf_return_qualified_lifecycles,
               rtf_return_three_bar_releases,
               rtf_cross_qualified_signals,
               rtf_cross_qualified_lifecycles,
               rtf_cross_maturity_decisions,
               rtf_cross_extensions,
               rtf_cross_native_maturities,
               rtf_cross_extended_closes,
               rtf_cross_native_closes);
  }

#endif
