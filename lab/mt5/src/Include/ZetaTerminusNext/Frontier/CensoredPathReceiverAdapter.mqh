#ifndef ZETA_NEXT_FRONTIER_CENSORED_PATH_RECEIVER_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_CENSORED_PATH_RECEIVER_ADAPTER_MQH

#define CENSORED_PATH_CAPACITY 64
const int CENSORED_PATH_RETURN_WINDOW_SECONDS = 2880 * 60;
const int CENSORED_PATH_CROSS_WINDOW_SECONDS = 4320 * 60;
const double CENSORED_PATH_EFFICIENCY_MEDIAN = 0.0125708051;
const double CENSORED_PATH_EFFICIENCY_Q75 = 0.0172140000;
const double CENSORED_PATH_CLOSEST_MEDIAN = 0.0097265612;

datetime censored_path_server[CENSORED_PATH_CAPACITY];
int censored_path_direction[CENSORED_PATH_CAPACITY];
double censored_path_closest_ratio[CENSORED_PATH_CAPACITY];
double censored_path_efficiency[CENSORED_PATH_CAPACITY];
double censored_path_terminal_persistence[CENSORED_PATH_CAPACITY];
int censored_path_count = 0;

bool censored_path_qualified[COMPONENT_COUNT];
datetime censored_path_signal_server[COMPONENT_COUNT];
double censored_path_selected_closest[COMPONENT_COUNT];
double censored_path_selected_efficiency[COMPONENT_COUNT];
double censored_path_selected_persistence[COMPONENT_COUNT];
long censored_path_selected_age[COMPONENT_COUNT];
long censored_path_signal_count[COMPONENT_COUNT];
long censored_path_qualified_count[COMPONENT_COUNT];

ulong censored_path_cross_gate_identifier = 0;
bool censored_path_cross_gate_decided = false;
bool censored_path_cross_gate_extended = false;
long censored_path_return_releases = 0;
long censored_path_cross_extended_lifecycles = 0;
long censored_path_cross_native_lifecycles = 0;
long censored_path_measurement_emitted = 0;
long censored_path_copy_failures = 0;
long censored_path_invalid_geometry = 0;
long censored_path_ticks_observed = 0;


string CensoredPathReceiverModeName()
  {
   if(InpCensoredPathReceiverMode == CENSORED_RETURN_LOW_EFFICIENCY)
      return("RETURN_LOW_EFFICIENCY");
   if(InpCensoredPathReceiverMode == CENSORED_RETURN_WIDE_LOW_EFFICIENCY)
      return("RETURN_WIDE_LOW_EFFICIENCY");
   return("PAIRED_NON_APPROACH_GATE");
  }


bool CensoredPathReceiverInitialize()
  {
   if(InpCensoredPathReceiverMode != CENSORED_RETURN_LOW_EFFICIENCY &&
      InpCensoredPathReceiverMode != CENSORED_RETURN_WIDE_LOW_EFFICIENCY &&
      InpCensoredPathReceiverMode != CENSORED_PAIRED_NON_APPROACH_GATE)
      return(false);
   FolderCreate("ZetaTerminusNext\\frontier");
   return(true);
  }


void CensoredPathReceiverReset()
  {
   ArrayInitialize(censored_path_server, 0);
   ArrayInitialize(censored_path_direction, 0);
   ArrayInitialize(censored_path_closest_ratio, 0.0);
   ArrayInitialize(censored_path_efficiency, 0.0);
   ArrayInitialize(censored_path_terminal_persistence, 0.0);
   ArrayInitialize(censored_path_qualified, false);
   ArrayInitialize(censored_path_signal_server, 0);
   ArrayInitialize(censored_path_selected_closest, 0.0);
   ArrayInitialize(censored_path_selected_efficiency, 0.0);
   ArrayInitialize(censored_path_selected_persistence, 0.0);
   ArrayInitialize(censored_path_selected_age, -1);
   ArrayInitialize(censored_path_signal_count, 0);
   ArrayInitialize(censored_path_qualified_count, 0);
   censored_path_count = 0;
   censored_path_cross_gate_identifier = 0;
   censored_path_cross_gate_decided = false;
   censored_path_cross_gate_extended = false;
   censored_path_return_releases = 0;
   censored_path_cross_extended_lifecycles = 0;
   censored_path_cross_native_lifecycles = 0;
   censored_path_measurement_emitted = 0;
   censored_path_copy_failures = 0;
   censored_path_invalid_geometry = 0;
   censored_path_ticks_observed = 0;
  }


double CensoredPathExecutableGap(const MqlTick &tick,
                                 const int direction,
                                 const double limit_price)
  {
   if(direction > 0)
      return(tick.ask - limit_price);
   return(limit_price - tick.bid);
  }


void CensoredPathStore(const datetime server,
                       const int direction,
                       const double closest_ratio,
                       const double path_efficiency,
                       const double terminal_persistence)
  {
   int slot = censored_path_count;
   if(censored_path_count < CENSORED_PATH_CAPACITY)
      ++censored_path_count;
   else
     {
      for(int index = 1; index < CENSORED_PATH_CAPACITY; ++index)
        {
         censored_path_server[index - 1] = censored_path_server[index];
         censored_path_direction[index - 1] = censored_path_direction[index];
         censored_path_closest_ratio[index - 1] =
            censored_path_closest_ratio[index];
         censored_path_efficiency[index - 1] =
            censored_path_efficiency[index];
         censored_path_terminal_persistence[index - 1] =
            censored_path_terminal_persistence[index];
        }
      slot = CENSORED_PATH_CAPACITY - 1;
     }
   censored_path_server[slot] = server;
   censored_path_direction[slot] = direction;
   censored_path_closest_ratio[slot] = closest_ratio;
   censored_path_efficiency[slot] = path_efficiency;
   censored_path_terminal_persistence[slot] = terminal_persistence;
  }


void CensoredPathReceiverObserveExpiration(const int direction,
                                           const datetime expiration)
  {
   const datetime observed_server = TimeCurrent();
   const datetime placed_server =
      expiration - PASSIVE_ACTIVATION_BARS * PASSIVE_BAR_SECONDS;
   const double limit_price = passive_pending_limit_price;
   const double stop_loss = passive_pending_stop_loss;
   const double protection_span = MathAbs(limit_price - stop_loss);
   if(direction == 0 || expiration <= 0 || placed_server <= 0 ||
      observed_server < placed_server || limit_price <= 0.0 ||
      stop_loss <= 0.0 || protection_span <= 0.0)
     {
      ++censored_path_invalid_geometry;
      return;
     }

   MqlTick ticks[];
   ResetLastError();
   const int copied =
      CopyTicksRange("US100",
                     ticks,
                     COPY_TICKS_ALL,
                     (ulong)((long)placed_server * 1000),
                     (ulong)((long)observed_server * 1000 + 999));
   const int history_error = GetLastError();
   if(copied <= 0 || history_error != 0 || ArraySize(ticks) != copied)
     {
      ++censored_path_copy_failures;
      PrintFormat("ZETA_FRONTIER_CENSORED_PATH_FAILURE|server=%I64d|expiration=%I64d|direction=%d|copied=%d|size=%d|error=%d",
                  (long)observed_server,
                  (long)expiration,
                  direction,
                  copied,
                  ArraySize(ticks),
                  history_error);
      return;
     }

   bool known = false;
   double first_gap = 0.0;
   double closest_gap = 0.0;
   double farthest_gap = 0.0;
   double endpoint_gap = 0.0;
   double prior_gap = 0.0;
   double path_travel = 0.0;
   int valid_ticks = 0;
   for(int index = 0; index < copied; ++index)
     {
      const MqlTick current = ticks[index];
      if(current.bid <= 0.0 || current.ask <= 0.0 ||
         current.ask < current.bid)
         continue;
      const double gap =
         CensoredPathExecutableGap(current, direction, limit_price);
      if(!MathIsValidNumber(gap))
         continue;
      if(!known)
        {
         known = true;
         first_gap = gap;
         closest_gap = gap;
         farthest_gap = gap;
        }
      else
        {
         closest_gap = MathMin(closest_gap, gap);
         farthest_gap = MathMax(farthest_gap, gap);
         path_travel += MathAbs(gap - prior_gap);
        }
      prior_gap = gap;
      endpoint_gap = gap;
      ++valid_ticks;
     }
   if(!known || valid_ticks <= 0)
     {
      ++censored_path_invalid_geometry;
      return;
     }

   const double closest_ratio = closest_gap / protection_span;
   const double endpoint_ratio = endpoint_gap / protection_span;
   const double farthest_ratio = farthest_gap / protection_span;
   const double path_efficiency =
      (path_travel > 0.0
       ? (endpoint_gap - first_gap) / path_travel
       : 0.0);
   const double terminal_persistence =
      (farthest_ratio > 0.0 ? endpoint_ratio / farthest_ratio : 0.0);

   CensoredPathStore(observed_server,
                     direction,
                     closest_ratio,
                     path_efficiency,
                     terminal_persistence);
   ++censored_path_measurement_emitted;
   censored_path_ticks_observed += valid_ticks;
   PrintFormat("ZETA_FRONTIER_CENSORED_PATH_EMITTER|server=%I64d|expiration=%I64d|direction=%d|ticks=%d|closest_ratio=%.10f|path_efficiency=%.10f|terminal_persistence=%.10f|count=%d",
               (long)observed_server,
               (long)expiration,
               direction,
               valid_ticks,
               closest_ratio,
               path_efficiency,
               terminal_persistence,
               censored_path_count);
  }


bool CensoredPathReturnQualified(const int receiver_direction,
                                 double &selected_efficiency,
                                 double &selected_persistence,
                                 long &selected_age)
  {
   const double threshold =
      (InpCensoredPathReceiverMode == CENSORED_RETURN_WIDE_LOW_EFFICIENCY
       ? CENSORED_PATH_EFFICIENCY_Q75
       : CENSORED_PATH_EFFICIENCY_MEDIAN);
   bool qualified = false;
   selected_efficiency = 0.0;
   selected_persistence = 0.0;
   selected_age = -1;
   const datetime now = TimeCurrent();
   for(int index = 0; index < censored_path_count; ++index)
     {
      const long age = (long)now - (long)censored_path_server[index];
      if(age < 0 || age > CENSORED_PATH_RETURN_WINDOW_SECONDS ||
         censored_path_direction[index] != receiver_direction ||
         censored_path_efficiency[index] > threshold)
         continue;
      if(!qualified || censored_path_efficiency[index] < selected_efficiency)
        {
         qualified = true;
         selected_efficiency = censored_path_efficiency[index];
         selected_persistence = censored_path_terminal_persistence[index];
         selected_age = age;
        }
     }
   return(qualified);
  }


bool CensoredPathCrossQualified(const int receiver_direction,
                                double &selected_closest,
                                long &selected_age)
  {
   bool qualified = false;
   selected_closest = 0.0;
   selected_age = -1;
   if(InpCensoredPathReceiverMode != CENSORED_PAIRED_NON_APPROACH_GATE)
      return(false);
   const datetime now = TimeCurrent();
   for(int index = 0; index < censored_path_count; ++index)
     {
      const long age = (long)now - (long)censored_path_server[index];
      if(age < 0 || age > CENSORED_PATH_CROSS_WINDOW_SECONDS ||
         censored_path_direction[index] == receiver_direction ||
         censored_path_closest_ratio[index] < CENSORED_PATH_CLOSEST_MEDIAN)
         continue;
      if(!qualified || censored_path_closest_ratio[index] > selected_closest)
        {
         qualified = true;
         selected_closest = censored_path_closest_ratio[index];
         selected_age = age;
        }
     }
   return(qualified);
  }


void CensoredPathReceiverObserveSignal(const int component,
                                       const double value,
                                       const bool passed,
                                       const int direction)
  {
   if(component != US30_RETURN_REV_LONG && component != US100_CROSS)
      return;
   censored_path_qualified[component] = false;
   censored_path_signal_server[component] = TimeCurrent();
   censored_path_selected_closest[component] = 0.0;
   censored_path_selected_efficiency[component] = 0.0;
   censored_path_selected_persistence[component] = 0.0;
   censored_path_selected_age[component] = -1;
   if(component == US100_CROSS)
     {
      censored_path_cross_gate_identifier = 0;
      censored_path_cross_gate_decided = false;
      censored_path_cross_gate_extended = false;
     }
   if(!passed || direction == 0)
      return;
   ++censored_path_signal_count[component];
   if(component == US30_RETURN_REV_LONG)
      censored_path_qualified[component] =
         CensoredPathReturnQualified(
            direction,
            censored_path_selected_efficiency[component],
            censored_path_selected_persistence[component],
            censored_path_selected_age[component]);
   else
      censored_path_qualified[component] =
         CensoredPathCrossQualified(
            direction,
            censored_path_selected_closest[component],
            censored_path_selected_age[component]);
   if(censored_path_qualified[component])
      ++censored_path_qualified_count[component];
   PrintFormat("ZETA_FRONTIER_CENSORED_PATH_RECEIVER|server=%I64d|component=%d|mode=%s|direction=%d|signal=%.10f|closest=%.10f|efficiency=%.10f|persistence=%.10f|age=%I64d|qualified=%d",
               (long)censored_path_signal_server[component],
               component,
               CensoredPathReceiverModeName(),
               direction,
               value,
               censored_path_selected_closest[component],
               censored_path_selected_efficiency[component],
               censored_path_selected_persistence[component],
               censored_path_selected_age[component],
               (int)censored_path_qualified[component]);
  }


bool CensoredPathReceiverCurrentLifecycle(const int component)
  {
   if(component < 0 || component >= COMPONENT_COUNT ||
      !censored_path_qualified[component] ||
      censored_path_signal_server[component] <= 0 ||
      component_states[component].entry_time_server <= 0)
      return(false);
   const long entry_lag =
      (long)component_states[component].entry_time_server -
      (long)censored_path_signal_server[component];
   return(entry_lag >= 0 && entry_lag <= InpMaxEntryDelayMinutes * 60);
  }


int CensoredPathReceiverHoldBars(const int component,
                                const ulong ticket,
                                const datetime opened_at,
                                const int held_bars,
                                const int native_hold_bars)
  {
   if(component != US100_CROSS ||
      InpCensoredPathReceiverMode != CENSORED_PAIRED_NON_APPROACH_GATE ||
      !CensoredPathReceiverCurrentLifecycle(component))
      return(native_hold_bars);
   if(held_bars < native_hold_bars)
      return(native_hold_bars);
   const ulong identifier = component_states[component].position_identifier;
   if(identifier == 0)
      return(native_hold_bars);
   if(!censored_path_cross_gate_decided ||
      censored_path_cross_gate_identifier != identifier)
     {
      censored_path_cross_gate_identifier = identifier;
      censored_path_cross_gate_decided = true;
      censored_path_cross_gate_extended = false;
      if(PositionSelectByTicket(ticket))
        {
         const double floating_net =
            PositionGetDouble(POSITION_PROFIT) +
            PositionGetDouble(POSITION_SWAP);
         censored_path_cross_gate_extended = (floating_net > 0.0);
        }
      if(censored_path_cross_gate_extended)
         ++censored_path_cross_extended_lifecycles;
      else
         ++censored_path_cross_native_lifecycles;
      PrintFormat("ZETA_FRONTIER_CENSORED_PATH_GATE|server=%I64d|ticket=%I64u|identifier=%I64u|opened=%I64d|held_bars=%d|extended=%d",
                  (long)TimeCurrent(),
                  ticket,
                  identifier,
                  (long)opened_at,
                  held_bars,
                  (int)censored_path_cross_gate_extended);
     }
   return(censored_path_cross_gate_extended ? 6 : native_hold_bars);
  }


bool CensoredPathReceiverShouldClose(const int component,
                                    const ulong ticket,
                                    const datetime opened_at,
                                    const int held_bars)
  {
   if(component != US30_RETURN_REV_LONG ||
      !CensoredPathReceiverCurrentLifecycle(component) || held_bars < 3)
      return(false);
   ++censored_path_return_releases;
   PrintFormat("ZETA_FRONTIER_CENSORED_PATH_RETURN_RELEASE|server=%I64d|ticket=%I64u|opened=%I64d|held_bars=%d|efficiency=%.10f|persistence=%.10f",
               (long)TimeCurrent(),
               ticket,
               (long)opened_at,
               held_bars,
               censored_path_selected_efficiency[component],
               censored_path_selected_persistence[component]);
   return(true);
  }


void CensoredPathReceiverReport()
  {
   PrintFormat("ZETA_FRONTIER_CENSORED_PATH_SUMMARY|mode=%s|emitters=%d|copy_failures=%I64d|invalid_geometry=%I64d|ticks_observed=%I64d|return_signals=%I64d|return_qualified=%I64d|return_releases=%I64d|cross_signals=%I64d|cross_qualified=%I64d|cross_extended=%I64d|cross_native=%I64d",
               CensoredPathReceiverModeName(),
               censored_path_count,
               censored_path_copy_failures,
               censored_path_invalid_geometry,
               censored_path_ticks_observed,
               censored_path_signal_count[US30_RETURN_REV_LONG],
               censored_path_qualified_count[US30_RETURN_REV_LONG],
               censored_path_return_releases,
               censored_path_signal_count[US100_CROSS],
               censored_path_qualified_count[US100_CROSS],
               censored_path_cross_extended_lifecycles,
               censored_path_cross_native_lifecycles);
  }

#endif
