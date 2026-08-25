#ifndef ZETA_NEXT_MODULE_12_MQH
#define ZETA_NEXT_MODULE_12_MQH

// Behavior-preserving function extraction from B70 V6R6: Execution\ZetaProtectionAndReconciliation.mqh

bool SelectedPositionProtectionMatches(const int component,
                                       string &detail)
  {
   detail = "";
   const string symbol = PositionGetString(POSITION_SYMBOL);
   const ENUM_POSITION_TYPE type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   const int direction =
      (type == POSITION_TYPE_BUY ? 1 :
       (type == POSITION_TYPE_SELL ? -1 : 0));
   const double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
   const double volume = PositionGetDouble(POSITION_VOLUME);
   const double broker_stop = PositionGetDouble(POSITION_SL);
   double expected_stop = component_states[component].entry_stop_loss;
   double admitted_risk = component_states[component].entry_planned_risk_usd;
   if(component == US100_PASSIVE_LIMIT && expected_stop <= 0.0 &&
      execution_state.passive_pending_order > 0)
     {
      expected_stop = passive_pending_stop_loss;
      admitted_risk = passive_pending_planned_risk_usd;
     }
   const double tick_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   const bool pending_arc_modify =
      (component == RC4_BOTH &&
       (execution_state.arc_modify_pending || execution_state.arc_modify_retry_pending) &&
       arc_pending_stop_loss > 0.0);
   const bool stop_matches_saved =
      (tick_size > 0.0 && expected_stop > 0.0 &&
       MathAbs(broker_stop - expected_stop) <=
       0.5 * tick_size + 1.0e-9);
   const bool stop_matches_pending =
      (pending_arc_modify && tick_size > 0.0 &&
       MathAbs(broker_stop - arc_pending_stop_loss) <=
       0.5 * tick_size + 1.0e-9);
   if(direction == 0 || open_price <= 0.0 || volume <= 0.0 ||
      tick_size <= 0.0 || broker_stop <= 0.0 || expected_stop <= 0.0 ||
      admitted_risk <= 0.0 ||
      (direction > 0 && broker_stop >= open_price) ||
      (direction < 0 && broker_stop <= open_price) ||
      (!stop_matches_saved && !stop_matches_pending))
     {
      detail = StringFormat("invalid stop component=%d open=%.5f broker=%.5f expected=%.5f pending=%.5f",
                            component,
                            open_price,
                            broker_stop,
                            expected_stop,
                            arc_pending_stop_loss);
      return(false);
     }
   double actual_risk = 0.0;
   if(!BufferedPlannedRisk(symbol,
                           direction,
                           volume,
                           open_price,
                           broker_stop,
                           actual_risk) ||
      actual_risk > admitted_risk + MathMax(0.01, admitted_risk * 0.01))
     {
      detail = StringFormat("risk mismatch component=%d actual=%.4f admitted=%.4f",
                            component,
                            actual_risk,
                            admitted_risk);
      return(false);
     }
   return(true);
  }


bool SelectedPassiveOrderProtectionMatches(string &detail)
  {
   detail = "";
   const ENUM_ORDER_TYPE type =
      (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
   const int direction =
      (type == ORDER_TYPE_BUY_LIMIT ? 1 :
       (type == ORDER_TYPE_SELL_LIMIT ? -1 : 0));
   const double price = OrderGetDouble(ORDER_PRICE_OPEN);
   const double volume = OrderGetDouble(ORDER_VOLUME_CURRENT);
   const double broker_stop = OrderGetDouble(ORDER_SL);
   const double tick_size =
      SymbolInfoDouble("US100", SYMBOL_TRADE_TICK_SIZE);
   if(direction == 0 || price <= 0.0 || volume <= 0.0 || tick_size <= 0.0 ||
      broker_stop <= 0.0 || passive_pending_stop_loss <= 0.0 ||
      passive_pending_planned_risk_usd <= 0.0 ||
      (direction > 0 && broker_stop >= price) ||
      (direction < 0 && broker_stop <= price) ||
      MathAbs(broker_stop - passive_pending_stop_loss) >
      0.5 * tick_size + 1.0e-9)
     {
      detail = StringFormat("invalid pending stop price=%.5f broker=%.5f expected=%.5f",
                            price,
                            broker_stop,
                            passive_pending_stop_loss);
      return(false);
     }
   double actual_risk = 0.0;
   if(!BufferedPlannedRisk("US100",
                           direction,
                           volume,
                           price,
                           broker_stop,
                           actual_risk) ||
      actual_risk > passive_pending_planned_risk_usd +
                    MathMax(0.01,
                            passive_pending_planned_risk_usd * 0.01))
     {
      detail = StringFormat("pending risk mismatch actual=%.4f admitted=%.4f",
                            actual_risk,
                            passive_pending_planned_risk_usd);
      return(false);
     }
   return(true);
  }


bool HandleMissingPassivePendingOrder()
  {
   if(execution_state.passive_pending_order == 0)
      return(true);
   const ulong order_ticket = execution_state.passive_pending_order;
   if(!HistorySelect(0, TimeCurrent()) ||
      !HistoryOrderSelect(order_ticket))
      return(false);
   const ENUM_ORDER_STATE state =
      (ENUM_ORDER_STATE)HistoryOrderGetInteger(order_ticket, ORDER_STATE);
   if(state == ORDER_STATE_EXPIRED)
     {
      const datetime expiration = passive_pending_expiration;
      const int expired_direction = passive_pending_direction;
      RfdFinalizeExpired(order_ticket,
                         expired_direction,
                         expiration,
                         TimeCurrent());
      ++passive_pending_expirations;
      passive_next_entry_current_bar =
         expiration + PASSIVE_BAR_SECONDS;
      ClearPassivePendingTracking();
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_EXPIRE",
                  (double)order_ticket,
                  (double)passive_next_entry_current_bar,
                  TimeToString(expiration, TIME_DATE | TIME_MINUTES));
      return(SaveState());
     }
   if(state == ORDER_STATE_FILLED || state == ORDER_STATE_PARTIAL)
     {
      return(ReconstructClosedPassiveEntry(order_ticket));
     }
   if(state == ORDER_STATE_CANCELED && execution_state.passive_cancel_pending)
     {
      ClearPassivePendingTracking();
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_CANCEL_RECOVERED",
                  (double)order_ticket,
                  0.0,
                  "persisted cancellation completed before reconciliation");
      return(SaveState());
     }
   ++passive_unexpected_order_outcomes;
   execution_state.broker_mismatch = true;
   EngageSafetyStop("passive pending order disappeared unexpectedly");
   RecordEvent(US100_PASSIVE_LIMIT,
               "PASSIVE_ORDER_MISMATCH",
               (double)order_ticket,
               (double)state,
               "missing order");
   ClearPassivePendingTracking();
   SaveState();
   return(false);
  }


bool DeferPassivePendingCancellation(const ulong order_ticket,
                                     const string reason)
  {
   if(order_ticket == 0 ||
      execution_state.passive_pending_order != order_ticket)
      return(false);
   execution_state.pending_reconcile = true;
   if(execution_state.passive_cancel_pending)
      return(true);
   execution_state.passive_cancel_pending = true;
   ++passive_cancel_connection_deferrals;
   const bool event_written =
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_CANCEL_DEFER",
                  (double)order_ticket,
                  (double)passive_cancel_connection_deferrals,
                  reason);
   const bool state_written = SaveState();
   return(event_written && state_written);
  }


bool CancelPassivePendingOrder(const ulong order_ticket,
                               const string reason)
  {
   if(order_ticket == 0)
      return(false);
   if(!tester_mode && !TerminalInfoInteger(TERMINAL_CONNECTED))
     {
      if(execution_state.passive_pending_order == order_ticket)
         DeferPassivePendingCancellation(
            order_ticket,
            reason + "; terminal disconnected before cancellation");
      return(false);
     }
   trade.SetExpertMagicNumber(MAGIC_US100_PASSIVE_LIMIT);
   trade.SetAsyncMode(false);
   execution_state.trade_operation_active = true;
   const bool requested = trade.OrderDelete(order_ticket);
   const uint retcode = trade.ResultRetcode();
   const string retcode_description = trade.ResultRetcodeDescription();
   execution_state.trade_operation_active = false;
   if(!requested || !IsCompletedTradeRetcode(retcode))
     {
      if(retcode == TRADE_RETCODE_CONNECTION &&
         execution_state.passive_pending_order == order_ticket)
        {
         DeferPassivePendingCancellation(
            order_ticket,
            reason + "; connection lost during cancellation");
         return(false);
        }
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_CANCEL_FAIL",
                  (double)retcode,
                  (double)order_ticket,
                  retcode_description);
      execution_state.broker_mismatch = true;
      EngageSafetyStop("passive pending order could not be cancelled");
      SaveState();
      return(false);
     }
   RecordEvent(US100_PASSIVE_LIMIT,
               "PASSIVE_CANCEL",
               (double)order_ticket,
               0.0,
               reason);
   if(execution_state.passive_pending_order == order_ticket)
      ClearPassivePendingTracking();
   return(SaveState());
  }


bool ReconcilePassivePendingOrder()
  {
   ulong order_ticket = 0;
   const int order_count = CountOwnedPassiveOrders(order_ticket);
   if(order_count > 1)
      return(false);
   if(order_count == 0)
      return(HandleMissingPassivePendingOrder());
   if(!OrderSelect(order_ticket))
      return(false);
   if(execution_state.passive_pending_order == 0 ||
      execution_state.passive_pending_order != order_ticket)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("broker passive order lacks matching local state");
      CancelPassivePendingOrder(order_ticket, "unrecoverable local state");
      return(false);
     }
   const ENUM_ORDER_TYPE type =
      (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
   const int direction =
      (type == ORDER_TYPE_BUY_LIMIT ? 1 :
       (type == ORDER_TYPE_SELL_LIMIT ? -1 : 0));
   const datetime expiration =
      (datetime)OrderGetInteger(ORDER_TIME_EXPIRATION);
   const double price = OrderGetDouble(ORDER_PRICE_OPEN);
   const double volume = OrderGetDouble(ORDER_VOLUME_CURRENT);
   const double stop_loss = OrderGetDouble(ORDER_SL);
   const double tick_size =
      SymbolInfoDouble("US100", SYMBOL_TRADE_TICK_SIZE);
   const double volume_step =
      SymbolInfoDouble("US100", SYMBOL_VOLUME_STEP);
   if(direction != passive_pending_direction ||
      expiration != passive_pending_expiration ||
       MathAbs(price - passive_pending_limit_price) >
       MathMax(1.0e-8, 0.5 * tick_size) ||
       MathAbs(stop_loss - passive_pending_stop_loss) >
       MathMax(1.0e-8, 0.5 * tick_size) ||
       MathAbs(volume - InpBaseVolume) >
      MathMax(1.0e-8, 0.5 * volume_step))
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("broker passive order differs from local state");
      CancelPassivePendingOrder(order_ticket, "broker/local mismatch");
      return(false);
     }
   return(true);
  }


bool ApplyExitDeal(const int component,
                   const ulong deal,
                   const MqlTick &sampled_tick,
                   const bool sampled_tick_known,
                   const string event_name)
  {
   if(deal == 0 || !HistoryDealSelect(deal))
      return(false);
   const long deal_time_msc =
      HistoryDealGetInteger(deal, DEAL_TIME_MSC);
   if(!DealAfterExitCursor(component, deal_time_msc, deal))
      return(true);
   if(component_states[component].position_identifier == 0 ||
      component_states[component].entry_volume <= 0.0 ||
      MathAbs(component_states[component].entry_direction) != 1)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("exit deal lacks recoverable entry state");
      return(false);
     }
   const ENUM_DEAL_ENTRY deal_entry =
      (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
   const ENUM_DEAL_TYPE deal_type =
      (ENUM_DEAL_TYPE)HistoryDealGetInteger(deal, DEAL_TYPE);
   const bool direction_matches =
      (component_states[component].entry_direction > 0
       ? deal_type == DEAL_TYPE_SELL
       : deal_type == DEAL_TYPE_BUY);
   if(deal_time_msc <= 0 ||
      (ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) !=
      component_definitions[component].magic ||
      HistoryDealGetString(deal, DEAL_SYMBOL) !=
      component_definitions[component].symbol ||
      (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID) !=
      component_states[component].position_identifier ||
      (deal_entry != DEAL_ENTRY_OUT && deal_entry != DEAL_ENTRY_OUT_BY) ||
      !direction_matches)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("exit execution identity mismatch");
      return(false);
     }
   const double executed_volume = HistoryDealGetDouble(deal, DEAL_VOLUME);
   const string symbol = component_definitions[component].symbol;
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   long remaining_before_steps = 0;
   long executed_steps = 0;
   if(step <= 0.0 ||
      !VolumeToSteps(symbol,
                     component_states[component].entry_volume,
                     remaining_before_steps) ||
      !VolumeToSteps(symbol, executed_volume, executed_steps) ||
      executed_steps > remaining_before_steps)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("exit execution volume mismatch");
      return(false);
     }
   const long remaining_after_steps =
      remaining_before_steps - executed_steps;
   const double allocation_fraction =
      (remaining_after_steps == 0
       ? 1.0
       : (double)executed_steps / (double)remaining_before_steps);
   const double allocated_entry_transaction_cost =
      (remaining_after_steps == 0
       ? component_states[component].entry_transaction_cost
       : component_states[component].entry_transaction_cost * allocation_fraction);
   const double allocated_entry_adverse_slippage =
      (remaining_after_steps == 0
       ? component_states[component].entry_adverse_slippage
       : component_states[component].entry_adverse_slippage * allocation_fraction);
   MqlTick exit_tick = sampled_tick;
   bool exit_quote_known = sampled_tick_known;
   if(!exit_quote_known)
      exit_quote_known =
         QuoteAtMilliseconds(symbol,
                             deal_time_msc,
                             exit_tick);
   const double exit_transaction_cost =
      HistoryDealGetDouble(deal, DEAL_COMMISSION) +
      HistoryDealGetDouble(deal, DEAL_SWAP) +
      HistoryDealGetDouble(deal, DEAL_FEE);
   const double deal_net =
      HistoryDealGetDouble(deal, DEAL_PROFIT) + exit_transaction_cost +
      allocated_entry_transaction_cost;
   const int direction = component_states[component].entry_direction;
   const double execution_price = HistoryDealGetDouble(deal, DEAL_PRICE);
   const double adverse_exit_price =
      (!exit_quote_known ? 0.0 :
       (direction > 0
        ? MathMax(0.0, exit_tick.bid - execution_price)
        : MathMax(0.0, execution_price - exit_tick.ask)));
   const double contract_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   const double exit_adverse_slippage =
      adverse_exit_price * contract_size * executed_volume;
   const double exit_spread =
      (exit_quote_known ? exit_tick.ask - exit_tick.bid : 0.0);
   const double additional_spread_cost =
      MathMax(component_states[component].entry_spread_price, exit_spread) *
      contract_size * executed_volume;
   const double additional_nonspread_cost =
      allocated_entry_adverse_slippage + exit_adverse_slippage +
      MathMax(0.0, -allocated_entry_transaction_cost) +
      MathMax(0.0, -exit_transaction_cost);
   const double additional_cost =
      additional_spread_cost + additional_nonspread_cost;
   const double stressed_net = deal_net - additional_cost;
   const ENUM_DEAL_REASON exit_reason =
      (ENUM_DEAL_REASON)HistoryDealGetInteger(deal, DEAL_REASON);
   const double admitted_stop_loss = component_states[component].entry_stop_loss;
   const double admitted_planned_risk = component_states[component].entry_planned_risk_usd;
   const ulong completed_identifier = component_states[component].position_identifier;
   const datetime completed_entry_time = component_states[component].entry_time_server;
   const int completed_direction = component_states[component].entry_direction;
   const double completed_arc_original_stop = arc_original_stop_loss;
   const bool completed_arc_request_unresolved =
      (execution_state.arc_modify_pending || execution_state.arc_modify_retry_pending);
   const double completed_arc_protected_stop =
      (component == RC4_BOTH && completed_arc_request_unresolved &&
       arc_pending_stop_loss > 0.0
       ? arc_pending_stop_loss : admitted_stop_loss);
   const bool compressed_rc4_stop_exit =
      (component == RC4_BOTH && remaining_after_steps == 0 &&
       exit_reason == DEAL_REASON_SL &&
       arc_lifecycle_identifier == completed_identifier &&
        (arc_lifecycle_compressed || completed_arc_request_unresolved));
   if(exit_reason == DEAL_REASON_SL)
      component_states[component].lifecycle_stop_loss_seen = true;
   portfolio_state.project_realized_net += deal_net;
   portfolio_state.stressed_balance += stressed_net;
   component_states[component].stressed_net += stressed_net;
   if(portfolio_state.stressed_balance > portfolio_state.stressed_peak)
      portfolio_state.stressed_peak = portfolio_state.stressed_balance;
   const double stressed_drawdown = portfolio_state.stressed_peak - portfolio_state.stressed_balance;
   if(stressed_drawdown > portfolio_state.stressed_maximum_closed_drawdown)
      portfolio_state.stressed_maximum_closed_drawdown = stressed_drawdown;
   component_states[component].last_processed_exit_time_msc = deal_time_msc;
   component_states[component].last_processed_exit_deal = deal;
   const bool complete_cost =
      (component_states[component].entry_cost_known && exit_quote_known);
   RfdRecordReceiverExit(component,
                         completed_identifier,
                         deal_net,
                         stressed_net,
                         remaining_after_steps,
                         deal_time_msc,
                         exit_reason,
                         component_states[component].lifecycle_stop_loss_seen);
   string applied_event = event_name;
   if(remaining_after_steps == 0)
     {
      if(component_states[component].lifecycle_stop_loss_seen)
         ++stop_loss_exits;
      ++component_states[component].closed_trades;
      component_states[component].last_close_attempt_server = 0;
      if(compressed_rc4_stop_exit)
        {
         if(completed_arc_request_unresolved && !arc_lifecycle_compressed &&
            (!exit_quote_known ||
             !ArcOriginalStopReached(completed_direction,
                                     completed_arc_original_stop,
                                     exit_tick)))
            ++arc_compressions_placed;
        }
      else if(component == RC4_BOTH)
         ClearArcLifecycleState();
      ClearEntryTracking(component);
      if(compressed_rc4_stop_exit)
         ActivateRC4ShadowAfterCompressedExit(completed_identifier,
                                              completed_entry_time,
                                              completed_direction,
                                              completed_arc_original_stop,
                                              deal,
                                              deal_time_msc,
                                              execution_price,
                                              exit_reason,
                                              completed_arc_protected_stop,
                                              sampled_tick,
                                              sampled_tick_known);
     }
   else
     {
      const double remaining_fraction =
         (double)remaining_after_steps / (double)remaining_before_steps;
      component_states[component].entry_volume = (double)remaining_after_steps * step;
      component_states[component].entry_transaction_cost -=
         allocated_entry_transaction_cost;
      component_states[component].entry_adverse_slippage -=
         allocated_entry_adverse_slippage;
      component_states[component].entry_planned_risk_usd *= remaining_fraction;
      if(MathAbs(component_states[component].entry_transaction_cost) < 1.0e-12)
         component_states[component].entry_transaction_cost = 0.0;
      if(component_states[component].entry_adverse_slippage < 1.0e-12)
         component_states[component].entry_adverse_slippage = 0.0;
      applied_event += "_PARTIAL";
     }
   if(!complete_cost)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("cost reconstruction incomplete after exit");
     }
   RecordEvent(component,
               applied_event,
               deal_net,
               stressed_net,
               StringFormat("%s reason=%s stop=%.5f planned_risk=%.4f executed=%.2f remaining=%.2f deal=%I64u",
                            (complete_cost ? "cost-known" : "cost-unknown"),
                            EnumToString(exit_reason),
                            admitted_stop_loss,
                            admitted_planned_risk,
                            executed_volume,
                            (double)remaining_after_steps * step,
                            deal));
   SaveState();
   return(true);
  }


bool ReconcileExitDealSequence(const int component,
                               const MqlTick &sampled_tick,
                               const bool sampled_tick_known,
                               const string event_name,
                               const bool require_new_exit,
                               ulong &waited_ms)
  {
   waited_ms = 0;
   if(component_states[component].position_identifier == 0)
      return(!require_new_exit);
   const ulong position_identifier =
      component_states[component].position_identifier;
   const ulong started = GetTickCount64();
   bool applied_exit = false;
   while(true)
     {
      SequencedExitDeal deals[];
      const int deal_count =
         CollectUnprocessedExitDeals(component,
                                     position_identifier,
                                     deals);
      if(deal_count < 0)
         return(false);
      for(int index = 0; index < deal_count; ++index)
        {
         if(!ApplyExitDeal(component,
                           deals[index].ticket,
                           sampled_tick,
                           sampled_tick_known,
                           event_name))
            return(false);
         applied_exit = true;
        }

      ulong ticket = 0;
      datetime opened_at = 0;
      const int position_count =
         CountOwnedPositions(component, ticket, opened_at);
      if(position_count > 1)
         return(false);
      if(position_count == 0 &&
         component_states[component].position_identifier == 0 &&
         (!require_new_exit || applied_exit))
        {
         waited_ms = GetTickCount64() - started;
         return(true);
        }
      if(position_count == 1 &&
         component_states[component].position_identifier == position_identifier &&
         PositionSelectByTicket(ticket) &&
         (ulong)PositionGetInteger(POSITION_IDENTIFIER) ==
         position_identifier)
        {
         long broker_steps = 0;
         long local_steps = 0;
         if(VolumeToSteps(component_definitions[component].symbol,
                          PositionGetDouble(POSITION_VOLUME),
                          broker_steps) &&
            VolumeToSteps(component_definitions[component].symbol,
                          component_states[component].entry_volume,
                          local_steps) &&
            broker_steps == local_steps)
           {
            if(require_new_exit && !applied_exit)
              {
               waited_ms = GetTickCount64() - started;
               if(tester_mode ||
                  waited_ms >= COMPLETED_DEAL_RECONCILIATION_TIMEOUT_MS)
                  return(false);
               Sleep(COMPLETED_DEAL_RECONCILIATION_POLL_MS);
               continue;
              }
            waited_ms = GetTickCount64() - started;
            return(true);
           }
        }
      waited_ms = GetTickCount64() - started;
      if(tester_mode ||
         waited_ms >= COMPLETED_DEAL_RECONCILIATION_TIMEOUT_MS)
         return(false);
      Sleep(COMPLETED_DEAL_RECONCILIATION_POLL_MS);
     }
   return(false);
  }


bool ReconcileBrokerState(const bool startup)
  {
   if(!AuditPositionOwnership())
     {
      MakeExistingRiskSafe("broker ownership/protection audit failed");
      return(false);
     }
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      ulong ticket = 0;
      datetime opened_at = 0;
      const int count = CountOwnedPositions(component, ticket, opened_at);
      if(count > 1)
        {
         execution_state.broker_mismatch = true;
         EngageSafetyStop("duplicate component position during reconcile");
         return(false);
        }
      if(count == 1)
        {
         if(!PositionSelectByTicket(ticket))
            return(false);
         const ulong identifier =
            (ulong)PositionGetInteger(POSITION_IDENTIFIER);
         if(component_states[component].position_identifier == 0)
           {
            if(!ReconstructEntryTracking(component, ticket))
               return(false);
           }
         else if(identifier != component_states[component].position_identifier)
           {
            execution_state.broker_mismatch = true;
            EngageSafetyStop("broker position identity differs from local state");
            return(false);
           }
         else
           {
            long broker_steps = 0;
            long local_steps = 0;
            if(!VolumeToSteps(component_definitions[component].symbol,
                              PositionGetDouble(POSITION_VOLUME),
                              broker_steps) ||
               !VolumeToSteps(component_definitions[component].symbol,
                              component_states[component].entry_volume,
                              local_steps) || broker_steps > local_steps)
              {
               execution_state.broker_mismatch = true;
               EngageSafetyStop("broker position volume exceeds local lifecycle");
               return(false);
              }
            if(broker_steps < local_steps)
              {
               MqlTick empty_tick = {};
               ulong waited_ms = 0;
               if(!ReconcileExitDealSequence(component,
                                             empty_tick,
                                             false,
                                             (startup ? "RECOVER_PARTIAL" :
                                                        "EXTERNAL_PARTIAL"),
                                             false,
                                             waited_ms))
                 {
                  execution_state.broker_mismatch = true;
                  EngageSafetyStop("partial exit deals do not match broker volume");
                  return(false);
                 }
               if(component_states[component].position_identifier == 0)
                  continue;
               ticket = 0;
               opened_at = 0;
               if(CountOwnedPositions(component, ticket, opened_at) != 1 ||
                  !PositionSelectByTicket(ticket) ||
                  (ulong)PositionGetInteger(POSITION_IDENTIFIER) !=
                  component_states[component].position_identifier)
                 {
                  execution_state.broker_mismatch = true;
                  EngageSafetyStop("position changed after partial reduction");
                  return(false);
                 }
              }
           }
         const datetime bar = BarForTime(component, opened_at);
         if(bar > component_states[component].last_decision_bar)
            component_states[component].last_decision_bar = bar;
         continue;
        }
      if(component_states[component].position_identifier == 0)
         continue;
      MqlTick empty_tick = {};
      ulong waited_ms = 0;
      if(!ReconcileExitDealSequence(component,
                                    empty_tick,
                                    false,
                                    (startup ? "RECOVER_CLOSE" :
                                               "EXTERNAL_CLOSE"),
                                    false,
                                    waited_ms))
        {
         execution_state.broker_mismatch = true;
         EngageSafetyStop("local open lifecycle has no complete exit sequence");
         return(false);
        }
     }
   if(!ReconcilePassivePendingOrder())
      return(false);
   last_reconcile_server = TimeCurrent();
   execution_state.pending_reconcile = false;
   return(true);
  }


void MakeExistingRiskSafe(const string reason)
  {
   for(int index = OrdersTotal() - 1; index >= 0; --index)
     {
      const ulong order_ticket = OrderGetTicket(index);
      if(order_ticket == 0 ||
         (ulong)OrderGetInteger(ORDER_MAGIC) !=
         MAGIC_US100_PASSIVE_LIMIT)
         continue;
      CancelPassivePendingOrder(order_ticket, reason);
     }
   for(int index = PositionsTotal() - 1; index >= 0; --index)
     {
      const ulong position_ticket = PositionGetTicket(index);
      if(position_ticket == 0)
         continue;
      const int component =
         ComponentForMagic((ulong)PositionGetInteger(POSITION_MAGIC),
                           PositionGetString(POSITION_SYMBOL));
      if(component >= 0)
         CloseComponent(component, position_ticket);
     }
  }



void ProcessClosures()
  {
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      if(component == US100_PASSIVE_LIMIT)
         continue;
      ulong ticket = 0;
      datetime opened_at = 0;
      const int count = CountOwnedPositions(component, ticket, opened_at);
      if(count > 1)
        {
         EngageSafetyStop("duplicate component position during close");
         continue;
        }
      if(count != 1)
         continue;
      const int held_bars =
         iBarShift(component_definitions[component].symbol,
                   component_definitions[component].timeframe,
                   opened_at,
                   false);
      if(held_bars >= component_definitions[component].hold_bars)
         CloseComponent(component, ticket);
     }
  }


#endif
