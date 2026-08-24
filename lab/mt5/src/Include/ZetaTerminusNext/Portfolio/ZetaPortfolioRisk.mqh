#ifndef ZETA_NEXT_MODULE_09_MQH
#define ZETA_NEXT_MODULE_09_MQH

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
   int next_multiplier =
      1 + (int)MathFloor(growth / InpAdditionStepUSD + 1.0e-9);
#ifdef ZETA_FRONTIER_VOLUME_MULTIPLIER
   next_multiplier =
      ZETA_FRONTIER_VOLUME_MULTIPLIER(current_day,
                                      portfolio_state.stressed_balance,
                                      next_multiplier,
                                      portfolio_state.day_volume_multiplier);
#endif
   portfolio_state.day_volume_multiplier = MathMax(1, next_multiplier);
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
   const double position_budget =
      capital * InpMaximumPositionRiskFraction;
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

   double aggregate_after =
      TrackedAggregatePlannedRisk() + position_budget;
   const double aggregate_budget =
      capital * InpMaximumAggregateRiskFraction;
   const double tolerance = 0.01;
#ifdef ZETA_FRONTIER_RISK_ADMISSION_EXCHANGE
   if(planned_risk <= position_budget + tolerance &&
      aggregate_after > aggregate_budget + tolerance &&
      ZETA_FRONTIER_RISK_ADMISSION_EXCHANGE(component,
                                            symbol,
                                            direction,
                                            volume,
                                            entry_price,
                                            position_budget,
                                            aggregate_after,
                                            aggregate_budget))
     {
      stop_loss = 0.0;
      planned_risk = 0.0;
      return(CalculateProtectiveStop(component,
                                     symbol,
                                     direction,
                                     volume,
                                     entry_price,
                                     minimum_distance,
                                     stop_loss,
                                     planned_risk));
     }
#endif
   if(planned_risk > position_budget + tolerance ||
      aggregate_after > aggregate_budget + tolerance)
     {
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


bool PassiveMarginAllows(const int direction,
                         const double limit_price,
                         const double volume)
  {
   const ENUM_ORDER_TYPE order_type =
      (direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   double required_margin = 0.0;
   if(!OrderCalcMargin(order_type,
                       "US100",
                       volume,
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
