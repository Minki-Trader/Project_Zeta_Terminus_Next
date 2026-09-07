#ifndef ZETA_LAC_LEARNING_MQH
#define ZETA_LAC_LEARNING_MQH

// This module owns only this campaign's allocator, completed labels and evidence.
// Core position state and the frozen V7 exit rules remain in their original modules.
const string LAC_MODEL_SHA = "634E583C7FA271EDA8E48401F8C5C546AB6B0CE1A05E119BA0A2B77D82B1FA88";
string lac_root = "";
bool lac_initialized = false;
bool lac_faulted = false;
long lac_model = INVALID_HANDLE;
long lac_faults = 0, lac_inferences = 0, lac_day_steps = 0;
long lac_label_days = 0, lac_labels = 0, lac_deals = 0;
long lac_births = 0, lac_minute_rows = 0, lac_unknown_marks = 0;
long lac_checkpoint_sequence = 0;
datetime lac_day = 0;
long lac_last_minute = -1;
double lac_shift[5], lac_weights[5];
datetime lac_bucket_days[];
double lac_bucket_r[][6];
long lac_bucket_counts[];
long lac_bucket_max_close_msc[];
ulong lac_ids[6], lac_last_deal[6];
long lac_last_deal_msc[6];
double lac_entry_risk[6], lac_entry_weight[6], lac_life_stress[6];
double lac_positive_realized_swap = 0.0;
int lac_equity_file = INVALID_HANDLE, lac_day_file = INVALID_HANDLE;
int lac_entry_file = INVALID_HANDLE, lac_close_file = INVALID_HANDLE;

void LACFault(const string reason)
  {
   ++lac_faults;
   if(!lac_faulted)
      PrintFormat("V7LAC_FAULT role=%d server=%s reason=%s", LAC_MODE,
                  TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),reason);
   lac_faulted = true;
  }

bool LACReady()
  {
   return(lac_initialized && !lac_faulted);
  }

double LACWeight(const int component)
  {
   if(component == US100_PASSIVE_LIMIT || LAC_MODE == 0)
      return(1.0);
   if(component < 0 || component >= 5 || !LACReady())
      return(0.0);
   return(lac_weights[component]);
  }

bool LACConfigurePaths()
  {
   if(StringLen(InpNativeRunTag) < 1 || StringLen(InpNativeRunTag) > 80 ||
      InpNativeFrom >= InpNativeTo)
      return(false);
   for(int i=0;i<StringLen(InpNativeRunTag);++i)
     {
      const ushort ch=StringGetCharacter(InpNativeRunTag,i);
      if(!((ch>=48 && ch<=57) || (ch>=65 && ch<=90) ||
           (ch>=97 && ch<=122) || ch==45 || ch==95))
         return(false);
     }
   lac_root = LAC_NAMESPACE + "\\" + InpNativeRunTag;
   STATE_PATH_A=lac_root+"\\state\\state-a.csv";
   STATE_PATH_B=lac_root+"\\state\\state-b.csv";
   EVENT_PATH_A=lac_root+"\\state\\events-a.csv";
   EVENT_PATH_B=lac_root+"\\state\\events-b.csv";
   CURRENT_SNAPSHOT_PATH_A=lac_root+"\\state\\current-a.csv";
   CURRENT_SNAPSHOT_PATH_B=lac_root+"\\state\\current-b.csv";
   OWNERSHIP_PATH=lac_root+"\\state\\runtime.lock";
   RESEARCH_OBSERVATION_DIRECTORY=lac_root+"\\research";
   RESEARCH_OBSERVATION_STATE_PATH_A=lac_root+"\\research\\research-state-a.csv";
   RESEARCH_OBSERVATION_STATE_PATH_B=lac_root+"\\research\\research-state-b.csv";
   RESEARCH_CANDIDATE_LEDGER_PATH=lac_root+"\\research\\research-candidates.csv";
   RESEARCH_LIFECYCLE_LEDGER_PATH=lac_root+"\\research\\research-lifecycles.csv";
   FolderCreate(LAC_NAMESPACE);
   FolderCreate(lac_root);
   FolderCreate(lac_root+"\\state");
   FolderCreate(lac_root+"\\research");
   FolderCreate(lac_root+"\\learning");
   // A fresh native path must never resume another path's future learner state.
   if(FileIsExist(lac_root+"\\learning\\run-marker.txt"))
     {
      Print("V7LAC refusing an existing native run tag: ",InpNativeRunTag);
      return(false);
     }
   return(true);
  }

bool LACInfer()
  {
   if(LAC_MODE == 0)
     {
      ArrayInitialize(lac_weights,1.0);
      return(true);
     }
   float model_input[1][5], output[1][5];
   for(int i=0;i<5;++i)
     {
      if(!MathIsValidNumber(lac_shift[i]) || MathAbs(lac_shift[i])>2.0+1e-12)
        { LACFault("invalid bounded displacement"); return(false); }
      model_input[0][i]=(float)lac_shift[i];
     }
   if(!OnnxRun(lac_model,ONNX_NO_CONVERSION,model_input,output))
     { LACFault("ONNX inference error="+IntegerToString(GetLastError())); return(false); }
   ++lac_inferences;
   double minimum_score=1e100;
   for(int i=0;i<5;++i)
     {
      if(!MathIsValidNumber((double)output[0][i]) || output[0][i]<=0.0)
        { LACFault("nonpositive or nonfinite ONNX score"); return(false); }
      minimum_score=MathMin(minimum_score,(double)output[0][i]);
     }
   double lower=0.0, upper=MathMax(1.0,5.0/minimum_score);
   for(int iteration=0;iteration<100;++iteration)
     {
      const double scale=0.5*(lower+upper);
      double total=0.0;
      for(int i=0;i<5;++i)
         total+=MathMax(0.25,MathMin(2.0,scale*(double)output[0][i]));
      if(total<5.0) lower=scale; else upper=scale;
     }
   double total=0.0;
   for(int i=0;i<5;++i)
     {
      lac_weights[i]=MathMax(0.25,MathMin(2.0,0.5*(lower+upper)*(double)output[0][i]));
      total+=lac_weights[i];
     }
   if(!MathIsValidNumber(total) || MathAbs(total-5.0)>1e-9)
     { LACFault("capped projection sum mismatch"); return(false); }
   return(true);
  }

int LACBucket(const datetime day,const bool create)
  {
   const int count=ArraySize(lac_bucket_days);
   for(int i=0;i<count;++i)
      if(lac_bucket_days[i]==day) return(i);
   if(!create) return(-1);
   // Resize every array before inspecting status; a prior short-circuit left
   // later arrays unallocated when the 2D return count was misinterpreted.
   const int day_status=ArrayResize(lac_bucket_days,count+1);
   const int r_status=ArrayResize(lac_bucket_r,count+1);
   const int count_status=ArrayResize(lac_bucket_counts,count+1);
   const int time_status=ArrayResize(lac_bucket_max_close_msc,count+1);
   if(day_status<0 || r_status<0 || count_status<0 || time_status<0 ||
      ArrayRange(lac_bucket_days,0)!=count+1 || ArrayRange(lac_bucket_r,0)!=count+1 ||
      ArrayRange(lac_bucket_r,1)!=6 || ArrayRange(lac_bucket_counts,0)!=count+1 ||
      ArrayRange(lac_bucket_max_close_msc,0)!=count+1)
     { LACFault("day bucket allocation failed"); return(-1); }
   lac_bucket_days[count]=day;
   lac_bucket_counts[count]=0;
   lac_bucket_max_close_msc[count]=0;
   for(int j=0;j<6;++j) lac_bucket_r[count][j]=0.0;
   return(count);
  }

void LACCheckpoint()
  {
   if(!lac_initialized) return;
   ++lac_checkpoint_sequence;
   string body=StringFormat("LAC_STATE_V1,%s,%d,%I64d,%I64d,%I64d,%I64d,%.17g\n",
                           LAC_MODEL_SHA,LAC_MODE,lac_checkpoint_sequence,
                           (long)lac_day,lac_labels,lac_deals,lac_positive_realized_swap);
   for(int i=0;i<5;++i)
      body+=StringFormat("WEIGHT,%d,%.17g,%.17g\n",i,lac_shift[i],lac_weights[i]);
   for(int i=0;i<6;++i)
      body+=StringFormat("ENTRY,%d,%I64u,%.17g,%.17g,%.17g,%I64u,%I64d\n",
                         i,lac_ids[i],lac_entry_risk[i],lac_entry_weight[i],
                         lac_life_stress[i],lac_last_deal[i],lac_last_deal_msc[i]);
   const int durable_buckets=MathMin(MathMin(ArrayRange(lac_bucket_days,0),ArrayRange(lac_bucket_r,0)),
      MathMin(ArrayRange(lac_bucket_counts,0),ArrayRange(lac_bucket_max_close_msc,0)));
   for(int b=0;b<durable_buckets;++b)
      body+=StringFormat("DAY,%I64d,%I64d,%I64d,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g\n",
                         (long)lac_bucket_days[b],lac_bucket_counts[b],lac_bucket_max_close_msc[b],
                         lac_bucket_r[b][0],lac_bucket_r[b][1],lac_bucket_r[b][2],
                         lac_bucket_r[b][3],lac_bucket_r[b][4],lac_bucket_r[b][5]);
   body+=StringFormat("END,%s,%I64d\n",LAC_MODEL_SHA,lac_checkpoint_sequence);
   const string path=lac_root+"\\learning\\state-"+
      ((lac_checkpoint_sequence%2)==0 ? "a" : "b")+".txt";
   uchar bytes[];
   const int length=StringToCharArray(body,bytes,0,WHOLE_ARRAY,CP_UTF8)-1;
   int h=FileOpen(path,FILE_WRITE|FILE_BIN);
   if(h==INVALID_HANDLE || length<=0)
     { if(h!=INVALID_HANDLE) FileClose(h); LACFault("checkpoint open failed"); return; }
   const uint written=FileWriteArray(h,bytes,0,length);
   FileFlush(h); FileClose(h);
   if(written!=(uint)length)
     { LACFault("checkpoint write incomplete"); return; }
   h=FileOpen(path,FILE_READ|FILE_BIN);
   if(h==INVALID_HANDLE)
     { LACFault("checkpoint readback unavailable"); return; }
   uchar readback[];
   const long size=(long)FileSize(h);
   const uint read=FileReadArray(h,readback);
   FileClose(h);
   if(size!=length || read!=(uint)length)
     { LACFault("checkpoint readback length mismatch"); return; }
   for(int i=0;i<length;++i)
      if(bytes[i]!=readback[i])
        { LACFault("checkpoint readback content mismatch"); return; }
  }

bool LACInitialize()
  {
   ArrayInitialize(lac_shift,0.0);
   ArrayInitialize(lac_weights,1.0);
   ArrayInitialize(lac_ids,0); ArrayInitialize(lac_last_deal,0);
   ArrayInitialize(lac_last_deal_msc,0);
   ArrayInitialize(lac_entry_risk,0.0); ArrayInitialize(lac_entry_weight,0.0);
   ArrayInitialize(lac_life_stress,0.0);
   lac_day=(datetime)(((long)InpNativeFrom/86400)*86400);
   if(LAC_MODE!=0)
     {
      lac_model=OnnxCreateFromBuffer(LAC_MODEL_BYTES,ONNX_DEFAULT);
      const long shape[2]={1,5};
      if(lac_model==INVALID_HANDLE || !OnnxSetInputShape(lac_model,0,shape) ||
         !OnnxSetOutputShape(lac_model,0,shape))
        { LACFault("ONNX model/shape initialization failed"); return(false); }
     }
   if(!LACInfer()) return(false);
   lac_equity_file=FileOpen(lac_root+"\\learning\\equity.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',',CP_UTF8);
   lac_day_file=FileOpen(lac_root+"\\learning\\days.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',',CP_UTF8);
   lac_entry_file=FileOpen(lac_root+"\\learning\\entries.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',',CP_UTF8);
   lac_close_file=FileOpen(lac_root+"\\learning\\closes.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',',CP_UTF8);
   if(lac_equity_file==INVALID_HANDLE || lac_day_file==INVALID_HANDLE ||
      lac_entry_file==INVALID_HANDLE || lac_close_file==INVALID_HANDLE)
     { LACFault("evidence stream open failed"); return(false); }
   FileWrite(lac_equity_file,"server_time","known","balance","equity","margin","positions",
             "original_stressed_closed","positive_realized_swap","conservative_closed",
             "conservative_mark","capital","day_multiplier","aggregate_reserved",
             "w0","w1","w2","w3","w4","faults");
   FileWrite(lac_day_file,"completed_day","observed_server","label_count","max_close_msc","denominator",
             "r0","r1","r2","r3","r4","r5","old_w0","old_w1","old_w2","old_w3","old_w4",
             "shift0","shift1","shift2","shift3","shift4","new_w0","new_w1","new_w2","new_w3","new_w4");
   FileWrite(lac_entry_file,"observed_server","component","position_id","entry_server","volume",
             "reserved_entry_risk","entry_weight","day_multiplier","entry_price","stop_loss");
   FileWrite(lac_close_file,"observed_server","close_msc","close_day","component","position_id","deal",
             "full_exit","deal_actual","deal_stressed","deal_positive_swap","initial_reserved_risk",
             "entry_weight","lifecycle_stressed","completed_r");
   const int marker=FileOpen(lac_root+"\\learning\\run-marker.txt",FILE_WRITE|FILE_TXT|FILE_ANSI,0,CP_UTF8);
   if(marker==INVALID_HANDLE)
     { LACFault("run marker open failed"); return(false); }
   FileWriteString(marker,StringFormat("%s\n%s\n%d\n%s\n",LAC_MODEL_SHA,InpNativeRunTag,LAC_MODE,RELEASE_ID));
   FileFlush(marker); FileClose(marker);
   lac_initialized=true;
   LACCheckpoint();
   PrintFormat("V7LAC_INIT mode=%d model=%s start=%s end=%s weights=%.12f/%.12f/%.12f/%.12f/%.12f/1",
               LAC_MODE,LAC_MODEL_SHA,TimeToString(InpNativeFrom,TIME_DATE),TimeToString(InpNativeTo,TIME_DATE),
               lac_weights[0],lac_weights[1],lac_weights[2],lac_weights[3],lac_weights[4]);
   return(!lac_faulted);
  }

void LACAdvanceDay()
  {
   if(!LACReady()) return;
   const datetime now=TimeCurrent();
   const datetime today=(datetime)(((long)now/86400)*86400);
   if(today<lac_day || now>=InpNativeTo)
     { LACFault("allocator time outside the declared path"); return; }
   while(lac_day<today && !lac_faulted)
     {
      double r[6],old[5]; ArrayInitialize(r,0.0);
      for(int j=0;j<5;++j) old[j]=lac_weights[j];
      const int b=LACBucket(lac_day,false);
      long labels=0,max_close=0;
      if(b>=0)
        {
         labels=lac_bucket_counts[b]; max_close=lac_bucket_max_close_msc[b];
         for(int j=0;j<6;++j) r[j]=lac_bucket_r[b][j];
        }
      if(max_close>=(long)(lac_day+86400)*1000 || max_close>=(long)today*1000)
        { LACFault("non-mature label in daily update"); return; }
      double sum=r[5];
      for(int j=0;j<5;++j) sum+=old[j]*r[j];
      const double denominator=1.0+0.04*sum;
      if(!MathIsValidNumber(denominator) || denominator<=0.0)
        { LACFault("nonpositive daily log utility denominator; no loss clipping"); return; }
      if(LAC_MODE==2)
         for(int j=0;j<5;++j)
            lac_shift[j]=MathMax(-2.0,MathMin(2.0,lac_shift[j]+0.04*r[j]/denominator));
      if(!LACInfer()) return;
      if(FileWrite(lac_day_file,(long)lac_day,(long)now,labels,max_close,denominator,
                   r[0],r[1],r[2],r[3],r[4],r[5],old[0],old[1],old[2],old[3],old[4],
                   lac_shift[0],lac_shift[1],lac_shift[2],lac_shift[3],lac_shift[4],
                   lac_weights[0],lac_weights[1],lac_weights[2],lac_weights[3],lac_weights[4])==0)
         LACFault("daily evidence write failed");
      ++lac_day_steps;
      if(labels>0) ++lac_label_days;
      // Keep completed buckets in the bounded annual checkpoint for attribution.
      lac_day+=86400;
      FileFlush(lac_day_file);
      LACCheckpoint();
     }
  }

void LACBindEntry(const int component)
  {
   if(!lac_initialized || component<0 || component>=6) return;
   const ulong id=component_states[component].position_identifier;
   if(id==0 || lac_ids[component]==id) return;
   const double risk=component_states[component].entry_planned_risk_usd;
   if(lac_ids[component]!=0 || risk<=0.0 || !MathIsValidNumber(risk))
     { LACFault("entry attribution identity/risk mismatch"); return; }
   lac_ids[component]=id; lac_entry_risk[component]=risk;
   lac_entry_weight[component]=LACWeight(component); lac_life_stress[component]=0.0;
   ++lac_births;
   if(FileWrite(lac_entry_file,(long)TimeCurrent(),component,id,
                (long)component_states[component].entry_time_server,
                component_states[component].entry_volume,risk,lac_entry_weight[component],
                portfolio_state.day_volume_multiplier,component_states[component].entry_check_order_price,
                component_states[component].entry_stop_loss)==0)
      LACFault("entry evidence write failed");
   FileFlush(lac_entry_file); LACCheckpoint();
  }

void LACObserveExit(const ResearchExitSnapshot &snapshot)
  {
   if(!lac_initialized) return;
   const int c=snapshot.component;
   if(c<0 || c>=6 || lac_ids[c]!=snapshot.position_identifier || lac_entry_risk[c]<=0.0 ||
      snapshot.deal_time_msc<lac_last_deal_msc[c] ||
      (snapshot.deal_time_msc==lac_last_deal_msc[c] && snapshot.deal_ticket<=lac_last_deal[c]))
     { LACFault("completed deal attribution/cursor mismatch"); return; }
   const datetime day=(datetime)((snapshot.deal_time_msc/86400000)*86400);
   if(day<lac_day || snapshot.deal_time_msc>(long)TimeCurrent()*1000+999)
     { LACFault("late or future completed label"); return; }
   const double positive_swap=MathMax(0.0,HistoryDealGetDouble(snapshot.deal_ticket,DEAL_SWAP));
   lac_positive_realized_swap+=positive_swap;
   lac_life_stress[c]+=snapshot.stressed_net;
   lac_last_deal[c]=snapshot.deal_ticket; lac_last_deal_msc[c]=snapshot.deal_time_msc;
   ++lac_deals;
   double completed_r=0.0;
   if(snapshot.full_exit)
     {
      completed_r=lac_life_stress[c]/lac_entry_risk[c];
      const int b=LACBucket(day,true);
      if(b<0 || !MathIsValidNumber(completed_r))
        { LACFault("invalid completed lifecycle label"); return; }
      lac_bucket_r[b][c]+=completed_r; ++lac_bucket_counts[b];
      lac_bucket_max_close_msc[b]=MathMax(lac_bucket_max_close_msc[b],snapshot.deal_time_msc);
      ++lac_labels;
     }
   if(FileWrite(lac_close_file,(long)TimeCurrent(),snapshot.deal_time_msc,(long)day,c,
                snapshot.position_identifier,snapshot.deal_ticket,(int)snapshot.full_exit,
                snapshot.deal_net,snapshot.stressed_net,positive_swap,lac_entry_risk[c],
                lac_entry_weight[c],lac_life_stress[c],completed_r)==0)
      LACFault("completed deal evidence write failed");
   if(snapshot.full_exit)
     { lac_ids[c]=0; lac_entry_risk[c]=0.0; lac_entry_weight[c]=0.0; lac_life_stress[c]=0.0; }
   FileFlush(lac_close_file); LACCheckpoint();
  }

void LACSampleEquity(const bool force=false)
  {
   if(!lac_initialized || !execution_state.runtime_ready) return;
   const datetime now=TimeCurrent();
   const long minute=(long)now/60;
   if(!force && minute==lac_last_minute) return;
   const double closed=portfolio_state.stressed_balance-lac_positive_realized_swap;
   double mark=closed;
   bool known=true; int owned=0;
   for(int c=0;c<6;++c)
     {
      if(component_states[c].position_identifier==0) continue;
      ulong ticket=0; datetime opened=0;
      if(CountOwnedPositions(c,ticket,opened)!=1 || !PositionSelectByTicket(ticket) ||
         (ulong)PositionGetInteger(POSITION_IDENTIFIER)!=component_states[c].position_identifier ||
         !component_states[c].entry_cost_known)
        { known=false; continue; }
      ++owned;
      const string symbol=component_definitions[c].symbol;
      MqlTick tick={};
      if(!SymbolInfoTick(symbol,tick) || tick.ask<tick.bid || tick.bid<=0.0)
        { known=false; continue; }
      const double volume=PositionGetDouble(POSITION_VOLUME);
      const double swap=PositionGetDouble(POSITION_SWAP);
      const double cost=component_states[c].entry_transaction_cost;
      const double spread=MathMax(component_states[c].entry_spread_price,tick.ask-tick.bid)*
                          SymbolInfoDouble(symbol,SYMBOL_TRADE_CONTRACT_SIZE)*volume;
      const double extra=spread+component_states[c].entry_adverse_slippage+
                         MathMax(0.0,-cost)+MathMax(0.0,-swap);
      mark+=PositionGetDouble(POSITION_PROFIT)+swap+cost-extra-MathMax(0.0,swap);
     }
   if(owned!=PositionsTotal()) known=false;
   if(!MathIsValidNumber(mark)) known=false;
   if(!known) ++lac_unknown_marks;
   if(FileWrite(lac_equity_file,(long)now,(int)known,AccountInfoDouble(ACCOUNT_BALANCE),
                AccountInfoDouble(ACCOUNT_EQUITY),AccountInfoDouble(ACCOUNT_MARGIN),PositionsTotal(),
                portfolio_state.stressed_balance,lac_positive_realized_swap,closed,
                (known ? DoubleToString(mark,12) : "UNKNOWN"),ConservativeRiskCapital(),
                portfolio_state.day_volume_multiplier,TrackedAggregatePlannedRisk(),
                lac_weights[0],lac_weights[1],lac_weights[2],lac_weights[3],lac_weights[4],lac_faults)==0)
      LACFault("equity evidence write failed");
   lac_last_minute=minute; ++lac_minute_rows;
   if((lac_minute_rows%60)==0 || force) FileFlush(lac_equity_file);
  }

void LACFinish()
  {
   if(!lac_initialized) return;
   LACSampleEquity(true); LACCheckpoint();
   PrintFormat("V7LAC_RESULT mode=%d faults=%I64d inferences=%I64d day_steps=%I64d label_days=%I64d births=%I64d labels=%I64d deals=%I64d equity_rows=%I64d unknown_marks=%I64d positive_swap=%.12f conservative_closed=%.12f positions=%d",
               LAC_MODE,lac_faults,lac_inferences,lac_day_steps,lac_label_days,lac_births,lac_labels,
               lac_deals,lac_minute_rows,lac_unknown_marks,lac_positive_realized_swap,
               portfolio_state.stressed_balance-lac_positive_realized_swap,PositionsTotal());
  }

void LACShutdown()
  {
   if(lac_equity_file!=INVALID_HANDLE) { FileFlush(lac_equity_file); FileClose(lac_equity_file); lac_equity_file=INVALID_HANDLE; }
   if(lac_day_file!=INVALID_HANDLE) { FileFlush(lac_day_file); FileClose(lac_day_file); lac_day_file=INVALID_HANDLE; }
   if(lac_entry_file!=INVALID_HANDLE) { FileFlush(lac_entry_file); FileClose(lac_entry_file); lac_entry_file=INVALID_HANDLE; }
   if(lac_close_file!=INVALID_HANDLE) { FileFlush(lac_close_file); FileClose(lac_close_file); lac_close_file=INVALID_HANDLE; }
   if(lac_model!=INVALID_HANDLE) { OnnxRelease(lac_model); lac_model=INVALID_HANDLE; }
  }

#endif
