#ifndef ZETA_NEXT_MODULE_11_MQH
#define ZETA_NEXT_MODULE_11_MQH

// Behavior-preserving function extraction from B70 V6R6: Execution\ZetaOrders.mqh

bool IsCompletedTradeRetcode(const uint retcode)
  {
   return(retcode == TRADE_RETCODE_DONE);
  }


bool IsCompletedMarketTradeRetcode(const uint retcode)
  {
   return(retcode == TRADE_RETCODE_DONE ||
          retcode == TRADE_RETCODE_DONE_PARTIAL);
  }


bool IsPendingPlacementRetcode(const uint retcode)
  {
   return(retcode == TRADE_RETCODE_PLACED ||
          retcode == TRADE_RETCODE_DONE);
  }


enum EMarketEntryResultCode
  {
   MARKET_ENTRY_NOT_STARTED = 0,
   MARKET_ENTRY_ENTRY_BLOCKED,
   MARKET_ENTRY_OWNERSHIP_BLOCKED,
   MARKET_ENTRY_EXISTING_EXPOSURE,
   MARKET_ENTRY_VOLUME_INVALID,
   MARKET_ENTRY_QUOTE_UNAVAILABLE,
   MARKET_ENTRY_PROTECTION_OR_RISK_BLOCKED,
   MARKET_ENTRY_SESSION_BLOCKED,
   MARKET_ENTRY_MARGIN_BLOCKED,
   MARKET_ENTRY_DURABLE_INTENT_FAILED,
   MARKET_ENTRY_SUBMIT_REJECTED,
   MARKET_ENTRY_OBSERVATION_FAILED,
   MARKET_ENTRY_IDENTITY_MISMATCH,
   MARKET_ENTRY_PROTECTION_MISMATCH,
   MARKET_ENTRY_ADOPTION_PERSIST_FAILED,
   MARKET_ENTRY_FINAL_PERSIST_FAILED,
   MARKET_ENTRY_POSITION_OPEN
  };


struct MarketEntryPlan
  {
   int component;
   string symbol;
   ulong magic;
   int direction;
   double feature;
   double volume;
   MqlTick sampled_tick;
   double expected_entry_price;
   double requested_stop_loss;
   double admitted_planned_risk;
   double admitted_capital;
   double aggregate_before;
   datetime decision_bar;
   datetime deadline;
   string comment;
  };


struct MarketSubmitReceipt
  {
   bool requested;
   uint retcode;
   string retcode_description;
   double result_volume;
   double result_price;
   ulong result_order;
   ulong result_deal;
  };


struct MarketEntryObservation
  {
   ulong position_ticket;
   ulong expected_position_identifier;
   ulong position_identifier;
   datetime opened_at;
   EntryDealAggregate aggregate;
   ulong deal_wait_ms;
   long requested_steps;
   double position_volume;
   double position_open_price;
   double broker_stop_loss;
   ulong position_magic;
   string position_symbol;
   ENUM_POSITION_TYPE position_type;
  };


struct MarketEntryOutcome
  {
   EMarketEntryResultCode code;
   bool broker_call_made;
   bool protective_close_requested;
   bool safety_stop_engaged;
   string entry_check_result;
  };


bool WaitForSingleOwnedPosition(const int component,
                                ulong &ticket,
                                datetime &opened_at)
  {
   const ulong started = GetTickCount64();
   while(true)
     {
      const int count = CountOwnedPositions(component, ticket, opened_at);
      if(count == 1 && PositionSelectByTicket(ticket))
         return(true);
      if(count > 1 || tester_mode ||
         GetTickCount64() - started >=
         COMPLETED_DEAL_RECONCILIATION_TIMEOUT_MS)
         return(false);
      Sleep(COMPLETED_DEAL_RECONCILIATION_POLL_MS);
     }
   return(false);
  }


int ComponentForMagic(const ulong magic, const string symbol)
  {
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(magic == component_definitions[component].magic &&
         symbol == component_definitions[component].symbol)
         return(component);
   return(-1);
  }


datetime BarForTime(const int component, const datetime value)
  {
   const int shift = iBarShift(component_definitions[component].symbol,
                               component_definitions[component].timeframe,
                               value,
                               false);
   if(shift < 0)
      return(0);
   return(iTime(component_definitions[component].symbol,
                component_definitions[component].timeframe,
                shift));
  }


bool QuoteAtMilliseconds(const string symbol,
                         const long target_msc,
                         MqlTick &quote)
  {
   if(target_msc <= 0)
      return(false);
   const ulong from_msc = (ulong)MathMax(0.0, (double)target_msc - 5000.0);
   const ulong to_msc = (ulong)((long)target_msc + 5000);
   MqlTick ticks[];
   const int count = CopyTicksRange(symbol,
                                    ticks,
                                    COPY_TICKS_ALL,
                                    from_msc,
                                    to_msc);
   int selected = -1;
   long selected_distance = LONG_MAX;
   bool selected_preceding = false;
   for(int index = 0; index < count; ++index)
     {
      if(ticks[index].ask <= ticks[index].bid || ticks[index].bid <= 0.0)
         continue;
      const bool preceding = (ticks[index].time_msc <= target_msc);
      const long distance =
         (long)MathAbs((double)(ticks[index].time_msc - target_msc));
      if(selected < 0 ||
         (preceding && !selected_preceding) ||
         (preceding == selected_preceding && distance < selected_distance))
        {
         selected = index;
         selected_distance = distance;
         selected_preceding = preceding;
        }
     }
   if(selected < 0)
      return(false);
   quote = ticks[selected];
   return(true);
  }


bool VolumeToSteps(const string symbol,
                   const double volume,
                   long &steps)
  {
   steps = 0;
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0 || volume <= 0.0 || !MathIsValidNumber(volume))
      return(false);
   const double raw_steps = volume / step;
   steps = (long)MathRound(raw_steps);
   return(steps > 0 &&
          MathAbs(volume - (double)steps * step) <=
          MathMax(1.0e-8, step * 1.0e-6));
  }


bool DealAfterExitCursor(const int component,
                         const long time_msc,
                         const ulong deal)
  {
   return(time_msc > component_states[component].last_processed_exit_time_msc ||
          (time_msc == component_states[component].last_processed_exit_time_msc &&
           deal > component_states[component].last_processed_exit_deal));
  }


bool AggregateEntryDeals(const int component,
                         const ulong position_identifier,
                         const ulong required_order,
                         const MqlTick &sampled_tick,
                         const bool sampled_tick_known,
                         EntryDealAggregate &aggregate)
  {
   aggregate.first_deal = 0;
   aggregate.last_deal = 0;
   aggregate.order_ticket = 0;
   aggregate.first_time_msc = 0;
   aggregate.last_time_msc = 0;
   aggregate.first_time_server = 0;
   aggregate.direction = 0;
   aggregate.volume_steps = 0;
   aggregate.volume = 0.0;
   aggregate.price = 0.0;
   aggregate.transaction_cost = 0.0;
   aggregate.spread_price = 0.0;
   aggregate.adverse_slippage = 0.0;
   aggregate.cost_known = true;
   aggregate.deal_count = 0;
   if(position_identifier == 0 ||
      !HistorySelectByPosition(position_identifier))
      return(false);
   const string symbol = component_definitions[component].symbol;
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   const double contract_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(step <= 0.0 || contract_size <= 0.0)
      return(false);
   double price_volume_sum = 0.0;
   double spread_volume_sum = 0.0;
   for(int index = 0; index < HistoryDealsTotal(); ++index)
     {
      const ulong deal = HistoryDealGetTicket(index);
      if(deal == 0 ||
         (ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) !=
         component_definitions[component].magic ||
         HistoryDealGetString(deal, DEAL_SYMBOL) != symbol ||
         (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID) !=
         position_identifier)
         continue;
      const ENUM_DEAL_ENTRY entry =
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_IN)
         continue;
      const ENUM_DEAL_TYPE type =
         (ENUM_DEAL_TYPE)HistoryDealGetInteger(deal, DEAL_TYPE);
      const int direction =
         (type == DEAL_TYPE_BUY ? 1 :
          (type == DEAL_TYPE_SELL ? -1 : 0));
      const ulong order =
         (ulong)HistoryDealGetInteger(deal, DEAL_ORDER);
      const double volume = HistoryDealGetDouble(deal, DEAL_VOLUME);
      const double price = HistoryDealGetDouble(deal, DEAL_PRICE);
      const long time_msc = HistoryDealGetInteger(deal, DEAL_TIME_MSC);
      long volume_steps = 0;
      if(direction == 0 || order == 0 || price <= 0.0 || time_msc <= 0 ||
         !VolumeToSteps(symbol, volume, volume_steps) ||
         (required_order > 0 && order != required_order) ||
         (aggregate.direction != 0 && aggregate.direction != direction) ||
         (aggregate.order_ticket != 0 && aggregate.order_ticket != order))
         return(false);
      aggregate.direction = direction;
      aggregate.order_ticket = order;
      aggregate.volume_steps += volume_steps;
      price_volume_sum += price * volume;
      aggregate.transaction_cost +=
         HistoryDealGetDouble(deal, DEAL_COMMISSION) +
         HistoryDealGetDouble(deal, DEAL_SWAP) +
         HistoryDealGetDouble(deal, DEAL_FEE);
      MqlTick quote = sampled_tick;
      bool quote_known = sampled_tick_known;
      if(!quote_known)
         quote_known = QuoteAtMilliseconds(symbol, time_msc, quote);
      if(quote_known)
        {
         const double spread = quote.ask - quote.bid;
         const double adverse_price =
            (direction > 0
             ? MathMax(0.0, price - quote.ask)
             : MathMax(0.0, quote.bid - price));
         spread_volume_sum += spread * volume;
         aggregate.adverse_slippage +=
            adverse_price * contract_size * volume;
        }
      else
         aggregate.cost_known = false;
      if(aggregate.first_deal == 0 ||
         time_msc < aggregate.first_time_msc ||
         (time_msc == aggregate.first_time_msc &&
          deal < aggregate.first_deal))
        {
         aggregate.first_deal = deal;
         aggregate.first_time_msc = time_msc;
         aggregate.first_time_server =
            (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
        }
      if(aggregate.last_deal == 0 ||
         time_msc > aggregate.last_time_msc ||
         (time_msc == aggregate.last_time_msc &&
          deal > aggregate.last_deal))
        {
         aggregate.last_deal = deal;
         aggregate.last_time_msc = time_msc;
        }
      ++aggregate.deal_count;
     }
   if(aggregate.deal_count <= 0 || aggregate.volume_steps <= 0 ||
      aggregate.first_deal == 0 || aggregate.last_deal == 0 ||
      aggregate.order_ticket == 0 || aggregate.first_time_server <= 0)
      return(false);
   aggregate.volume = (double)aggregate.volume_steps * step;
   aggregate.price = price_volume_sum / aggregate.volume;
   aggregate.spread_price = spread_volume_sum / aggregate.volume;
   return(MathIsValidNumber(aggregate.price) && aggregate.price > 0.0 &&
          MathIsValidNumber(aggregate.transaction_cost) &&
          MathIsValidNumber(aggregate.spread_price) &&
          aggregate.spread_price >= 0.0 &&
          MathIsValidNumber(aggregate.adverse_slippage) &&
          aggregate.adverse_slippage >= 0.0);
  }


bool EntryPositionIdentifierForOrder(const int component,
                                     const ulong order_ticket,
                                     ulong &position_identifier)
  {
   position_identifier = 0;
   if(order_ticket == 0 || !HistorySelect(0, TimeCurrent()))
      return(false);
   int matches = 0;
   for(int index = 0; index < HistoryDealsTotal(); ++index)
     {
      const ulong deal = HistoryDealGetTicket(index);
      if(deal == 0 ||
         (ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) !=
         component_definitions[component].magic ||
         HistoryDealGetString(deal, DEAL_SYMBOL) !=
         component_definitions[component].symbol ||
         (ulong)HistoryDealGetInteger(deal, DEAL_ORDER) != order_ticket)
         continue;
      const ENUM_DEAL_ENTRY entry =
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_IN)
         continue;
      const ulong identifier =
         (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      if(identifier == 0 ||
         (position_identifier != 0 && position_identifier != identifier))
         return(false);
      position_identifier = identifier;
      ++matches;
     }
   return(matches > 0 && position_identifier > 0);
  }


bool WaitForEntryDealAggregation(const int component,
                                 const ulong position_identifier,
                                 const MqlTick &sampled_tick,
                                 const long requested_steps,
                                 const bool completed_partial,
                                 EntryDealAggregate &aggregate,
                                 ulong &waited_ms)
  {
   waited_ms = 0;
   if(requested_steps <= 0)
      return(false);
   const ulong started = GetTickCount64();
   while(true)
     {
      ulong ticket = 0;
      datetime opened_at = 0;
      const int count = CountOwnedPositions(component, ticket, opened_at);
      long position_steps = 0;
      if(count == 1 && PositionSelectByTicket(ticket) &&
         (ulong)PositionGetInteger(POSITION_IDENTIFIER) ==
         position_identifier &&
         VolumeToSteps(component_definitions[component].symbol,
                       PositionGetDouble(POSITION_VOLUME),
                       position_steps) &&
         AggregateEntryDeals(component,
                             position_identifier,
                             0,
                             sampled_tick,
                             true,
                             aggregate) &&
         aggregate.volume_steps == position_steps &&
         aggregate.volume_steps <= requested_steps &&
         (completed_partial ||
          aggregate.volume_steps == requested_steps))
        {
         waited_ms = GetTickCount64() - started;
         return(true);
        }
      waited_ms = GetTickCount64() - started;
      if(count > 1 || tester_mode ||
         waited_ms >= COMPLETED_DEAL_RECONCILIATION_TIMEOUT_MS)
         return(false);
      Sleep(COMPLETED_DEAL_RECONCILIATION_POLL_MS);
     }
  }


int CollectUnprocessedExitDeals(const int component,
                                const ulong position_identifier,
                                SequencedExitDeal &deals[])
  {
   ArrayResize(deals, 0);
   if(position_identifier == 0 ||
      !HistorySelectByPosition(position_identifier))
      return(-1);
   for(int index = 0; index < HistoryDealsTotal(); ++index)
     {
      const ulong deal = HistoryDealGetTicket(index);
      if(deal == 0 ||
         (ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) !=
         component_definitions[component].magic ||
         HistoryDealGetString(deal, DEAL_SYMBOL) !=
         component_definitions[component].symbol ||
         (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID) !=
         position_identifier)
         continue;
      const ENUM_DEAL_ENTRY entry =
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
         continue;
      const long time_msc = HistoryDealGetInteger(deal, DEAL_TIME_MSC);
      if(time_msc <= 0)
         return(-1);
      if(!DealAfterExitCursor(component, time_msc, deal))
         continue;
      const int count = ArraySize(deals);
      if(ArrayResize(deals, count + 1) != count + 1)
         return(-1);
      deals[count].ticket = deal;
      deals[count].time_msc = time_msc;
     }
   const int count = ArraySize(deals);
   for(int index = 1; index < count; ++index)
     {
      const SequencedExitDeal current = deals[index];
      int cursor = index - 1;
      while(cursor >= 0 &&
            (deals[cursor].time_msc > current.time_msc ||
             (deals[cursor].time_msc == current.time_msc &&
              deals[cursor].ticket > current.ticket)))
        {
         deals[cursor + 1] = deals[cursor];
         --cursor;
        }
      deals[cursor + 1] = current;
     }
   return(count);
  }


bool ReconstructEntryTracking(const int component, const ulong ticket)
  {
   if(!PositionSelectByTicket(ticket))
      return(false);
   const ulong identifier =
      (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   MqlTick empty_tick = {};
   EntryDealAggregate aggregate = {};
   if(identifier == 0 ||
      !AggregateEntryDeals(component,
                           identifier,
                           0,
                           empty_tick,
                           false,
                           aggregate))
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("cannot reconstruct entry deal sequence");
      return(false);
     }
   if(!PositionSelectByTicket(ticket) ||
      (ulong)PositionGetInteger(POSITION_IDENTIFIER) != identifier)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("position changed during entry reconstruction");
      return(false);
     }
   const double volume = PositionGetDouble(POSITION_VOLUME);
   long current_steps = 0;
   long configured_steps = 0;
   if(!VolumeToSteps(component_definitions[component].symbol,
                     volume,
                     current_steps) ||
      aggregate.volume_steps < current_steps ||
      (component == US100_PASSIVE_LIMIT &&
       (!VolumeToSteps(component_definitions[component].symbol,
                       InpBaseVolume,
                       configured_steps) ||
        aggregate.volume_steps != configured_steps)))
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("entry reconstruction volume mismatch");
      return(false);
     }
   const ENUM_POSITION_TYPE position_type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   const int direction = (position_type == POSITION_TYPE_BUY ? 1 : -1);
   const datetime opened_at =
      (datetime)PositionGetInteger(POSITION_TIME);
   const double position_open_price =
      PositionGetDouble(POSITION_PRICE_OPEN);
   const double deal_price = aggregate.price;
   const bool quote_known = aggregate.cost_known;
   if(aggregate.direction != direction)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("entry reconstruction direction mismatch");
      return(false);
     }
   const double broker_stop_loss = PositionGetDouble(POSITION_SL);
   double recovered_stop_loss = 0.0;
   double recovered_planned_risk = 0.0;
   if(component == US100_PASSIVE_LIMIT)
     {
      if(passive_pending_stop_loss <= 0.0 ||
         passive_pending_planned_risk_usd <= 0.0)
        {
         execution_state.broker_mismatch = true;
         EngageSafetyStop("passive entry protection state cannot be reconstructed");
         return(false);
        }
      recovered_stop_loss = passive_pending_stop_loss;
      recovered_planned_risk = passive_pending_planned_risk_usd;
     }
   else
     {
      double gross_stop_risk = 0.0;
      const double modeled_target_fraction =
         1.0 - InpUnmodelledRiskReserveFraction -
         InpStopPlacementHeadroomFraction;
      const double current_position_budget =
         ConservativeRiskCapital() * InpMaximumPositionRiskFraction *
         ExecutableComponentVolumeMultiplier(component,
                                             component_definitions[component].symbol,
                                             aggregate.volume);
      if(broker_stop_loss <= 0.0 || current_position_budget <= 0.0 ||
         modeled_target_fraction <= 0.0 ||
         !GrossStopRisk(component_definitions[component].symbol,
                        direction,
                        aggregate.volume,
                        position_open_price,
                        broker_stop_loss,
                        gross_stop_risk))
        {
         execution_state.broker_mismatch = true;
         EngageSafetyStop("market entry broker protection cannot be reconstructed");
         return(false);
        }
      recovered_stop_loss = broker_stop_loss;
      recovered_planned_risk =
         MathMax(gross_stop_risk / modeled_target_fraction,
                 current_position_budget);
      if(!MathIsValidNumber(recovered_planned_risk) ||
         recovered_planned_risk <= 0.0)
        {
         execution_state.broker_mismatch = true;
         EngageSafetyStop("market entry risk reserve cannot be reconstructed");
         return(false);
        }
     }
   component_states[component].position_identifier = identifier;
   component_states[component].entry_time_server = aggregate.first_time_server;
   component_states[component].entry_direction = direction;
   component_states[component].entry_volume = aggregate.volume;
   component_states[component].entry_feature =
      (component == US100_PASSIVE_LIMIT
       ? passive_pending_feature : 0.0);
   component_states[component].entry_stop_loss = recovered_stop_loss;
   component_states[component].entry_planned_risk_usd = recovered_planned_risk;
   component_states[component].entry_transaction_cost = aggregate.transaction_cost;
   component_states[component].entry_spread_price = aggregate.spread_price;
   component_states[component].entry_adverse_slippage = aggregate.adverse_slippage;
   component_states[component].entry_cost_known = quote_known;
   string protection_detail = "";
   double actual_planned_risk = 0.0;
   if(!SelectedPositionProtectionMatches(component, protection_detail) ||
       !BufferedPlannedRisk(component_definitions[component].symbol,
                            direction,
                            volume,
                            position_open_price,
                            PositionGetDouble(POSITION_SL),
                            actual_planned_risk))
     {
      ++protection_mismatches;
      execution_state.broker_mismatch = true;
      EngageSafetyStop("reconstructed entry protection mismatch: " +
                       protection_detail);
      return(false);
     }
   component_states[component].entry_stop_loss = PositionGetDouble(POSITION_SL);
   const datetime entry_bar = BarForTime(component, opened_at);
   if(entry_bar > component_states[component].last_decision_bar)
      component_states[component].last_decision_bar = entry_bar;
   if(component == US100_PASSIVE_LIMIT)
     {
      ++passive_completed_entries;
      ClearPassivePendingTracking();
     }
   const double aggregate_planned_risk = TrackedAggregatePlannedRisk();
   if(aggregate_planned_risk > portfolio_state.maximum_aggregate_planned_risk_usd)
      portfolio_state.maximum_aggregate_planned_risk_usd = aggregate_planned_risk;
   if(!quote_known)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("entry quote history unavailable during recovery");
     }
   RecordEvent(component,
                (component == US100_PASSIVE_LIMIT
                 ? "PASSIVE_FILL" : "RECOVER_MARKET_OPEN"),
               deal_price,
               aggregate.volume,
               StringFormat("%s entry_deals=%d current_volume=%.2f",
                            (quote_known ? "cost-known" : "cost-unknown"),
                            aggregate.deal_count,
                            volume));
   if(!SaveState())
      return(false);
   if(aggregate.volume_steps > current_steps)
     {
      ulong waited_ms = 0;
      if(!ReconcileExitDealSequence(component,
                                    empty_tick,
                                    false,
                                    "RECOVER_PARTIAL",
                                    false,
                                    waited_ms))
        {
         execution_state.broker_mismatch = true;
         EngageSafetyStop("reconstructed partial exits do not match position");
         return(false);
        }
     }
   return(true);
  }


bool ReconstructClosedPassiveEntry(const ulong order_ticket)
  {
   if(order_ticket == 0 ||
      component_states[US100_PASSIVE_LIMIT].position_identifier > 0)
      return(false);
   ulong identifier = 0;
   MqlTick empty_tick = {};
   EntryDealAggregate aggregate = {};
   long configured_steps = 0;
   if(!EntryPositionIdentifierForOrder(US100_PASSIVE_LIMIT,
                                       order_ticket,
                                       identifier) ||
      !AggregateEntryDeals(US100_PASSIVE_LIMIT,
                           identifier,
                           order_ticket,
                           empty_tick,
                           false,
                           aggregate) ||
      !aggregate.cost_known ||
      !VolumeToSteps("US100", InpBaseVolume, configured_steps) ||
      aggregate.volume_steps != configured_steps)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("historical passive entry contract mismatch");
      return(false);
     }
   const int direction = aggregate.direction;
   const double volume = aggregate.volume;
   const double deal_price = aggregate.price;
   component_states[US100_PASSIVE_LIMIT].position_identifier = identifier;
   component_states[US100_PASSIVE_LIMIT].entry_time_server =
      aggregate.first_time_server;
   component_states[US100_PASSIVE_LIMIT].entry_direction = direction;
   component_states[US100_PASSIVE_LIMIT].entry_volume = volume;
   component_states[US100_PASSIVE_LIMIT].entry_feature = passive_pending_feature;
   if(passive_pending_stop_loss <= 0.0 ||
      passive_pending_planned_risk_usd <= 0.0)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("historical passive protection state missing");
      return(false);
     }
   component_states[US100_PASSIVE_LIMIT].entry_stop_loss = passive_pending_stop_loss;
   component_states[US100_PASSIVE_LIMIT].entry_planned_risk_usd =
      passive_pending_planned_risk_usd;
   component_states[US100_PASSIVE_LIMIT].entry_transaction_cost =
      aggregate.transaction_cost;
   component_states[US100_PASSIVE_LIMIT].entry_spread_price = aggregate.spread_price;
   component_states[US100_PASSIVE_LIMIT].entry_adverse_slippage =
      aggregate.adverse_slippage;
   component_states[US100_PASSIVE_LIMIT].entry_cost_known = aggregate.cost_known;
   double actual_planned_risk = 0.0;
   if(!BufferedPlannedRisk("US100",
                           direction,
                           volume,
                           deal_price,
                           component_states[US100_PASSIVE_LIMIT].entry_stop_loss,
                           actual_planned_risk) ||
      actual_planned_risk >
      component_states[US100_PASSIVE_LIMIT].entry_planned_risk_usd +
      MathMax(0.01,
              component_states[US100_PASSIVE_LIMIT].entry_planned_risk_usd * 0.01))
     {
      ++protection_mismatches;
      execution_state.broker_mismatch = true;
      EngageSafetyStop("historical passive risk exceeds admission");
      return(false);
     }
   const datetime entry_bar =
      BarForTime(US100_PASSIVE_LIMIT,
                 component_states[US100_PASSIVE_LIMIT].entry_time_server);
   if(entry_bar > component_states[US100_PASSIVE_LIMIT].last_decision_bar)
      component_states[US100_PASSIVE_LIMIT].last_decision_bar = entry_bar;
   ++passive_completed_entries;
   ClearPassivePendingTracking();
   RecordEvent(US100_PASSIVE_LIMIT,
               "RECOVER_PASSIVE_FILL",
               deal_price,
               volume,
               StringFormat("feature=%.8f entry_deals=%d order=%I64u",
                            component_states[US100_PASSIVE_LIMIT].entry_feature,
                            aggregate.deal_count,
                            order_ticket));
   if(!SaveState())
      return(false);
   ulong waited_ms = 0;
   if(!ReconcileExitDealSequence(US100_PASSIVE_LIMIT,
                                 empty_tick,
                                 false,
                                 "RECOVER_PASSIVE_CLOSE",
                                 false,
                                 waited_ms))
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("filled passive order lacks complete exit sequence");
      return(false);
     }
   return(true);
  }


bool BuildMarketEntryPlan(const int component,
                          const int direction,
                          const double feature,
                          MarketEntryPlan &plan,
                          MarketEntryOutcome &outcome)
  {
   if(direction == 0 || !NewEntriesOperationallyAllowed())
     {
      component_states[component].entry_check_result = "ENTRY_BLOCKED";
      outcome.code = MARKET_ENTRY_ENTRY_BLOCKED;
      outcome.entry_check_result = "ENTRY_BLOCKED";
      return(false);
     }
   if(!AuditPositionOwnership() || execution_state.foreign_exposure)
     {
      component_states[component].entry_check_result = "OWNERSHIP_BLOCKED";
      outcome.code = MARKET_ENTRY_OWNERSHIP_BLOCKED;
      outcome.entry_check_result = "OWNERSHIP_BLOCKED";
      return(false);
     }
   ulong existing_ticket = 0;
   datetime existing_opened_at = 0;
   if(CountOwnedPositions(component,
                          existing_ticket,
                          existing_opened_at) != 0)
     {
      component_states[component].entry_check_result = "EXISTING_EXPOSURE";
      outcome.code = MARKET_ENTRY_EXISTING_EXPOSURE;
      outcome.entry_check_result = "EXISTING_EXPOSURE";
      return(false);
     }
   const string symbol = component_definitions[component].symbol;
   const double volume = NormalizedComponentVolume(component, symbol);
   if(volume <= 0.0)
     {
      component_states[component].entry_check_result = "VOLUME_INVALID";
      outcome.code = MARKET_ENTRY_VOLUME_INVALID;
      outcome.entry_check_result = "VOLUME_INVALID";
      return(false);
     }
   component_states[component].entry_check_volume = volume;
   MqlTick tick = {};
   if(!ExecutableTick(symbol, tick))
     {
      component_states[component].entry_check_result = "QUOTE_UNAVAILABLE";
      outcome.code = MARKET_ENTRY_QUOTE_UNAVAILABLE;
      outcome.entry_check_result = "QUOTE_UNAVAILABLE";
      return(false);
     }
   const double entry_price = (direction > 0 ? tick.ask : tick.bid);
   component_states[component].entry_check_order_price = entry_price;
   const double base_protection_distance = MinimumProtectionDistance(symbol);
   const double minimum_protection_distance =
      (direction > 0
       ? entry_price - (tick.bid - base_protection_distance)
       : (tick.ask + base_protection_distance) - entry_price);
   double stop_loss = 0.0;
   double admitted_planned_risk = 0.0;
   if(!CalculateProtectiveStop(component,
                               symbol,
                               direction,
                               volume,
                               entry_price,
                               minimum_protection_distance,
                               stop_loss,
                               admitted_planned_risk))
     {
      component_states[component].entry_check_result = "PROTECTION_OR_RISK_BLOCKED";
      SaveState();
      outcome.code = MARKET_ENTRY_PROTECTION_OR_RISK_BLOCKED;
      outcome.entry_check_result = "PROTECTION_OR_RISK_BLOCKED";
      return(false);
     }
   component_states[component].entry_check_stop_loss = stop_loss;
   component_states[component].entry_check_planned_risk_usd = admitted_planned_risk;
   const double admitted_capital = ConservativeRiskCapital();
   const double aggregate_before = TrackedAggregatePlannedRisk();
   if(!TradeSessionAllows(symbol, TimeCurrent(), true))
     {
      component_states[component].entry_check_result = "TRADE_SESSION_BLOCKED";
      outcome.code = MARKET_ENTRY_SESSION_BLOCKED;
      outcome.entry_check_result = "TRADE_SESSION_BLOCKED";
      return(false);
     }
   if(!MarginAllows(symbol, direction, volume))
     {
      component_states[component].entry_check_result = "MARGIN_BLOCKED";
      outcome.code = MARKET_ENTRY_MARGIN_BLOCKED;
      outcome.entry_check_result = "MARGIN_BLOCKED";
      return(false);
     }
   plan.component = component;
   plan.symbol = symbol;
   plan.magic = component_definitions[component].magic;
   plan.direction = direction;
   plan.feature = feature;
   plan.volume = volume;
   plan.sampled_tick = tick;
   plan.expected_entry_price = entry_price;
   plan.requested_stop_loss = stop_loss;
   plan.admitted_planned_risk = admitted_planned_risk;
   plan.admitted_capital = admitted_capital;
   plan.aggregate_before = aggregate_before;
   plan.decision_bar = decision_intent.decision_bar;
   plan.deadline = decision_intent.deadline;
   plan.comment = "ZN " + IntegerToString(component + 1) + " PCR2";
   return(true);
  }


bool PersistMarketEntryIntent(const MarketEntryPlan &plan,
                              MarketEntryOutcome &outcome)
  {
   trade.SetExpertMagicNumber(plan.magic);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol(plan.symbol);
   trade.SetMarginMode();
   trade.SetAsyncMode(false);
   decision_intent.order_type =
      (plan.direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   decision_intent.order_type_known = true;
   decision_intent.intended_price = plan.expected_entry_price;
   decision_intent.expiration = decision_intent.deadline;
   decision_intent.volume = plan.volume;
   decision_intent.stop_loss = plan.requested_stop_loss;
   decision_intent.planned_risk_usd = plan.admitted_planned_risk;
   if(!MarkDecisionOrderAttempted(plan.component,
                                  plan.direction,
                                  plan.feature,
                                  "MARKET_OPEN"))
     {
      component_states[plan.component].entry_check_result = "PERSISTENCE_FAILED";
      outcome.code = MARKET_ENTRY_DURABLE_INTENT_FAILED;
      outcome.entry_check_result = "PERSISTENCE_FAILED";
      return(false);
     }
   return(true);
  }


void SubmitMarketEntry(const MarketEntryPlan &plan,
                       MarketSubmitReceipt &receipt)
  {
   execution_state.trade_operation_active = true;
   receipt.requested =
      (plan.direction > 0
       ? trade.Buy(plan.volume,
                   plan.symbol,
                   0.0,
                   plan.requested_stop_loss,
                   0.0,
                   plan.comment)
       : trade.Sell(plan.volume,
                    plan.symbol,
                    0.0,
                    plan.requested_stop_loss,
                    0.0,
                    plan.comment));
   receipt.retcode = trade.ResultRetcode();
   receipt.retcode_description = trade.ResultRetcodeDescription();
   receipt.result_volume = trade.ResultVolume();
   receipt.result_price = trade.ResultPrice();
   receipt.result_order = trade.ResultOrder();
   receipt.result_deal = trade.ResultDeal();
   execution_state.trade_operation_active = false;
   if(!receipt.requested ||
      !IsCompletedMarketTradeRetcode(receipt.retcode))
     {
      component_states[plan.component].entry_check_result = "BROKER_REJECTED";
      RecordEvent(plan.component,
                  "OPEN_FAIL",
                  (double)receipt.retcode,
                  plan.feature,
                  receipt.retcode_description);
      SaveState();
     }
  }


bool ObserveMarketEntry(const MarketEntryPlan &plan,
                        const MarketSubmitReceipt &receipt,
                        MarketEntryObservation &observation,
                        MarketEntryOutcome &outcome)
  {
   if(!WaitForSingleOwnedPosition(plan.component,
                                  observation.position_ticket,
                                  observation.opened_at))
     {
      component_states[plan.component].entry_check_result = "SAFETY_STOP";
      execution_state.broker_mismatch = true;
      EngageSafetyStop("entry position unavailable after bounded reconciliation");
      execution_state.pending_reconcile = true;
      MakeExistingRiskSafe("entry broker state mismatch");
      outcome.code = MARKET_ENTRY_OBSERVATION_FAILED;
      outcome.safety_stop_engaged = true;
      outcome.entry_check_result = "SAFETY_STOP";
      return(false);
     }
   if(!PositionSelectByTicket(observation.position_ticket))
     {
      component_states[plan.component].entry_check_result = "SAFETY_STOP";
      execution_state.broker_mismatch = true;
      EngageSafetyStop("entry position identity unavailable after bounded reconciliation");
      execution_state.pending_reconcile = true;
      MakeExistingRiskSafe("entry position identity unavailable");
      outcome.code = MARKET_ENTRY_OBSERVATION_FAILED;
      outcome.safety_stop_engaged = true;
      outcome.entry_check_result = "SAFETY_STOP";
      return(false);
     }
   observation.expected_position_identifier =
      (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   if(observation.expected_position_identifier == 0 ||
      !VolumeToSteps(plan.symbol,
                     plan.volume,
                     observation.requested_steps) ||
      !WaitForEntryDealAggregation(
         plan.component,
         observation.expected_position_identifier,
         plan.sampled_tick,
         observation.requested_steps,
         receipt.retcode == TRADE_RETCODE_DONE_PARTIAL,
         observation.aggregate,
         observation.deal_wait_ms))
     {
      component_states[plan.component].entry_check_result = "SAFETY_STOP";
      execution_state.broker_mismatch = true;
      EngageSafetyStop("entry deal sequence unavailable after bounded reconciliation");
      execution_state.pending_reconcile = true;
      MakeExistingRiskSafe("entry deal sequence unavailable");
      outcome.code = MARKET_ENTRY_OBSERVATION_FAILED;
      outcome.safety_stop_engaged = true;
      outcome.entry_check_result = "SAFETY_STOP";
      return(false);
     }
   if(!PositionSelectByTicket(observation.position_ticket))
     {
      component_states[plan.component].entry_check_result = "SAFETY_STOP";
      execution_state.broker_mismatch = true;
      EngageSafetyStop("authoritative entry state became unavailable");
      execution_state.pending_reconcile = true;
      MakeExistingRiskSafe("authoritative entry state unavailable");
      outcome.code = MARKET_ENTRY_OBSERVATION_FAILED;
      outcome.safety_stop_engaged = true;
      outcome.entry_check_result = "SAFETY_STOP";
      return(false);
     }
   observation.position_identifier =
      (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   observation.position_magic =
      (ulong)PositionGetInteger(POSITION_MAGIC);
   observation.position_symbol = PositionGetString(POSITION_SYMBOL);
   observation.position_type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   observation.position_volume = PositionGetDouble(POSITION_VOLUME);
   observation.position_open_price =
      PositionGetDouble(POSITION_PRICE_OPEN);
   observation.broker_stop_loss = PositionGetDouble(POSITION_SL);
   return(true);
  }


void SeedProvisionalMarketLifecycle(
   const MarketEntryPlan &plan,
   const MarketEntryObservation &observation)
  {
   component_states[plan.component].position_identifier =
      observation.position_identifier;
   component_states[plan.component].entry_time_server =
      observation.aggregate.first_time_server;
   component_states[plan.component].entry_direction = plan.direction;
   component_states[plan.component].entry_volume = observation.position_volume;
   component_states[plan.component].entry_feature = plan.feature;
   component_states[plan.component].entry_stop_loss =
      observation.broker_stop_loss;
   component_states[plan.component].entry_planned_risk_usd =
      plan.admitted_planned_risk;
   component_states[plan.component].entry_spread_price =
      observation.aggregate.spread_price;
   component_states[plan.component].entry_transaction_cost =
      observation.aggregate.transaction_cost;
   component_states[plan.component].entry_adverse_slippage =
      observation.aggregate.adverse_slippage;
   component_states[plan.component].entry_cost_known =
      observation.aggregate.cost_known;
  }


bool ValidateMarketEntry(const MarketEntryPlan &plan,
                         const MarketSubmitReceipt &receipt,
                         const MarketEntryObservation &observation,
                         MarketEntryOutcome &outcome)
  {
   const ulong published_entry_order = observation.aggregate.order_ticket;
   const ulong entry_deal = observation.aggregate.first_deal;
   const double deal_volume = observation.aggregate.volume;
   const double deal_price = observation.aggregate.price;
   const double volume_step =
      SymbolInfoDouble(plan.symbol, SYMBOL_VOLUME_STEP);
   long position_steps = 0;
   const bool deal_direction_matches =
      (observation.aggregate.direction == plan.direction);
   const bool position_direction_matches =
      (plan.direction > 0
       ? observation.position_type == POSITION_TYPE_BUY
       : observation.position_type == POSITION_TYPE_SELL);
   const bool execution_identity_valid =
      published_entry_order > 0 &&
      observation.position_identifier > 0 &&
      observation.position_identifier ==
      observation.expected_position_identifier &&
      observation.position_magic == plan.magic &&
      observation.position_symbol == plan.symbol &&
      deal_direction_matches &&
      position_direction_matches &&
      volume_step > 0.0 && deal_volume > 0.0 &&
      observation.position_volume > 0.0 && deal_price > 0.0 &&
      observation.position_open_price > 0.0 &&
      observation.aggregate.cost_known &&
      VolumeToSteps(plan.symbol,
                    observation.position_volume,
                    position_steps) &&
      observation.aggregate.volume_steps == position_steps &&
      position_steps <= observation.requested_steps;
   if(!execution_identity_valid)
     {
      component_states[plan.component].entry_check_result = "SAFETY_STOP";
      execution_state.broker_mismatch = true;
      RecordEvent(plan.component,
                  "OPEN_EXECUTION_MISMATCH",
                  deal_price,
                  observation.position_volume,
                  StringFormat("result_order=%I64u published_order=%I64u result_deal=%I64u first_deal=%I64u last_deal=%I64u entry_deals=%d result_price=%.5f result_volume=%.2f requested_steps=%I64d position_steps=%I64d broker_position=%I64u magic=%I64u symbol=%s aggregate_direction=%d position_type=%d",
                               receipt.result_order,
                               published_entry_order,
                               receipt.result_deal,
                               entry_deal,
                               observation.aggregate.last_deal,
                               observation.aggregate.deal_count,
                               receipt.result_price,
                               receipt.result_volume,
                               observation.requested_steps,
                               position_steps,
                               observation.position_identifier,
                               observation.position_magic,
                               observation.position_symbol,
                               observation.aggregate.direction,
                               (int)observation.position_type));
      EngageSafetyStop("authoritative entry execution identity mismatch");
      execution_state.pending_reconcile = true;
      outcome.code = MARKET_ENTRY_IDENTITY_MISMATCH;
      outcome.protective_close_requested = true;
      outcome.safety_stop_engaged = true;
      outcome.entry_check_result = "SAFETY_STOP";
      CloseComponent(plan.component, observation.position_ticket);
      return(false);
     }

   double actual_planned_risk = 0.0;
   const double protection_tolerance =
      MathMax(0.01, plan.admitted_planned_risk * 0.01);
   const double tick_size =
      SymbolInfoDouble(plan.symbol, SYMBOL_TRADE_TICK_SIZE);
   const bool stop_present = observation.broker_stop_loss > 0.0;
   const bool stop_direction_valid =
      (plan.direction > 0
       ? observation.broker_stop_loss < observation.position_open_price
       : observation.broker_stop_loss > observation.position_open_price);
   const bool stop_matches_request =
      tick_size > 0.0 &&
      MathAbs(observation.broker_stop_loss - plan.requested_stop_loss) <=
      0.5 * tick_size + 1.0e-9;
   const bool risk_known =
      BufferedPlannedRisk(plan.symbol,
                          plan.direction,
                          observation.position_volume,
                          observation.position_open_price,
                          observation.broker_stop_loss,
                          actual_planned_risk);
   const bool position_risk_within_cap =
      risk_known &&
      actual_planned_risk <= plan.admitted_planned_risk + protection_tolerance;
   const bool aggregate_risk_within_cap =
      risk_known &&
      plan.aggregate_before + actual_planned_risk <=
      plan.admitted_capital * InpMaximumAggregateRiskFraction +
      protection_tolerance;
   const bool protection_valid =
      stop_present && stop_direction_valid && stop_matches_request &&
      position_risk_within_cap && aggregate_risk_within_cap;
   if(!protection_valid)
     {
      component_states[plan.component].entry_check_result = "SAFETY_STOP";
      ++protection_mismatches;
      execution_state.broker_mismatch = true;
      RecordEvent(plan.component,
                  "OPEN_PROTECTION_MISMATCH",
                  component_states[plan.component].entry_stop_loss,
                  component_states[plan.component].entry_planned_risk_usd,
                  StringFormat("deal_price=%.5f position_open=%.5f result_price=%.5f broker_stop=%.5f requested_stop=%.5f actual_risk=%.4f admitted_risk=%.4f aggregate_before=%.4f stop_present=%d stop_direction=%d stop_exact=%d risk_known=%d position_cap=%d aggregate_cap=%d",
                               deal_price,
                               observation.position_open_price,
                               receipt.result_price,
                               observation.broker_stop_loss,
                               plan.requested_stop_loss,
                               actual_planned_risk,
                               plan.admitted_planned_risk,
                               plan.aggregate_before,
                               (int)stop_present,
                               (int)stop_direction_valid,
                               (int)stop_matches_request,
                               (int)risk_known,
                               (int)position_risk_within_cap,
                               (int)aggregate_risk_within_cap));
      EngageSafetyStop("market entry protection not confirmed");
      outcome.code = MARKET_ENTRY_PROTECTION_MISMATCH;
      outcome.protective_close_requested = true;
      outcome.safety_stop_engaged = true;
      outcome.entry_check_result = "SAFETY_STOP";
      CloseComponent(plan.component, observation.position_ticket);
      return(false);
     }
   return(true);
  }


bool AdoptMarketEntry(const MarketEntryPlan &plan,
                      const MarketEntryObservation &observation,
                      MarketEntryOutcome &outcome)
  {
   if(!MarkDecisionBrokerStateAdopted(plan.component,
                                      observation.position_identifier,
                                      "POSITION_ADOPTED"))
     {
      component_states[plan.component].entry_check_result = "SAFETY_STOP";
      EngageSafetyStop("adopted position journal could not be persisted");
      outcome.code = MARKET_ENTRY_ADOPTION_PERSIST_FAILED;
      outcome.protective_close_requested = true;
      outcome.safety_stop_engaged = true;
      outcome.entry_check_result = "SAFETY_STOP";
      CloseComponent(plan.component, observation.position_ticket);
      return(false);
     }
   return(true);
  }


bool FinalizeMarketEntry(const MarketEntryPlan &plan,
                         const MarketSubmitReceipt &receipt,
                         const MarketEntryObservation &observation,
                         MarketEntryOutcome &outcome)
  {
   const ulong published_entry_order = observation.aggregate.order_ticket;
   const ulong entry_deal = observation.aggregate.first_deal;
   const double deal_price = observation.aggregate.price;
   component_states[plan.component].entry_check_result = "POSITION_OPEN";
   RecordEvent(plan.component,
               "OPEN",
               deal_price,
               observation.position_volume,
               StringFormat("feature=%.8f position_open=%.5f result_price=%.5f result_volume=%.2f filled_volume=%.2f entry_deals=%d stop=%.5f planned_risk=%.4f deal_wait_ms=%I64u order=%I64u first_deal=%I64u last_deal=%I64u",
                            plan.feature,
                            observation.position_open_price,
                            receipt.result_price,
                            receipt.result_volume,
                            observation.position_volume,
                            observation.aggregate.deal_count,
                            component_states[plan.component].entry_stop_loss,
                            component_states[plan.component].entry_planned_risk_usd,
                            observation.deal_wait_ms,
                            published_entry_order,
                            entry_deal,
                            observation.aggregate.last_deal));
   if(!SaveState())
     {
      EngageSafetyStop("entry state could not be persisted");
      outcome.code = MARKET_ENTRY_FINAL_PERSIST_FAILED;
      outcome.safety_stop_engaged = true;
      outcome.entry_check_result = "POSITION_OPEN";
      return(false);
     }
   outcome.code = MARKET_ENTRY_POSITION_OPEN;
   outcome.entry_check_result = "POSITION_OPEN";
   return(true);
  }


bool OpenComponent(const int component,
                   const int direction,
                   const double feature)
  {
   MarketEntryPlan plan = {};
   MarketSubmitReceipt receipt = {};
   MarketEntryObservation observation = {};
   MarketEntryOutcome outcome = {};
   outcome.code = MARKET_ENTRY_NOT_STARTED;
   if(!BuildMarketEntryPlan(component,
                            direction,
                            feature,
                            plan,
                            outcome))
      return(false);
   if(!PersistMarketEntryIntent(plan, outcome))
      return(false);
   SubmitMarketEntry(plan, receipt);
   outcome.broker_call_made = true;
   if(!receipt.requested ||
      !IsCompletedMarketTradeRetcode(receipt.retcode))
     {
      outcome.code = MARKET_ENTRY_SUBMIT_REJECTED;
      outcome.entry_check_result = "BROKER_REJECTED";
      return(false);
     }
   if(!ObserveMarketEntry(plan, receipt, observation, outcome))
      return(true);
   SeedProvisionalMarketLifecycle(plan, observation);
   if(!ValidateMarketEntry(plan, receipt, observation, outcome))
      return(true);
   if(!AdoptMarketEntry(plan, observation, outcome))
      return(true);
   FinalizeMarketEntry(plan, receipt, observation, outcome);
   return(true);
  }


bool CloseComponent(const int component, const ulong ticket)
  {
   const datetime now = TimeCurrent();
   if(component_states[component].last_close_attempt_server > 0 &&
      now - component_states[component].last_close_attempt_server < 60)
      return(false);
   if(!PositionSelectByTicket(ticket))
      return(false);
   const string symbol = PositionGetString(POSITION_SYMBOL);
   if(!TradeSessionAllows(symbol, now, false))
     {
      component_states[component].last_close_attempt_server = now;
      return(false);
     }
   MqlTick tick = {};
   if(!StructurallyValidTick(symbol, tick))
      return(false);
   const double tick_age_seconds =
      MathAbs((double)((long)TimeCurrent() - (long)tick.time));
   const bool sampled_tick_known =
      (tick_age_seconds <= MAX_EXECUTABLE_TICK_AGE_SECONDS);
   component_states[component].last_close_attempt_server = now;
   trade.SetExpertMagicNumber(component_definitions[component].magic);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol(symbol);
   trade.SetAsyncMode(false);
   execution_state.trade_operation_active = true;
   const bool requested = trade.PositionClose(ticket, InpDeviationPoints);
   const uint retcode = trade.ResultRetcode();
   const string retcode_description = trade.ResultRetcodeDescription();
   const ulong close_order = trade.ResultOrder();
   const ulong returned_close_deal = trade.ResultDeal();
   execution_state.trade_operation_active = false;
   if((!requested || !IsCompletedMarketTradeRetcode(retcode)) &&
      retcode == TRADE_RETCODE_POSITION_CLOSED &&
      !PositionSelectByTicket(ticket))
     {
      MqlTick empty_tick = {};
      ulong waited_ms = 0;
      if(ReconcileExitDealSequence(component,
                                   empty_tick,
                                   false,
                                   "CLOSE_RACE",
                                   true,
                                   waited_ms))
         return(true);
      execution_state.pending_reconcile = true;
      RecordEvent(component,
                  "CLOSE_RACE_PENDING",
                  (double)retcode,
                  (double)ticket,
                  retcode_description);
      SaveState();
      return(true);
     }
   if(!requested || !IsCompletedMarketTradeRetcode(retcode))
     {
      RecordEvent(component,
                   "CLOSE_FAIL",
                   (double)retcode,
                   0.0,
                   retcode_description);
      SaveState();
      return(false);
     }

   ulong close_deal_wait_ms = 0;
   if(!ReconcileExitDealSequence(component,
                                 tick,
                                 sampled_tick_known,
                                 "CLOSE",
                                 true,
                                 close_deal_wait_ms))
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("close deal sequence unavailable after bounded reconciliation");
      execution_state.pending_reconcile = true;
      return(false);
     }
   if(close_deal_wait_ms > 0)
      PrintFormat("%s close deals reconciled after %I64u ms component=%s result_order=%I64u result_deal=%I64u remaining=%.2f",
                  EXECUTION_VERSION,
                  close_deal_wait_ms,
                  component_definitions[component].id,
                  close_order,
                  returned_close_deal,
                  component_states[component].entry_volume);
   return(true);
  }


#endif
