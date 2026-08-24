#ifndef ZETA_NEXT_FRONTIER_OPPORTUNITY_AFTERIMAGE_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_OPPORTUNITY_AFTERIMAGE_ADAPTER_MQH

#define OPPORTUNITY_AFTERIMAGE_CAPACITY 64
const int OPPORTUNITY_AFTERIMAGE_HALF_LIFE_SECONDS = 2880 * 60;
const int OPPORTUNITY_AFTERIMAGE_MAX_AGE_SECONDS =
   8 * OPPORTUNITY_AFTERIMAGE_HALF_LIFE_SECONDS;
const double OPPORTUNITY_AFTERIMAGE_MINIMUM_ENERGY = 0.25;
const double OPPORTUNITY_AFTERIMAGE_MINIMUM_DOMINANCE = 0.25;

datetime afterimage_expired_server[OPPORTUNITY_AFTERIMAGE_CAPACITY];
int afterimage_expired_direction[OPPORTUNITY_AFTERIMAGE_CAPACITY];
int afterimage_expired_count = 0;
bool afterimage_return_qualified = false;
datetime afterimage_return_signal_server = 0;
double afterimage_return_energy = 0.0;
double afterimage_return_dominance = 0.0;
long afterimage_return_signals = 0;
long afterimage_return_qualified_signals = 0;
long afterimage_release_attempts = 0;
long afterimage_loss_only_holds = 0;


string OpportunityAfterimageModeName()
  {
   if(InpOpportunityAfterimageMode == AFTERIMAGE_RETURN_RELEASE_2)
      return("RETURN_RELEASE_2");
   if(InpOpportunityAfterimageMode == AFTERIMAGE_RETURN_RELEASE_3)
      return("RETURN_RELEASE_3");
   return("RETURN_LOSS_ONLY_RELEASE_3");
  }


bool OpportunityAfterimageInitialize()
  {
   if(InpOpportunityAfterimageMode != AFTERIMAGE_RETURN_RELEASE_2 &&
      InpOpportunityAfterimageMode != AFTERIMAGE_RETURN_RELEASE_3 &&
      InpOpportunityAfterimageMode != AFTERIMAGE_RETURN_LOSS_ONLY_RELEASE_3)
      return(false);
   FolderCreate("ZetaTerminusNext\\frontier");
   return(true);
  }


void OpportunityAfterimageReset()
  {
   ArrayInitialize(afterimage_expired_server, 0);
   ArrayInitialize(afterimage_expired_direction, 0);
   afterimage_expired_count = 0;
   afterimage_return_qualified = false;
   afterimage_return_signal_server = 0;
   afterimage_return_energy = 0.0;
   afterimage_return_dominance = 0.0;
   afterimage_return_signals = 0;
   afterimage_return_qualified_signals = 0;
   afterimage_release_attempts = 0;
   afterimage_loss_only_holds = 0;
  }


void OpportunityAfterimageObservePassiveExpiration(const int direction,
                                                    const datetime expiration)
  {
   if(direction == 0)
      return;
   const datetime now = TimeCurrent();
   if(afterimage_expired_count < OPPORTUNITY_AFTERIMAGE_CAPACITY)
     {
      afterimage_expired_server[afterimage_expired_count] = now;
      afterimage_expired_direction[afterimage_expired_count] = direction;
      ++afterimage_expired_count;
     }
   else
     {
      for(int index = 1; index < OPPORTUNITY_AFTERIMAGE_CAPACITY; ++index)
        {
         afterimage_expired_server[index - 1] =
            afterimage_expired_server[index];
         afterimage_expired_direction[index - 1] =
            afterimage_expired_direction[index];
        }
      afterimage_expired_server[OPPORTUNITY_AFTERIMAGE_CAPACITY - 1] = now;
      afterimage_expired_direction[OPPORTUNITY_AFTERIMAGE_CAPACITY - 1] =
         direction;
     }
   PrintFormat("ZETA_FRONTIER_AFTERIMAGE_EMITTER|server=%I64d|expiration=%I64d|direction=%d|count=%d",
               (long)now,
               (long)expiration,
               direction,
               afterimage_expired_count);
  }


void OpportunityAfterimageState(const int receiver_direction,
                                double &energy,
                                double &dominance)
  {
   energy = 0.0;
   double signed_energy = 0.0;
   const datetime now = TimeCurrent();
   for(int index = 0; index < afterimage_expired_count; ++index)
     {
      const long age = (long)now - (long)afterimage_expired_server[index];
      if(age < 0 || age > OPPORTUNITY_AFTERIMAGE_MAX_AGE_SECONDS)
         continue;
      const double weight =
         MathPow(0.5,
                 (double)age /
                 (double)OPPORTUNITY_AFTERIMAGE_HALF_LIFE_SECONDS);
      const int relation =
         (afterimage_expired_direction[index] == receiver_direction ? 1 : -1);
      energy += weight;
      signed_energy += relation * weight;
     }
   dominance = (energy > 0.0 ? signed_energy / energy : 0.0);
  }


void OpportunityAfterimageObserveSignal(const int component,
                                        const double value,
                                        const bool passed,
                                        const int direction)
  {
   if(component != US30_RETURN_REV_LONG)
      return;
   afterimage_return_qualified = false;
   afterimage_return_signal_server = TimeCurrent();
   afterimage_return_energy = 0.0;
   afterimage_return_dominance = 0.0;
   if(!passed || direction == 0)
      return;
   ++afterimage_return_signals;
   OpportunityAfterimageState(direction,
                              afterimage_return_energy,
                              afterimage_return_dominance);
   afterimage_return_qualified =
      (afterimage_return_energy >= OPPORTUNITY_AFTERIMAGE_MINIMUM_ENERGY &&
       afterimage_return_dominance >=
       OPPORTUNITY_AFTERIMAGE_MINIMUM_DOMINANCE);
   if(afterimage_return_qualified)
      ++afterimage_return_qualified_signals;
   PrintFormat("ZETA_FRONTIER_AFTERIMAGE_RECEIVER|server=%I64d|component=%d|mode=%s|direction=%d|signal=%.10f|energy=%.10f|dominance=%.10f|qualified=%d",
               (long)afterimage_return_signal_server,
               component,
               OpportunityAfterimageModeName(),
               direction,
               value,
               afterimage_return_energy,
               afterimage_return_dominance,
               (int)afterimage_return_qualified);
  }


bool OpportunityAfterimageCurrentReturnLifecycle()
  {
   if(!afterimage_return_qualified ||
      afterimage_return_signal_server <= 0 ||
      component_states[US30_RETURN_REV_LONG].entry_time_server <= 0)
      return(false);
   const long entry_lag =
      (long)component_states[US30_RETURN_REV_LONG].entry_time_server -
      (long)afterimage_return_signal_server;
   return(entry_lag >= 0 &&
          entry_lag <= InpMaxEntryDelayMinutes * 60);
  }


bool OpportunityAfterimageShouldClose(const int component,
                                      const ulong ticket,
                                      const datetime opened_at,
                                      const int held_bars)
  {
   if(component != US30_RETURN_REV_LONG ||
      !OpportunityAfterimageCurrentReturnLifecycle())
      return(false);
   const int release_bars =
      (InpOpportunityAfterimageMode == AFTERIMAGE_RETURN_RELEASE_2 ? 2 : 3);
   if(held_bars < release_bars)
      return(false);
   if(InpOpportunityAfterimageMode == AFTERIMAGE_RETURN_LOSS_ONLY_RELEASE_3)
     {
      if(!PositionSelectByTicket(ticket))
         return(false);
      const double floating_net =
         PositionGetDouble(POSITION_PROFIT) +
         PositionGetDouble(POSITION_SWAP);
      if(floating_net > 0.0)
        {
         ++afterimage_loss_only_holds;
         return(false);
        }
     }
   ++afterimage_release_attempts;
   PrintFormat("ZETA_FRONTIER_AFTERIMAGE_RELEASE|server=%I64d|mode=%s|ticket=%I64u|opened=%I64d|held_bars=%d|energy=%.10f|dominance=%.10f",
               (long)TimeCurrent(),
               OpportunityAfterimageModeName(),
               ticket,
               (long)opened_at,
               held_bars,
               afterimage_return_energy,
               afterimage_return_dominance);
   return(true);
  }


void OpportunityAfterimageReport()
  {
   PrintFormat("ZETA_FRONTIER_AFTERIMAGE_SUMMARY|mode=%s|expired_emitters=%d|return_signals=%I64d|qualified=%I64d|release_attempts=%I64d|loss_only_holds=%I64d|half_life_minutes=2880|min_energy=%.2f|min_dominance=%.2f",
               OpportunityAfterimageModeName(),
               afterimage_expired_count,
               afterimage_return_signals,
               afterimage_return_qualified_signals,
               afterimage_release_attempts,
               afterimage_loss_only_holds,
               OPPORTUNITY_AFTERIMAGE_MINIMUM_ENERGY,
               OPPORTUNITY_AFTERIMAGE_MINIMUM_DOMINANCE);
  }

#endif
