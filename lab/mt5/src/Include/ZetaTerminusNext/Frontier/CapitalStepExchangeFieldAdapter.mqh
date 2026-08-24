#ifndef ZETA_NEXT_FRONTIER_CAPITAL_STEP_EXCHANGE_FIELD_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_CAPITAL_STEP_EXCHANGE_FIELD_ADAPTER_MQH

bool CapitalStepExchangeFieldInitialize()
  {
   if(!ReceiverTimeFieldInitialize() || !CapitalStepPhaseInitialize())
      return(false);
   return(!InpCapitalStepUseSlotExchange || SlotShadowExchangeInitialize());
  }


void CapitalStepExchangeFieldReset()
  {
   ReceiverTimeFieldReset();
   CapitalStepPhaseReset();
   if(InpCapitalStepUseSlotExchange)
      SlotShadowExchangeReset();
  }


void CapitalStepExchangeFieldObserveSignal(const int component,
                                           const double value,
                                           const bool passed,
                                           const int direction)
  {
   ReceiverTimeFieldObserveSignal(component, value, passed, direction);
   if(InpCapitalStepUseSlotExchange)
      SlotShadowExchangeObserveSignal(component, value, passed, direction);
  }


void CapitalStepExchangeFieldObserveExpiration(const int direction,
                                               const datetime expiration)
  {
   ReceiverTimeFieldObservePassiveExpiration(direction, expiration);
  }


int CapitalStepExchangeFieldHoldBars(const int component,
                                     const ulong ticket,
                                     const datetime opened_at,
                                     const int held_bars,
                                     const int native_hold_bars)
  {
   return(ReceiverTimeFieldHoldBars(component,
                                    ticket,
                                    opened_at,
                                    held_bars,
                                    native_hold_bars));
  }


bool CapitalStepExchangeFieldShouldClose(const int component,
                                         const ulong ticket,
                                         const datetime opened_at,
                                         const int held_bars)
  {
   return(ReceiverTimeFieldShouldClose(component,
                                       ticket,
                                       opened_at,
                                       held_bars));
  }


bool CapitalStepExchangeFieldTryRelease(const int component,
                                        const string symbol,
                                        const int direction,
                                        const double volume,
                                        const double entry_price,
                                        const double position_budget,
                                        const double aggregate_after,
                                        const double aggregate_budget)
  {
   if(!InpCapitalStepUseSlotExchange ||
      CapitalStepPhaseExchangeQuarantined())
      return(false);
   return(SlotShadowExchangeTryRelease(component,
                                       symbol,
                                       direction,
                                       volume,
                                       entry_price,
                                       position_budget,
                                       aggregate_after,
                                       aggregate_budget));
  }


void CapitalStepExchangeFieldObserveExit(const int component,
                                         const ulong identifier,
                                         const double stressed_net,
                                         const double admitted_planned_risk,
                                         const bool completed)
  {
   CapitalStepPhaseObserveExit(component,
                               identifier,
                               stressed_net,
                               admitted_planned_risk,
                               completed);
   if(InpCapitalStepUseSlotExchange)
      SlotShadowExchangeObserveExit(component,
                                    identifier,
                                    stressed_net,
                                    admitted_planned_risk,
                                    completed);
  }


int CapitalStepExchangeFieldMultiplier(const datetime current_day,
                                       const double stressed_balance,
                                       const int raw_multiplier,
                                       const int current_multiplier)
  {
   return(CapitalStepPhaseMultiplier(current_day,
                                     stressed_balance,
                                     raw_multiplier,
                                     current_multiplier));
  }


void CapitalStepExchangeFieldReport()
  {
   ReceiverTimeFieldReport();
   CapitalStepPhaseReport();
   if(InpCapitalStepUseSlotExchange)
      SlotShadowExchangeReport();
  }

#endif
