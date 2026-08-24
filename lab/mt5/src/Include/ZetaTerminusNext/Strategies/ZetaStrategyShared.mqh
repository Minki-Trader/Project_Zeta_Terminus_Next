#ifndef ZETA_NEXT_MODULE_02_MQH
#define ZETA_NEXT_MODULE_02_MQH

// Behavior-preserving function extraction from B70 V6R6: Strategies\ZetaStrategyShared.mqh

double Median(double &values[])
  {
   const int count = ArraySize(values);
   if(count <= 0)
      return(0.0);
   ArraySort(values);
   if((count % 2) == 1)
      return(values[count / 2]);
   return(0.5 * (values[count / 2 - 1] + values[count / 2]));
  }


double WindowLogRange(const double &highs[],
                      const double &lows[],
                      const int start,
                      const int count)
  {
   double maximum = highs[start];
   double minimum = lows[start];
   for(int offset = 1; offset < count; ++offset)
     {
      maximum = MathMax(maximum, highs[start + offset]);
      minimum = MathMin(minimum, lows[start + offset]);
     }
   if(maximum <= 0.0 || minimum <= 0.0 || maximum < minimum)
      return(0.0);
   return(MathLog(maximum / minimum));
  }


bool CalculateRangeCompression(const string symbol,
                               const int compression_window,
                               double &signed_tightness)
  {
   const int normal_window = 96;
   const int direction_lookback = MathMax(1, compression_window / 2);
   const int bar_count = normal_window + compression_window;
   double highs[];
   double lows[];
   double closes[];
   if(CopyHigh(symbol, PERIOD_M30, 1, bar_count, highs) != bar_count ||
      CopyLow(symbol, PERIOD_M30, 1, bar_count, lows) != bar_count ||
      CopyClose(symbol, PERIOD_M30, 1, bar_count, closes) != bar_count)
      return(false);
   double prior_ranges[];
   ArrayResize(prior_ranges, normal_window);
   for(int sample = 0; sample < normal_window; ++sample)
     {
      prior_ranges[sample] =
         WindowLogRange(highs, lows, sample, compression_window);
      if(prior_ranges[sample] <= 0.0)
         return(false);
     }
   const double normal_range = Median(prior_ranges);
   const double current_range =
      WindowLogRange(highs, lows, normal_window, compression_window);
   const int latest = bar_count - 1;
   const int earlier = latest - direction_lookback;
   if(normal_range <= 0.0 || current_range <= 0.0 ||
      closes[latest] <= 0.0 || closes[earlier] <= 0.0)
      return(false);
   const double direction_return =
      MathLog(closes[latest] / closes[earlier]);
   if(direction_return == 0.0)
     {
      signed_tightness = 0.0;
      return(true);
     }
   signed_tightness =
      (direction_return > 0.0 ? 1.0 : -1.0) /
      (current_range / normal_range);
   return(MathIsValidNumber(signed_tightness));
  }


bool CopySynchronizedCloses(const string symbol,
                            const int count,
                            const datetime expected_latest,
                            double &closes[])
  {
   if(iTime(symbol, PERIOD_H1, 1) != expected_latest)
      return(false);
   return(CopyClose(symbol, PERIOD_H1, 1, count, closes) == count);
  }


bool IsEntryWindow(const int hour,
                   const int minute,
                   int &elapsed_minutes)
  {
   MqlDateTime server = {};
   TimeCurrent(server);
   if(server.hour != hour || server.min < minute)
      return(false);
   elapsed_minutes = server.min - minute;
   return(elapsed_minutes < 30);
  }


bool PrepareEntry(const int component,
                  const int hour,
                  const int minute,
                  datetime &current_bar)
  {
   current_bar = iTime(component_definitions[component].symbol,
                       component_definitions[component].timeframe,
                       0);
   if(current_bar == 0 || component_states[component].last_decision_bar == current_bar)
      return(false);
   ulong ticket = 0;
   datetime opened_at = 0;
   const int owned = CountOwnedPositions(component, ticket, opened_at);
   if(owned > 1)
     {
      BeginEntryCheck(component, current_bar, "DUPLICATE_EXPOSURE");
      execution_state.broker_mismatch = true;
      EngageSafetyStop("duplicate component position before entry");
      PersistDecision(component, current_bar);
      return(false);
     }
   if(owned == 1)
     {
      BeginEntryCheck(component, current_bar, "EXISTING_EXPOSURE");
      PersistDecision(component, current_bar);
      return(false);
     }
   if(component == RC4_BOTH && execution_state.rc4_shadow_occupied)
     {
      BeginEntryCheck(component, current_bar, "SHADOW_ACCEPTED_OCCUPANCY");
      ++rc4_shadow_entry_blocks;
      PersistDecision(component, current_bar);
      return(false);
     }
   int elapsed = 0;
   if(!IsEntryWindow(hour, minute, elapsed))
      return(false);
   if(elapsed > InpMaxEntryDelayMinutes)
     {
      BeginEntryCheck(component, current_bar, "ENTRY_DELAY_EXCEEDED");
      RecordEvent(component,
                  "SKIP_DELAY",
                  (double)elapsed,
                  0.0,
                  TimeToString(current_bar));
      PersistDecision(component, current_bar);
      return(false);
     }
   BeginEntryCheck(component, current_bar, "CHECKING_SIGNAL");
   return(true);
  }



#endif
