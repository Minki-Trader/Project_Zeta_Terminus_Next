#ifndef ZETA_NEXT_FRONTIER_TRANSITION_RESERVE_GEOMETRY_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_TRANSITION_RESERVE_GEOMETRY_ADAPTER_MQH

double transition_reserve_planned_volume[COMPONENT_COUNT];
datetime transition_reserve_last_signal_bar[COMPONENT_COUNT];
int transition_reserve_last_raw_tier = 1;
int transition_reserve_maximum_raw_tier = 1;
long transition_reserve_sizing_days = 0;
long transition_reserve_upsteps = 0;
long transition_reserve_downsteps = 0;
long transition_reserve_high_tier_opportunities = 0;
long transition_reserve_lower_tier_allocations = 0;
long transition_reserve_upper_tier_allocations = 0;


string TransitionReserveModeName()
  {
   if(InpTransitionReserveMode == TRANSITION_RESERVE_NONE)
      return("linear-capital-anchor");
   if(InpTransitionReserveMode == TRANSITION_RESERVE_FIXED_20)
      return("fixed-dollar-20");
   return("prospective-position-budget-1.25");
  }


bool TransitionReserveCapitalInputsValid()
  {
   const double deposit = InpReferenceCapitalUSD;
   const bool allowed =
      (MathAbs(deposit - 100.0) <= 1.0e-9 ||
       MathAbs(deposit - 200.0) <= 1.0e-9 ||
       MathAbs(deposit - 300.0) <= 1.0e-9);
   if(!allowed ||
      MathAbs(AccountInfoDouble(ACCOUNT_BALANCE) - deposit) > 0.011)
      return(false);
   const double units = deposit / 100.0;
   return(MathAbs(InpBaseVolume - 0.01 * units) <= 1.0e-9 &&
          MathAbs(InpAdditionStepUSD - 150.0 * units) <= 1.0e-9);
  }


bool TransitionReserveInitialize()
  {
   if(InpTransitionReserveMode < TRANSITION_RESERVE_NONE ||
      InpTransitionReserveMode > TRANSITION_RESERVE_POSITION_BUDGET_1_25)
      return(false);
   FolderCreate("ZetaTerminusNext\\frontier");
   return(true);
  }


void TransitionReserveReset()
  {
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      transition_reserve_planned_volume[component] = 0.0;
      transition_reserve_last_signal_bar[component] = 0;
     }
   transition_reserve_last_raw_tier = 1;
   transition_reserve_maximum_raw_tier = 1;
   transition_reserve_sizing_days = 0;
   transition_reserve_upsteps = 0;
   transition_reserve_downsteps = 0;
   transition_reserve_high_tier_opportunities = 0;
   transition_reserve_lower_tier_allocations = 0;
   transition_reserve_upper_tier_allocations = 0;
  }


int TransitionReserveObserveSizing(const datetime current_day,
                                   const double stressed_balance,
                                   const int raw_multiplier,
                                   const int current_multiplier)
  {
   ++transition_reserve_sizing_days;
   if(raw_multiplier > transition_reserve_last_raw_tier)
      ++transition_reserve_upsteps;
   else if(raw_multiplier < transition_reserve_last_raw_tier)
      ++transition_reserve_downsteps;
   transition_reserve_maximum_raw_tier =
      MathMax(transition_reserve_maximum_raw_tier, raw_multiplier);
   if(execution_state.runtime_ready &&
      (raw_multiplier >= 3 || transition_reserve_last_raw_tier >= 3))
      RecordEvent(-1,
                  "TRANSITION_RESERVE_DAY",
                  stressed_balance,
                  (double)raw_multiplier,
                  StringFormat("mode=%s prior=%d current=%d",
                               TransitionReserveModeName(),
                               transition_reserve_last_raw_tier,
                               raw_multiplier));
   transition_reserve_last_raw_tier = raw_multiplier;
   return(raw_multiplier);
  }


double TransitionReserveRequired(const int raw_tier)
  {
   if(InpTransitionReserveMode == TRANSITION_RESERVE_NONE)
      return(0.0);
   if(InpTransitionReserveMode == TRANSITION_RESERVE_FIXED_20)
      return(20.0);
   const double threshold =
      InpReferenceCapitalUSD + (raw_tier - 1) * InpAdditionStepUSD;
   return(threshold * InpMaximumPositionRiskFraction * 1.25);
  }


double TransitionReserveNormalizedTierVolume(const string symbol,
                                             const int tier)
  {
   const double minimum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   const double maximum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0 || tier <= 0)
      return(0.0);
   const double normalized =
      MathRound((InpBaseVolume * tier) / step) * step;
   if(normalized < minimum || normalized > maximum)
      return(0.0);
   return(normalized);
  }


void TransitionReserveObserveSignal(const int component,
                                    const double value,
                                    const bool passed,
                                    const int direction)
  {
   if(component < 0 || component >= COMPONENT_COUNT)
      return;
   if(!passed || direction == 0)
     {
      transition_reserve_planned_volume[component] = 0.0;
      return;
     }
   const datetime signal_bar = component_states[component].entry_check_bar;
   if(signal_bar > 0 &&
      transition_reserve_last_signal_bar[component] == signal_bar &&
      transition_reserve_planned_volume[component] > 0.0)
      return;
   transition_reserve_last_signal_bar[component] = signal_bar;
   if(component == US100_PASSIVE_LIMIT)
     {
      transition_reserve_planned_volume[component] = InpBaseVolume;
      return;
     }

   const int raw_tier = portfolio_state.day_volume_multiplier;
   int selected_tier = raw_tier;
   if(raw_tier >= 3)
     {
      ++transition_reserve_high_tier_opportunities;
      const double threshold =
         InpReferenceCapitalUSD + (raw_tier - 1) * InpAdditionStepUSD;
      const double reserve = TransitionReserveRequired(raw_tier);
      if(portfolio_state.stressed_balance + 1.0e-9 < threshold + reserve)
         selected_tier = raw_tier - 1;
      if(selected_tier < raw_tier)
         ++transition_reserve_lower_tier_allocations;
      else
         ++transition_reserve_upper_tier_allocations;
      RecordEvent(component,
                  "TRANSITION_RESERVE_PLAN",
                  reserve,
                  (double)selected_tier,
                  StringFormat("mode=%s raw=%d threshold=%.6f balance=%.6f",
                               TransitionReserveModeName(),
                               raw_tier,
                               threshold,
                               portfolio_state.stressed_balance));
     }
   transition_reserve_planned_volume[component] =
      TransitionReserveNormalizedTierVolume(component_definitions[component].symbol,
                                            selected_tier);
  }


double TransitionReserveEntryVolume(const int component,
                                    const string symbol)
  {
   if(component == US100_PASSIVE_LIMIT)
      return(InpBaseVolume);
   if(component >= 0 && component < COMPONENT_COUNT &&
      transition_reserve_planned_volume[component] > 0.0)
      return(transition_reserve_planned_volume[component]);
   return(NormalizedVolume(symbol));
  }


void TransitionReserveReport()
  {
   PrintFormat("ZETA_FRONTIER_TRANSITION_RESERVE_SUMMARY|mode=%s|deposit=%.2f|base_volume=%.2f|addition_step=%.2f|sizing_days=%I64d|upsteps=%I64d|downsteps=%I64d|max_raw_tier=%d|high_tier_opportunities=%I64d|lower_tier_allocations=%I64d|upper_tier_allocations=%I64d",
               TransitionReserveModeName(),
               InpReferenceCapitalUSD,
               InpBaseVolume,
               InpAdditionStepUSD,
               transition_reserve_sizing_days,
               transition_reserve_upsteps,
               transition_reserve_downsteps,
               transition_reserve_maximum_raw_tier,
               transition_reserve_high_tier_opportunities,
               transition_reserve_lower_tier_allocations,
               transition_reserve_upper_tier_allocations);
  }

#endif
