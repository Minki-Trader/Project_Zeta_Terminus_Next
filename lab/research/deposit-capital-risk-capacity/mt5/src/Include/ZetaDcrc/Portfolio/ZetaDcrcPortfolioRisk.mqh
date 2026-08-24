#ifndef ZETA_DCRC_PORTFOLIO_RISK_MQH
#define ZETA_DCRC_PORTFOLIO_RISK_MQH

// Keep every frozen risk, quote, stop-search and session function except the
// declared sizing-day, volume and margin-observation seams.
#define UpdateSizingDay DcrcParentUpdateSizingDay
#define NormalizedVolume DcrcParentNormalizedVolume
#define PassiveMarginAllows DcrcParentPassiveMarginAllows
#define MarginAllows DcrcParentMarginAllows
#define UpdateAccountRisk DcrcParentUpdateAccountRisk
#include <ZetaTerminusNext\Portfolio\ZetaPortfolioRisk.mqh>
#undef UpdateAccountRisk
#undef MarginAllows
#undef PassiveMarginAllows
#undef NormalizedVolume
#undef UpdateSizingDay

int DcrcDepositUnits()
  {
   return(MathMax(1, (int)MathRound(InpResearchDepositUSD / 100.0)));
  }


double DcrcEntryVolume(const string symbol)
  {
   const double minimum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   const double maximum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0)
      return(0.0);
   const double requested =
      (DCRC_POLICY == DCRC_POLICY_FIXED_LOT_LADDER
       ? 0.01 * (double)portfolio_state.day_volume_multiplier
       : InpBaseVolume * (double)portfolio_state.day_volume_multiplier);
   const double normalized = MathRound(requested / step) * step;
   if(normalized < minimum || normalized > maximum)
      return(0.0);
   return(normalized);
  }


double NormalizedVolume(const string symbol)
  {
   return(DcrcEntryVolume(symbol));
  }


double DcrcPassiveExpectedVolume()
  {
   if(component_states[US100_PASSIVE_LIMIT].position_identifier > 0 &&
      component_states[US100_PASSIVE_LIMIT].entry_volume > 0.0)
      return(component_states[US100_PASSIVE_LIMIT].entry_volume);
   if(execution_state.passive_pending_order > 0 &&
      component_states[US100_PASSIVE_LIMIT].entry_check_volume > 0.0)
      return(component_states[US100_PASSIVE_LIMIT].entry_check_volume);
   if(decision_intent.component == US100_PASSIVE_LIMIT &&
      decision_intent.volume > 0.0)
      return(decision_intent.volume);
   return(DcrcEntryVolume("US100"));
  }


void UpdateSizingDay()
  {
   const datetime current_day = ServerMidnight();
   if(current_day == portfolio_state.sizing_server_day)
      return;
   const datetime prior_day = portfolio_state.sizing_server_day;
   const int prior_size = portfolio_state.day_volume_multiplier;
   portfolio_state.sizing_server_day = current_day;
   const double growth = MathMax(0.0,
                                 portfolio_state.stressed_balance -
                                 InpReferenceCapitalUSD);
   if(DCRC_POLICY == DCRC_POLICY_BREADTH_DOLLAR_SLOTS)
      portfolio_state.day_volume_multiplier = 1;
   else if(DCRC_POLICY == DCRC_POLICY_FIXED_LOT_LADDER)
      portfolio_state.day_volume_multiplier =
         DcrcDepositUnits() +
         (int)MathFloor(growth / InpAdditionStepUSD + 1.0e-9);
   else
      portfolio_state.day_volume_multiplier =
         1 + (int)MathFloor(growth / InpAdditionStepUSD + 1.0e-9);
   portfolio_state.day_volume_multiplier =
      MathMax(1, portfolio_state.day_volume_multiplier);
   const double current_volume = DcrcEntryVolume("US30");
   if(current_volume > dcrc_maximum_entry_volume)
      dcrc_maximum_entry_volume = current_volume;
   if(prior_day > 0 && prior_size != portfolio_state.day_volume_multiplier)
      ++dcrc_sizing_interventions;
   if(execution_state.runtime_ready)
     {
      RecordEvent(-1,
                  "DCRC_SIZE_DAY",
                  current_volume,
                  (double)portfolio_state.day_volume_multiplier,
                  StringFormat("policy=%s deposit=%.2f growth=%.4f",
                               DCRC_POLICY_NAME,
                               InpResearchDepositUSD,
                               growth));
      SaveState();
     }
  }


bool MarginAllows(const string symbol,
                  const int direction,
                  const double volume)
  {
   const bool allowed = DcrcParentMarginAllows(symbol, direction, volume);
   if(!allowed)
     {
      ++dcrc_market_margin_or_calc_blocks;
      RecordEvent(-1,
                  "DCRC_MARKET_MARGIN_OR_CALC_BLOCK",
                  volume,
                  AccountInfoDouble(ACCOUNT_EQUITY),
                  symbol);
     }
   return(allowed);
  }


bool PassiveMarginAllows(const int direction, const double limit_price)
  {
   const double volume = DcrcEntryVolume("US100");
   const ENUM_ORDER_TYPE order_type =
      (direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   double required_margin = 0.0;
   if(volume <= 0.0 ||
      !OrderCalcMargin(order_type,
                       "US100",
                       volume,
                       limit_price,
                       required_margin) || required_margin <= 0.0)
     {
      ++passive_margin_calculation_failures;
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_MARGIN_CALC_FAIL",
                  (double)direction,
                  limit_price,
                  IntegerToString(GetLastError()));
      return(false);
     }
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   const double projected_margin =
      AccountInfoDouble(ACCOUNT_MARGIN) + required_margin;
   if(equity <= 0.0 ||
      projected_margin > equity * InpMaximumMarginFraction)
     {
      ++passive_margin_skips;
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_MARGIN_SKIP",
                  projected_margin,
                  equity,
                  DoubleToString(required_margin, 4));
      return(false);
     }
   return(true);
  }


void UpdateAccountRisk()
  {
   DcrcParentUpdateAccountRisk();
   const double margin = AccountInfoDouble(ACCOUNT_MARGIN);
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(margin > dcrc_maximum_margin_usd)
      dcrc_maximum_margin_usd = margin;
   if(equity > 0.0)
     {
      const double fraction = margin / equity;
      if(fraction > dcrc_maximum_margin_to_equity_fraction)
         dcrc_maximum_margin_to_equity_fraction = fraction;
     }
  }

#endif
