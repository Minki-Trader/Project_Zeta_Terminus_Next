#ifndef ZETA_NEXT_FRONTIER_CAPITAL_ELASTICITY_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_CAPITAL_ELASTICITY_ADAPTER_MQH

double capital_elasticity_credit[COMPONENT_COUNT];
double capital_elasticity_planned_volume[COMPONENT_COUNT];
datetime capital_elasticity_last_signal_bar[COMPONENT_COUNT];
int capital_elasticity_last_raw_tier = 1;
long capital_elasticity_sizing_days = 0;
long capital_elasticity_downcross_resets = 0;
long capital_elasticity_high_tier_opportunities = 0;
long capital_elasticity_lower_tier_allocations = 0;
long capital_elasticity_upper_tier_allocations = 0;
long capital_elasticity_exchange_quarantines = 0;
int capital_elasticity_days_since_upstep = -1;


string CapitalElasticityModeName()
  {
   if(InpCapitalElasticityMode == CAPITAL_ELASTICITY_COMPONENT_CLOCK_30)
      return("component-clock-band-30");
   return("hard-third-tier-escrow-20");
  }


bool CapitalElasticityInitialize()
  {
   if(InpCapitalElasticityMode < CAPITAL_ELASTICITY_COMPONENT_CLOCK_30 ||
      InpCapitalElasticityMode > CAPITAL_ELASTICITY_HARD_ESCROW_20)
      return(false);
   FolderCreate("ZetaTerminusNext\\frontier");
   return(true);
  }


void CapitalElasticityClearCredits()
  {
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      capital_elasticity_credit[component] = 0.0;
  }


void CapitalElasticityReset()
  {
   CapitalElasticityClearCredits();
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      capital_elasticity_planned_volume[component] = 0.0;
      capital_elasticity_last_signal_bar[component] = 0;
     }
   capital_elasticity_last_raw_tier = 1;
   capital_elasticity_sizing_days = 0;
   capital_elasticity_downcross_resets = 0;
   capital_elasticity_high_tier_opportunities = 0;
   capital_elasticity_lower_tier_allocations = 0;
   capital_elasticity_upper_tier_allocations = 0;
   capital_elasticity_exchange_quarantines = 0;
   capital_elasticity_days_since_upstep = -1;
  }


int CapitalElasticityObserveSizing(const datetime current_day,
                                   const double stressed_balance,
                                   const int raw_multiplier,
                                   const int current_multiplier)
  {
   ++capital_elasticity_sizing_days;
   if(raw_multiplier < 3 && capital_elasticity_last_raw_tier >= 3)
     {
      CapitalElasticityClearCredits();
      ++capital_elasticity_downcross_resets;
     }
   if(raw_multiplier > current_multiplier)
      capital_elasticity_days_since_upstep = 0;
   else if(capital_elasticity_days_since_upstep >= 0)
      ++capital_elasticity_days_since_upstep;
   if(execution_state.runtime_ready &&
      (raw_multiplier >= 3 || capital_elasticity_last_raw_tier >= 3))
      RecordEvent(-1,
                  "CAPITAL_ELASTICITY_DAY",
                  stressed_balance,
                  (double)raw_multiplier,
                  StringFormat("mode=%s prior=%d current=%d",
                               CapitalElasticityModeName(),
                               capital_elasticity_last_raw_tier,
                               raw_multiplier));
   capital_elasticity_last_raw_tier = raw_multiplier;
   return(raw_multiplier);
  }


bool CapitalElasticityExchangeQuarantined()
  {
   if(!InpCapitalElasticityQuarantineExchange ||
      portfolio_state.day_volume_multiplier <= 1 ||
      capital_elasticity_days_since_upstep < 0 ||
      capital_elasticity_days_since_upstep > 10)
      return(false);
   ++capital_elasticity_exchange_quarantines;
   return(true);
  }


double CapitalElasticityNormalizedTierVolume(const string symbol,
                                             const int tier)
  {
   const double minimum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   const double maximum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0 || tier <= 0)
      return(0.0);
   const double requested = InpBaseVolume * tier;
   const double normalized = MathRound(requested / step) * step;
   if(normalized < minimum || normalized > maximum)
      return(0.0);
   return(normalized);
  }


void CapitalElasticityObserveSignal(const int component,
                                    const double value,
                                    const bool passed,
                                    const int direction)
  {
   if(component < 0 || component >= COMPONENT_COUNT)
      return;
   if(!passed || direction == 0)
     {
      capital_elasticity_planned_volume[component] = 0.0;
      return;
     }
   const datetime signal_bar = component_states[component].entry_check_bar;
   if(signal_bar > 0 &&
      capital_elasticity_last_signal_bar[component] == signal_bar &&
      capital_elasticity_planned_volume[component] > 0.0)
      return;
   capital_elasticity_last_signal_bar[component] = signal_bar;
   const string symbol = component_definitions[component].symbol;
   if(component == US100_PASSIVE_LIMIT)
     {
      capital_elasticity_planned_volume[component] = InpBaseVolume;
      return;
     }

   const int raw_tier = portfolio_state.day_volume_multiplier;
   int selected_tier = raw_tier;
   double progress = 1.0;
   if(raw_tier >= 3)
     {
      ++capital_elasticity_high_tier_opportunities;
      const double threshold =
         InpReferenceCapitalUSD + (raw_tier - 1) * InpAdditionStepUSD;
      const double band =
         (InpCapitalElasticityMode == CAPITAL_ELASTICITY_COMPONENT_CLOCK_30
          ? 30.0
          : 20.0);
      progress =
         MathMax(0.0,
                 MathMin(1.0,
                         (portfolio_state.stressed_balance - threshold) /
                         band));
      if(InpCapitalElasticityMode == CAPITAL_ELASTICITY_HARD_ESCROW_20)
         selected_tier = (progress >= 1.0 ? raw_tier : raw_tier - 1);
      else if(progress < 1.0)
        {
         capital_elasticity_credit[component] += progress;
         if(capital_elasticity_credit[component] + 1.0e-12 >= 1.0)
           {
            capital_elasticity_credit[component] -= 1.0;
            selected_tier = raw_tier;
           }
         else
            selected_tier = raw_tier - 1;
        }
      if(selected_tier < raw_tier)
         ++capital_elasticity_lower_tier_allocations;
      else
         ++capital_elasticity_upper_tier_allocations;
      RecordEvent(component,
                  "CAPITAL_ELASTICITY_PLAN",
                  progress,
                  (double)selected_tier,
                  StringFormat("mode=%s raw=%d balance=%.6f credit=%.10f",
                               CapitalElasticityModeName(),
                               raw_tier,
                               portfolio_state.stressed_balance,
                               capital_elasticity_credit[component]));
     }
   capital_elasticity_planned_volume[component] =
      CapitalElasticityNormalizedTierVolume(symbol, selected_tier);
  }


double CapitalElasticityEntryVolume(const int component,
                                    const string symbol)
  {
   if(component == US100_PASSIVE_LIMIT)
      return(InpBaseVolume);
   if(component >= 0 && component < COMPONENT_COUNT &&
      capital_elasticity_planned_volume[component] > 0.0)
      return(capital_elasticity_planned_volume[component]);
   return(NormalizedVolume(symbol));
  }


void CapitalElasticityReport()
  {
   PrintFormat("ZETA_FRONTIER_CAPITAL_ELASTICITY_SUMMARY|mode=%s|sizing_days=%I64d|downcross_resets=%I64d|high_tier_opportunities=%I64d|lower_tier_allocations=%I64d|upper_tier_allocations=%I64d|exchange_quarantines=%I64d",
               CapitalElasticityModeName(),
               capital_elasticity_sizing_days,
               capital_elasticity_downcross_resets,
               capital_elasticity_high_tier_opportunities,
               capital_elasticity_lower_tier_allocations,
               capital_elasticity_upper_tier_allocations,
               capital_elasticity_exchange_quarantines);
  }

#endif
