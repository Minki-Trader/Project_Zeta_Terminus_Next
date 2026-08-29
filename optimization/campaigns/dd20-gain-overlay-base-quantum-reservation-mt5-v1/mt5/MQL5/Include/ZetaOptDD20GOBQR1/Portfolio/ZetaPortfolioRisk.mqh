#ifndef ZETA_OPT_DD20_GOBQR1_PORTFOLIO_RISK_MQH
#define ZETA_OPT_DD20_GOBQR1_PORTFOLIO_RISK_MQH

// Behavior-preserving function extraction from B70 V6R6: Portfolio\ZetaPortfolioRisk.mqh

bool NewEntriesAuthorized()
  {
   if(tester_mode)
      return(true);
   return(InpAllowNewEntries &&
          TerminalInfoInteger(TERMINAL_CONNECTED) &&
          LiveAccountIdentityCompatible() &&
          TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) &&
          MQLInfoInteger(MQL_TRADE_ALLOWED) &&
          AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) &&
          AccountInfoInteger(ACCOUNT_TRADE_EXPERT));
  }


bool NewEntriesOperationallyAllowed()
  {
   return(NewEntriesAuthorized() &&
          !execution_state.passive_cancel_pending &&
          !portfolio_state.safety_stopped &&
          !persistence_failed &&
          !execution_state.broker_mismatch &&
          !execution_state.foreign_exposure &&
          FPMarketsServerClockCompatible());
  }


double ProjectStageBalance()
  {
   return(InpReferenceCapitalUSD + portfolio_state.project_realized_net);
  }


void UpdateSizingDay()
  {
   const datetime current_day = ServerMidnight();
   if(current_day == portfolio_state.sizing_server_day)
      return;
   portfolio_state.sizing_server_day = current_day;
   const double growth = MathMax(0.0,
                                 portfolio_state.stressed_balance -
                                 InpReferenceCapitalUSD);
   portfolio_state.day_volume_multiplier =
      1 + (int)MathFloor(growth / InpAdditionStepUSD + 1.0e-9);
   portfolio_state.day_volume_multiplier = MathMax(1, portfolio_state.day_volume_multiplier);
   if(execution_state.runtime_ready)
     {
      RecordEvent(-1,
                  "SIZE_DAY",
                  portfolio_state.stressed_balance,
                  (double)portfolio_state.day_volume_multiplier,
                  TimeToString(current_day, TIME_DATE));
      SaveState();
     }
  }


double NormalizedVolume(const string symbol)
  {
   const double minimum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   const double maximum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0)
      return(0.0);
   const double requested = InpBaseVolume * portfolio_state.day_volume_multiplier;
   const double normalized = MathRound(requested / step) * step;
   if(normalized < minimum || normalized > maximum)
      return(0.0);
   return(normalized);
  }


double ConservativeRiskCapital()
  {
   double capital = ProjectStageBalance();
   const double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(capital <= 0.0 || balance <= 0.0 || equity <= 0.0 ||
      portfolio_state.stressed_balance <= 0.0)
      return(0.0);
   capital = MathMin(capital, balance);
   capital = MathMin(capital, equity);
   capital = MathMin(capital, portfolio_state.stressed_balance);
   return(capital);
  }


double TrackedAggregatePlannedRisk()
  {
   double risk = MathMax(0.0, passive_pending_planned_risk_usd);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      risk += MathMax(0.0, component_states[component].entry_planned_risk_usd);
   return(risk);
  }


double MinimumProtectionDistance(const string symbol)
  {
   const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   const double tick_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   const long stops_level =
      SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
   const long freeze_level =
      SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   return(MathMax(tick_size,
                  (double)MathMax(stops_level, freeze_level) * point));
  }


bool GrossStopRisk(const string symbol,
                   const int direction,
                   const double volume,
                   const double entry_price,
                   const double stop_loss,
                   double &gross_risk)
  {
   gross_risk = 0.0;
   if(direction == 0 || volume <= 0.0 || entry_price <= 0.0 ||
      stop_loss <= 0.0 ||
      (direction > 0 && stop_loss >= entry_price) ||
      (direction < 0 && stop_loss <= entry_price))
      return(false);
   const double contract_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   const double direct_usd_risk =
      MathAbs(entry_price - stop_loss) * contract_size * volume;
   if(contract_size <= 0.0 || !MathIsValidNumber(direct_usd_risk) ||
      direct_usd_risk <= 0.0)
      return(false);
   double profit = 0.0;
   const ENUM_ORDER_TYPE order_type =
      (direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   const bool broker_risk_known =
      OrderCalcProfit(order_type,
                      symbol,
                      volume,
                      entry_price,
                      stop_loss,
                      profit);
   if(broker_risk_known &&
      (!MathIsValidNumber(profit) || profit > 1.0e-9))
      return(false);
   // FPMarkets' tester can decline or round a one-tick loss calculation.
   // The startup contract fixes a USD profit currency and unit contract size,
   // so the direct linear loss remains valid and is never smaller than a
   // broker value when one is available.
   gross_risk = MathMax(direct_usd_risk,
                        (broker_risk_known ? MathMax(0.0, -profit) : 0.0));
   return(gross_risk > 0.0);
  }


bool BufferedPlannedRisk(const string symbol,
                         const int direction,
                         const double volume,
                         const double entry_price,
                         const double stop_loss,
                         double &planned_risk)
  {
   planned_risk = 0.0;
   double gross_risk = 0.0;
   if(!GrossStopRisk(symbol,
                     direction,
                     volume,
                     entry_price,
                     stop_loss,
                     gross_risk))
      return(false);
   const double modeled_fraction =
      1.0 - InpUnmodelledRiskReserveFraction;
   if(modeled_fraction <= 0.0)
      return(false);
   planned_risk = gross_risk / modeled_fraction;
   return(MathIsValidNumber(planned_risk) && planned_risk > 0.0);
  }


bool StopRiskAtTicks(const string symbol,
                     const int direction,
                     const double volume,
                     const double entry_price,
                     const double tick_size,
                     const int digits,
                     const long ticks,
                     double &candidate_stop,
                     double &gross_risk)
  {
   candidate_stop = 0.0;
   gross_risk = 0.0;
   if(ticks < 1)
      return(false);
   const double raw_stop =
      entry_price - (double)direction * (double)ticks * tick_size;
   const double units = raw_stop / tick_size;
   candidate_stop =
      NormalizeDouble((direction > 0
                       ? MathFloor(units + 1.0e-9) * tick_size
                       : MathCeil(units - 1.0e-9) * tick_size),
                      digits);
   if(candidate_stop <= 0.0 ||
      (direction > 0 && candidate_stop >= entry_price) ||
      (direction < 0 && candidate_stop <= entry_price))
      return(false);
   const double contract_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   const double direct_usd_risk =
      MathAbs(entry_price - candidate_stop) * contract_size * volume;
   if(contract_size <= 0.0 || !MathIsValidNumber(direct_usd_risk) ||
      direct_usd_risk <= 0.0)
      return(false);
   double profit = 0.0;
   const ENUM_ORDER_TYPE order_type =
      (direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   const bool broker_risk_known =
      OrderCalcProfit(order_type,
                      symbol,
                      volume,
                      entry_price,
                      candidate_stop,
                      profit);
   if(broker_risk_known &&
      (!MathIsValidNumber(profit) || profit > 1.0e-9))
      return(false);
   gross_risk = MathMax(direct_usd_risk,
                        (broker_risk_known ? MathMax(0.0, -profit) : 0.0));
   return(true);
  }


void ResetComponentEquityState()
  {
   component_equity_state_faults = 0;
   gain_overlay_reserve_evaluations = 0;
   gain_overlay_reserve_bindings = 0;
   gain_overlay_reserve_steps_removed = 0;
   gain_overlay_reserve_neutral_floor_preserved = 0;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      component_equity_state_count[component] = 0;
      component_equity_state_next[component] = 0;
      component_equity_state_full_closes[component] = 0;
      component_equity_state_partial_exits[component] = 0;
      component_equity_state_volume_evaluations[component] = 0;
      component_equity_state_loss_evaluations[component] = 0;
      component_equity_state_neutral_evaluations[component] = 0;
      component_equity_state_gain_evaluations[component] = 0;
      component_equity_lifecycle_identifier[component] = 0;
      component_equity_lifecycle_original_planned_risk[component] = 0.0;
      component_equity_lifecycle_stressed_net[component] = 0.0;
      for(int observation = 0;
          observation < COMPONENT_EQUITY_STATE_MAX_LOOKBACK;
          ++observation)
         component_equity_state_r[component][observation] = 0.0;
     }
  }


double ComponentBaseWeight(const int component)
  {
   if(component == RC16_LONG)
      return(InpRC16BaseWeight);
   if(component == RC4_BOTH)
      return(InpRC4BaseWeight);
   if(component == US100_CROSS)
      return(InpUS100CrossBaseWeight);
   if(component == US30_PRESSURE)
      return(InpUS30PressureBaseWeight);
   if(component == US30_RETURN_REV_LONG)
      return(InpUS30ReturnBaseWeight);
   if(component == US100_PASSIVE_LIMIT)
      return(InpUS100PassiveBaseWeight);
   return(-1.0);
  }


double ComponentEquityStateMeanR(const int component)
  {
   if(component < 0 || component >= COMPONENT_COUNT ||
      component_equity_state_count[component] <= 0)
      return(0.0);
   double total = 0.0;
   for(int observation = 0;
       observation < component_equity_state_count[component];
       ++observation)
      total += component_equity_state_r[component][observation];
   return(total / (double)component_equity_state_count[component]);
  }


double ComponentEquityStateOverlay(const int component)
  {
   if(component < 0 || component >= COMPONENT_COUNT)
      return(-1.0);
   if(component_equity_state_count[component] < InpComponentStateLookback)
      return(1.0);
   const double mean_r = ComponentEquityStateMeanR(component);
   if(mean_r < -InpComponentStateMeanBandR)
      return(InpComponentStateLossOverlay);
   if(mean_r > InpComponentStateMeanBandR)
      return(InpComponentStateGainOverlay);
   return(1.0);
  }


double ComponentEffectiveWeight(const int component)
  {
   const double base_weight = ComponentBaseWeight(component);
   const double overlay = ComponentEquityStateOverlay(component);
   if(!MathIsValidNumber(base_weight) || !MathIsValidNumber(overlay) ||
      base_weight < 0.0 || overlay < 0.0)
      return(-1.0);
   return(base_weight * overlay);
  }


double NormalizedComponentVolume(const int component, const string symbol)
  {
   const double overlay = ComponentEquityStateOverlay(component);
   const double base_weight = ComponentBaseWeight(component);
   const double effective_weight = ComponentEffectiveWeight(component);
   const double minimum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   const double maximum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(component >= 0 && component < COMPONENT_COUNT)
     {
      ++component_equity_state_volume_evaluations[component];
      if(overlay < 1.0 - 1.0e-9)
         ++component_equity_state_loss_evaluations[component];
      else if(overlay > 1.0 + 1.0e-9)
         ++component_equity_state_gain_evaluations[component];
      else
         ++component_equity_state_neutral_evaluations[component];
     }
   if(!MathIsValidNumber(base_weight) ||
      !MathIsValidNumber(effective_weight) ||
      base_weight < 0.0 || effective_weight <= 0.0 || step <= 0.0)
      return(0.0);

   const double gain_requested =
      InpBaseVolume * portfolio_state.day_volume_multiplier * effective_weight;
   double selected = MathRound(gain_requested / step) * step;
   const double neutral_requested =
      InpBaseVolume * portfolio_state.day_volume_multiplier * base_weight;
   const double neutral = MathRound(neutral_requested / step) * step;

   if(overlay > 1.0 + 1.0e-9 && selected > neutral + 0.5 * step)
     {
      ++gain_overlay_reserve_evaluations;
      const double capital = ConservativeRiskCapital();
      const double base_volume = NormalizedVolume(symbol);
      const double aggregate_before = TrackedAggregatePlannedRisk();
      const double aggregate_budget =
         capital * InpMaximumAggregateRiskFraction;
      const double reserve =
         capital * InpGainOverlayBaseQuantumReserveFraction;
      const double available_for_candidate =
         MathMax(0.0, aggregate_budget - reserve - aggregate_before);
      const double position_quantum =
         capital * InpMaximumPositionRiskFraction;
      if(capital > 0.0 && base_volume > 0.0 && position_quantum > 0.0)
        {
         const double maximum_multiplier =
            available_for_candidate / position_quantum;
         const double maximum_raw_volume =
            base_volume * maximum_multiplier;
         const double maximum_executable =
            MathFloor(maximum_raw_volume / step + 1.0e-9) * step;
         if(maximum_executable < neutral - 0.5 * step)
            ++gain_overlay_reserve_neutral_floor_preserved;
         const double clamped =
            MathMax(neutral, MathMin(selected, maximum_executable));
         if(clamped < selected - 0.5 * step)
           {
            ++gain_overlay_reserve_bindings;
            gain_overlay_reserve_steps_removed +=
               (long)MathRound((selected - clamped) / step);
            RecordEvent(component,
                        "GAIN_OVERLAY_RESERVE_BIND",
                        selected,
                        clamped,
                        StringFormat("neutral=%.2f aggregate_before=%.4f reserve=%.4f",
                                     neutral,
                                     aggregate_before,
                                     reserve));
            selected = clamped;
           }
        }
     }

   if(selected < minimum || selected > maximum)
      return(0.0);
   return(selected);
  }


double ExecutableComponentVolumeMultiplier(const int component,
                                           const string symbol,
                                           const double volume)
  {
   if(ComponentEffectiveWeight(component) <= 0.0 || volume <= 0.0)
      return(0.0);
   const double base_volume = NormalizedVolume(symbol);
   if(base_volume <= 0.0)
      return(0.0);
   const double multiplier = volume / base_volume;
   return(MathIsValidNumber(multiplier) && multiplier > 0.0
          ? multiplier : 0.0);
  }


void ObserveComponentEquityExit(const ResearchExitSnapshot &snapshot)
  {
   const int component = snapshot.component;
   if(component < 0 || component >= COMPONENT_COUNT ||
      snapshot.position_identifier == 0 ||
      !MathIsValidNumber(snapshot.stressed_net) ||
      !MathIsValidNumber(snapshot.entry_planned_risk_usd) ||
      snapshot.entry_planned_risk_usd <= 0.0)
     {
      ++component_equity_state_faults;
      return;
     }

   if(component_equity_lifecycle_identifier[component] == 0)
     {
      component_equity_lifecycle_identifier[component] =
         snapshot.position_identifier;
      component_equity_lifecycle_original_planned_risk[component] =
         snapshot.entry_planned_risk_usd;
      component_equity_lifecycle_stressed_net[component] = 0.0;
     }
   else if(component_equity_lifecycle_identifier[component] !=
           snapshot.position_identifier)
     {
      ++component_equity_state_faults;
      component_equity_lifecycle_identifier[component] =
         snapshot.position_identifier;
      component_equity_lifecycle_original_planned_risk[component] =
         snapshot.entry_planned_risk_usd;
      component_equity_lifecycle_stressed_net[component] = 0.0;
     }

   component_equity_lifecycle_stressed_net[component] +=
      snapshot.stressed_net;
   if(!snapshot.full_exit)
     {
      ++component_equity_state_partial_exits[component];
      return;
     }

   const double original_planned_risk =
      component_equity_lifecycle_original_planned_risk[component];
   if(!MathIsValidNumber(original_planned_risk) ||
      original_planned_risk <= 0.0)
     {
      ++component_equity_state_faults;
     }
   else
     {
      const double observation_r =
         component_equity_lifecycle_stressed_net[component] /
         original_planned_risk;
      if(!MathIsValidNumber(observation_r))
        {
         ++component_equity_state_faults;
         component_equity_lifecycle_identifier[component] = 0;
         component_equity_lifecycle_original_planned_risk[component] = 0.0;
         component_equity_lifecycle_stressed_net[component] = 0.0;
         return;
        }
      const int next = component_equity_state_next[component];
      component_equity_state_r[component][next] = observation_r;
      component_equity_state_next[component] =
         (next + 1) % InpComponentStateLookback;
      if(component_equity_state_count[component] <
         InpComponentStateLookback)
         ++component_equity_state_count[component];
      ++component_equity_state_full_closes[component];
     }
   component_equity_lifecycle_identifier[component] = 0;
   component_equity_lifecycle_original_planned_risk[component] = 0.0;
   component_equity_lifecycle_stressed_net[component] = 0.0;
  }


bool CalculateProtectiveStop(const int component,
                             const string symbol,
                             const int direction,
                             const double volume,
                             const double entry_price,
                             const double minimum_distance,
                             double &stop_loss,
                             double &planned_risk)
  {
   stop_loss = 0.0;
   planned_risk = 0.0;
   const double capital = ConservativeRiskCapital();
   const double tick_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   const int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   const double risk_multiplier =
      ExecutableComponentVolumeMultiplier(component, symbol, volume);
   if(!MathIsValidNumber(risk_multiplier) || risk_multiplier < 0.0)
     {
      ++protection_calculation_failures;
      RecordEvent(component,
                  "PROTECTION_CALC_FAIL",
                  risk_multiplier,
                  (double)component,
                  "invalid executable component exposure multiplier");
      return(false);
     }
   if(risk_multiplier <= 1.0e-9)
     {
      ++risk_admission_skips;
      ResearchCaptureAdmissionContext(component,
                                      "COMPONENT_DISABLED",
                                      0.0,
                                      TrackedAggregatePlannedRisk(),
                                      0.0,
                                      capital * InpMaximumAggregateRiskFraction);
      RecordEvent(component,
                  "COMPONENT_DISABLED",
                  risk_multiplier,
                  ComponentEquityStateMeanR(component),
                  "component base weight or causal overlay is zero");
      return(false);
     }
   const double position_budget =
      capital * InpMaximumPositionRiskFraction * risk_multiplier;
   const double target_gross_risk =
      position_budget *
      (1.0 - InpUnmodelledRiskReserveFraction -
       InpStopPlacementHeadroomFraction);
   if(capital <= 0.0 || tick_size <= 0.0 || volume <= 0.0 ||
      entry_price <= 0.0 || minimum_distance <= 0.0 ||
      target_gross_risk <= 0.0)
     {
      ++protection_calculation_failures;
      RecordEvent(component,
                  "PROTECTION_CALC_FAIL",
                  capital,
                  entry_price,
                  "invalid risk or contract input");
      return(false);
     }

   const long minimum_ticks =
      (long)MathCeil(minimum_distance / tick_size - 1.0e-9);
   double minimum_stop = 0.0;
   double minimum_gross_risk = 0.0;
   if(minimum_ticks < 1 ||
      !StopRiskAtTicks(symbol,
                       direction,
                       volume,
                       entry_price,
                       tick_size,
                       digits,
                       minimum_ticks,
                       minimum_stop,
                       minimum_gross_risk))
     {
      ++protection_calculation_failures;
      RecordEvent(component,
                  "PROTECTION_CALC_FAIL",
                  target_gross_risk,
                  minimum_distance,
                  "minimum stop risk unavailable");
      return(false);
     }
   if(minimum_gross_risk > target_gross_risk + 1.0e-9)
     {
      ResearchCaptureAdmissionContext(
         component,
         "RISK_MIN_LOT_SKIP",
         minimum_gross_risk,
         TrackedAggregatePlannedRisk() + minimum_gross_risk,
         position_budget,
         capital * InpMaximumAggregateRiskFraction);
      ++risk_admission_skips;
      RecordEvent(component,
                  "RISK_MIN_LOT_SKIP",
                  position_budget,
                  minimum_gross_risk,
                  StringFormat("min_ticks=%I64d target_gross=%.4f volume=%.2f",
                               minimum_ticks,
                               target_gross_risk,
                               volume));
      return(false);
     }

   long upper_ticks = MathMax((long)1, minimum_ticks);
   double upper_stop = 0.0;
   double upper_gross_risk = 0.0;
   bool bracketed = false;
   for(int expansion = 0; expansion < 50; ++expansion)
     {
      if(!StopRiskAtTicks(symbol,
                          direction,
                          volume,
                          entry_price,
                          tick_size,
                          digits,
                          upper_ticks,
                          upper_stop,
                          upper_gross_risk))
         break;
      if(upper_gross_risk > target_gross_risk + 1.0e-9)
        {
         bracketed = true;
         break;
        }
      if(upper_ticks > 1000000000)
         break;
      upper_ticks *= 2;
     }
   if(!bracketed)
     {
      ++protection_calculation_failures;
      RecordEvent(component,
                  "PROTECTION_CALC_FAIL",
                  target_gross_risk,
                  upper_gross_risk,
                  "stop-risk search could not bracket budget");
      return(false);
     }

   long lower_ticks = minimum_ticks;
   long best_ticks = 0;
   while(lower_ticks <= upper_ticks)
     {
      const long middle_ticks =
         lower_ticks + (upper_ticks - lower_ticks) / 2;
      double middle_stop = 0.0;
      double middle_gross_risk = 0.0;
      if(!StopRiskAtTicks(symbol,
                          direction,
                          volume,
                          entry_price,
                          tick_size,
                          digits,
                          middle_ticks,
                          middle_stop,
                          middle_gross_risk))
        {
         upper_ticks = middle_ticks - 1;
         continue;
        }
      if(middle_gross_risk <= target_gross_risk + 1.0e-9)
        {
         best_ticks = middle_ticks;
         stop_loss = middle_stop;
         lower_ticks = middle_ticks + 1;
        }
      else
         upper_ticks = middle_ticks - 1;
     }
   if(best_ticks < minimum_ticks || stop_loss <= 0.0)
     {
      ++protection_calculation_failures;
      RecordEvent(component,
                  "PROTECTION_CALC_FAIL",
                  target_gross_risk,
                  (double)best_ticks,
                  "stop-risk search found no admissible price");
      return(false);
     }
   const double actual_distance =
      (direction > 0 ? entry_price - stop_loss : stop_loss - entry_price);
   if(actual_distance + 0.25 * tick_size < minimum_distance ||
      !BufferedPlannedRisk(symbol,
                           direction,
                           volume,
                           entry_price,
                           stop_loss,
                           planned_risk))
     {
      ++protection_calculation_failures;
      RecordEvent(component,
                  "PROTECTION_CALC_FAIL",
                  stop_loss,
                  actual_distance,
                  "rounded stop invalid");
      stop_loss = 0.0;
      planned_risk = 0.0;
      return(false);
     }

   const double aggregate_after =
      TrackedAggregatePlannedRisk() + position_budget;
   const double aggregate_budget =
      capital * InpMaximumAggregateRiskFraction;
   const double tolerance = 0.01;
   if(planned_risk > position_budget + tolerance ||
      aggregate_after > aggregate_budget + tolerance)
     {
      ResearchCaptureAdmissionContext(
         component,
         (planned_risk > position_budget + tolerance
          ? "POSITION_RISK_CAP" : "AGGREGATE_RISK_CAP"),
         planned_risk,
         aggregate_after,
         position_budget,
         aggregate_budget);
      ++risk_admission_skips;
      RecordEvent(component,
                  "RISK_ADMISSION_SKIP",
                  planned_risk,
                  aggregate_after,
                  StringFormat("position_cap=%.4f aggregate_cap=%.4f",
                               position_budget,
                               aggregate_budget));
      stop_loss = 0.0;
      planned_risk = 0.0;
      return(false);
     }
   if(aggregate_after > portfolio_state.maximum_aggregate_planned_risk_usd)
      portfolio_state.maximum_aggregate_planned_risk_usd = aggregate_after;
   ResearchCaptureAdmissionContext(component,
                                   "ADMITTED",
                                   planned_risk,
                                   aggregate_after,
                                   position_budget,
                                   aggregate_budget);
   planned_risk = position_budget;
   return(true);
  }


bool StructurallyValidTick(const string symbol, MqlTick &tick)
  {
   if(!SymbolInfoTick(symbol, tick) || tick.ask <= tick.bid || tick.time <= 0)
      return(false);
   return(true);
  }


bool ExecutableTick(const string symbol, MqlTick &tick)
  {
   if(!StructurallyValidTick(symbol, tick))
      return(false);
   const double age_seconds =
      MathAbs((double)((long)TimeCurrent() - (long)tick.time));
   return(age_seconds <= MAX_EXECUTABLE_TICK_AGE_SECONDS);
  }


bool CurrentTradeSessionStart(const string symbol,
                              const datetime now,
                              datetime &session_start)
  {
   session_start = 0;
   if(now <= 0)
      return(false);
   MqlDateTime parts = {};
   TimeToStruct(now, parts);
   const ulong seconds_per_day = 86400;
   const ulong time_of_day = (ulong)now % seconds_per_day;
   const datetime midnight = now - (datetime)time_of_day;
   for(uint session = 0; session < 16; ++session)
     {
      datetime from = 0;
      datetime to = 0;
      if(!SymbolInfoSessionTrade(symbol,
                                 (ENUM_DAY_OF_WEEK)parts.day_of_week,
                                 session,
                                 from,
                                 to))
         break;
      const ulong session_from = (ulong)from;
       const ulong session_to = (ulong)to;
       if(session_to > session_from &&
          time_of_day >= session_from && time_of_day < session_to)
         {
          session_start = midnight + (datetime)session_from;
          return(true);
         }
       if(session_to < session_from &&
          (time_of_day >= session_from || time_of_day < session_to))
         {
          session_start =
             (time_of_day >= session_from
              ? midnight + (datetime)session_from
              : midnight - 86400 + (datetime)session_from);
          return(true);
         }
     }
   return(false);
  }


bool TradeSessionAllows(const string symbol,
                        const datetime now,
                        const bool opening)
  {
   datetime session_start = 0;
   if(!CurrentTradeSessionStart(symbol, now, session_start))
      return(false);
   const ENUM_SYMBOL_TRADE_MODE mode =
      (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE);
   if(opening)
      return(mode == SYMBOL_TRADE_MODE_FULL);
   return(mode != SYMBOL_TRADE_MODE_DISABLED);
  }


bool MarginAllows(const string symbol,
                   const int direction,
                   const double volume)
  {
   MqlTick tick = {};
   if(!ExecutableTick(symbol, tick))
      return(false);
   const ENUM_ORDER_TYPE order_type =
      (direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   const double price = (direction > 0 ? tick.ask : tick.bid);
   double required_margin = 0.0;
   if(!OrderCalcMargin(order_type,
                       symbol,
                       volume,
                       price,
                       required_margin))
      return(false);
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   const double projected_margin =
      AccountInfoDouble(ACCOUNT_MARGIN) + required_margin;
   if(equity <= 0.0 ||
      projected_margin > equity * InpMaximumMarginFraction)
     {
      PrintFormat("%s margin skip symbol=%s required=%.2f projected=%.2f "
                  "equity=%.2f limit=%.2f",
                  EXECUTION_VERSION,
                  symbol,
                  required_margin,
                  projected_margin,
                  equity,
                  InpMaximumMarginFraction);
      return(false);
     }
   return(true);
  }


bool PassiveMarginAllows(const int direction, const double limit_price)
  {
   const ENUM_ORDER_TYPE order_type =
      (direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   double required_margin = 0.0;
   if(!OrderCalcMargin(order_type,
                       "US100",
                       InpBaseVolume,
                       limit_price,
                       required_margin) || required_margin <= 0.0)
     {
      ++passive_margin_calculation_failures;
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_MARGIN_CALC_FAIL",
                  (double)direction,
                  limit_price,
                  IntegerToString(GetLastError()));
      return(false);
     }
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   const double projected_margin =
      AccountInfoDouble(ACCOUNT_MARGIN) + required_margin;
   if(equity <= 0.0 ||
      projected_margin > equity * InpMaximumMarginFraction)
     {
      ++passive_margin_skips;
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_MARGIN_SKIP",
                  projected_margin,
                  equity,
                  DoubleToString(required_margin, 4));
      return(false);
     }
   return(true);
  }


void UpdateAccountRisk()
  {
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > portfolio_state.account_peak_equity)
      portfolio_state.account_peak_equity = equity;
   if(portfolio_state.account_peak_equity <= 0.0)
      return;
   const double drawdown = portfolio_state.account_peak_equity - equity;
   if(drawdown > portfolio_state.account_maximum_drawdown)
      portfolio_state.account_maximum_drawdown = drawdown;
  }


#endif
