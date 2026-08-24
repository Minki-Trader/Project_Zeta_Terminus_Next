#ifndef ZETA_DCRC_ASSEMBLY_MQH
#define ZETA_DCRC_ASSEMBLY_MQH

#include <Trade\Trade.mqh>

#include <ZetaDcrc\Domain\ZetaDcrcDomain.mqh>
#include <ZetaTerminusNext\Time\ZetaSessionClock.mqh>
#include <ZetaTerminusNext\Strategies\ZetaStrategyShared.mqh>
#include <ZetaTerminusNext\Strategies\ZetaRC16.mqh>
#include <ZetaTerminusNext\Strategies\ZetaRC4.mqh>
#include <ZetaTerminusNext\Strategies\ZetaCross.mqh>
#include <ZetaTerminusNext\Strategies\ZetaPressure.mqh>
#include <ZetaTerminusNext\Strategies\ZetaReturn.mqh>
#define InpBaseVolume DcrcEntryVolume("US100")
#include <ZetaTerminusNext\Strategies\ZetaPassive.mqh>
#undef InpBaseVolume
#include <ZetaDcrc\Portfolio\ZetaDcrcPortfolioRisk.mqh>
#include <ZetaTerminusNext\Execution\ZetaOwnership.mqh>
#define InpBaseVolume DcrcPassiveExpectedVolume()
#include <ZetaTerminusNext\Execution\ZetaOrders.mqh>
#include <ZetaTerminusNext\Execution\ZetaProtectionAndReconciliation.mqh>
#undef InpBaseVolume
#include <ZetaSira\Persistence\ZetaSiraStateAndEvents.mqh>

// Reuse the frozen tester scheduler and event lifecycle while replacing the
// two callbacks that own parameter validation and policy telemetry.
#define OnInit DcrcParentOnInit
#define OnDeinit DcrcParentOnDeinit
#include <ZetaSira\ZetaSiraAssembly.mqh>
#undef OnDeinit
#undef OnInit

bool DcrcAllowedDeposit(const double value)
  {
   return(MathAbs(value - 100.0) <= 1.0e-9 ||
          MathAbs(value - 200.0) <= 1.0e-9 ||
          MathAbs(value - 300.0) <= 1.0e-9);
  }


bool DcrcPolicyInputsValid()
  {
   if(!DcrcAllowedDeposit(InpResearchDepositUSD) ||
      MathAbs(AccountInfoDouble(ACCOUNT_BALANCE) -
              InpResearchDepositUSD) > 0.011 ||
      MathAbs(InpReferenceCapitalUSD - InpResearchDepositUSD) > 1.0e-9)
      return(false);
   const double units = InpResearchDepositUSD / 100.0;
   if(DCRC_POLICY == DCRC_POLICY_LINEAR_CAPITAL)
      return(MathAbs(InpBaseVolume - 0.01 * units) <= 1.0e-9 &&
             MathAbs(InpAdditionStepUSD - 150.0 * units) <= 1.0e-9 &&
             MathAbs(InpMaximumPositionRiskFraction - 0.04) <= 1.0e-9);
   if(DCRC_POLICY == DCRC_POLICY_BREADTH_DOLLAR_SLOTS)
      return(InpResearchDepositUSD >= 200.0 &&
             MathAbs(InpBaseVolume - 0.01) <= 1.0e-9 &&
             MathAbs(InpAdditionStepUSD - 150.0) <= 1.0e-9 &&
             MathAbs(InpMaximumPositionRiskFraction -
                     4.0 / InpResearchDepositUSD) <= 1.0e-9);
   if(DCRC_POLICY == DCRC_POLICY_FIXED_LOT_LADDER)
      return(InpResearchDepositUSD >= 200.0 &&
             MathAbs(InpBaseVolume - 0.01 * units) <= 1.0e-9 &&
             MathAbs(InpAdditionStepUSD - 150.0) <= 1.0e-9 &&
             MathAbs(InpMaximumPositionRiskFraction - 0.04) <= 1.0e-9);
   return(false);
  }


int OnInit()
  {
   InitializeComponentDefinitions();
   tester_mode = (bool)MQLInfoInteger(MQL_TESTER);
   if(!tester_mode)
     {
      PrintFormat("%s is Lab tester-only and refuses chart/live execution",
                  EXECUTION_VERSION);
      return(INIT_FAILED);
     }
   if(_Symbol != "US30" || _Period != PERIOD_M30 ||
      !DcrcPolicyInputsValid() ||
      !MathIsValidNumber(InpPriorProjectRealizedNetUSD) ||
      MathAbs(InpPriorProjectRealizedNetUSD) > 1.0e-9 ||
      MathAbs(InpMaximumMarginFraction - 0.45) > 1.0e-9 ||
      MathAbs(InpMaximumAggregateRiskFraction - 0.12) > 1.0e-9 ||
      MathAbs(InpUnmodelledRiskReserveFraction - 0.25) > 1.0e-9 ||
      MathAbs(InpStopPlacementHeadroomFraction - 0.25) > 1.0e-9 ||
      InpMaxEntryDelayMinutes != 2 || InpDeviationPoints != 100 ||
      InpExpectedLiveAccountLogin < 0 || InpAllowNewEntries ||
      InpEventCapacity < 256 || InpEventCapacity > 8192 ||
      InpSnapshotSeconds < 10 || InpSnapshotSeconds > 600)
      return(INIT_PARAMETERS_INCORRECT);
   FolderCreate("ZetaDcrc");
   FolderCreate("ZetaDcrc\\dcrc");
   ResetTesterArtifacts();
   if(!AcquireRuntimeOwnership())
      return(INIT_FAILED);
   ResetRuntimeState();
   if(!InitializeConnectedRuntime())
      PrintFormat("%s waiting for the saved FPMarkets connection",
                  EXECUTION_VERSION);
   PrintFormat("%s DCRC policy=%s deposit=%.2f reference=%.2f base=%.2f "
               "step=%.2f position_fraction=%.8f aggregate_fraction=%.8f",
               EXECUTION_VERSION,
               DCRC_POLICY_NAME,
               InpResearchDepositUSD,
               InpReferenceCapitalUSD,
               InpBaseVolume,
               InpAdditionStepUSD,
               InpMaximumPositionRiskFraction,
               InpMaximumAggregateRiskFraction);
   return(INIT_SUCCEEDED);
  }


void OnDeinit(const int reason)
  {
   PrintFormat("%s DCRC_FINAL policy=%s deposit=%.2f sizing_interventions=%I64d "
               "market_margin_or_calc_blocks=%I64d passive_margin_skips=%I64d "
               "maximum_margin_usd=%.4f maximum_margin_equity_fraction=%.8f "
               "maximum_entry_volume=%.2f",
               EXECUTION_VERSION,
               DCRC_POLICY_NAME,
               InpResearchDepositUSD,
               dcrc_sizing_interventions,
               dcrc_market_margin_or_calc_blocks,
               passive_margin_skips,
               dcrc_maximum_margin_usd,
               dcrc_maximum_margin_to_equity_fraction,
               dcrc_maximum_entry_volume);
   DcrcParentOnDeinit(reason);
  }

#endif
