#ifndef ZETA_NEXT_FRONTIER_CAPITAL_STEP_PHASE_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_CAPITAL_STEP_PHASE_ADAPTER_MQH

#define CAPITAL_STEP_PHASE_WINDOW 20

double capital_step_phase_outcomes[CAPITAL_STEP_PHASE_WINDOW];
int capital_step_phase_outcome_count = 0;
int capital_step_phase_outcome_cursor = 0;
ulong capital_step_phase_exit_identifier[COMPONENT_COUNT];
double capital_step_phase_exit_stressed[COMPONENT_COUNT];
long capital_step_phase_sizing_days = 0;
long capital_step_phase_upsteps = 0;
long capital_step_phase_downsteps = 0;
long capital_step_phase_blocked_upsteps = 0;
long capital_step_phase_exchange_quarantines = 0;
int capital_step_phase_confirmation_streak = 0;
int capital_step_phase_days_since_upstep = -1;


string CapitalStepPhaseModeName()
  {
   if(InpCapitalStepPhaseMode == CAPITAL_STEP_DOWNSIDE_ESCROW_25)
      return("recent-downside-escrow-25");
   return("two-sizing-day-confirmation");
  }


bool CapitalStepPhaseInitialize()
  {
   if(InpCapitalStepPhaseMode < CAPITAL_STEP_DOWNSIDE_ESCROW_25 ||
      InpCapitalStepPhaseMode > CAPITAL_STEP_CONFIRM_TWO)
      return(false);
   FolderCreate("ZetaTerminusNext\\frontier");
   return(true);
  }


void CapitalStepPhaseReset()
  {
   capital_step_phase_outcome_count = 0;
   capital_step_phase_outcome_cursor = 0;
   capital_step_phase_sizing_days = 0;
   capital_step_phase_upsteps = 0;
   capital_step_phase_downsteps = 0;
   capital_step_phase_blocked_upsteps = 0;
   capital_step_phase_exchange_quarantines = 0;
   capital_step_phase_confirmation_streak = 0;
   capital_step_phase_days_since_upstep = -1;
   for(int index = 0; index < CAPITAL_STEP_PHASE_WINDOW; ++index)
      capital_step_phase_outcomes[index] = 0.0;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      capital_step_phase_exit_identifier[component] = 0;
      capital_step_phase_exit_stressed[component] = 0.0;
     }
  }


void CapitalStepPhasePushOutcome(const double stressed_net)
  {
   if(!MathIsValidNumber(stressed_net))
      return;
   if(capital_step_phase_outcome_count < CAPITAL_STEP_PHASE_WINDOW)
     {
      capital_step_phase_outcomes[capital_step_phase_outcome_count] =
         stressed_net;
      ++capital_step_phase_outcome_count;
      if(capital_step_phase_outcome_count == CAPITAL_STEP_PHASE_WINDOW)
         capital_step_phase_outcome_cursor = 0;
      return;
     }
   capital_step_phase_outcomes[capital_step_phase_outcome_cursor] =
      stressed_net;
   capital_step_phase_outcome_cursor =
      (capital_step_phase_outcome_cursor + 1) % CAPITAL_STEP_PHASE_WINDOW;
  }


double CapitalStepPhaseRecentDrawdown()
  {
   double cumulative = 0.0;
   double peak = 0.0;
   double maximum = 0.0;
   for(int offset = 0; offset < capital_step_phase_outcome_count; ++offset)
     {
      const int index =
         (capital_step_phase_outcome_count < CAPITAL_STEP_PHASE_WINDOW
          ? offset
          : (capital_step_phase_outcome_cursor + offset) %
            CAPITAL_STEP_PHASE_WINDOW);
      cumulative += capital_step_phase_outcomes[index];
      peak = MathMax(peak, cumulative);
      maximum = MathMax(maximum, peak - cumulative);
     }
   return(maximum);
  }


void CapitalStepPhaseObserveExit(const int component,
                                 const ulong identifier,
                                 const double stressed_net,
                                 const double admitted_planned_risk,
                                 const bool completed)
  {
   if(component < 0 || component >= COMPONENT_COUNT || identifier == 0)
      return;
   if(capital_step_phase_exit_identifier[component] != identifier)
     {
      capital_step_phase_exit_identifier[component] = identifier;
      capital_step_phase_exit_stressed[component] = 0.0;
     }
   capital_step_phase_exit_stressed[component] += stressed_net;
   if(!completed)
      return;
   CapitalStepPhasePushOutcome(capital_step_phase_exit_stressed[component]);
   capital_step_phase_exit_identifier[component] = 0;
   capital_step_phase_exit_stressed[component] = 0.0;
  }


int CapitalStepPhaseMultiplier(const datetime current_day,
                               const double stressed_balance,
                               const int raw_multiplier,
                               const int current_multiplier)
  {
   ++capital_step_phase_sizing_days;
   int selected = MathMax(1, current_multiplier);
   string action = "hold";
   double threshold =
      InpReferenceCapitalUSD + selected * InpAdditionStepUSD;
   const double recent_drawdown = CapitalStepPhaseRecentDrawdown();
   double required_balance = threshold;
   if(InpCapitalStepPhaseMode == CAPITAL_STEP_DOWNSIDE_ESCROW_25)
      required_balance += 0.25 * recent_drawdown;

   if(raw_multiplier < selected)
     {
      selected = MathMax(1, raw_multiplier);
      capital_step_phase_confirmation_streak = 0;
      capital_step_phase_days_since_upstep = -1;
      ++capital_step_phase_downsteps;
      action = "downstep";
     }
   else if(raw_multiplier > selected)
     {
      const bool eligible = stressed_balance + 1.0e-9 >= required_balance;
      if(eligible)
         ++capital_step_phase_confirmation_streak;
      else
         capital_step_phase_confirmation_streak = 0;
      const int confirmations =
         (InpCapitalStepPhaseMode == CAPITAL_STEP_CONFIRM_TWO ? 2 : 1);
      if(capital_step_phase_confirmation_streak >= confirmations)
        {
         ++selected;
         capital_step_phase_confirmation_streak = 0;
         capital_step_phase_days_since_upstep = 0;
         ++capital_step_phase_upsteps;
         action = "upstep";
        }
      else
        {
         ++capital_step_phase_blocked_upsteps;
         action = "escrow";
        }
     }
   else
     {
      capital_step_phase_confirmation_streak = 0;
      if(capital_step_phase_days_since_upstep >= 0)
         ++capital_step_phase_days_since_upstep;
     }

   if(execution_state.runtime_ready)
      RecordEvent(-1,
                  "CAPITAL_STEP_PHASE",
                  required_balance,
                  (double)selected,
                  StringFormat("mode=%s raw=%d prior=%d action=%s recent_dd=%.6f streak=%d since_up=%d",
                               CapitalStepPhaseModeName(),
                               raw_multiplier,
                               current_multiplier,
                               action,
                               recent_drawdown,
                               capital_step_phase_confirmation_streak,
                               capital_step_phase_days_since_upstep));
   return(selected);
  }


bool CapitalStepPhaseExchangeQuarantined()
  {
   if(!InpCapitalStepQuarantineExchange ||
      portfolio_state.day_volume_multiplier <= 1 ||
      capital_step_phase_days_since_upstep < 0 ||
      capital_step_phase_days_since_upstep > 10)
      return(false);
   ++capital_step_phase_exchange_quarantines;
   return(true);
  }


void CapitalStepPhaseReport()
  {
   PrintFormat("ZETA_FRONTIER_CAPITAL_STEP_PHASE_SUMMARY|mode=%s|sizing_days=%I64d|upsteps=%I64d|downsteps=%I64d|blocked_upsteps=%I64d|exchange_quarantines=%I64d|recent_dd=%.10f|outcomes=%d",
               CapitalStepPhaseModeName(),
               capital_step_phase_sizing_days,
               capital_step_phase_upsteps,
               capital_step_phase_downsteps,
               capital_step_phase_blocked_upsteps,
               capital_step_phase_exchange_quarantines,
               CapitalStepPhaseRecentDrawdown(),
               capital_step_phase_outcome_count);
  }

#endif
