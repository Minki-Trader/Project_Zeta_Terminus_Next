#ifndef ZETA_UI_OBSERVATION_MQH
#define ZETA_UI_OBSERVATION_MQH

int unit_path_handle = INVALID_HANDLE;
long unit_path_rows = 0;
long unit_path_faults = 0;
long unit_last_minute = -1;
bool unit_last_mark_known = false;

double UnitObservedStressMark(int &open_count, double &maximum_quote_age, bool &known)
  {
   open_count = 0;
   maximum_quote_age = 0.0;
   known = false;
   double mark = portfolio_state.stressed_balance - unit_positive_closed_swap;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      ulong ticket = 0;
      datetime opened = 0;
      const int count = CountOwnedPositions(component, ticket, opened);
      if(count == 0)
        {
         if(component_states[component].position_identifier != 0)
            return(0.0);
         continue;
        }
      if(count != 1 || !PositionSelectByTicket(ticket) ||
         !component_states[component].entry_cost_known ||
         (ulong)PositionGetInteger(POSITION_IDENTIFIER) != component_states[component].position_identifier)
         return(0.0);
      const string symbol = component_definitions[component].symbol;
      MqlTick tick = {};
      if(!StructurallyValidTick(symbol, tick))
         return(0.0);
      const double volume = PositionGetDouble(POSITION_VOLUME);
      const double swap = PositionGetDouble(POSITION_SWAP);
      const double transaction = component_states[component].entry_transaction_cost;
      const double contract = SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
      const double additional =
         MathMax(component_states[component].entry_spread_price, tick.ask-tick.bid)*contract*volume +
         component_states[component].entry_adverse_slippage +
         MathMax(0.0,-transaction) + MathMax(0.0,-swap);
      mark += PositionGetDouble(POSITION_PROFIT) + MathMin(0.0,swap) + transaction - additional;
      maximum_quote_age = MathMax(maximum_quote_age,MathAbs((double)((long)TimeCurrent()-(long)tick.time)));
      ++open_count;
     }
   known = MathIsValidNumber(mark);
   return(mark);
  }

bool UnitObserve(const bool force=false)
  {
   if(!execution_state.runtime_ready)
      return(false);
   const long minute = (long)TimeCurrent()/60;
   if(!force && minute == unit_last_minute)
      return(unit_last_mark_known);
   unit_last_mark_known = false;
   if(execution_state.pending_reconcile || execution_state.trade_operation_active)
      return(false);
   int open_count = 0;
   double maximum_quote_age = 0.0;
   bool known = false;
   const double mark = UnitObservedStressMark(open_count,maximum_quote_age,known);
   if(!known)
      return(false);
   if(unit_path_handle == INVALID_HANDLE ||
      FileWrite(unit_path_handle,
                TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),
                AccountInfoDouble(ACCOUNT_BALANCE),AccountInfoDouble(ACCOUNT_EQUITY),
                portfolio_state.stressed_balance,mark,unit_positive_closed_swap,
                ConservativeRiskCapital(),portfolio_state.day_volume_multiplier,
                open_count,unit_pending_volume,TrackedAggregatePlannedRisk(),maximum_quote_age) == 0)
     {
      ++unit_path_faults;
      MarkPersistenceFailure("unit account path write failed");
      return(false);
     }
   FileFlush(unit_path_handle);
   ++unit_path_rows;
   unit_last_minute = minute;
   unit_last_mark_known = true;
   return(true);
  }

bool UnitInitializePaths()
  {
   if(StringLen(InpUnitRunTag) < 1 || StringLen(InpUnitRunTag) > 32)
      return(false);
   for(int i=0;i<StringLen(InpUnitRunTag);++i)
     {
      const ushort c=StringGetCharacter(InpUnitRunTag,i);
      if(!((c>=97 && c<=122) || (c>=48 && c<=57) || c==45))
         return(false);
     }
   const string identity = "ZetaV7UIReinvest";
   unit_run_root = identity+"\\ui\\"+InpUnitRunTag;
   STATE_PATH_A=unit_run_root+"\\state\\state-a.csv";
   STATE_PATH_B=unit_run_root+"\\state\\state-b.csv";
   EVENT_PATH_A=unit_run_root+"\\state\\events-a.csv";
   EVENT_PATH_B=unit_run_root+"\\state\\events-b.csv";
   CURRENT_SNAPSHOT_PATH_A=unit_run_root+"\\state\\current-a.csv";
   CURRENT_SNAPSHOT_PATH_B=unit_run_root+"\\state\\current-b.csv";
   OWNERSHIP_PATH=unit_run_root+"\\state\\runtime.lock";
   RESEARCH_OBSERVATION_DIRECTORY=unit_run_root+"\\research";
   RESEARCH_OBSERVATION_STATE_PATH_A=RESEARCH_OBSERVATION_DIRECTORY+"\\research-state-a.csv";
   RESEARCH_OBSERVATION_STATE_PATH_B=RESEARCH_OBSERVATION_DIRECTORY+"\\research-state-b.csv";
   RESEARCH_CANDIDATE_LEDGER_PATH=RESEARCH_OBSERVATION_DIRECTORY+"\\research-candidates.csv";
   RESEARCH_LIFECYCLE_LEDGER_PATH=RESEARCH_OBSERVATION_DIRECTORY+"\\research-lifecycles.csv";
   unit_path_file=unit_run_root+"\\equity.csv";
   if(FileIsExist(STATE_PATH_A) || FileIsExist(STATE_PATH_B) ||
      FileIsExist(EVENT_PATH_A) || FileIsExist(EVENT_PATH_B) ||
      FileIsExist(RESEARCH_CANDIDATE_LEDGER_PATH) || FileIsExist(RESEARCH_LIFECYCLE_LEDGER_PATH) ||
      FileIsExist(unit_path_file))
     {
      Print("V7UI existing run output preserved; a fresh attributable run tag is required");
      return(false);
     }
   FolderCreate(identity);
   FolderCreate(identity+"\\ui");
   FolderCreate(unit_run_root);
   FolderCreate(unit_run_root+"\\state");
   FolderCreate(RESEARCH_OBSERVATION_DIRECTORY);
   unit_path_handle=FileOpen(unit_path_file,FILE_WRITE|FILE_CSV|FILE_ANSI,',',CP_UTF8);
   if(unit_path_handle == INVALID_HANDLE)
      return(false);
   if(FileWrite(unit_path_handle,"server","actual_balance","actual_equity",
                "original_stress_balance","conservative_stress_equity","positive_closed_swap",
                "risk_capital","day_multiplier","open_positions","pending_order_volume",
                "planned_risk","max_owned_quote_age_seconds") == 0)
      return(false);
   FileFlush(unit_path_handle);
   return(true);
  }

bool UnitCompleteObservation()
  {
   const bool observed=UnitObserve(true);
   int open_count=0;
   double age=0.0;
   bool known=false;
   const double mark=UnitObservedStressMark(open_count,age,known);
   const bool complete=(observed && known && unit_path_faults==0 && open_count==0 &&
                        execution_state.passive_pending_order==0 && unit_pending_volume==0.0);
   PrintFormat("V7UI_PATH role=%s tag=%s rows=%I64d faults=%I64d mark_known=%d open=%d pending_volume=%.8f positive_closed_swap=%.9f conservative_final=%.9f complete=%d",
               (UNIT_REINVESTMENT ? "reinvest" : "control"),InpUnitRunTag,
               unit_path_rows,unit_path_faults,(known ? 1:0),open_count,unit_pending_volume,
               unit_positive_closed_swap,mark,(complete ? 1:0));
   return(complete);
  }

void UnitCloseObservation()
  {
   if(unit_path_handle != INVALID_HANDLE)
     {
      FileFlush(unit_path_handle);
      FileClose(unit_path_handle);
      unit_path_handle=INVALID_HANDLE;
     }
  }
#endif
