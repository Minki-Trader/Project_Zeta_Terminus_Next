#property strict
#property version   "1.00"
#property description "Project Zeta Terminus Next isolated portfolio risk-cap optimization"
#property description "Execution version: zt-opt-live-v7-portfolio-risk-cap-envelope-v1"

#include <Trade\Trade.mqh>

#include <ZetaOptimizationPortfolioRiskCapV1\Domain\ZetaDomain.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Time\ZetaSessionClock.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Strategies\ZetaStrategyShared.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Strategies\ZetaRC16.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Strategies\ZetaRC4.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Strategies\ZetaCross.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Strategies\ZetaPressure.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Strategies\ZetaReturn.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Strategies\ZetaPassive.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Portfolio\ZetaPortfolioRisk.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Execution\ZetaOwnership.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Execution\ZetaOrders.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Execution\ZetaProtectionAndReconciliation.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Persistence\ZetaStateAndEvents.mqh>
#include <ZetaOptimizationPortfolioRiskCapV1\Observation\ZetaResearchObservation.mqh>

// The EA owns assembly and the inherited event ordering only.

bool InitializeConnectedRuntime()
  {
   if(execution_state.runtime_ready)
      return(true);
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
      return(false);
   if(!ConnectedEnvironmentCompatible())
     {
      if(!runtime_error_logged)
        {
         PrintFormat("%s incompatible connected broker/account/contract",
                     EXECUTION_VERSION);
         runtime_error_logged = true;
        }
      return(false);
     }

    const bool state_files_exist =
       (FileIsExist(STATE_PATH_A) || FileIsExist(STATE_PATH_B));
   ResetRuntimeState();
   const bool recovered = (!tester_mode && LoadState());
   if(!recovered)
     {
      ResetRuntimeState();
      if(state_files_exist && !tester_mode)
        {
         execution_state.broker_mismatch = true;
         portfolio_state.safety_stopped = true;
         PrintFormat("%s state snapshots exist but neither is valid; "
                     "new entries remain blocked",
                     EXECUTION_VERSION);
        }
      else if(!tester_mode && HasOwnedDealHistory())
        {
         execution_state.broker_mismatch = true;
         portfolio_state.safety_stopped = true;
         PrintFormat("%s owned broker history exists without state; "
                     "new entries remain blocked",
                     EXECUTION_VERSION);
         }
      }

   if(tester_mode)
      portfolio_state.bound_account_login = 0;
   else if(portfolio_state.bound_account_login <= 0)
      portfolio_state.bound_account_login =
         (long)AccountInfoInteger(ACCOUNT_LOGIN);

   execution_state.runtime_ready = true;
   InitializeResearchObservation();
   UpdateAccountRisk();
   const bool broker_reconciled = ReconcileBrokerState(true);
   if(recovered && broker_reconciled && !ReconcileArcPendingModify(true))
      EngageSafetyStop("restart RC4 stop journal could not be resolved");
   if(recovered && !ResolveRestartDecisionJournal())
      EngageSafetyStop("restart decision journal could not be resolved");
   UpdateSizingDay();
   RecordEvent(-1,
               (recovered ? "RESUME" : "START"),
               portfolio_state.stressed_balance,
               (double)state_sequence,
               (NewEntriesOperationallyAllowed() ? "entries-enabled" :
                                                   "entries-disabled"));
   SaveState();
   ResearchSampleOpenPositions();
   PrintFormat("%s initialized portfolio=%s recovered=%s "
               "entries=%s safety=%s sequence=%I64d",
               EXECUTION_VERSION,
               PORTFOLIO_ID,
               (recovered ? "true" : "false"),
               (NewEntriesOperationallyAllowed() ? "enabled" : "disabled"),
               (portfolio_state.safety_stopped ? "true" : "false"),
               state_sequence);
   return(true);
  }


int OnInit()
  {
   InitializeComponentDefinitions();
   tester_mode = (bool)MQLInfoInteger(MQL_TESTER);
   if(!tester_mode || _Symbol != "US30" || _Period != PERIOD_M30 ||
       MathAbs(InpReferenceCapitalUSD - 100.0) > 1.0e-9 ||
       !MathIsValidNumber(InpPriorProjectRealizedNetUSD) ||
       MathAbs(InpPriorProjectRealizedNetUSD) > 1.0e9 ||
       InpReferenceCapitalUSD + InpPriorProjectRealizedNetUSD <= 0.0 ||
       MathAbs(InpBaseVolume - 0.01) > 1.0e-9 ||
       MathAbs(InpAdditionStepUSD - 150.0) > 1.0e-9 ||
       MathAbs(InpMaximumMarginFraction - 0.45) > 1.0e-9 ||
       InpMaximumPositionRiskFraction < 0.03 - 1.0e-9 ||
       InpMaximumPositionRiskFraction > 0.05 + 1.0e-9 ||
       InpMaximumAggregateRiskFraction < 0.10 - 1.0e-9 ||
       InpMaximumAggregateRiskFraction > 0.18 + 1.0e-9 ||
       InpMaximumAggregateRiskFraction + 1.0e-9 <
          InpMaximumPositionRiskFraction ||
       MathAbs(InpUnmodelledRiskReserveFraction - 0.25) > 1.0e-9 ||
       MathAbs(InpStopPlacementHeadroomFraction - 0.25) > 1.0e-9 ||
       InpMaxEntryDelayMinutes != 2 || InpDeviationPoints != 100 ||
       InpExpectedLiveAccountLogin < 0 ||
       (!tester_mode && InpAllowNewEntries &&
        InpExpectedLiveAccountLogin <= 0) ||
       InpEventCapacity < 256 || InpEventCapacity > 8192 ||
      InpSnapshotSeconds < 10 || InpSnapshotSeconds > 600)
      return(INIT_PARAMETERS_INCORRECT);
   FolderCreate("ZetaOptimization");
   FolderCreate("ZetaOptimization\\portfolio-risk-cap-envelope-v1");
   FolderCreate("ZetaOptimization\\portfolio-risk-cap-envelope-v1\\state");
   FolderCreate("ZetaOptimization\\portfolio-risk-cap-envelope-v1\\research");
   FolderCreate(RESEARCH_OBSERVATION_DIRECTORY);
   if(tester_mode)
      ResetTesterArtifacts();
   if(!AcquireRuntimeOwnership())
      return(INIT_FAILED);
   ResetRuntimeState();
   if(!tester_mode && !EventSetTimer(2))
     {
      PrintFormat("%s timer initialization failed error=%d",
                  EXECUTION_VERSION, GetLastError());
      ReleaseRuntimeOwnership();
      return(INIT_FAILED);
     }
   if(!InitializeConnectedRuntime())
      PrintFormat("%s waiting for the saved FPMarkets connection",
                  EXECUTION_VERSION);
   return(INIT_SUCCEEDED);
  }


bool TesterDataRetryRequired(const datetime current_server,
                             const datetime us100_m15_bar)
  {
   MqlDateTime server = {};
   TimeToStruct(current_server, server);
   const bool fixed_data_retry =
      ((component_states[RC4_BOTH].entry_check_result == "DATA_UNAVAILABLE" &&
        server.hour == 13 && server.min >= 0 && server.min <= 2) ||
       (component_states[RC16_LONG].entry_check_result == "DATA_UNAVAILABLE" &&
        server.hour == 13 && server.min >= 30 && server.min <= 32) ||
       (component_states[US30_PRESSURE].entry_check_result == "DATA_UNAVAILABLE" &&
        server.hour == 15 && server.min >= 0 && server.min <= 2) ||
       (component_states[US30_RETURN_REV_LONG].entry_check_result == "DATA_UNAVAILABLE" &&
        server.hour == 16 && server.min >= 0 && server.min <= 2) ||
       (component_states[US100_CROSS].entry_check_result == "DATA_UNAVAILABLE" &&
        server.hour == 17 && server.min >= 0 && server.min <= 2));
   const bool passive_data_retry =
      (execution_state.passive_pending_order == 0 &&
       (component_states[US100_PASSIVE_LIMIT].entry_check_result == "DATA_UNAVAILABLE" ||
        (component_states[US100_PASSIVE_LIMIT].position_identifier > 0 &&
         us100_m15_bar > 0 &&
         component_states[US100_PASSIVE_LIMIT].last_decision_bar != us100_m15_bar)));
   const datetime slot_start =
      (datetime)(((long)current_server / PASSIVE_BAR_SECONDS) *
                 PASSIVE_BAR_SECONDS);
   const long seconds_into_slot =
      (long)current_server - (long)slot_start;
   const bool bounded_native_sync_retry =
      (us100_m15_bar > 0 && us100_m15_bar < slot_start &&
       seconds_into_slot >= 0 &&
       seconds_into_slot <= InpMaxEntryDelayMinutes * 60);
   return(fixed_data_retry || passive_data_retry ||
          bounded_native_sync_retry);
  }


void OnTick()
  {
   if(!execution_state.runtime_ready && !InitializeConnectedRuntime())
      return;

   // Optional research sampling is read-only. It never authorizes, blocks,
   // sizes, modifies or closes an order.
   ResearchSampleOpenPositions();

   datetime current_server = 0;
   datetime us100_m15_bar = 0;
   bool tester_clock_dispatch = false;
   bool tester_retry_dispatch = false;
   if(tester_mode)
     {
      // Shadow occupancy must observe every real tick so an intrabar touch of
      // the accepted original stop cannot be missed by the tester scheduler.
      if(execution_state.rc4_shadow_occupied)
         ProcessRC4ShadowOccupancy();
      current_server = TimeCurrent();
      const long current_m15_slot =
         (long)current_server / PASSIVE_BAR_SECONDS;
      tester_clock_dispatch =
         (current_m15_slot != tester_last_m15_slot);
      const bool transaction_gate =
         (execution_state.pending_reconcile || execution_state.passive_cancel_pending ||
          execution_state.arc_modify_retry_pending);
      tester_retry_dispatch = tester_data_retry_active;
      if(!tester_clock_dispatch && !transaction_gate &&
         !tester_retry_dispatch)
         return;
      if(tester_clock_dispatch)
         tester_last_m15_slot = current_m15_slot;
     }
   else if(!TerminalInfoInteger(TERMINAL_CONNECTED))
     {
      if(execution_state.passive_pending_order > 0)
         DeferPassivePendingCancellation(
            execution_state.passive_pending_order,
            "tick observed disconnected terminal");
      return;
     }
   if(!EnforceLiveAccountIdentity())
      return;
   UpdateAccountRisk();
   if(tester_mode)
     {
      us100_m15_bar = iTime("US100", PERIOD_M15, 0);
      const bool passive_order_disappeared =
         (execution_state.passive_pending_order > 0 &&
          !OrderSelect(execution_state.passive_pending_order));
      if(passive_order_disappeared)
         execution_state.pending_reconcile = true;
      ++tester_dispatched_ticks;
      if(tester_clock_dispatch)
         ++tester_clock_dispatches;
      if(execution_state.pending_reconcile || execution_state.passive_cancel_pending ||
         passive_order_disappeared)
         ++tester_transaction_dispatches;
      if(tester_retry_dispatch)
         ++tester_retry_dispatches;
     }
   UpdateSizingDay();
   if(!AuditPositionOwnership())
     {
      MakeExistingRiskSafe("tick ownership/protection audit failed");
      return;
     }
   if(execution_state.pending_reconcile || execution_state.passive_cancel_pending ||
      (!tester_mode && TimeCurrent() - last_reconcile_server >= 60))
     {
      const bool deferred_cancel_requires_reconciliation =
         execution_state.passive_cancel_pending;
      const bool reconciled = ReconcileBrokerState(false);
      if(deferred_cancel_requires_reconciliation && !reconciled)
         return;
     }
   ProcessClosures();
   ProcessPassiveLimit();
   if(!tester_mode)
      ProcessRC4ShadowOccupancy();
   if(NewEntriesOperationallyAllowed())
     {
      ProcessRC4Both();
      ProcessRC16Long();
      ProcessUS30Pressure();
      ProcessUS30ReturnReversalLong();
      ProcessUS100Cross();
     }
   ProcessRC4AdverseRiskCompression();
   ResearchSampleOpenPositions();
   if(tester_mode)
      tester_data_retry_active =
         TesterDataRetryRequired(current_server, us100_m15_bar);
  }


void OnTimer()
  {
   if(tester_mode)
      return;
   if(!execution_state.runtime_ready && !InitializeConnectedRuntime())
      return;
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
     {
      if(execution_state.passive_pending_order > 0)
         DeferPassivePendingCancellation(
            execution_state.passive_pending_order,
            "timer observed disconnected terminal");
      return;
     }
   if(!EnforceLiveAccountIdentity())
      return;
   UpdateAccountRisk();
   if(!ReconcileBrokerState(false))
      return;
   ResearchSampleOpenPositions();
   if(execution_state.passive_pending_order > 0 &&
      (execution_state.passive_cancel_pending || !NewEntriesOperationallyAllowed()))
     {
      ulong order_ticket = 0;
      if(CountOwnedPassiveOrders(order_ticket) == 1)
         CancelPassivePendingOrder(order_ticket,
                                   "new entries disabled by runtime");
     }
   if((long)TimeGMT() - (long)last_snapshot_utc >= InpSnapshotSeconds)
     {
      SaveState();
      SaveResearchObservationState();
     }
  }


void OnTradeTransaction(const MqlTradeTransaction &transaction,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(execution_state.runtime_ready && !execution_state.trade_operation_active)
      execution_state.pending_reconcile = true;
  }


double OnTester()
  {
   long closed_lifecycles = 0;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      closed_lifecycles += component_states[component].closed_trades;

   const bool correction_required =
      (portfolio_state.safety_stopped || persistence_failed ||
       execution_state.broker_mismatch || execution_state.foreign_exposure ||
       protection_calculation_failures != 0 || protection_mismatches != 0 ||
       research_dropped_records != 0 || closed_lifecycles <= 0);
   if(correction_required)
     {
      PrintFormat("OPTIMIZATION_RESULT status=CORRECTION_REQUIRED "
                  "position_risk=%.6f aggregate_risk=%.6f "
                  "closed=%I64d safety=%d persistence=%d broker=%d foreign=%d "
                  "protection_calc=%I64d protection_mismatch=%I64d "
                  "research_dropped=%I64d final_server=%s",
                  InpMaximumPositionRiskFraction,
                  InpMaximumAggregateRiskFraction,
                  closed_lifecycles,
                  (portfolio_state.safety_stopped ? 1 : 0),
                  (persistence_failed ? 1 : 0),
                  (execution_state.broker_mismatch ? 1 : 0),
                  (execution_state.foreign_exposure ? 1 : 0),
                  protection_calculation_failures,
                  protection_mismatches,
                  research_dropped_records,
                  TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES));
      return(-1.0e100);
     }

   const double actual_net = portfolio_state.project_realized_net;
   const double stressed_net =
      portfolio_state.stressed_balance - InpReferenceCapitalUSD;
   const double actual_dd = portfolio_state.account_maximum_drawdown;
   const double stressed_dd =
      portfolio_state.stressed_maximum_closed_drawdown;
   const double robust_net = MathMin(actual_net, stressed_net);
   const double robust_dd = MathMax(0.01, MathMax(actual_dd, stressed_dd));
   const double robust_recovery = robust_net / robust_dd;

   PrintFormat("OPTIMIZATION_RESULT status=ECONOMIC position_risk=%.6f "
               "aggregate_risk=%.6f actual_net=%.6f stressed_net=%.6f "
               "actual_dd=%.6f stressed_dd=%.6f robust_net=%.6f "
               "robust_recovery=%.9f closed=%I64d risk_skips=%I64d "
               "stop_exits=%I64d final_server=%s",
               InpMaximumPositionRiskFraction,
               InpMaximumAggregateRiskFraction,
               actual_net,
               stressed_net,
               actual_dd,
               stressed_dd,
               robust_net,
               robust_recovery,
               closed_lifecycles,
               risk_admission_skips,
               stop_loss_exits,
               TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES));
   return(robust_recovery);
  }


void OnDeinit(const int reason)
  {
   if(!tester_mode)
      EventKillTimer();
   if(execution_state.runtime_ready)
     {
      UpdateAccountRisk();
      RecordEvent(-1,
                  "STOP",
                  portfolio_state.stressed_balance,
                  (double)reason,
                  (portfolio_state.safety_stopped ? "safety" : "normal"));
      SaveState();
      SaveResearchObservationState();
     }
   PrintFormat("%s final portfolio=%s reason=%d stressed_balance_2x=%.4f "
                "stressed_net_2x=%.4f stressed_max_closed_dd=%.4f "
                "project_realized_net=%.4f project_stage_balance=%.4f "
                "safety_stopped=%s persistence_failed=%s "
                "broker_mismatch=%s foreign_exposure=%s "
                "protection_calc_failures=%I64d risk_admission_skips=%I64d "
                "protection_mismatches=%I64d stop_loss_exits=%I64d "
                "aggregate_planned_risk=%.4f max_aggregate_planned_risk=%.4f",
               EXECUTION_VERSION,
               PORTFOLIO_ID,
               reason,
                portfolio_state.stressed_balance,
                portfolio_state.stressed_balance - InpReferenceCapitalUSD,
                portfolio_state.stressed_maximum_closed_drawdown,
                portfolio_state.project_realized_net,
                ProjectStageBalance(),
               (portfolio_state.safety_stopped ? "true" : "false"),
                (persistence_failed ? "true" : "false"),
                (execution_state.broker_mismatch ? "true" : "false"),
                (execution_state.foreign_exposure ? "true" : "false"),
                protection_calculation_failures,
                risk_admission_skips,
                protection_mismatches,
                stop_loss_exits,
                TrackedAggregatePlannedRisk(),
                portfolio_state.maximum_aggregate_planned_risk_usd);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      PrintFormat("%s component=%s closed=%I64d stressed_net_2x=%.4f",
                  EXECUTION_VERSION,
                  component_definitions[component].id,
                  component_states[component].closed_trades,
                  component_states[component].stressed_net);
   PrintFormat("%s tester_scheduler dispatched_ticks=%I64d "
               "clock_dispatches=%I64d transaction_dispatches=%I64d "
               "retry_dispatches=%I64d",
               EXECUTION_VERSION,
               tester_dispatched_ticks,
               tester_clock_dispatches,
               tester_transaction_dispatches,
               tester_retry_dispatches);
   PrintFormat("%s arc_checkpoints=%I64d adverse_triggers=%I64d "
               "compressions_placed=%I64d compression_refusals=%I64d "
                "data_unavailable=%I64d modify_pending=%s "
                "pending_stop=%.5f retry_pending=%s retry_consumed=%s "
                "retry_after_msc=%I64d retry_initial_retcode=%u "
                "retry_intents=%I64d retry_attempts=%I64d "
                "retry_successes=%I64d "
                "retry_adoptions=%I64d retry_holds=%I64d "
                "shadow_occupied=%s "
               "shadow_activations=%I64d shadow_stop_releases=%I64d "
               "shadow_deadline_releases=%I64d shadow_entry_blocks=%I64d "
               "shadow_last_observed_msc=%I64d shadow_cursor_ordinal=%I64d "
               "catchup_required=%s "
               "catchup_scans=%I64d catchup_ticks=%I64d "
               "catchup_stop_releases=%I64d catchup_failures=%I64d "
               "cursor_checkpoint_observation_bucket=%I64d "
               "cursor_checkpoint_last_completed_bucket=%I64d "
               "cursor_checkpoint_last_persisted=%I64d/%I64d "
               "cursor_checkpoint_eligible=%I64d "
               "cursor_checkpoint_persisted=%I64d "
               "cursor_checkpoint_save_failures=%I64d "
               "cursor_checkpoint_readback_failures=%I64d "
               "cursor_checkpoint_event_failures=%I64d "
               "cursor_checkpoint_duplicate_bucket_failures=%I64d "
               "cursor_checkpoint_regressions=%I64d "
               "cursor_checkpoint_pending=%s",
               EXECUTION_VERSION,
               arc_checkpoints,
               arc_adverse_triggers,
               arc_compressions_placed,
               arc_compression_refusals,
                arc_data_unavailable,
                (execution_state.arc_modify_pending ? "true" : "false"),
                arc_pending_stop_loss,
                (execution_state.arc_modify_retry_pending ? "true" : "false"),
                (arc_modify_retry_consumed ? "true" : "false"),
                execution_state.arc_modify_retry_after_msc,
                arc_modify_retry_initial_retcode,
                arc_modify_retry_intents,
                arc_modify_retry_attempts,
                arc_modify_retry_successes,
                arc_modify_retry_adoptions,
                arc_modify_retry_holds,
                (execution_state.rc4_shadow_occupied ? "true" : "false"),
               rc4_shadow_activations,
               rc4_shadow_stop_releases,
               rc4_shadow_deadline_releases,
               rc4_shadow_entry_blocks,
               rc4_shadow_last_observed_msc,
               rc4_shadow_cursor_ordinal,
               (rc4_shadow_catchup_required ? "true" : "false"),
               rc4_shadow_catchup_scans,
               rc4_shadow_catchup_ticks,
               rc4_shadow_catchup_stop_releases,
               rc4_shadow_catchup_failures,
               rc4_shadow_cursor_checkpoint_observation_bucket,
               rc4_shadow_cursor_checkpoint_last_completed_bucket,
               rc4_shadow_cursor_checkpoint_last_persisted_msc,
               rc4_shadow_cursor_checkpoint_last_persisted_ordinal,
               rc4_shadow_cursor_checkpoint_eligible,
               rc4_shadow_cursor_checkpoint_persisted,
               rc4_shadow_cursor_checkpoint_save_failures,
               rc4_shadow_cursor_checkpoint_readback_failures,
               rc4_shadow_cursor_checkpoint_event_failures,
               rc4_shadow_cursor_checkpoint_duplicate_bucket_failures,
               rc4_shadow_cursor_checkpoint_regressions,
               (rc4_shadow_cursor_checkpoint_pending ? "true" : "false"));
   PrintFormat("%s activation_seal eligible=%I64d sealed=%I64d "
               "pending=%I64d save_attempts=%I64d save_failures=%I64d "
               "readbacks=%I64d readback_failures=%I64d failures=%I64d "
               "ambiguities=%I64d sealed_cursor=%I64d/%I64d "
               "pre_boundary_consumed=%I64d current_sealed=%s "
               "current_pending=%s current_boundary=%I64d/%I64d",
               EXECUTION_VERSION,
               rc4_shadow_activation_seal_eligible,
               rc4_shadow_activation_seal_sealed,
               rc4_shadow_activation_seal_pending_count,
               rc4_shadow_activation_seal_save_attempts,
               rc4_shadow_activation_seal_save_failures,
               rc4_shadow_activation_seal_readbacks,
               rc4_shadow_activation_seal_readback_failures,
               rc4_shadow_activation_seal_failures,
               rc4_shadow_activation_seal_ambiguities,
               rc4_shadow_activation_last_sealed_msc,
               rc4_shadow_activation_last_sealed_ordinal,
               rc4_shadow_activation_pre_boundary_consumed,
               (execution_state.rc4_shadow_activation_sealed ? "true" : "false"),
               (execution_state.rc4_shadow_activation_seal_pending ? "true" : "false"),
               rc4_shadow_activation_boundary_msc,
               rc4_shadow_activation_boundary_ordinal);
   ReleaseRuntimeOwnership();
  }
