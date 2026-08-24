#ifndef ZETA_NEXT_FRONTIER_SLOT_SHADOW_EXCHANGE_FIELD_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_SLOT_SHADOW_EXCHANGE_FIELD_ADAPTER_MQH

bool SlotShadowExchangeFieldInitialize()
  {
   return(ReceiverTimeFieldInitialize() && SlotShadowExchangeInitialize());
  }


void SlotShadowExchangeFieldReset()
  {
   ReceiverTimeFieldReset();
   SlotShadowExchangeReset();
  }


void SlotShadowExchangeFieldObserveSignal(const int component,
                                          const double value,
                                          const bool passed,
                                          const int direction)
  {
   ReceiverTimeFieldObserveSignal(component, value, passed, direction);
   SlotShadowExchangeObserveSignal(component, value, passed, direction);
  }


void SlotShadowExchangeFieldObserveExpiration(const int direction,
                                              const datetime expiration)
  {
   ReceiverTimeFieldObservePassiveExpiration(direction, expiration);
  }


int SlotShadowExchangeFieldHoldBars(const int component,
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


bool SlotShadowExchangeFieldShouldClose(const int component,
                                        const ulong ticket,
                                        const datetime opened_at,
                                        const int held_bars)
  {
   return(ReceiverTimeFieldShouldClose(component,
                                       ticket,
                                       opened_at,
                                       held_bars));
  }


void SlotShadowExchangeFieldReport()
  {
   ReceiverTimeFieldReport();
   SlotShadowExchangeReport();
  }

#endif
