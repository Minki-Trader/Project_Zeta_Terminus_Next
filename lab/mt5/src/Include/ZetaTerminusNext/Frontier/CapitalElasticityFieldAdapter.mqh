#ifndef ZETA_NEXT_FRONTIER_CAPITAL_ELASTICITY_FIELD_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_CAPITAL_ELASTICITY_FIELD_ADAPTER_MQH

bool CapitalElasticityFieldInitialize()
  {
   return(ReceiverTimeFieldInitialize() &&
          SlotShadowExchangeInitialize() &&
          CapitalElasticityInitialize());
  }


void CapitalElasticityFieldReset()
  {
   ReceiverTimeFieldReset();
   SlotShadowExchangeReset();
   CapitalElasticityReset();
  }


void CapitalElasticityFieldObserveSignal(const int component,
                                         const double value,
                                         const bool passed,
                                         const int direction)
  {
   ReceiverTimeFieldObserveSignal(component, value, passed, direction);
   SlotShadowExchangeObserveSignal(component, value, passed, direction);
   CapitalElasticityObserveSignal(component, value, passed, direction);
  }


void CapitalElasticityFieldObserveExpiration(const int direction,
                                             const datetime expiration)
  {
   ReceiverTimeFieldObservePassiveExpiration(direction, expiration);
  }


int CapitalElasticityFieldHoldBars(const int component,
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


bool CapitalElasticityFieldShouldClose(const int component,
                                       const ulong ticket,
                                       const datetime opened_at,
                                       const int held_bars)
  {
   return(ReceiverTimeFieldShouldClose(component,
                                       ticket,
                                       opened_at,
                                       held_bars));
  }


bool CapitalElasticityFieldTryRelease(const int component,
                                      const string symbol,
                                      const int direction,
                                      const double volume,
                                      const double entry_price,
                                      const double position_budget,
                                      const double aggregate_after,
                                      const double aggregate_budget)
  {
   if(CapitalElasticityExchangeQuarantined())
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


void CapitalElasticityFieldObserveExit(const int component,
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


int CapitalElasticityFieldObserveSizing(const datetime current_day,
                                        const double stressed_balance,
                                        const int raw_multiplier,
                                        const int current_multiplier)
  {
   return(CapitalElasticityObserveSizing(current_day,
                                         stressed_balance,
                                         raw_multiplier,
                                         current_multiplier));
  }


double CapitalElasticityFieldEntryVolume(const int component,
                                         const string symbol)
  {
   return(CapitalElasticityEntryVolume(component, symbol));
  }


void CapitalElasticityFieldReport()
  {
   ReceiverTimeFieldReport();
   SlotShadowExchangeReport();
   CapitalElasticityReport();
  }

#endif
