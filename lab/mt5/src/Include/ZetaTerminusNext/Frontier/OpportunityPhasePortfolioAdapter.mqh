#ifndef ZETA_NEXT_FRONTIER_OPPORTUNITY_PHASE_PORTFOLIO_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_OPPORTUNITY_PHASE_PORTFOLIO_ADAPTER_MQH

bool OpportunityPhasePortfolioInitialize()
  {
   return(ReceiverTimeFieldInitialize() &&
          ExpirationPhaseTransitionInitialize());
  }


void OpportunityPhasePortfolioReset()
  {
   ReceiverTimeFieldReset();
   ExpirationPhaseTransitionReset();
  }


void OpportunityPhasePortfolioObserveSignal(const int component,
                                            const double value,
                                            const bool passed,
                                            const int direction)
  {
   ReceiverTimeFieldObserveSignal(component, value, passed, direction);
  }


void OpportunityPhasePortfolioObserveExpiration(const int direction,
                                                const datetime expiration)
  {
   ReceiverTimeFieldObservePassiveExpiration(direction, expiration);
   ExpirationPhaseTransitionObserveExpiration(direction, expiration);
  }


void OpportunityPhasePortfolioAfterExpiration(const int direction,
                                              const datetime expiration,
                                              const double feature,
                                              const double limit_price,
                                              const double stop_loss,
                                              const double planned_risk)
  {
   ExpirationPhaseTransitionAfterExpiration(direction,
                                            expiration,
                                            feature,
                                            limit_price,
                                            stop_loss,
                                            planned_risk);
  }


int OpportunityPhasePortfolioHoldBars(const int component,
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


bool OpportunityPhasePortfolioShouldClose(const int component,
                                          const ulong ticket,
                                          const datetime opened_at,
                                          const int held_bars)
  {
   return(ReceiverTimeFieldShouldClose(component,
                                       ticket,
                                       opened_at,
                                       held_bars));
  }


void OpportunityPhasePortfolioReport()
  {
   ReceiverTimeFieldReport();
   ExpirationPhaseTransitionReport();
  }

#endif
