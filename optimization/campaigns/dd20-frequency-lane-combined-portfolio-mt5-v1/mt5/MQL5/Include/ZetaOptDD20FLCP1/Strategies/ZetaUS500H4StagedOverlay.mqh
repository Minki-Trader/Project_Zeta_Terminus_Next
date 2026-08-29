#ifndef ZETA_OPT_DD20_FLCP1_US500_H4_STAGED_OVERLAY_MQH
#define ZETA_OPT_DD20_FLCP1_US500_H4_STAGED_OVERLAY_MQH

// Exact lineage-pinned ZT-H4-US500-V2-VOLATILITY-EXP-b4d28831f9
// translated into the shared tester executable. The fixed overlay owns one
// US500 H4 position and remains outside all six-component planned-risk, state
// and slot accounting. It shares only the real account balance, equity,
// margin, execution and downstream account-state effects.


void ResetH4OverlayState()
  {
   h4_overlay_last_completed_decision_bar = 0;
   h4_overlay_last_order_attempt_server = 0;
   h4_overlay_entry_spread_price = 0.0;
   h4_overlay_entry_transaction_cost = 0.0;
   h4_overlay_entry_adverse_slippage = 0.0;
   h4_overlay_entry_cost_known = false;
   h4_overlay_pending_exit_deal = 0;
   h4_overlay_last_processed_exit_deal = 0;
   h4_overlay_completed_entries = 0;
   h4_overlay_completed_exits = 0;
   h4_overlay_entry_failures = 0;
   h4_overlay_exit_failures = 0;
   h4_overlay_partial_or_placed_outcomes = 0;
   h4_overlay_margin_skips = 0;
   h4_overlay_stage_gate_blocks = 0;
   h4_overlay_state_unavailable = 0;
   h4_overlay_late_entry_windows = 0;
   h4_overlay_faults = 0;
   h4_overlay_actual_net = 0.0;
   h4_overlay_stressed_net = 0.0;
  }


void MarkH4OverlayFault(const string reason)
  {
   ++h4_overlay_faults;
   execution_state.broker_mismatch = true;
   EngageSafetyStop("US500 H4 overlay: " + reason);
  }


double H4OverlaySampleStandardDeviation(const double &values[],
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


bool CalculateH4OverlayVolatilityExpansionState(double &state)
  {
   const int close_count = 50;
   double closes[];
   ArraySetAsSeries(closes, false);
   if(CopyClose(US500_H4_STAGED_OVERLAY_SYMBOL,
                PERIOD_H4,
                1,
                close_count,
                closes) != close_count)
      return(false);

   double returns[];
   ArrayResize(returns, close_count - 1);
   for(int index = 0; index < close_count - 1; ++index)
     {
      if(closes[index] <= 0.0 || closes[index + 1] <= 0.0)
         return(false);
      returns[index] = MathLog(closes[index + 1] / closes[index]);
     }

   const double short_volatility =
      H4OverlaySampleStandardDeviation(returns,
                                       37,
                                       US500_H4_STAGED_OVERLAY_LOOKBACK);
   const double past_volatility =
      H4OverlaySampleStandardDeviation(returns, 0, 48);
   const double long_volatility =
      H4OverlaySampleStandardDeviation(returns, 0, 48);
   if(short_volatility <= 0.0 || past_volatility <= 0.0 ||
      long_volatility <= 0.0)
      return(false);

   const double horizon_return = MathLog(closes[49] / closes[37]);
   if(horizon_return == 0.0)
     {
      state = 0.0;
      return(true);
     }
   const double strength =
      (short_volatility / long_volatility) *
      (MathAbs(horizon_return) /
       (past_volatility *
        MathSqrt((double)US500_H4_STAGED_OVERLAY_LOOKBACK)));
   state = (horizon_return > 0.0 ? strength : -strength);
   return(MathIsValidNumber(state));
  }


bool H4OverlayMarginAllows(const int direction)
  {
   MqlTick tick = {};
   if(!ExecutableTick(US500_H4_STAGED_OVERLAY_SYMBOL, tick))
      return(false);
   double required = 0.0;
   const ENUM_ORDER_TYPE order_type =
      (direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   const double price = (direction > 0 ? tick.ask : tick.bid);
   if(!OrderCalcMargin(order_type,
                       US500_H4_STAGED_OVERLAY_SYMBOL,
                       US500_H4_STAGED_OVERLAY_VOLUME,
                       price,
                       required) || required <= 0.0)
      return(false);
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   const double used = AccountInfoDouble(ACCOUNT_MARGIN);
   if(equity <= 0.0 ||
      used + required >
         equity * US500_H4_STAGED_OVERLAY_MARGIN_FRACTION)
     {
      ++h4_overlay_margin_skips;
      PrintFormat("%s H4_OVERLAY margin skip equity=%.4f used=%.4f "
                  "required=%.4f limit=%.4f",
                  EXECUTION_VERSION,
                  equity,
                  used,
                  required,
                  equity * US500_H4_STAGED_OVERLAY_MARGIN_FRACTION);
      return(false);
     }
   return(true);
  }


bool H4OverlayEntryWindowAllows(const datetime current_bar,
                                bool &too_late)
  {
   too_late = false;
   const datetime now = TimeCurrent();
   datetime session_start = 0;
   if(!CurrentTradeSessionStart(US500_H4_STAGED_OVERLAY_SYMBOL,
                                now,
                                session_start))
      return(false);
   const datetime executable_start =
      (datetime)MathMax((long)current_bar, (long)session_start);
   if(now < executable_start)
      return(false);
   too_late =
      (now - executable_start > InpMaxEntryDelayMinutes * 60);
   return(!too_late);
  }


void ObserveH4OverlayTradeTransaction(
   const MqlTradeTransaction &transaction)
  {
   if(transaction.type != TRADE_TRANSACTION_DEAL_ADD ||
      transaction.deal == 0 || !HistoryDealSelect(transaction.deal))
      return;
   if((ulong)HistoryDealGetInteger(transaction.deal, DEAL_MAGIC) !=
         MAGIC_US500_H4_STAGED_OVERLAY ||
      HistoryDealGetString(transaction.deal, DEAL_SYMBOL) !=
         US500_H4_STAGED_OVERLAY_SYMBOL)
      return;
   const ENUM_DEAL_ENTRY entry =
      (ENUM_DEAL_ENTRY)HistoryDealGetInteger(transaction.deal,
                                             DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
      return;
   if(h4_overlay_pending_exit_deal != 0 &&
      h4_overlay_pending_exit_deal != transaction.deal)
     {
      MarkH4OverlayFault("multiple unprocessed exit deals");
      return;
     }
   h4_overlay_pending_exit_deal = transaction.deal;
  }


bool ApplyH4OverlayExitDeal(const ulong deal,
                            const MqlTick &sampled_tick,
                            const bool sampled_tick_known)
  {
   if(deal == 0)
      return(false);
   if(deal == h4_overlay_last_processed_exit_deal)
     {
      if(h4_overlay_pending_exit_deal == deal)
         h4_overlay_pending_exit_deal = 0;
      return(true);
     }
   if(!HistoryDealSelect(deal) ||
      (ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) !=
         MAGIC_US500_H4_STAGED_OVERLAY ||
      HistoryDealGetString(deal, DEAL_SYMBOL) !=
         US500_H4_STAGED_OVERLAY_SYMBOL)
      return(false);
   const ENUM_DEAL_ENTRY entry =
      (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
      return(false);
   if(!h4_overlay_entry_cost_known)
     {
      MarkH4OverlayFault("exit has no complete entry-cost state");
      return(false);
     }

   const double executed_volume = HistoryDealGetDouble(deal, DEAL_VOLUME);
   const double volume_step =
      SymbolInfoDouble(US500_H4_STAGED_OVERLAY_SYMBOL,
                       SYMBOL_VOLUME_STEP);
   if(executed_volume <= 0.0 || volume_step <= 0.0 ||
      MathAbs(executed_volume - US500_H4_STAGED_OVERLAY_VOLUME) >
         MathMax(1.0e-8, 0.5 * volume_step))
     {
      MarkH4OverlayFault("exit execution volume mismatch");
      return(false);
     }

   MqlTick exit_tick = sampled_tick;
   bool exit_quote_known = sampled_tick_known;
   const long deal_time_msc =
      HistoryDealGetInteger(deal, DEAL_TIME_MSC);
   if(!exit_quote_known)
      exit_quote_known =
         QuoteAtMilliseconds(US500_H4_STAGED_OVERLAY_SYMBOL,
                             deal_time_msc,
                             exit_tick);
   if(!exit_quote_known)
     {
      MarkH4OverlayFault("exit quote unavailable");
      return(false);
     }

   const double exit_transaction_cost =
      HistoryDealGetDouble(deal, DEAL_COMMISSION) +
      HistoryDealGetDouble(deal, DEAL_SWAP) +
      HistoryDealGetDouble(deal, DEAL_FEE);
   const double deal_net =
      HistoryDealGetDouble(deal, DEAL_PROFIT) +
      exit_transaction_cost + h4_overlay_entry_transaction_cost;
   const ENUM_DEAL_TYPE deal_type =
      (ENUM_DEAL_TYPE)HistoryDealGetInteger(deal, DEAL_TYPE);
   const int direction = (deal_type == DEAL_TYPE_SELL ? 1 : -1);
   const double execution_price = HistoryDealGetDouble(deal, DEAL_PRICE);
   const double adverse_exit_price =
      (direction > 0
       ? MathMax(0.0, exit_tick.bid - execution_price)
       : MathMax(0.0, execution_price - exit_tick.ask));
   const double contract_size =
      SymbolInfoDouble(US500_H4_STAGED_OVERLAY_SYMBOL,
                       SYMBOL_TRADE_CONTRACT_SIZE);
   const double exit_adverse_slippage =
      adverse_exit_price * contract_size * executed_volume;
   const double exit_spread = exit_tick.ask - exit_tick.bid;
   const double additional_spread_cost =
      MathMax(h4_overlay_entry_spread_price, exit_spread) *
      contract_size * executed_volume;
   const double additional_nonspread_cost =
      h4_overlay_entry_adverse_slippage + exit_adverse_slippage +
      MathMax(0.0, -h4_overlay_entry_transaction_cost) +
      MathMax(0.0, -exit_transaction_cost);
   const double additional_cost =
      additional_spread_cost + additional_nonspread_cost;
   const double stressed_net = deal_net - additional_cost;
   if(!MathIsValidNumber(deal_net) ||
      !MathIsValidNumber(stressed_net))
     {
      MarkH4OverlayFault("non-finite exit economics");
      return(false);
     }

   portfolio_state.project_realized_net += deal_net;
   portfolio_state.stressed_balance += stressed_net;
   portfolio_state.stressed_peak =
      MathMax(portfolio_state.stressed_peak,
              portfolio_state.stressed_balance);
   portfolio_state.stressed_maximum_closed_drawdown =
      MathMax(portfolio_state.stressed_maximum_closed_drawdown,
              portfolio_state.stressed_peak -
                 portfolio_state.stressed_balance);
   h4_overlay_actual_net += deal_net;
   h4_overlay_stressed_net += stressed_net;
   ++h4_overlay_completed_exits;
   h4_overlay_last_processed_exit_deal = deal;
   if(h4_overlay_pending_exit_deal == deal)
      h4_overlay_pending_exit_deal = 0;

   PrintFormat("%s H4_OVERLAY close candidate=%s deal=%I64u "
               "actual_net=%.4f extra_cost=%.4f stressed_net=%.4f "
               "overlay_actual=%.4f overlay_stressed=%.4f",
               EXECUTION_VERSION,
               US500_H4_STAGED_OVERLAY_CANDIDATE_ID,
               deal,
               deal_net,
               additional_cost,
               stressed_net,
               h4_overlay_actual_net,
               h4_overlay_stressed_net);
   RecordEvent(-1,
               "H4_OVERLAY_CLOSE",
               deal_net,
               stressed_net,
               StringFormat("candidate=%s deal=%I64u",
                            US500_H4_STAGED_OVERLAY_CANDIDATE_ID,
                            deal));
   h4_overlay_entry_spread_price = 0.0;
   h4_overlay_entry_transaction_cost = 0.0;
   h4_overlay_entry_adverse_slippage = 0.0;
   h4_overlay_entry_cost_known = false;
   return(SaveState());
  }


bool ApplyPendingH4OverlayExit()
  {
   if(h4_overlay_pending_exit_deal == 0)
      return(true);
   MqlTick empty_tick = {};
   return(ApplyH4OverlayExitDeal(h4_overlay_pending_exit_deal,
                                 empty_tick,
                                 false));
  }


bool OpenH4OverlayPosition(const int direction, const double state)
  {
   if(direction == 0 || !NewEntriesOperationallyAllowed() ||
      AccountInfoDouble(ACCOUNT_BALANCE) <
         US500_H4_STAGED_OVERLAY_BALANCE_GATE_USD ||
      !TradeSessionAllows(US500_H4_STAGED_OVERLAY_SYMBOL,
                          TimeCurrent(),
                          true) ||
      !H4OverlayMarginAllows(direction))
      return(false);
   MqlTick tick = {};
   if(!ExecutableTick(US500_H4_STAGED_OVERLAY_SYMBOL, tick))
      return(false);
   trade.SetExpertMagicNumber(MAGIC_US500_H4_STAGED_OVERLAY);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol(US500_H4_STAGED_OVERLAY_SYMBOL);
   trade.SetMarginMode();
   trade.SetAsyncMode(false);
   const bool requested =
      (direction > 0
       ? trade.Buy(US500_H4_STAGED_OVERLAY_VOLUME,
                   US500_H4_STAGED_OVERLAY_SYMBOL,
                   0.0,
                   0.0,
                   0.0,
                   "ZT US500 H4 staged overlay")
       : trade.Sell(US500_H4_STAGED_OVERLAY_VOLUME,
                    US500_H4_STAGED_OVERLAY_SYMBOL,
                    0.0,
                    0.0,
                    0.0,
                    "ZT US500 H4 staged overlay"));
   const uint retcode = trade.ResultRetcode();
   if(retcode == TRADE_RETCODE_DONE_PARTIAL ||
      retcode == TRADE_RETCODE_PLACED)
      ++h4_overlay_partial_or_placed_outcomes;
   if(!requested || !IsCompletedTradeRetcode(retcode))
     {
      ++h4_overlay_entry_failures;
      PrintFormat("%s H4_OVERLAY open failed direction=%d state=%.6f "
                  "retcode=%u %s",
                  EXECUTION_VERSION,
                  direction,
                  state,
                  retcode,
                  trade.ResultRetcodeDescription());
      return(false);
     }
   const double executed_volume = trade.ResultVolume();
   const double volume_step =
      SymbolInfoDouble(US500_H4_STAGED_OVERLAY_SYMBOL,
                       SYMBOL_VOLUME_STEP);
   if(executed_volume <= 0.0 ||
      MathAbs(executed_volume - US500_H4_STAGED_OVERLAY_VOLUME) >
         MathMax(1.0e-8, 0.5 * volume_step))
     {
      MarkH4OverlayFault("entry execution volume mismatch");
      return(true);
     }

   const ulong deal = trade.ResultDeal();
   if(deal == 0 || !HistoryDealSelect(deal))
     {
      MarkH4OverlayFault("entry deal unavailable after execution");
      return(true);
     }
   h4_overlay_entry_spread_price = tick.ask - tick.bid;
   h4_overlay_entry_transaction_cost =
      HistoryDealGetDouble(deal, DEAL_COMMISSION) +
      HistoryDealGetDouble(deal, DEAL_SWAP) +
      HistoryDealGetDouble(deal, DEAL_FEE);
   const double execution_price = trade.ResultPrice();
   const double adverse_price =
      (direction > 0
       ? MathMax(0.0, execution_price - tick.ask)
       : MathMax(0.0, tick.bid - execution_price));
   h4_overlay_entry_adverse_slippage =
      adverse_price *
      SymbolInfoDouble(US500_H4_STAGED_OVERLAY_SYMBOL,
                       SYMBOL_TRADE_CONTRACT_SIZE) *
      executed_volume;
   h4_overlay_entry_cost_known = true;
   ++h4_overlay_completed_entries;
   PrintFormat("%s H4_OVERLAY open candidate=%s direction=%d "
               "state=%.6f volume=%.2f price=%.2f spread=%.2f "
               "deal=%I64u balance=%.2f",
               EXECUTION_VERSION,
               US500_H4_STAGED_OVERLAY_CANDIDATE_ID,
               direction,
               state,
               executed_volume,
               execution_price,
               h4_overlay_entry_spread_price,
               deal,
               AccountInfoDouble(ACCOUNT_BALANCE));
   RecordEvent(-1,
               "H4_OVERLAY_OPEN",
               state,
               (double)direction,
               StringFormat("candidate=%s deal=%I64u",
                            US500_H4_STAGED_OVERLAY_CANDIDATE_ID,
                            deal));
   return(SaveState());
  }


bool CloseH4OverlayPosition(const ulong ticket)
  {
   if(!TradeSessionAllows(US500_H4_STAGED_OVERLAY_SYMBOL,
                          TimeCurrent(),
                          false) ||
      !PositionSelectByTicket(ticket))
      return(false);
   const double volume = PositionGetDouble(POSITION_VOLUME);
   MqlTick tick = {};
   if(!ExecutableTick(US500_H4_STAGED_OVERLAY_SYMBOL, tick))
      return(false);
   trade.SetExpertMagicNumber(MAGIC_US500_H4_STAGED_OVERLAY);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol(US500_H4_STAGED_OVERLAY_SYMBOL);
   trade.SetAsyncMode(false);
   const bool requested = trade.PositionClose(ticket, InpDeviationPoints);
   const uint retcode = trade.ResultRetcode();
   if(retcode == TRADE_RETCODE_DONE_PARTIAL ||
      retcode == TRADE_RETCODE_PLACED)
      ++h4_overlay_partial_or_placed_outcomes;
   if(!requested || !IsCompletedTradeRetcode(retcode))
     {
      ++h4_overlay_exit_failures;
      PrintFormat("%s H4_OVERLAY close failed ticket=%I64u "
                  "retcode=%u %s",
                  EXECUTION_VERSION,
                  ticket,
                  retcode,
                  trade.ResultRetcodeDescription());
      return(false);
     }
   const double executed_volume = trade.ResultVolume();
   const double volume_step =
      SymbolInfoDouble(US500_H4_STAGED_OVERLAY_SYMBOL,
                       SYMBOL_VOLUME_STEP);
   if(executed_volume <= 0.0 ||
      MathAbs(executed_volume - volume) >
         MathMax(1.0e-8, 0.5 * volume_step) ||
      PositionSelectByTicket(ticket))
     {
      MarkH4OverlayFault("close incomplete or residual position remains");
      return(false);
     }
   const ulong deal = trade.ResultDeal();
   if(deal == 0)
     {
      MarkH4OverlayFault("close deal unavailable after execution");
      return(false);
     }
   if(h4_overlay_pending_exit_deal == 0)
      h4_overlay_pending_exit_deal = deal;
   return(ApplyH4OverlayExitDeal(deal, tick, true));
  }


void ProcessH4StagedOverlay()
  {
   if(!ApplyPendingH4OverlayExit())
      return;
   const datetime current_bar =
      iTime(US500_H4_STAGED_OVERLAY_SYMBOL, PERIOD_H4, 0);
   if(current_bar == 0 ||
      current_bar == h4_overlay_last_completed_decision_bar)
      return;
   if(h4_overlay_last_order_attempt_server > 0 &&
      TimeCurrent() - h4_overlay_last_order_attempt_server < 5)
      return;

   ulong ticket = 0;
   datetime opened_at = 0;
   int owned = CountH4OverlayPositions(ticket, opened_at);
   if(owned > 1)
      return;
   double state = 0.0;
   if(!CalculateH4OverlayVolatilityExpansionState(state))
     {
      ++h4_overlay_state_unavailable;
      return;
     }
   if(owned == 1)
     {
      if(!PositionSelectByTicket(ticket))
         return;
      const ENUM_POSITION_TYPE position_type =
         (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      const int direction =
         (position_type == POSITION_TYPE_BUY ? 1 : -1);
      const int desired_direction =
         (state > 0.0 ? -1 : (state < 0.0 ? 1 : 0));
      const int held_bars =
         iBarShift(US500_H4_STAGED_OVERLAY_SYMBOL,
                   PERIOD_H4,
                   opened_at,
                   false);
      const bool should_close =
         (held_bars >= US500_H4_STAGED_OVERLAY_MAXIMUM_HOLD_BARS ||
          MathAbs(state) <= US500_H4_STAGED_OVERLAY_EXIT_STRENGTH ||
          (desired_direction != 0 && desired_direction != direction));
      if(!should_close)
        {
         h4_overlay_last_completed_decision_bar = current_bar;
         return;
        }
      h4_overlay_last_order_attempt_server = TimeCurrent();
      if(!CloseH4OverlayPosition(ticket))
         return;
      h4_overlay_last_order_attempt_server = 0;
      owned = 0;
     }

   const datetime previous_bar =
      iTime(US500_H4_STAGED_OVERLAY_SYMBOL, PERIOD_H4, 1);
   if(previous_bar == 0 || current_bar <= previous_bar ||
      current_bar - previous_bar > 8 * 3600)
     {
      h4_overlay_last_completed_decision_bar = current_bar;
      return;
     }
   bool too_late = false;
   if(!H4OverlayEntryWindowAllows(current_bar, too_late))
     {
      if(too_late)
        {
         ++h4_overlay_late_entry_windows;
         h4_overlay_last_completed_decision_bar = current_bar;
        }
      return;
     }
   if(MathAbs(state) < US500_H4_STAGED_OVERLAY_ENTRY_STRENGTH)
     {
      h4_overlay_last_completed_decision_bar = current_bar;
      return;
     }
   if(!NewEntriesOperationallyAllowed() ||
      AccountInfoDouble(ACCOUNT_BALANCE) <
         US500_H4_STAGED_OVERLAY_BALANCE_GATE_USD)
     {
      ++h4_overlay_stage_gate_blocks;
      h4_overlay_last_completed_decision_bar = current_bar;
      return;
     }

   h4_overlay_last_order_attempt_server = TimeCurrent();
   if(OpenH4OverlayPosition((state > 0.0 ? -1 : 1), state))
     {
      h4_overlay_last_completed_decision_bar = current_bar;
      h4_overlay_last_order_attempt_server = 0;
     }
  }


#endif
