#ifndef ZETA_OPT_DD20_GOBQR1_PRESSURE_MQH
#define ZETA_OPT_DD20_GOBQR1_PRESSURE_MQH

// Behavior-preserving function extraction from B70 V6R6: Strategies\ZetaPressure.mqh

bool CalculateIntradayRangePressure(const string symbol, double &pressure)
  {
   const datetime day_start = ServerMidnight();
   const datetime current_bar = iTime(symbol, PERIOD_M30, 0);
   if(day_start <= 0 || current_bar <= day_start)
      return(false);
   MqlRates recent[];
   const int copied = CopyRates(symbol, PERIOD_M30, 1, 64, recent);
   if(copied <= 0)
      return(false);
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
      return(false);
   double daily_highs[];
   double daily_lows[];
   const int daily_count = 20;
   if(CopyHigh(symbol, PERIOD_D1, 1, daily_count, daily_highs) != daily_count ||
      CopyLow(symbol, PERIOD_D1, 1, daily_count, daily_lows) != daily_count)
      return(false);
   double daily_ranges[];
   ArrayResize(daily_ranges, daily_count);
   for(int index = 0; index < daily_count; ++index)
     {
      if(daily_highs[index] <= daily_lows[index] || daily_lows[index] <= 0.0)
         return(false);
      daily_ranges[index] = MathLog(daily_highs[index] / daily_lows[index]);
     }
   const double range_scale = Median(daily_ranges);
   const double running_log_range = MathLog(running_high / running_low);
   if(range_scale <= 0.0 || running_log_range <= 0.0)
      return(false);
   const double range_location =
      2.0 * ((latest_close - running_low) /
             (running_high - running_low) - 0.5);
   pressure = range_location * (running_log_range / range_scale);
   return(MathIsValidNumber(pressure));
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
