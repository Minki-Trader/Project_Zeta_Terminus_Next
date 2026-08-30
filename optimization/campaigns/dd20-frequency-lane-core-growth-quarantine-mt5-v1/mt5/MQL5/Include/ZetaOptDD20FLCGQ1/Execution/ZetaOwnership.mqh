#ifndef ZETA_OPT_DD20_FLCGQ1_MODULE_10_MQH
#define ZETA_OPT_DD20_FLCGQ1_MODULE_10_MQH

// Behavior-preserving function extraction from B70 V6R6: Execution\ZetaOwnership.mqh

bool IsOwnedMagic(const ulong magic)
  {
   if(magic == MAGIC_US500_H4_STAGED_OVERLAY)
      return(true);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(component_definitions[component].magic == magic)
         return(true);
   return(false);
  }


bool SelectedOrderIsOwnedStopLossTransit(int &component)
  {
   component = -1;
   const string symbol = OrderGetString(ORDER_SYMBOL);
   const ulong magic = (ulong)OrderGetInteger(ORDER_MAGIC);
   for(int candidate = 0; candidate < COMPONENT_COUNT; ++candidate)
     {
      if(component_definitions[candidate].magic == magic &&
         component_definitions[candidate].symbol == symbol)
        {
         component = candidate;
         break;
        }
     }
   if(component < 0)
      return(false);

   const ENUM_ORDER_TYPE type =
      (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
   const ENUM_ORDER_REASON reason =
      (ENUM_ORDER_REASON)OrderGetInteger(ORDER_REASON);
   if((type != ORDER_TYPE_BUY && type != ORDER_TYPE_SELL) ||
      reason != ORDER_REASON_SL)
      return(false);

   const ulong saved_identifier =
      component_states[component].position_identifier;
   const int saved_direction = component_states[component].entry_direction;
   const double saved_volume = component_states[component].entry_volume;
   if(saved_identifier == 0 || MathAbs(saved_direction) != 1 ||
      saved_volume <= 0.0 ||
      (saved_direction > 0 && type != ORDER_TYPE_SELL) ||
      (saved_direction < 0 && type != ORDER_TYPE_BUY))
      return(false);

   const double volume_step =
      SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   const double order_volume = OrderGetDouble(ORDER_VOLUME_INITIAL);
   if(volume_step <= 0.0 || order_volume <= 0.0 ||
      MathAbs(order_volume - saved_volume) >
      0.5 * volume_step + 1.0e-9)
      return(false);

   const ulong linked_identifier =
      (ulong)OrderGetInteger(ORDER_POSITION_ID);
   return(linked_identifier == 0 || linked_identifier == saved_identifier);
  }


void EngageSafetyStop(const string reason)
  {
   if(portfolio_state.safety_stopped)
      return;
   portfolio_state.safety_stopped = true;
   PrintFormat("%s SAFETY_STOP %s", EXECUTION_VERSION, reason);
   if(execution_state.runtime_ready)
     {
      RecordEvent(-1, "SAFETY_STOP", 0.0, 0.0, reason);
      SaveState();
     }
  }


bool LiveAccountIdentityCompatible()
  {
   if(tester_mode)
      return(true);
   const long current_login =
      (long)AccountInfoInteger(ACCOUNT_LOGIN);
   if(portfolio_state.bound_account_login <= 0 || current_login != portfolio_state.bound_account_login)
      return(false);
   if(!InpAllowNewEntries)
      return(true);
   return(InpExpectedLiveAccountLogin > 0 &&
          current_login == InpExpectedLiveAccountLogin);
  }


bool EnforceLiveAccountIdentity()
  {
   if(LiveAccountIdentityCompatible())
      return(true);
   execution_state.broker_mismatch = true;
   EngageSafetyStop("live account identity mismatch");
   return(false);
  }


bool AuditPositionOwnership()
  {
   execution_state.foreign_exposure = false;
   int owned_counts[COMPONENT_COUNT];
   ArrayInitialize(owned_counts, 0);
   int passive_order_count = 0;
   int h4_overlay_owned_count = 0;
   for(int index = PositionsTotal() - 1; index >= 0; --index)
     {
      const ulong ticket = PositionGetTicket(index);
      if(ticket == 0)
         continue;
      const string symbol = PositionGetString(POSITION_SYMBOL);
      const ulong magic = (ulong)PositionGetInteger(POSITION_MAGIC);
      bool matched = false;
      if(magic == MAGIC_US500_H4_STAGED_OVERLAY &&
         symbol == US500_H4_STAGED_OVERLAY_SYMBOL)
        {
         ++h4_overlay_owned_count;
         matched = true;
        }
      for(int component = 0; component < COMPONENT_COUNT; ++component)
        {
          if(magic == component_definitions[component].magic &&
             symbol == component_definitions[component].symbol)
            {
             ++owned_counts[component];
             matched = true;
             if(component_states[component].position_identifier == 0)
                execution_state.pending_reconcile = true;
             else
               {
                string protection_detail = "";
                if(!SelectedPositionProtectionMatches(component,
                                                      protection_detail))
                  {
                   ++protection_mismatches;
                   execution_state.broker_mismatch = true;
                   EngageSafetyStop("owned position protection mismatch: " +
                                    protection_detail);
                   return(false);
                  }
               }
             break;
           }
        }
      if(!matched)
        {
         if(IsOwnedMagic(magic))
           {
            execution_state.broker_mismatch = true;
            EngageSafetyStop("owned Magic Number on mismatched symbol");
            return(false);
           }
         execution_state.foreign_exposure = true;
        }
     }
   for(int index = OrdersTotal() - 1; index >= 0; --index)
     {
      const ulong ticket = OrderGetTicket(index);
      if(ticket == 0)
         continue;
      const string symbol = OrderGetString(ORDER_SYMBOL);
      const ulong magic = (ulong)OrderGetInteger(ORDER_MAGIC);
      int stop_loss_component = -1;
      if(SelectedOrderIsOwnedStopLossTransit(stop_loss_component) &&
         owned_counts[stop_loss_component] == 1)
         continue;
      if(magic == MAGIC_US100_PASSIVE_LIMIT && symbol == "US100")
        {
         const ENUM_ORDER_TYPE type =
            (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
          if(type != ORDER_TYPE_BUY_LIMIT && type != ORDER_TYPE_SELL_LIMIT)
           {
            execution_state.broker_mismatch = true;
            EngageSafetyStop("unexpected passive pending-order type");
             return(false);
            }
          string protection_detail = "";
          if(!SelectedPassiveOrderProtectionMatches(protection_detail))
            {
             ++protection_mismatches;
             execution_state.broker_mismatch = true;
             EngageSafetyStop("pending-order protection mismatch: " +
                              protection_detail);
             return(false);
            }
          ++passive_order_count;
        }
      else if(IsOwnedMagic(magic))
        {
         execution_state.broker_mismatch = true;
         EngageSafetyStop("owned pending order on mismatched component");
         return(false);
        }
      else
         execution_state.foreign_exposure = true;
     }
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      if(owned_counts[component] > 1)
        {
         execution_state.broker_mismatch = true;
         EngageSafetyStop("duplicate owned positions");
         return(false);
        }
     }
   if(h4_overlay_owned_count > 1)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("duplicate owned US500 H4 overlay positions");
      return(false);
     }
   if(passive_order_count > 1)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("duplicate owned passive pending orders");
      return(false);
     }
   if(passive_order_count == 1 && owned_counts[US100_PASSIVE_LIMIT] == 1)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("passive position and pending order coexist");
      return(false);
     }
   if(execution_state.foreign_exposure && !foreign_exposure_logged)
     {
      PrintFormat("%s foreign account exposure present; new entries blocked",
                  EXECUTION_VERSION);
      foreign_exposure_logged = true;
     }
   else if(!execution_state.foreign_exposure && foreign_exposure_logged)
     {
      PrintFormat("%s foreign account exposure cleared", EXECUTION_VERSION);
      foreign_exposure_logged = false;
     }
   return(true);
  }


int CountH4OverlayPositions(ulong &ticket, datetime &opened_at)
  {
   int count = 0;
   ticket = 0;
   opened_at = 0;
   for(int index = PositionsTotal() - 1; index >= 0; --index)
     {
      const ulong position_ticket = PositionGetTicket(index);
      if(position_ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) !=
            US500_H4_STAGED_OVERLAY_SYMBOL ||
         (ulong)PositionGetInteger(POSITION_MAGIC) !=
            MAGIC_US500_H4_STAGED_OVERLAY)
         continue;
      ++count;
      ticket = position_ticket;
      opened_at = (datetime)PositionGetInteger(POSITION_TIME);
     }
   if(count > 1)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("duplicate owned US500 H4 overlay positions");
     }
   return(count);
  }


int CountOwnedPositions(const int component,
                        ulong &ticket,
                        datetime &opened_at)
  {
   int count = 0;
   ticket = 0;
   opened_at = 0;
   for(int index = PositionsTotal() - 1; index >= 0; --index)
     {
      const ulong position_ticket = PositionGetTicket(index);
      if(position_ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != component_definitions[component].symbol ||
         (ulong)PositionGetInteger(POSITION_MAGIC) !=
         component_definitions[component].magic)
         continue;
      ++count;
      ticket = position_ticket;
      opened_at = (datetime)PositionGetInteger(POSITION_TIME);
     }
   return(count);
  }


int CountOwnedPassiveOrders(ulong &ticket)
  {
   int count = 0;
   ticket = 0;
   for(int index = OrdersTotal() - 1; index >= 0; --index)
     {
      const ulong order_ticket = OrderGetTicket(index);
      if(order_ticket == 0)
         continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC) !=
         MAGIC_US100_PASSIVE_LIMIT)
         continue;
      if(OrderGetString(ORDER_SYMBOL) != "US100")
        {
         execution_state.broker_mismatch = true;
         EngageSafetyStop("passive Magic Number on mismatched order symbol");
         continue;
        }
      const ENUM_ORDER_TYPE type =
         (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if(type != ORDER_TYPE_BUY_LIMIT && type != ORDER_TYPE_SELL_LIMIT)
        {
         execution_state.broker_mismatch = true;
         EngageSafetyStop("unexpected passive pending-order type");
         continue;
        }
      ++count;
      ticket = order_ticket;
     }
   if(count > 1)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("duplicate owned passive pending orders");
     }
   return(count);
  }


bool HasOwnedDealHistory()
  {
   if(!HistorySelect(0, TimeCurrent()))
      return(false);
   for(int index = 0; index < HistoryDealsTotal(); ++index)
     {
      const ulong deal = HistoryDealGetTicket(index);
      if(deal > 0 &&
         IsOwnedMagic((ulong)HistoryDealGetInteger(deal, DEAL_MAGIC)))
         return(true);
     }
   return(false);
  }


bool ContractSpecificationsCompatible()
  {
   for(int index = 0; index < 3; ++index)
     {
      const string symbol =
         (index == 0 ? "US100" : (index == 1 ? "US30" : "US500"));
      if(!SymbolSelect(symbol, true))
         return(false);
      const ENUM_SYMBOL_TRADE_EXECUTION execution_mode =
         (ENUM_SYMBOL_TRADE_EXECUTION)SymbolInfoInteger(
            symbol, SYMBOL_TRADE_EXEMODE);
      if(execution_mode != SYMBOL_TRADE_EXECUTION_MARKET)
        {
         PrintFormat("%s requires market execution symbol=%s actual=%d",
                     EXECUTION_VERSION,
                     symbol,
                     (int)execution_mode);
         return(false);
        }
      if(
         MathAbs(SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN) - 0.01) >
         1.0e-9 ||
         MathAbs(SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP) - 0.01) >
         1.0e-9 ||
          MathAbs(SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE) - 1.0) >
          1.0e-9 ||
          SymbolInfoString(symbol, SYMBOL_CURRENCY_PROFIT) != "USD" ||
          SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE) <= 0.0 ||
          SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE) <= 0.0 ||
          (SymbolInfoInteger(symbol, SYMBOL_ORDER_MODE) & SYMBOL_ORDER_SL) == 0)
         return(false);
      if(symbol == "US100" &&
         (SymbolInfoInteger(symbol, SYMBOL_EXPIRATION_MODE) &
          SYMBOL_EXPIRATION_SPECIFIED) == 0)
         return(false);
     }
   PrintFormat("%s contract execution=MARKET deviation_field=%d",
               EXECUTION_VERSION,
               InpDeviationPoints);
   return(true);
  }


bool ConnectedEnvironmentCompatible()
  {
   if(!TerminalInfoInteger(TERMINAL_CONNECTED) ||
      AccountInfoString(ACCOUNT_SERVER) != "FPMarketsSC-Live" ||
      AccountInfoString(ACCOUNT_CURRENCY) != "USD" ||
      AccountInfoInteger(ACCOUNT_LEVERAGE) != 100 ||
      AccountInfoInteger(ACCOUNT_MARGIN_MODE) !=
      ACCOUNT_MARGIN_MODE_RETAIL_HEDGING ||
       (!tester_mode && AccountInfoInteger(ACCOUNT_TRADE_MODE) !=
        ACCOUNT_TRADE_MODE_REAL) ||
       (!tester_mode && InpAllowNewEntries &&
        (InpExpectedLiveAccountLogin <= 0 ||
         (long)AccountInfoInteger(ACCOUNT_LOGIN) !=
         InpExpectedLiveAccountLogin)) ||
       !ContractSpecificationsCompatible())
      return(false);
   return(true);
  }


#endif
