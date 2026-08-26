#ifndef ZETA_ONE_HOUR_ADVERSE_EXIT_MQH
#define ZETA_ONE_HOUR_ADVERSE_EXIT_MQH

const int ONE_HOUR_ADVERSE_EXIT_SECONDS = 3600;


double OneHourAdverseExitThresholdR()
  {
   if(InpOneHourAdverseExitKind == 1)
      return(0.0);
   if(InpOneHourAdverseExitKind == 2)
      return(-0.25);
   if(InpOneHourAdverseExitKind == 3)
      return(-0.50);
   return(0.0);
  }


void ProcessOneHourAdverseExits()
  {
   if(InpOneHourAdverseExitKind == 0)
      return;
   const datetime now = TimeCurrent();
   const double threshold_r = OneHourAdverseExitThresholdR();
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      ulong ticket = 0;
      datetime opened_at = 0;
      const int count = CountOwnedPositions(component, ticket, opened_at);
      if(count != 1 || opened_at <= 0 ||
         (long)now - (long)opened_at < ONE_HOUR_ADVERSE_EXIT_SECONDS)
         continue;
      if(!PositionSelectByTicket(ticket))
        {
         ++one_hour_adverse_exit_data_faults;
         PrintFormat("%s one_hour_adverse_exit data_fault=position_select component=%s ticket=%I64u",
                     EXECUTION_VERSION,
                     component_definitions[component].id,
                     ticket);
         continue;
        }
      const string symbol = PositionGetString(POSITION_SYMBOL);
      if(!TradeSessionAllows(symbol, now, false))
         continue;
      MqlTick tick = {};
      if(!ExecutableTick(symbol, tick))
         continue;
      const ENUM_POSITION_TYPE position_type =
         (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      const ENUM_ORDER_TYPE order_type =
         (position_type == POSITION_TYPE_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
      const double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
      const double volume = PositionGetDouble(POSITION_VOLUME);
      const double close_price =
         (position_type == POSITION_TYPE_BUY ? tick.bid : tick.ask);
      const double planned_risk =
         component_states[component].entry_planned_risk_usd;
      double gross_mark = 0.0;
      if((position_type != POSITION_TYPE_BUY &&
          position_type != POSITION_TYPE_SELL) ||
         symbol != component_definitions[component].symbol ||
         open_price <= 0.0 || volume <= 0.0 || close_price <= 0.0 ||
         !MathIsValidNumber(planned_risk) || planned_risk <= 0.0 ||
         !OrderCalcProfit(order_type,
                          symbol,
                          volume,
                          open_price,
                          close_price,
                          gross_mark) ||
         !MathIsValidNumber(gross_mark))
        {
         ++one_hour_adverse_exit_data_faults;
         PrintFormat("%s one_hour_adverse_exit data_fault=mark component=%s ticket=%I64u risk=%.4f",
                     EXECUTION_VERSION,
                     component_definitions[component].id,
                     ticket,
                     planned_risk);
         continue;
        }
      ++one_hour_adverse_exit_evaluations;
      const double mark_r = gross_mark / planned_risk;
      if(mark_r > threshold_r + 1.0e-12)
         continue;
      ++one_hour_adverse_exit_triggers;
      ++one_hour_adverse_exit_component_triggers[component];
      PrintFormat("%s one_hour_adverse_exit trigger kind=%d component=%s ticket=%I64u age_seconds=%I64d mark_usd=%.4f planned_risk=%.4f mark_r=%.9f threshold_r=%.2f",
                  EXECUTION_VERSION,
                  InpOneHourAdverseExitKind,
                  component_definitions[component].id,
                  ticket,
                  (long)now - (long)opened_at,
                  gross_mark,
                  planned_risk,
                  mark_r,
                  threshold_r);
      if(!CloseComponent(component, ticket))
        {
         ++one_hour_adverse_exit_close_failures;
         continue;
        }
      ++one_hour_adverse_exit_successes;
      if(component == US100_PASSIVE_LIMIT)
        {
         const datetime current_bar = iTime("US100", PERIOD_M15, 0);
         if(current_bar > 0)
           {
            component_states[component].last_decision_bar = current_bar;
            passive_next_entry_current_bar =
               current_bar + 2 * PASSIVE_BAR_SECONDS;
            SaveState();
           }
        }
     }
  }

#endif
