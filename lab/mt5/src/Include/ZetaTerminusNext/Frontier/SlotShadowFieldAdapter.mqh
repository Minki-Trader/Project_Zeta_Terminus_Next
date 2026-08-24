#ifndef ZETA_NEXT_FRONTIER_SLOT_SHADOW_FIELD_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_SLOT_SHADOW_FIELD_ADAPTER_MQH

bool SlotShadowFieldInitialize()
  {
   return(ReceiverTimeFieldInitialize() && SlotShadowTapeInitialize());
  }


void SlotShadowFieldReset()
  {
   ReceiverTimeFieldReset();
   SlotShadowTapeReset();
  }


void SlotShadowFieldObserveSignal(const int component,
                                  const double value,
                                  const bool passed,
                                  const int direction)
  {
   ReceiverTimeFieldObserveSignal(component, value, passed, direction);
   SlotShadowTapeObserveSignal(component, value, passed, direction);
  }


void SlotShadowFieldObserveExpiration(const int direction,
                                      const datetime expiration)
  {
   ReceiverTimeFieldObservePassiveExpiration(direction, expiration);
  }


int SlotShadowFieldHoldBars(const int component,
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


bool SlotShadowFieldShouldClose(const int component,
                                const ulong ticket,
                                const datetime opened_at,
                                const int held_bars)
  {
   return(ReceiverTimeFieldShouldClose(component,
                                       ticket,
                                       opened_at,
                                       held_bars));
  }


void SlotShadowFieldReport()
  {
   ReceiverTimeFieldReport();
   SlotShadowTapeReport();
  }

#endif
