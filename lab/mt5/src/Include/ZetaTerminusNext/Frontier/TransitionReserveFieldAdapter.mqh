#ifndef ZETA_NEXT_FRONTIER_TRANSITION_RESERVE_FIELD_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_TRANSITION_RESERVE_FIELD_ADAPTER_MQH

bool TransitionReserveFieldInitialize()
  {
   return(ReceiverTimeFieldInitialize() &&
          SlotShadowExchangeInitialize() &&
          TransitionReserveInitialize());
  }


void TransitionReserveFieldReset()
  {
   ReceiverTimeFieldReset();
   SlotShadowExchangeReset();
   TransitionReserveReset();
  }


void TransitionReserveFieldObserveSignal(const int component,
                                         const double value,
                                         const bool passed,
                                         const int direction)
  {
   ReceiverTimeFieldObserveSignal(component, value, passed, direction);
   SlotShadowExchangeObserveSignal(component, value, passed, direction);
   TransitionReserveObserveSignal(component, value, passed, direction);
  }


void TransitionReserveFieldObserveExpiration(const int direction,
                                             const datetime expiration)
  {
   ReceiverTimeFieldObservePassiveExpiration(direction, expiration);
  }


int TransitionReserveFieldHoldBars(const int component,
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


bool TransitionReserveFieldShouldClose(const int component,
                                       const ulong ticket,
                                       const datetime opened_at,
                                       const int held_bars)
  {
   return(ReceiverTimeFieldShouldClose(component,
                                       ticket,
                                       opened_at,
                                       held_bars));
  }


bool TransitionReserveFieldTryRelease(const int component,
                                      const string symbol,
                                      const int direction,
                                      const double volume,
                                      const double entry_price,
                                      const double position_budget,
                                      const double aggregate_after,
                                      const double aggregate_budget)
  {
   return(SlotShadowExchangeTryRelease(component,
                                       symbol,
                                       direction,
                                       volume,
                                       entry_price,
                                       position_budget,
                                       aggregate_after,
                                       aggregate_budget));
  }


void TransitionReserveFieldObserveExit(const int component,
                                       const ulong identifier,
                                       const double stressed_net,
                                       const double admitted_planned_risk,
                                       const bool completed)
  {
   SlotShadowExchangeObserveExit(component,
                                 identifier,
                                 stressed_net,
                                 admitted_planned_risk,
                                 completed);
  }


int TransitionReserveFieldObserveSizing(const datetime current_day,
                                        const double stressed_balance,
                                        const int raw_multiplier,
                                        const int current_multiplier)
  {
   return(TransitionReserveObserveSizing(current_day,
                                         stressed_balance,
                                         raw_multiplier,
                                         current_multiplier));
  }


double TransitionReserveFieldEntryVolume(const int component,
                                         const string symbol)
  {
   return(TransitionReserveEntryVolume(component, symbol));
  }


void TransitionReserveFieldReport()
  {
   ReceiverTimeFieldReport();
   SlotShadowExchangeReport();
   TransitionReserveReport();
  }

#endif
