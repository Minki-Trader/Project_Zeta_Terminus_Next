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


enum EEntryGateCode
  {
   ENTRY_GATE_BAR_UNAVAILABLE = 0,
   ENTRY_GATE_ALREADY_CONSUMED,
   ENTRY_GATE_DUPLICATE_EXPOSURE,
   ENTRY_GATE_EXISTING_EXPOSURE,
   ENTRY_GATE_RC4_SHADOW_OCCUPIED,
   ENTRY_GATE_NOT_IN_WINDOW,
   ENTRY_GATE_DELAY_EXCEEDED,
   ENTRY_GATE_READY
  };


struct EntryGateResult
  {
   EEntryGateCode code;
   datetime current_bar;
   int owned_position_count;
   int elapsed_minutes;
   bool consume_opportunity;
   bool begin_observation;
   bool set_broker_mismatch;
   bool engage_safety_stop;
   bool increment_rc4_shadow_block;
   bool write_skip_delay_event;
   bool enter_signal_path;
  };


void EvaluateEntryGate(const int component,
                       const int hour,
                       const int minute,
                       EntryGateResult &result)
  {
   result.code = ENTRY_GATE_BAR_UNAVAILABLE;
   result.current_bar = 0;
   result.owned_position_count = 0;
   result.elapsed_minutes = 0;
   result.consume_opportunity = false;
   result.begin_observation = false;
   result.set_broker_mismatch = false;
   result.engage_safety_stop = false;
   result.increment_rc4_shadow_block = false;
   result.write_skip_delay_event = false;
   result.enter_signal_path = false;

   // Path 1: the current component bar is unavailable.
   result.current_bar =
      iTime(component_definitions[component].symbol,
            component_definitions[component].timeframe,
            0);
   if(result.current_bar == 0)
      return;

   // Path 2: this durable opportunity was already consumed.
   if(component_states[component].last_decision_bar == result.current_bar)
     {
      result.code = ENTRY_GATE_ALREADY_CONSUMED;
      return;
     }

   ulong ticket = 0;
   datetime opened_at = 0;
   const int owned = CountOwnedPositions(component, ticket, opened_at);
   result.owned_position_count = owned;

   // Path 3: duplicate owned exposure is a safety fault and is consumed.
   if(owned > 1)
     {
      result.code = ENTRY_GATE_DUPLICATE_EXPOSURE;
      result.consume_opportunity = true;
      result.begin_observation = true;
      result.set_broker_mismatch = true;
      result.engage_safety_stop = true;
      return;
     }

   // Path 4: an existing owned position consumes this opportunity.
   if(owned == 1)
     {
      result.code = ENTRY_GATE_EXISTING_EXPOSURE;
      result.consume_opportunity = true;
      result.begin_observation = true;
      return;
     }

   // Path 5: accepted RC4 shadow occupancy consumes this opportunity.
   if(component == RC4_BOTH && execution_state.rc4_shadow_occupied)
     {
      result.code = ENTRY_GATE_RC4_SHADOW_OCCUPIED;
      result.consume_opportunity = true;
      result.begin_observation = true;
      result.increment_rc4_shadow_block = true;
      return;
     }

   int elapsed = 0;
   if(!IsEntryWindow(hour, minute, elapsed))
     {
      // Path 6: position and shadow observations precede the time window.
      result.code = ENTRY_GATE_NOT_IN_WINDOW;
      result.elapsed_minutes = elapsed;
      return;
     }
   result.elapsed_minutes = elapsed;

   // Path 7: a late opportunity is observed, logged, and consumed.
   if(elapsed > InpMaxEntryDelayMinutes)
     {
      result.code = ENTRY_GATE_DELAY_EXCEEDED;
      result.consume_opportunity = true;
      result.begin_observation = true;
      result.write_skip_delay_event = true;
      return;
     }

   // Path 8: signal evaluation may proceed without consuming the bar yet.
   result.code = ENTRY_GATE_READY;
   result.begin_observation = true;
   result.enter_signal_path = true;
  }


void ApplyEntryGateResult(const int component,
                          const EntryGateResult &result)
  {
   if(result.begin_observation)
     {
      string observation_result = "";
      switch(result.code)
        {
         case ENTRY_GATE_DUPLICATE_EXPOSURE:
            observation_result = "DUPLICATE_EXPOSURE";
            break;
         case ENTRY_GATE_EXISTING_EXPOSURE:
            observation_result = "EXISTING_EXPOSURE";
            break;
         case ENTRY_GATE_RC4_SHADOW_OCCUPIED:
            observation_result = "SHADOW_ACCEPTED_OCCUPANCY";
            break;
         case ENTRY_GATE_DELAY_EXCEEDED:
            observation_result = "ENTRY_DELAY_EXCEEDED";
            break;
         case ENTRY_GATE_READY:
            observation_result = "CHECKING_SIGNAL";
            break;
         default:
            break;
        }
      BeginEntryCheck(component, result.current_bar, observation_result);
     }
   if(result.set_broker_mismatch)
      execution_state.broker_mismatch = true;
   if(result.engage_safety_stop)
      EngageSafetyStop("duplicate component position before entry");
   if(result.increment_rc4_shadow_block)
      ++rc4_shadow_entry_blocks;
   if(result.write_skip_delay_event)
      RecordEvent(component,
                  "SKIP_DELAY",
                  (double)result.elapsed_minutes,
                  0.0,
                  TimeToString(result.current_bar));
  }


bool CommitOpportunityConsumption(const int component,
                                  const EntryGateResult &result)
  {
   if(!result.consume_opportunity)
      return(true);
   const bool saved = PersistDecision(component, result.current_bar);
   if(saved && result.begin_observation)
      ResearchRecordGateObservation(component,
                                    result.current_bar,
                                    component_states[component].entry_check_result);
   return(saved);
  }



#endif
