#ifndef ZETA_OPT_DD20_H4SO1_MODULE_08_MQH
#define ZETA_OPT_DD20_H4SO1_MODULE_08_MQH

// Behavior-preserving function extraction from B70 V6R6: Strategies\ZetaPassive.mqh

double SampleStandardDeviation(const double &values[],
                               const int start,
                               const int count)
  {
   if(count < 2 || start < 0 || start + count > ArraySize(values))
      return(0.0);
   double mean = 0.0;
   for(int offset = 0; offset < count; ++offset)
      mean += values[start + offset];
   mean /= count;
   double squared = 0.0;
   for(int offset = 0; offset < count; ++offset)
     {
      const double deviation = values[start + offset] - mean;
      squared += deviation * deviation;
     }
   return(MathSqrt(squared / (count - 1)));
  }


bool CalculatePassiveState(double &state,
                           double &range_scale,
                           double &decision_close)
  {
   const int close_count = PASSIVE_SCALE_RETURNS + 2;
   double closes[];
   ArraySetAsSeries(closes, false);
   if(CopyClose("US100", PERIOD_M15, 1, close_count, closes) !=
      close_count)
      return(false);
   double returns[];
   ArrayResize(returns, PASSIVE_SCALE_RETURNS);
   for(int index = 0; index < PASSIVE_SCALE_RETURNS; ++index)
     {
      if(closes[index] <= 0.0 || closes[index + 1] <= 0.0)
         return(false);
      returns[index] = MathLog(closes[index + 1] / closes[index]);
     }
   const double standard_deviation =
      SampleStandardDeviation(returns, 0, PASSIVE_SCALE_RETURNS);
   const int latest = close_count - 1;
   const int earlier = latest - PASSIVE_LOOKBACK;
   if(standard_deviation <= 0.0 || earlier < 0 ||
      closes[earlier] <= 0.0)
      return(false);
   state = MathLog(closes[latest] / closes[earlier]) /
           (standard_deviation * MathSqrt((double)PASSIVE_LOOKBACK));
   decision_close = closes[latest];

   double highs[];
   double lows[];
   ArraySetAsSeries(highs, false);
   ArraySetAsSeries(lows, false);
   if(CopyHigh("US100",
               PERIOD_M15,
               2,
               PASSIVE_SCALE_RETURNS,
               highs) != PASSIVE_SCALE_RETURNS ||
      CopyLow("US100",
              PERIOD_M15,
              2,
              PASSIVE_SCALE_RETURNS,
              lows) != PASSIVE_SCALE_RETURNS)
      return(false);
   double ranges[];
   ArrayResize(ranges, PASSIVE_SCALE_RETURNS);
   for(int index = 0; index < PASSIVE_SCALE_RETURNS; ++index)
     {
      if(highs[index] <= lows[index] || lows[index] <= 0.0)
         return(false);
      ranges[index] = highs[index] - lows[index];
     }
   range_scale = Median(ranges);
   return(range_scale > 0.0 && MathIsValidNumber(state));
  }


double PassiveLimitPrice(const double raw_price, const int direction)
  {
   const double tick_size =
      SymbolInfoDouble("US100", SYMBOL_TRADE_TICK_SIZE);
   const int digits = (int)SymbolInfoInteger("US100", SYMBOL_DIGITS);
   if(tick_size <= 0.0)
      return(0.0);
   const double units = raw_price / tick_size;
   const double rounded =
      (direction > 0
       ? MathFloor(units + 1.0e-10) * tick_size
       : MathCeil(units - 1.0e-10) * tick_size);
   return(NormalizeDouble(rounded, digits));
  }


bool PassiveDecisionSessionAllows(const datetime decision_bar)
  {
   MqlDateTime parts = {};
   TimeToStruct(decision_bar, parts);
   return(parts.hour >= 12 && parts.hour < 16);
  }


bool PlacePassiveLimit(const int direction,
                       const double state,
                       const double limit_price,
                       const datetime expiration)
  {
   if(direction == 0 || expiration <= TimeCurrent() ||
      !NewEntriesOperationallyAllowed())
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "ENTRY_BLOCKED";
      return(false);
     }
   if(!AuditPositionOwnership() || execution_state.foreign_exposure)
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "OWNERSHIP_BLOCKED";
      return(false);
     }
   ulong position_ticket = 0;
   datetime opened_at = 0;
   ulong order_ticket = 0;
   if(CountOwnedPositions(US100_PASSIVE_LIMIT,
                          position_ticket,
                          opened_at) != 0 ||
      CountOwnedPassiveOrders(order_ticket) != 0)
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "EXISTING_EXPOSURE";
      return(false);
     }
   MqlTick tick = {};
   if(!ExecutableTick("US100", tick))
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "QUOTE_UNAVAILABLE";
      return(false);
     }
   if(!TradeSessionAllows("US100", TimeCurrent(), true))
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "TRADE_SESSION_BLOCKED";
      return(false);
     }
   component_states[US100_PASSIVE_LIMIT].entry_check_order_price = limit_price;
   component_states[US100_PASSIVE_LIMIT].entry_check_volume = InpBaseVolume;
   if(!PassiveMarginAllows(direction, limit_price))
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "MARGIN_BLOCKED";
      SaveState();
      return(false);
     }
   const double point = SymbolInfoDouble("US100", SYMBOL_POINT);
   const double tick_size =
      SymbolInfoDouble("US100", SYMBOL_TRADE_TICK_SIZE);
   const double stops_distance =
      (double)SymbolInfoInteger("US100", SYMBOL_TRADE_STOPS_LEVEL) * point;
   const double required_distance = MathMax(tick_size, stops_distance);
   if((direction > 0 && tick.bid - limit_price < required_distance) ||
      (direction < 0 && limit_price - tick.ask < required_distance))
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "PRICE_DISTANCE_BLOCKED";
      ++passive_price_constraint_skips;
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_PRICE_SKIP",
                  limit_price,
                  required_distance,
                  StringFormat("direction=%d bid=%.2f ask=%.2f",
                               direction,
                               tick.bid,
                               tick.ask));
      SaveState();
      return(false);
     }

   double stop_loss = 0.0;
   double admitted_planned_risk = 0.0;
   if(!CalculateProtectiveStop(US100_PASSIVE_LIMIT,
                               "US100",
                               direction,
                               InpBaseVolume,
                               limit_price,
                               MathMax(required_distance,
                                       MinimumProtectionDistance("US100")),
                               stop_loss,
                               admitted_planned_risk))
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "PROTECTION_OR_RISK_BLOCKED";
      SaveState();
      return(false);
     }
   component_states[US100_PASSIVE_LIMIT].entry_check_stop_loss = stop_loss;
   component_states[US100_PASSIVE_LIMIT].entry_check_planned_risk_usd =
      admitted_planned_risk;
   const double admitted_capital = ConservativeRiskCapital();
   const double aggregate_before = TrackedAggregatePlannedRisk();

   trade.SetExpertMagicNumber(MAGIC_US100_PASSIVE_LIMIT);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol("US100");
   trade.SetMarginMode();
   trade.SetAsyncMode(false);
   decision_intent.order_type =
      (direction > 0 ? ORDER_TYPE_BUY_LIMIT : ORDER_TYPE_SELL_LIMIT);
   decision_intent.order_type_known = true;
   decision_intent.intended_price = limit_price;
   decision_intent.expiration = expiration;
   decision_intent.volume = InpBaseVolume;
   decision_intent.stop_loss = stop_loss;
   decision_intent.planned_risk_usd = admitted_planned_risk;
   if(!MarkDecisionOrderAttempted(US100_PASSIVE_LIMIT,
                                  direction,
                                  state,
                                  "PASSIVE_LIMIT"))
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "PERSISTENCE_FAILED";
      return(false);
     }
   passive_pending_stop_loss = stop_loss;
   passive_pending_planned_risk_usd = admitted_planned_risk;
   execution_state.trade_operation_active = true;
   const bool requested =
      (direction > 0
       ? trade.BuyLimit(InpBaseVolume,
                        limit_price,
                        "US100",
                        stop_loss,
                        0.0,
                        ORDER_TIME_SPECIFIED,
                        expiration,
                        "ZN 6 V7")
       : trade.SellLimit(InpBaseVolume,
                         limit_price,
                         "US100",
                         stop_loss,
                         0.0,
                         ORDER_TIME_SPECIFIED,
                         expiration,
                         "ZN 6 V7"));
   const uint retcode = trade.ResultRetcode();
   const string retcode_description = trade.ResultRetcodeDescription();
   const ulong returned_order = trade.ResultOrder();
   execution_state.trade_operation_active = false;
   if(!requested || !IsPendingPlacementRetcode(retcode))
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "BROKER_REJECTED";
      passive_pending_stop_loss = 0.0;
      passive_pending_planned_risk_usd = 0.0;
      if(retcode == TRADE_RETCODE_INVALID_PRICE)
        {
         ++passive_stale_price_rejections;
         RecordEvent(US100_PASSIVE_LIMIT,
                      "PASSIVE_STALE_PRICE",
                      limit_price,
                      state,
                      retcode_description);
        }
      else
        {
         ++passive_placement_failures;
         RecordEvent(US100_PASSIVE_LIMIT,
                      "PASSIVE_PLACE_FAIL",
                      (double)retcode,
                      limit_price,
                      retcode_description);
        }
      SaveState();
      return(false);
     }

   order_ticket = 0;
   position_ticket = 0;
   opened_at = 0;
   const int orders = CountOwnedPassiveOrders(order_ticket);
   const int positions =
      CountOwnedPositions(US100_PASSIVE_LIMIT,
                          position_ticket,
                          opened_at);
   if((orders != 1 || positions != 0) &&
      (orders != 0 || positions != 1))
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "SAFETY_STOP";
      execution_state.broker_mismatch = true;
      EngageSafetyStop("passive placement created invalid broker state");
      execution_state.pending_reconcile = true;
      return(true);
     }
   execution_state.passive_pending_order =
      (orders == 1 ? order_ticket : returned_order);
   passive_pending_expiration = expiration;
   passive_pending_direction = direction;
   passive_pending_feature = state;
   passive_pending_limit_price = limit_price;
   ++passive_pending_placements;
   if(orders == 1 && execution_state.passive_pending_order == 0)
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "SAFETY_STOP";
      execution_state.broker_mismatch = true;
      EngageSafetyStop("passive placement lacks order identity");
      execution_state.pending_reconcile = true;
      return(true);
     }
   if(orders == 1)
     {
      string protection_detail = "";
      if(!OrderSelect(order_ticket) ||
         !SelectedPassiveOrderProtectionMatches(protection_detail) ||
         aggregate_before + passive_pending_planned_risk_usd >
         admitted_capital * InpMaximumAggregateRiskFraction +
         MathMax(0.01, passive_pending_planned_risk_usd * 0.01))
        {
         component_states[US100_PASSIVE_LIMIT].entry_check_result = "SAFETY_STOP";
         ++protection_mismatches;
         execution_state.broker_mismatch = true;
         EngageSafetyStop("placed passive protection not confirmed: " +
                          protection_detail);
         CancelPassivePendingOrder(order_ticket,
                                   "post-placement protection mismatch");
         return(true);
        }
     }
   component_states[US100_PASSIVE_LIMIT].entry_check_result =
      (positions == 1 ? "POSITION_OPEN" : "PENDING_ORDER");
   if(positions == 1 &&
      !ReconstructEntryTracking(US100_PASSIVE_LIMIT, position_ticket))
      return(false);
   const ulong adopted_ticket =
      (positions == 1
       ? component_states[US100_PASSIVE_LIMIT].position_identifier
       : execution_state.passive_pending_order);
   if(!MarkDecisionBrokerStateAdopted(US100_PASSIVE_LIMIT,
                                      adopted_ticket,
                                      (positions == 1
                                       ? "POSITION_ADOPTED" :
                                         "PENDING_ORDER_ADOPTED")))
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "SAFETY_STOP";
      EngageSafetyStop("adopted passive broker state could not be persisted");
      MakeExistingRiskSafe("passive adoption journal failure");
      return(true);
     }
   RecordEvent(US100_PASSIVE_LIMIT,
               "PASSIVE_PLACE",
               limit_price,
               state,
               StringFormat("direction=%d expiration=%s order=%I64u stop=%.5f planned_risk=%.4f",
                            direction,
                            TimeToString(expiration,
                                         TIME_DATE | TIME_MINUTES),
                            (positions == 1
                             ? returned_order :
                               execution_state.passive_pending_order),
                            stop_loss,
                            admitted_planned_risk));
   return(SaveState());
  }


void ProcessPassiveLimit()
  {
   if(ComponentEffectiveWeight(US100_PASSIVE_LIMIT) <= 1.0e-9)
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result =
         "COMPONENT_DISABLED";
      return;
     }
   const datetime current_bar = iTime("US100", PERIOD_M15, 0);
   if(current_bar == 0)
      return;
   ulong position_ticket = 0;
   datetime opened_at = 0;
   ulong order_ticket = 0;
   const int positions =
      CountOwnedPositions(US100_PASSIVE_LIMIT,
                          position_ticket,
                          opened_at);
   const int orders = CountOwnedPassiveOrders(order_ticket);
   if(positions > 1 || orders > 1 ||
      (positions == 1 && orders == 1))
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("invalid passive broker multiplicity");
      return;
     }
   if(positions == 1)
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "POSITION_OPEN";
      if(component_states[US100_PASSIVE_LIMIT].position_identifier == 0 &&
         !ReconstructEntryTracking(US100_PASSIVE_LIMIT, position_ticket))
         return;
      if(component_states[US100_PASSIVE_LIMIT].last_decision_bar == current_bar)
         return;
      double state = 0.0;
      double range_scale = 0.0;
      double decision_close = 0.0;
      if(!CalculatePassiveState(state, range_scale, decision_close))
         return;
      if(!PositionSelectByTicket(position_ticket))
         return;
      const ENUM_POSITION_TYPE position_type =
         (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      const int direction =
         (position_type == POSITION_TYPE_BUY ? 1 : -1);
      const int desired_direction =
         (state > 0.0 ? -1 : (state < 0.0 ? 1 : 0));
      const int held_bars =
         iBarShift("US100", PERIOD_M15, opened_at, false);
      const bool should_close =
         (held_bars >= PASSIVE_MAXIMUM_HOLD_BARS ||
          MathAbs(state) <= PASSIVE_EXIT_STRENGTH ||
          (desired_direction != 0 && desired_direction != direction));
      if(!should_close)
        {
         component_states[US100_PASSIVE_LIMIT].last_decision_bar = current_bar;
         return;
        }
      if(CloseComponent(US100_PASSIVE_LIMIT, position_ticket))
        {
         component_states[US100_PASSIVE_LIMIT].last_decision_bar = current_bar;
         passive_next_entry_current_bar =
            current_bar + 2 * PASSIVE_BAR_SECONDS;
         SaveState();
        }
      return;
     }

   if(orders == 1)
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "PENDING_ORDER";
      if(execution_state.passive_pending_order == 0 ||
         execution_state.passive_pending_order != order_ticket)
        {
         execution_state.broker_mismatch = true;
         EngageSafetyStop("passive broker order lacks local state");
         CancelPassivePendingOrder(order_ticket,
                                   "missing or mismatched local state");
         return;
        }
      if(!NewEntriesOperationallyAllowed())
         CancelPassivePendingOrder(order_ticket,
                                   "new entries not authorized");
      return;
     }
   if(execution_state.passive_pending_order > 0 &&
      !HandleMissingPassivePendingOrder())
      return;
   if(component_states[US100_PASSIVE_LIMIT].last_decision_bar == current_bar)
      return;
   BeginEntryCheck(US100_PASSIVE_LIMIT, current_bar, "CHECKING_SIGNAL");
   if(current_bar < passive_next_entry_current_bar)
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "COOLDOWN";
      component_states[US100_PASSIVE_LIMIT].last_decision_bar = current_bar;
      return;
     }
   if(TimeCurrent() - current_bar >
      InpMaxEntryDelayMinutes * 60)
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "ENTRY_DELAY_EXCEEDED";
      component_states[US100_PASSIVE_LIMIT].last_decision_bar = current_bar;
      return;
     }
   const datetime decision_bar = iTime("US100", PERIOD_M15, 1);
   if(decision_bar == 0 ||
      current_bar - decision_bar != PASSIVE_BAR_SECONDS ||
      !PassiveDecisionSessionAllows(decision_bar))
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "OUTSIDE_DECISION_SESSION";
      component_states[US100_PASSIVE_LIMIT].last_decision_bar = current_bar;
      return;
     }
   if(passive_last_feature_attempt_bar == current_bar &&
      TimeCurrent() - passive_last_feature_attempt_server < 5)
      return;
   passive_last_feature_attempt_bar = current_bar;
   passive_last_feature_attempt_server = TimeCurrent();
   double state = 0.0;
   double range_scale = 0.0;
   double decision_close = 0.0;
   if(!CalculatePassiveState(state, range_scale, decision_close))
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "DATA_UNAVAILABLE";
      return;
     }
   const bool signal_passed =
      (MathAbs(state) >= PASSIVE_ENTRY_STRENGTH);
   const int signal_direction =
      (signal_passed ? (state > 0.0 ? -1 : 1) : 0);
   SetEntrySignalCheck(US100_PASSIVE_LIMIT,
                       state,
                       signal_passed,
                       signal_direction,
                       (signal_passed
                        ? "SIGNAL_MET_ORDER_CHECK"
                        : "SIGNAL_NOT_MET"));
   if(!signal_passed)
     {
      component_states[US100_PASSIVE_LIMIT].last_decision_bar = current_bar;
      ResearchRecordCandidateOutcome(
         US100_PASSIVE_LIMIT,
         "SIGNAL",
         component_states[US100_PASSIVE_LIMIT].entry_check_result,
         "passive signal evaluation completed without an order path");
      return;
     }
   component_states[US100_PASSIVE_LIMIT].last_decision_bar = current_bar;
   if(!NewEntriesOperationallyAllowed())
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "ENTRY_BLOCKED";
      return;
     }
   const int direction = signal_direction;
   const double raw_limit =
      decision_close -
      direction * PASSIVE_LIMIT_OFFSET_RANGE_SCALE * range_scale;
   const double limit_price = PassiveLimitPrice(raw_limit, direction);
   if(limit_price <= 0.0)
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "LIMIT_PRICE_INVALID";
      return;
     }
   component_states[US100_PASSIVE_LIMIT].entry_check_order_price = limit_price;
   component_states[US100_PASSIVE_LIMIT].entry_check_volume = InpBaseVolume;
   const datetime expiration =
      current_bar + PASSIVE_ACTIVATION_BARS * PASSIVE_BAR_SECONDS;
   if(!PersistDecisionUntil(US100_PASSIVE_LIMIT,
                            current_bar,
                            expiration))
     {
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "PERSISTENCE_FAILED";
      return;
     }
   PlacePassiveLimit(direction, state, limit_price, expiration);
   if(!FinalizeDecisionJournal(US100_PASSIVE_LIMIT,
                               component_states[US100_PASSIVE_LIMIT].entry_check_result))
      component_states[US100_PASSIVE_LIMIT].entry_check_result = "PERSISTENCE_FAILED";
  }


#endif
