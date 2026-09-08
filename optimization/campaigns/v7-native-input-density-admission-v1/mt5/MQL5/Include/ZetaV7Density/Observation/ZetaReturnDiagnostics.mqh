// Read-only diagnostics derived from the frozen PCR2 observation implementation.
bool ObserveCalculateIntradayRangePressure(const string symbol, double &pressure);

void ArcResetUnavailabilityObservation()
  {
   arc_unavailability_reason_class = "UNCLASSIFIED";
   arc_unavailability_reason_detail = "not-classified";
   arc_unavailability_requested_count = 0;
   arc_unavailability_copied_count = 0;
   arc_unavailability_first_invalid_index = -1;
   arc_unavailability_observed_value = 0.0;
   arc_unavailability_value_finite = true;
   arc_unavailability_history_complete = false;
  }


void ArcSetUnavailabilityObservation(const string reason_class,
                                     const string reason_detail,
                                     const int requested_count,
                                     const int copied_count,
                                     const int first_invalid_index,
                                     const double observed_value,
                                     const bool value_finite,
                                     const bool history_complete)
  {
   arc_unavailability_reason_class = reason_class;
   arc_unavailability_reason_detail = reason_detail;
   arc_unavailability_requested_count = requested_count;
   arc_unavailability_copied_count = copied_count;
   arc_unavailability_first_invalid_index = first_invalid_index;
   arc_unavailability_observed_value = observed_value;
   arc_unavailability_value_finite = value_finite;
   arc_unavailability_history_complete = history_complete;
  }


bool ObserveArcCalculateRangeCompressionAtOffset(const int completed_offset,
                                          double &signed_tightness)
  {
   signed_tightness = 0.0;
   const int compression_window = 4;
   const int normal_window = 96;
   const int direction_lookback = 2;
   const int bar_count = normal_window + compression_window;
   double highs[];
   double lows[];
   double closes[];
   const int start_shift = 1 + completed_offset;
   const int copied_high =
      CopyHigh("US30", PERIOD_M30, start_shift, bar_count, highs);
   if(copied_high != bar_count)
     {
      ArcSetUnavailabilityObservation(
         "SHORT_HISTORY_COPY",
         StringFormat("range_high_offset_%d", completed_offset),
         bar_count, copied_high, completed_offset, (double)copied_high,
         true, false);
      return(false);
     }
   const int copied_low =
      CopyLow("US30", PERIOD_M30, start_shift, bar_count, lows);
   if(copied_low != bar_count)
     {
      ArcSetUnavailabilityObservation(
         "SHORT_HISTORY_COPY",
         StringFormat("range_low_offset_%d", completed_offset),
         bar_count, copied_low, completed_offset, (double)copied_low,
         true, false);
      return(false);
     }
   const int copied_close =
      CopyClose("US30", PERIOD_M30, start_shift, bar_count, closes);
   if(copied_close != bar_count)
     {
      ArcSetUnavailabilityObservation(
         "SHORT_HISTORY_COPY",
         StringFormat("range_close_offset_%d", completed_offset),
         bar_count, copied_close, completed_offset, (double)copied_close,
         true, false);
      return(false);
     }

   double prior_ranges[];
   ArrayResize(prior_ranges, normal_window);
   for(int sample = 0; sample < normal_window; ++sample)
     {
      prior_ranges[sample] =
         WindowLogRange(highs, lows, sample, compression_window);
      if(prior_ranges[sample] <= 0.0)
        {
         for(int offset = 0; offset < compression_window; ++offset)
           {
            const int index = sample + offset;
            if(!MathIsValidNumber(highs[index]) ||
               !MathIsValidNumber(lows[index]))
              {
               ArcSetUnavailabilityObservation(
                  "NONFINITE",
                  StringFormat("range_prior_offset_%d", completed_offset),
                  bar_count, bar_count, index,
                  (!MathIsValidNumber(highs[index]) ? highs[index] : lows[index]),
                  false, true);
               return(false);
              }
            if(highs[index] <= 0.0 || lows[index] <= 0.0 ||
               highs[index] < lows[index])
              {
               ArcSetUnavailabilityObservation(
                  "INVALID_OR_NONPOSITIVE_PRICE",
                  StringFormat("range_prior_offset_%d", completed_offset),
                  bar_count, bar_count, index,
                  MathMin(highs[index], lows[index]), true, true);
               return(false);
              }
           }
         ArcSetUnavailabilityObservation(
            "COMPLETE_ZERO_RANGE_WINDOW",
            StringFormat("range_prior_offset_%d", completed_offset),
            bar_count, bar_count, sample, prior_ranges[sample], true, true);
         return(false);
        }
     }
   const double normal_range = Median(prior_ranges);
   const double current_range =
      WindowLogRange(highs, lows, normal_window, compression_window);
   const int latest = bar_count - 1;
   const int earlier = latest - direction_lookback;
   if(!MathIsValidNumber(normal_range) ||
      !MathIsValidNumber(current_range))
     {
      ArcSetUnavailabilityObservation(
         "NONFINITE",
         StringFormat("range_summary_offset_%d", completed_offset),
         bar_count, bar_count, normal_window,
         (!MathIsValidNumber(normal_range) ? normal_range : current_range),
         false, true);
      return(false);
     }
   if(normal_range <= 0.0)
     {
      ArcSetUnavailabilityObservation(
         (normal_range == 0.0
          ? "COMPLETE_ZERO_RANGE_WINDOW"
          : "UNCLASSIFIED"),
         StringFormat("range_normal_offset_%d", completed_offset),
         bar_count, bar_count, normal_window,
         normal_range, true, true);
      return(false);
     }
   if(current_range <= 0.0)
     {
      for(int offset = 0; offset < compression_window; ++offset)
        {
         const int index = normal_window + offset;
         if(!MathIsValidNumber(highs[index]) ||
            !MathIsValidNumber(lows[index]))
           {
            ArcSetUnavailabilityObservation(
               "NONFINITE",
               StringFormat("range_current_offset_%d", completed_offset),
               bar_count, bar_count, index,
               (!MathIsValidNumber(highs[index])
                ? highs[index]
                : lows[index]),
               false, true);
            return(false);
           }
         if(highs[index] <= 0.0 || lows[index] <= 0.0 ||
            highs[index] < lows[index])
           {
            ArcSetUnavailabilityObservation(
               "INVALID_OR_NONPOSITIVE_PRICE",
               StringFormat("range_current_offset_%d", completed_offset),
               bar_count, bar_count, index,
               MathMin(highs[index], lows[index]), true, true);
            return(false);
           }
        }
      ArcSetUnavailabilityObservation(
         "COMPLETE_ZERO_RANGE_WINDOW",
         StringFormat("range_current_offset_%d", completed_offset),
         bar_count, bar_count, normal_window,
         current_range, true, true);
      return(false);
     }
   if(!MathIsValidNumber(closes[latest]) ||
      !MathIsValidNumber(closes[earlier]))
     {
      ArcSetUnavailabilityObservation(
         "NONFINITE",
         StringFormat("range_close_value_offset_%d", completed_offset),
         bar_count, bar_count, latest,
         (!MathIsValidNumber(closes[latest]) ? closes[latest] : closes[earlier]),
         false, true);
      return(false);
     }
   if(closes[latest] <= 0.0 || closes[earlier] <= 0.0)
     {
      ArcSetUnavailabilityObservation(
         "INVALID_OR_NONPOSITIVE_PRICE",
         StringFormat("range_close_value_offset_%d", completed_offset),
         bar_count, bar_count, latest,
         MathMin(closes[latest], closes[earlier]), true, true);
      return(false);
     }
   const double direction_return =
      MathLog(closes[latest] / closes[earlier]);
   if(direction_return == 0.0)
      return(true);
   signed_tightness =
      (direction_return > 0.0 ? 1.0 : -1.0) /
      (current_range / normal_range);
   if(!MathIsValidNumber(signed_tightness))
     {
      ArcSetUnavailabilityObservation(
         "NONFINITE",
         StringFormat("range_tightness_offset_%d", completed_offset),
         bar_count, bar_count, latest, signed_tightness, false, true);
      return(false);
     }
   return(true);
  }


bool ObserveArcCalculateUS30M30NativeState(double &ret1_z,
                                    double &efficiency4,
                                    double &close_location,
                                    double &vol_ratio,
                                    double &range_median96)
  {
   ret1_z = 0.0;
   efficiency4 = 0.0;
   close_location = 0.0;
   vol_ratio = 0.0;
   range_median96 = 0.0;
   const int count = 97;
   MqlRates rates[];
   const int copied = CopyRates("US30", PERIOD_M30, 1, count, rates);
   if(copied != count)
     {
      ArcSetUnavailabilityObservation(
         "SHORT_HISTORY_COPY",
         "native_m30_rates",
         count, copied, -1, (double)copied, true, false);
      return(false);
     }

   double returns[];
   ArrayResize(returns, count - 1);
   for(int index = 1; index < count; ++index)
     {
      if(!MathIsValidNumber(rates[index].close) ||
         !MathIsValidNumber(rates[index - 1].close))
        {
         ArcSetUnavailabilityObservation(
            "NONFINITE",
            "native_close",
            count, copied, index,
            (!MathIsValidNumber(rates[index].close)
             ? rates[index].close
             : rates[index - 1].close),
            false, true);
         return(false);
        }
      if(rates[index].close <= 0.0 || rates[index - 1].close <= 0.0)
        {
         ArcSetUnavailabilityObservation(
            "INVALID_OR_NONPOSITIVE_PRICE",
            "native_close",
            count, copied, index,
            MathMin(rates[index].close, rates[index - 1].close),
            true, true);
         return(false);
        }
      returns[index - 1] =
         MathLog(rates[index].close / rates[index - 1].close);
      if(!MathIsValidNumber(returns[index - 1]))
        {
         ArcSetUnavailabilityObservation(
            "NONFINITE",
            "native_log_return",
            count, copied, index - 1, returns[index - 1], false, true);
         return(false);
        }
     }
   const double prior_std = ArcSampleStandardDeviation(returns, 47, 48);
   const double fast_std = ArcSampleStandardDeviation(returns, 92, 4);
   const double slow_std = ArcSampleStandardDeviation(returns, 71, 24);
   if(!MathIsValidNumber(prior_std) ||
      !MathIsValidNumber(fast_std) ||
      !MathIsValidNumber(slow_std))
     {
      ArcSetUnavailabilityObservation(
         "NONFINITE",
         "native_standard_deviation",
         count, copied, -1,
         (!MathIsValidNumber(prior_std)
          ? prior_std
          : (!MathIsValidNumber(fast_std) ? fast_std : slow_std)),
         false, true);
      return(false);
     }
   if(prior_std <= 0.0 || slow_std < 0.0)
     {
      ArcSetUnavailabilityObservation(
         (prior_std == 0.0
          ? "COMPLETE_ZERO_VARIANCE_WINDOW"
          : "UNCLASSIFIED"),
         (prior_std == 0.0
          ? "native_prior_return_variance"
          : "native_negative_standard_deviation"),
         count, copied, -1,
         (prior_std <= 0.0 ? prior_std : slow_std), true, true);
      return(false);
     }

   const int latest = count - 1;
   ret1_z = returns[95] / prior_std;
   double absolute_path = 0.0;
   for(int index = 92; index <= 95; ++index)
      absolute_path += MathAbs(returns[index]);
   efficiency4 =
      MathAbs(MathLog(rates[latest].close / rates[latest - 4].close)) /
      (absolute_path + 1.0e-12);
   const double latest_range = rates[latest].high - rates[latest].low;
   if(!MathIsValidNumber(latest_range))
     {
      ArcSetUnavailabilityObservation(
         "NONFINITE",
         "native_latest_range",
         count, copied, latest, latest_range, false, true);
      return(false);
     }
   if(latest_range <= 0.0)
     {
      ArcSetUnavailabilityObservation(
         (latest_range == 0.0
          ? "COMPLETE_ZERO_RANGE_WINDOW"
          : "INVALID_OR_NONPOSITIVE_PRICE"),
         "native_latest_range",
         count, copied, latest, latest_range, true, true);
      return(false);
     }
   close_location =
      2.0 * ((rates[latest].close - rates[latest].low) /
             latest_range - 0.5);
   vol_ratio = fast_std / (slow_std + 1.0e-12);

   double prior_ranges[];
   ArrayResize(prior_ranges, 96);
   for(int index = 0; index < 96; ++index)
     {
      prior_ranges[index] = rates[index].high - rates[index].low;
      if(!MathIsValidNumber(prior_ranges[index]))
        {
         ArcSetUnavailabilityObservation(
            "NONFINITE",
            "native_prior_range",
            count, copied, index, prior_ranges[index], false, true);
         return(false);
        }
      if(prior_ranges[index] <= 0.0)
        {
         ArcSetUnavailabilityObservation(
            (prior_ranges[index] == 0.0
             ? "COMPLETE_ZERO_RANGE_WINDOW"
             : "INVALID_OR_NONPOSITIVE_PRICE"),
            "native_prior_range",
            count, copied, index, prior_ranges[index], true, true);
         return(false);
        }
     }
   range_median96 = Median(prior_ranges);
   if(!MathIsValidNumber(ret1_z) ||
      !MathIsValidNumber(efficiency4) ||
      !MathIsValidNumber(close_location) ||
      !MathIsValidNumber(vol_ratio) ||
      !MathIsValidNumber(range_median96))
     {
      double observed = ret1_z;
      string detail = "native_ret1_z";
      if(MathIsValidNumber(observed))
        {
         observed = efficiency4;
         detail = "native_efficiency4";
        }
      if(MathIsValidNumber(observed))
        {
         observed = close_location;
         detail = "native_close_location";
        }
      if(MathIsValidNumber(observed))
        {
         observed = vol_ratio;
         detail = "native_vol_ratio";
        }
      if(MathIsValidNumber(observed))
        {
         observed = range_median96;
         detail = "native_range_median96";
        }
      ArcSetUnavailabilityObservation(
         "NONFINITE", detail, count, copied, -1,
         observed, false, true);
      return(false);
     }
   if(range_median96 <= 0.0)
     {
      ArcSetUnavailabilityObservation(
         (range_median96 == 0.0
          ? "COMPLETE_ZERO_RANGE_WINDOW"
          : "UNCLASSIFIED"),
         "native_range_median96",
         count, copied, -1, range_median96, true, true);
      return(false);
     }
   return(true);
  }


bool ObserveArcCalculateRC4Heads(const int direction,
                          double &market,
                          double &decision,
                          double &confirmation)
  {
   ArcResetUnavailabilityObservation();
   market = 0.0;
   decision = 0.0;
   confirmation = 0.0;
   if(MathAbs(direction) != 1)
     {
      ArcSetUnavailabilityObservation(
         "INVALID_DIRECTION",
         "rc4_entry_direction",
         0, 0, -1, (double)direction, true, true);
      return(false);
     }

   double current_feature = 0.0;
   double previous_feature = 0.0;
   double two_back_feature = 0.0;
   if(!ObserveArcCalculateRangeCompressionAtOffset(0, current_feature) ||
      !ObserveArcCalculateRangeCompressionAtOffset(1, previous_feature) ||
      !ObserveArcCalculateRangeCompressionAtOffset(2, two_back_feature))
      return(false);

   double ret1_z = 0.0;
   double efficiency4 = 0.0;
   double close_location = 0.0;
   double vol_ratio = 0.0;
   double native_range = 0.0;
   if(!ObserveArcCalculateUS30M30NativeState(ret1_z,
                                      efficiency4,
                                      close_location,
                                      vol_ratio,
                                      native_range))
      return(false);
   double pressure = 0.0;
   if(!ObserveCalculateIntradayRangePressure("US30", pressure))
      return(false);
   MqlTick tick = {};
   if(!StructurallyValidTick("US30", tick))
     {
      ArcSetUnavailabilityObservation(
         "INVALID_TICK",
         "rc4_structural_tick",
         1, 0, -1,
         (tick.ask > 0.0 ? tick.ask : tick.bid),
         (MathIsValidNumber(tick.ask) && MathIsValidNumber(tick.bid)),
         false);
      return(false);
     }

   const double entry_support =
      (double)direction * component_states[RC4_BOTH].entry_feature;
   const double current_support = (double)direction * current_feature;
   const double previous_support = (double)direction * previous_feature;
   const double two_back_support = (double)direction * two_back_feature;
   const double scale = MathMax(MathMax(MathAbs(entry_support), 1.5), 0.25);
   const double velocity =
      (current_support - previous_support) / scale;
   const double prior_velocity =
      (previous_support - two_back_support) / scale;
   const double curvature = velocity - prior_velocity;
   const double spread = MathMax(tick.ask - tick.bid, 1.10);
   const double cost_scale =
      MathMax(0.0, MathMin(2.0, spread / native_range));

   market = ArcBounded(
      (double)direction * ret1_z * (0.40 + 0.60 * efficiency4) -
      0.25 * MathMax(0.0, vol_ratio - 1.0) -
      0.20 * cost_scale);
   decision = ArcBounded(
      current_support / scale +
      0.65 * velocity +
      0.35 * curvature -
      (current_support < 0.0 ? 1.25 : 0.0));
   confirmation = ArcBounded(
      0.70 * (double)direction * pressure +
      0.30 * (double)direction * close_location);
   if(!MathIsValidNumber(market) ||
      !MathIsValidNumber(decision) ||
      !MathIsValidNumber(confirmation))
     {
      double observed = market;
      string detail = "rc4_market_head";
      if(MathIsValidNumber(observed))
        {
         observed = decision;
         detail = "rc4_decision_head";
        }
      if(MathIsValidNumber(observed))
        {
         observed = confirmation;
         detail = "rc4_confirmation_head";
        }
      ArcSetUnavailabilityObservation(
         "NONFINITE", detail, 0, 0, -1,
         observed, false, true);
      return(false);
     }
   return(true);
  }



bool ObserveCalculateIntradayRangePressure(const string symbol, double &pressure)
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



void ObserveArcUnavailability(const datetime current_bar)
  {
   if(!tester_mode)
      return;
   double market = 0.0, decision = 0.0, confirmation = 0.0;
   const bool available = ObserveArcCalculateRC4Heads(
      component_states[RC4_BOTH].entry_direction, market, decision, confirmation);
   if(available)
      ArcSetUnavailabilityObservation("UNCLASSIFIED", "observer_did_not_reproduce_failure", 0, 0, -1, 0.0, true, false);
      ++arc_unavailability_rows;
      if(arc_unavailability_reason_class == "COMPLETE_ZERO_RANGE_WINDOW")
         ++arc_unavailability_complete_zero_range;
      else if(arc_unavailability_reason_class == "COMPLETE_ZERO_VARIANCE_WINDOW")
         ++arc_unavailability_complete_zero_variance;
      else if(arc_unavailability_reason_class == "SESSION_BOUNDARY_NO_COMPLETED_CURRENT_DAY_BAR")
         ++arc_unavailability_session_boundary;
      else if(arc_unavailability_reason_class == "INVALID_DIRECTION")
         ++arc_unavailability_invalid_direction;
      else if(arc_unavailability_reason_class == "SHORT_HISTORY_COPY")
         ++arc_unavailability_short_copy;
      else if(arc_unavailability_reason_class == "INVALID_OR_NONPOSITIVE_PRICE")
         ++arc_unavailability_invalid_price;
      else if(arc_unavailability_reason_class == "INVALID_TICK")
         ++arc_unavailability_invalid_tick;
      else if(arc_unavailability_reason_class == "NONFINITE")
         ++arc_unavailability_nonfinite;
      else
        {
         arc_unavailability_reason_class = "UNCLASSIFIED";
         ++arc_unavailability_unclassified;
        }
      PrintFormat("%s V7RR1_UNAVAILABLE reason_class=%s reason_detail=%s "
                  "symbol=US30 period=M30 server_time=%I64d "
                  "current_bar=%I64d lifecycle_identifier=%I64u "
                  "requested_count=%d copied_count=%d "
                  "first_invalid_index=%d observed_value=%.12f "
                  "finite=%s history_complete=%s",
                  EXECUTION_VERSION,
                  arc_unavailability_reason_class,
                  arc_unavailability_reason_detail,
                  (long)TimeCurrent(),
                  (long)current_bar,
                  arc_lifecycle_identifier,
                  arc_unavailability_requested_count,
                  arc_unavailability_copied_count,
                  arc_unavailability_first_invalid_index,
                  arc_unavailability_observed_value,
                  (arc_unavailability_value_finite ? "true" : "false"),
                  (arc_unavailability_history_complete ? "true" : "false"));
  }

void PrintV7RR1RequiredSymbolContract(const string stage,
                                     const string symbol)
  {
   PrintFormat("%s V7RR1_CONTRACT stage=%s symbol=%s "
               "contract=%.8f tick_size=%.8f tick_value=%.8f "
               "tick_value_profit=%.8f tick_value_loss=%.8f "
               "volume_min=%.8f volume_step=%.8f stops=%I64d "
               "freeze=%I64d swap_mode=%I64d swap_long=%.8f "
               "swap_short=%.8f rollover3=%I64d sun=%.8f mon=%.8f "
               "tue=%.8f wed=%.8f thu=%.8f fri=%.8f sat=%.8f",
               EXECUTION_VERSION,
               stage,
               symbol,
               SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE),
               SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE),
               SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE),
               SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_PROFIT),
               SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_LOSS),
               SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN),
               SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP),
               SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL),
               SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL),
               SymbolInfoInteger(symbol, SYMBOL_SWAP_MODE),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_LONG),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_SHORT),
               SymbolInfoInteger(symbol, SYMBOL_SWAP_ROLLOVER3DAYS),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_SUNDAY),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_MONDAY),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_TUESDAY),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_WEDNESDAY),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_THURSDAY),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_FRIDAY),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_SATURDAY));
  }


void PrintV7RR1RequiredContracts(const string stage)
  {
   PrintV7RR1RequiredSymbolContract(stage, "US30");
   PrintV7RR1RequiredSymbolContract(stage, "US100");
   PrintV7RR1RequiredSymbolContract(stage, "US500");
  }

