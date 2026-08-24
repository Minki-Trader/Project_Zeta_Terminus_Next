#ifndef ZETA_NEXT_FRONTIER_RECEIVER_TIME_FIELD_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_RECEIVER_TIME_FIELD_ADAPTER_MQH

#define RECEIVER_TIME_FIELD_CAPACITY 64
const int RECEIVER_TIME_FIELD_HALF_LIFE_SECONDS = 2880 * 60;
const int RECEIVER_TIME_FIELD_WINDOW_SECONDS = 2880 * 60;
const int RECEIVER_TIME_FIELD_MAX_AGE_SECONDS =
   8 * RECEIVER_TIME_FIELD_HALF_LIFE_SECONDS;
const double RECEIVER_TIME_FIELD_MINIMUM_ENERGY = 0.25;
const double RECEIVER_TIME_FIELD_MINIMUM_DOMINANCE = 0.25;

datetime time_field_expired_server[RECEIVER_TIME_FIELD_CAPACITY];
int time_field_expired_direction[RECEIVER_TIME_FIELD_CAPACITY];
int time_field_expired_count = 0;
bool time_field_qualified[COMPONENT_COUNT];
datetime time_field_signal_server[COMPONENT_COUNT];
long time_field_signal_count[COMPONENT_COUNT];
long time_field_qualified_count[COMPONENT_COUNT];
ulong time_field_cross_gate_identifier = 0;
bool time_field_cross_gate_decided = false;
bool time_field_cross_gate_extended = false;
long time_field_return_releases = 0;
long time_field_cross_extended_lifecycles = 0;
long time_field_cross_native_lifecycles = 0;


string ReceiverTimeFieldModeName()
  {
   if(InpReceiverTimeFieldMode == TIME_FIELD_CROSS_FIXED_6)
      return("CROSS_FIXED_6");
   if(InpReceiverTimeFieldMode == TIME_FIELD_CROSS_FIXED_8)
      return("CROSS_FIXED_8");
   return("CROSS_PROFIT_GATE_6");
  }


bool ReceiverTimeFieldInitialize()
  {
   if(InpReceiverTimeFieldMode != TIME_FIELD_CROSS_FIXED_6 &&
      InpReceiverTimeFieldMode != TIME_FIELD_CROSS_FIXED_8 &&
      InpReceiverTimeFieldMode != TIME_FIELD_CROSS_PROFIT_GATE_6)
      return(false);
   FolderCreate("ZetaTerminusNext\\frontier");
   return(true);
  }


void ReceiverTimeFieldReset()
  {
   ArrayInitialize(time_field_expired_server, 0);
   ArrayInitialize(time_field_expired_direction, 0);
   ArrayInitialize(time_field_qualified, false);
   ArrayInitialize(time_field_signal_server, 0);
   ArrayInitialize(time_field_signal_count, 0);
   ArrayInitialize(time_field_qualified_count, 0);
   time_field_expired_count = 0;
   time_field_cross_gate_identifier = 0;
   time_field_cross_gate_decided = false;
   time_field_cross_gate_extended = false;
   time_field_return_releases = 0;
   time_field_cross_extended_lifecycles = 0;
   time_field_cross_native_lifecycles = 0;
  }


void ReceiverTimeFieldObservePassiveExpiration(const int direction,
                                               const datetime expiration)
  {
   if(direction == 0)
      return;
   const datetime now = TimeCurrent();
   if(time_field_expired_count < RECEIVER_TIME_FIELD_CAPACITY)
     {
      time_field_expired_server[time_field_expired_count] = now;
      time_field_expired_direction[time_field_expired_count] = direction;
      ++time_field_expired_count;
     }
   else
     {
      for(int index = 1; index < RECEIVER_TIME_FIELD_CAPACITY; ++index)
        {
         time_field_expired_server[index - 1] = time_field_expired_server[index];
         time_field_expired_direction[index - 1] =
            time_field_expired_direction[index];
        }
      time_field_expired_server[RECEIVER_TIME_FIELD_CAPACITY - 1] = now;
      time_field_expired_direction[RECEIVER_TIME_FIELD_CAPACITY - 1] =
         direction;
     }
   PrintFormat("ZETA_FRONTIER_TIME_FIELD_EMITTER|server=%I64d|expiration=%I64d|direction=%d|count=%d",
               (long)now,
               (long)expiration,
               direction,
               time_field_expired_count);
  }


bool ReceiverTimeFieldReturnQualified(const int receiver_direction,
                                      double &energy,
                                      double &dominance)
  {
   energy = 0.0;
   double signed_energy = 0.0;
   const datetime now = TimeCurrent();
   for(int index = 0; index < time_field_expired_count; ++index)
     {
      const long age = (long)now - (long)time_field_expired_server[index];
      if(age < 0 || age > RECEIVER_TIME_FIELD_MAX_AGE_SECONDS)
         continue;
      const double weight =
         MathPow(0.5,
                 (double)age /
                 (double)RECEIVER_TIME_FIELD_HALF_LIFE_SECONDS);
      const int relation =
         (time_field_expired_direction[index] == receiver_direction ? 1 : -1);
      energy += weight;
      signed_energy += relation * weight;
     }
   dominance = (energy > 0.0 ? signed_energy / energy : 0.0);
   return(energy >= RECEIVER_TIME_FIELD_MINIMUM_ENERGY &&
          dominance >= RECEIVER_TIME_FIELD_MINIMUM_DOMINANCE);
  }


bool ReceiverTimeFieldCrossQualified(const int receiver_direction,
                                     long &youngest_same_age)
  {
   youngest_same_age = -1;
   const datetime now = TimeCurrent();
   for(int index = 0; index < time_field_expired_count; ++index)
     {
      const long age = (long)now - (long)time_field_expired_server[index];
      if(age < 0 || age > RECEIVER_TIME_FIELD_WINDOW_SECONDS ||
         time_field_expired_direction[index] != receiver_direction)
         continue;
      if(youngest_same_age < 0 || age < youngest_same_age)
         youngest_same_age = age;
     }
   return(youngest_same_age >= 0);
  }


void ReceiverTimeFieldObserveSignal(const int component,
                                    const double value,
                                    const bool passed,
                                    const int direction)
  {
   if(component != US30_RETURN_REV_LONG && component != US100_CROSS)
      return;
   time_field_qualified[component] = false;
   time_field_signal_server[component] = TimeCurrent();
   if(component == US100_CROSS)
     {
      time_field_cross_gate_identifier = 0;
      time_field_cross_gate_decided = false;
      time_field_cross_gate_extended = false;
     }
   if(!passed || direction == 0)
      return;
   ++time_field_signal_count[component];
   double energy = 0.0;
   double dominance = 0.0;
   long youngest_same_age = -1;
   if(component == US30_RETURN_REV_LONG)
      time_field_qualified[component] =
         ReceiverTimeFieldReturnQualified(direction, energy, dominance);
   else
      time_field_qualified[component] =
         ReceiverTimeFieldCrossQualified(direction, youngest_same_age);
   if(time_field_qualified[component])
      ++time_field_qualified_count[component];
   PrintFormat("ZETA_FRONTIER_TIME_FIELD_RECEIVER|server=%I64d|component=%d|mode=%s|direction=%d|signal=%.10f|energy=%.10f|dominance=%.10f|youngest_same_age=%I64d|qualified=%d",
               (long)time_field_signal_server[component],
               component,
               ReceiverTimeFieldModeName(),
               direction,
               value,
               energy,
               dominance,
               youngest_same_age,
               (int)time_field_qualified[component]);
  }


bool ReceiverTimeFieldCurrentLifecycle(const int component)
  {
   if(component < 0 || component >= COMPONENT_COUNT ||
      !time_field_qualified[component] ||
      time_field_signal_server[component] <= 0 ||
      component_states[component].entry_time_server <= 0)
      return(false);
   const long entry_lag =
      (long)component_states[component].entry_time_server -
      (long)time_field_signal_server[component];
   return(entry_lag >= 0 &&
          entry_lag <= InpMaxEntryDelayMinutes * 60);
  }


int ReceiverTimeFieldHoldBars(const int component,
                             const ulong ticket,
                             const datetime opened_at,
                             const int held_bars,
                             const int native_hold_bars)
  {
   if(component != US100_CROSS ||
      !ReceiverTimeFieldCurrentLifecycle(component))
      return(native_hold_bars);
   if(InpReceiverTimeFieldMode == TIME_FIELD_CROSS_FIXED_6)
      return(6);
   if(InpReceiverTimeFieldMode == TIME_FIELD_CROSS_FIXED_8)
      return(8);
   if(held_bars < native_hold_bars)
      return(native_hold_bars);
   const ulong identifier = component_states[component].position_identifier;
   if(identifier == 0)
      return(native_hold_bars);
   if(!time_field_cross_gate_decided ||
      time_field_cross_gate_identifier != identifier)
     {
      time_field_cross_gate_identifier = identifier;
      time_field_cross_gate_decided = true;
      time_field_cross_gate_extended = false;
      if(PositionSelectByTicket(ticket))
        {
         const double floating_net =
            PositionGetDouble(POSITION_PROFIT) +
            PositionGetDouble(POSITION_SWAP);
         time_field_cross_gate_extended = (floating_net > 0.0);
        }
      if(time_field_cross_gate_extended)
         ++time_field_cross_extended_lifecycles;
      else
         ++time_field_cross_native_lifecycles;
      PrintFormat("ZETA_FRONTIER_TIME_FIELD_GATE|server=%I64d|ticket=%I64u|identifier=%I64u|opened=%I64d|held_bars=%d|extended=%d",
                  (long)TimeCurrent(),
                  ticket,
                  identifier,
                  (long)opened_at,
                  held_bars,
                  (int)time_field_cross_gate_extended);
     }
   return(time_field_cross_gate_extended ? 6 : native_hold_bars);
  }


bool ReceiverTimeFieldShouldClose(const int component,
                                  const ulong ticket,
                                  const datetime opened_at,
                                  const int held_bars)
  {
   if(component != US30_RETURN_REV_LONG ||
      !ReceiverTimeFieldCurrentLifecycle(component) || held_bars < 3)
      return(false);
   ++time_field_return_releases;
   PrintFormat("ZETA_FRONTIER_TIME_FIELD_RETURN_RELEASE|server=%I64d|ticket=%I64u|opened=%I64d|held_bars=%d",
               (long)TimeCurrent(),
               ticket,
               (long)opened_at,
               held_bars);
   return(true);
  }


void ReceiverTimeFieldReport()
  {
   PrintFormat("ZETA_FRONTIER_TIME_FIELD_SUMMARY|mode=%s|expired_emitters=%d|return_signals=%I64d|return_qualified=%I64d|return_releases=%I64d|cross_signals=%I64d|cross_qualified=%I64d|cross_extended=%I64d|cross_native=%I64d",
               ReceiverTimeFieldModeName(),
               time_field_expired_count,
               time_field_signal_count[US30_RETURN_REV_LONG],
               time_field_qualified_count[US30_RETURN_REV_LONG],
               time_field_return_releases,
               time_field_signal_count[US100_CROSS],
               time_field_qualified_count[US100_CROSS],
               time_field_cross_extended_lifecycles,
               time_field_cross_native_lifecycles);
  }

#endif
