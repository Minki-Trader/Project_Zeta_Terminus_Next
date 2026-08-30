#ifndef ZETA_NEXT_MODULE_06_MQH
#define ZETA_NEXT_MODULE_06_MQH

// Behavior-preserving function extraction from B70 V6R6: Strategies\ZetaPressure.mqh

bool CalculateIntradayRangePressure(const string symbol, double &pressure)
  {
   const datetime day_start = ServerMidnight();
   const datetime current_bar = iTime(symbol, PERIOD_M30, 0);
   if(day_start <= 0 || current_bar <= day_start)
     {
      const bool exact_boundary =
         (day_start > 0 && current_bar == day_start);
      ArcSetUnavailabilityObservation(
         (exact_boundary
          ? "SESSION_BOUNDARY_NO_COMPLETED_CURRENT_DAY_BAR"
          : "UNCLASSIFIED"),
         (exact_boundary
          ? "pressure_current_bar_at_server_midnight"
          : "pressure_invalid_day_or_current_bar"),
         0, 0, -1, (double)current_bar, true, exact_boundary);
      return(false);
     }
   MqlRates recent[];
   const int recent_count = 64;
   const int copied =
      CopyRates(symbol, PERIOD_M30, 1, recent_count, recent);
   if(copied <= 0)
     {
      ArcSetUnavailabilityObservation(
         "SHORT_HISTORY_COPY",
         "pressure_recent_m30_rates",
         recent_count, copied, -1, (double)copied, true, false);
      return(false);
     }
   const bool recent_history_complete = (copied == recent_count);
   bool found = false;
   double session_open = 0.0;
   double running_high = 0.0;
   double running_low = 0.0;
   double latest_close = 0.0;
   for(int index = 0; index < copied; ++index)
     {
      if(recent[index].time < day_start ||
         recent[index].time >= current_bar)
         continue;
      if(!found)
        {
         session_open = recent[index].open;
         running_high = recent[index].high;
         running_low = recent[index].low;
         found = true;
        }
      else
        {
         running_high = MathMax(running_high, recent[index].high);
         running_low = MathMin(running_low, recent[index].low);
        }
      latest_close = recent[index].close;
     }
   if(!found || session_open <= 0.0 || latest_close <= 0.0 ||
      running_high <= running_low || running_low <= 0.0)
     {
      if(!recent_history_complete)
         ArcSetUnavailabilityObservation(
            "SHORT_HISTORY_COPY",
            "pressure_recent_m30_rates",
            recent_count, copied, -1, (double)copied, true, false);
      else if(!found)
         ArcSetUnavailabilityObservation(
            "SESSION_BOUNDARY_NO_COMPLETED_CURRENT_DAY_BAR",
            "pressure_no_completed_current_day_bar",
            recent_count, copied, -1,
            (double)((long)current_bar - (long)day_start), true, true);
      else if(!MathIsValidNumber(session_open) ||
              !MathIsValidNumber(latest_close) ||
              !MathIsValidNumber(running_high) ||
              !MathIsValidNumber(running_low))
        {
         double observed = session_open;
         string detail = "pressure_session_open";
         if(MathIsValidNumber(observed))
           {
            observed = latest_close;
            detail = "pressure_latest_close";
           }
         if(MathIsValidNumber(observed))
           {
            observed = running_high;
            detail = "pressure_running_high";
           }
         if(MathIsValidNumber(observed))
           {
            observed = running_low;
            detail = "pressure_running_low";
           }
         ArcSetUnavailabilityObservation(
            "NONFINITE", detail,
            recent_count, copied, -1, observed, false, true);
        }
      else if(running_high == running_low && running_low > 0.0)
         ArcSetUnavailabilityObservation(
            "COMPLETE_ZERO_RANGE_WINDOW",
            "pressure_running_session_range",
            recent_count, copied, -1, 0.0, true, true);
      else
         ArcSetUnavailabilityObservation(
            "INVALID_OR_NONPOSITIVE_PRICE",
            "pressure_running_session_price",
            recent_count, copied, -1,
            MathMin(MathMin(session_open, latest_close), running_low),
            true, true);
      return(false);
     }
   double daily_highs[];
   double daily_lows[];
   const int daily_count = 20;
   const int copied_daily_high =
      CopyHigh(symbol, PERIOD_D1, 1, daily_count, daily_highs);
   if(copied_daily_high != daily_count)
     {
      ArcSetUnavailabilityObservation(
         "SHORT_HISTORY_COPY",
         "pressure_daily_high",
         daily_count, copied_daily_high, -1,
         (double)copied_daily_high, true, false);
      return(false);
     }
   const int copied_daily_low =
      CopyLow(symbol, PERIOD_D1, 1, daily_count, daily_lows);
   if(copied_daily_low != daily_count)
     {
      ArcSetUnavailabilityObservation(
         "SHORT_HISTORY_COPY",
         "pressure_daily_low",
         daily_count, copied_daily_low, -1,
         (double)copied_daily_low, true, false);
      return(false);
     }
   double daily_ranges[];
   ArrayResize(daily_ranges, daily_count);
   for(int index = 0; index < daily_count; ++index)
     {
      if(!MathIsValidNumber(daily_highs[index]) ||
         !MathIsValidNumber(daily_lows[index]))
        {
         if(!recent_history_complete)
            ArcSetUnavailabilityObservation(
               "SHORT_HISTORY_COPY",
               "pressure_recent_m30_rates",
               recent_count, copied, -1, (double)copied, true, false);
         else
            ArcSetUnavailabilityObservation(
               "NONFINITE",
               "pressure_daily_price",
               daily_count, daily_count, index,
               (!MathIsValidNumber(daily_highs[index])
                ? daily_highs[index]
                : daily_lows[index]),
               false, true);
         return(false);
        }
      if(daily_highs[index] <= daily_lows[index] || daily_lows[index] <= 0.0)
        {
         if(!recent_history_complete)
            ArcSetUnavailabilityObservation(
               "SHORT_HISTORY_COPY",
               "pressure_recent_m30_rates",
               recent_count, copied, -1, (double)copied, true, false);
         else if(daily_highs[index] == daily_lows[index] &&
                 daily_lows[index] > 0.0)
            ArcSetUnavailabilityObservation(
               "COMPLETE_ZERO_RANGE_WINDOW",
               "pressure_daily_range",
               daily_count, daily_count, index, 0.0, true, true);
         else
            ArcSetUnavailabilityObservation(
               "INVALID_OR_NONPOSITIVE_PRICE",
               "pressure_daily_price",
               daily_count, daily_count, index,
               MathMin(daily_highs[index], daily_lows[index]), true, true);
         return(false);
        }
      daily_ranges[index] = MathLog(daily_highs[index] / daily_lows[index]);
      if(!MathIsValidNumber(daily_ranges[index]))
        {
         if(!recent_history_complete)
            ArcSetUnavailabilityObservation(
               "SHORT_HISTORY_COPY",
               "pressure_recent_m30_rates",
               recent_count, copied, -1, (double)copied, true, false);
         else
            ArcSetUnavailabilityObservation(
               "NONFINITE",
               "pressure_daily_log_range",
               daily_count, daily_count, index,
               daily_ranges[index], false, true);
         return(false);
        }
     }
   const double range_scale = Median(daily_ranges);
   const double running_log_range = MathLog(running_high / running_low);
   if(!MathIsValidNumber(range_scale) ||
      !MathIsValidNumber(running_log_range))
     {
      if(!recent_history_complete)
         ArcSetUnavailabilityObservation(
            "SHORT_HISTORY_COPY",
            "pressure_recent_m30_rates",
            recent_count, copied, -1, (double)copied, true, false);
      else
         ArcSetUnavailabilityObservation(
            "NONFINITE",
            (!MathIsValidNumber(range_scale)
             ? "pressure_daily_range_scale"
             : "pressure_running_log_range"),
            daily_count, daily_count, -1,
            (!MathIsValidNumber(range_scale)
             ? range_scale
             : running_log_range),
            false, true);
      return(false);
     }
   if(range_scale <= 0.0 || running_log_range <= 0.0)
     {
      if(!recent_history_complete)
         ArcSetUnavailabilityObservation(
            "SHORT_HISTORY_COPY",
            "pressure_recent_m30_rates",
            recent_count, copied, -1, (double)copied, true, false);
      else
         ArcSetUnavailabilityObservation(
            ((range_scale == 0.0 || running_log_range == 0.0)
             ? "COMPLETE_ZERO_RANGE_WINDOW"
             : "UNCLASSIFIED"),
            (range_scale <= 0.0
             ? "pressure_daily_range_scale"
             : "pressure_running_log_range"),
            daily_count, daily_count, -1,
            (range_scale <= 0.0 ? range_scale : running_log_range),
            true, true);
      return(false);
     }
   const double range_location =
      2.0 * ((latest_close - running_low) /
             (running_high - running_low) - 0.5);
   pressure = range_location * (running_log_range / range_scale);
   if(!MathIsValidNumber(pressure))
     {
      if(!recent_history_complete)
         ArcSetUnavailabilityObservation(
            "SHORT_HISTORY_COPY",
            "pressure_recent_m30_rates",
            recent_count, copied, -1, (double)copied, true, false);
      else
         ArcSetUnavailabilityObservation(
            "NONFINITE",
            "pressure_final_value",
            daily_count, daily_count, -1, pressure, false, true);
      return(false);
     }
   return(true);
  }


void ProcessUS30Pressure()
  {
   EntryGateResult gate = {};
   EvaluateEntryGate(US30_PRESSURE, 15, 0, gate);
   ApplyEntryGateResult(US30_PRESSURE, gate);
   CommitOpportunityConsumption(US30_PRESSURE, gate);
   if(!gate.enter_signal_path)
      return;
   const datetime bar = gate.current_bar;
   double feature = 0.0;
   if(!CalculateIntradayRangePressure("US30", feature))
     {
      component_states[US30_PRESSURE].entry_check_result = "DATA_UNAVAILABLE";
      return;
     }
   const bool signal_passed = (MathAbs(feature) >= 0.5);
   const int direction =
      (signal_passed ? (feature > 0.0 ? 1 : -1) : 0);
   SetEntrySignalCheck(US30_PRESSURE,
                       feature,
                       signal_passed,
                       direction,
                       (signal_passed
                        ? "SIGNAL_MET_ORDER_CHECK"
                        : "SIGNAL_NOT_MET"));
   if(!PersistDecision(US30_PRESSURE, bar))
     {
      component_states[US30_PRESSURE].entry_check_result = "PERSISTENCE_FAILED";
      return;
     }
   if(signal_passed)
     {
      OpenComponent(US30_PRESSURE, direction, feature);
      if(!FinalizeDecisionJournal(US30_PRESSURE,
                                  component_states[US30_PRESSURE].entry_check_result))
         component_states[US30_PRESSURE].entry_check_result = "PERSISTENCE_FAILED";
     }
  }


#endif
