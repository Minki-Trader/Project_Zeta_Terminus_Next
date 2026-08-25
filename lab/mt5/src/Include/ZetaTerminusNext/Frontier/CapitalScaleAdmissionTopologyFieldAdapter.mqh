#ifndef ZETA_ADMISSION_FIELD_MQH
#define ZETA_ADMISSION_FIELD_MQH

bool AdmissionTopologyFieldInitialize()
  {
   return(TransitionReserveFieldInitialize() &&
          AdmissionTopologyInitialize());
  }


void AdmissionTopologyFieldReset()
  {
   TransitionReserveFieldReset();
   AdmissionTopologyReset();
  }


void AdmissionTopologyFieldObserveSignal(const int component,
                                         const double value,
                                         const bool passed,
                                         const int direction)
  {
   TransitionReserveFieldObserveSignal(component, value, passed, direction);
  }


void AdmissionTopologyFieldObserveExpiration(const int direction,
                                             const datetime expiration)
  {
   TransitionReserveFieldObserveExpiration(direction, expiration);
  }


int AdmissionTopologyFieldHoldBars(const int component,
                                   const ulong ticket,
                                   const datetime opened_at,
                                   const int held_bars,
                                   const int native_hold_bars)
  {
   return(TransitionReserveFieldHoldBars(component,
                                         ticket,
                                         opened_at,
                                         held_bars,
                                         native_hold_bars));
  }


bool AdmissionTopologyFieldShouldClose(const int component,
                                       const ulong ticket,
                                       const datetime opened_at,
                                       const int held_bars)
  {
   return(TransitionReserveFieldShouldClose(component,
                                             ticket,
                                             opened_at,
                                             held_bars));
  }


bool AdmissionTopologyFieldTryRelease(const int component,
                                      const string symbol,
                                      const int direction,
                                      const double volume,
                                      const double entry_price,
                                      const double position_budget,
                                      const double aggregate_after,
                                      const double aggregate_budget)
  {
   return(TransitionReserveFieldTryRelease(component,
                                           symbol,
                                           direction,
                                           volume,
                                           entry_price,
                                           position_budget,
                                           aggregate_after,
                                           aggregate_budget));
  }


bool AdmissionTopologyFieldAllow(const int component,
                                 const string symbol,
                                 const int direction,
                                 const double volume,
                                 const double entry_price,
                                 const double stop_loss,
                                 const double candidate_actual_stop_risk,
                                 const double position_budget,
                                 const double aggregate_after,
                                 const double aggregate_budget)
  {
   return(AdmissionTopologyAllow(component,
                                 symbol,
                                 direction,
                                 volume,
                                 entry_price,
                                 stop_loss,
                                 candidate_actual_stop_risk,
                                 position_budget,
                                 aggregate_after,
                                 aggregate_budget));
  }


bool AdmissionTopologyFieldPostPlacementConfirmed(
   const double aggregate_before,
   const double pending_planned_risk,
   const double admitted_capital)
  {
   return(AdmissionTopologyPostPlacementConfirmed(aggregate_before,
                                                  pending_planned_risk,
                                                  admitted_capital));
  }


void AdmissionTopologyFieldObserveExit(const int component,
                                       const ulong identifier,
                                       const double stressed_net,
                                       const double admitted_planned_risk,
                                       const bool completed)
  {
   TransitionReserveFieldObserveExit(component,
                                     identifier,
                                     stressed_net,
                                     admitted_planned_risk,
                                     completed);
  }


int AdmissionTopologyFieldObserveSizing(const datetime current_day,
                                        const double stressed_balance,
                                        const int raw_multiplier,
                                        const int current_multiplier)
  {
   return(TransitionReserveFieldObserveSizing(current_day,
                                               stressed_balance,
                                               raw_multiplier,
                                               current_multiplier));
  }


double AdmissionTopologyFieldEntryVolume(const int component,
                                         const string symbol)
  {
   return(TransitionReserveFieldEntryVolume(component, symbol));
  }


void AdmissionTopologyFieldReport()
  {
   TransitionReserveFieldReport();
   AdmissionTopologyReport();
  }

#endif
