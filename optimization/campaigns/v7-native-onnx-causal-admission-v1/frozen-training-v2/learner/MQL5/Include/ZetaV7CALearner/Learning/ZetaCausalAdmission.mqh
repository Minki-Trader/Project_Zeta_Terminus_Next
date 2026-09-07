#ifndef ZETA_CAUSAL_ADMISSION_MQH
#define ZETA_CAUSAL_ADMISSION_MQH

#include <ZetaV7CALearner\Learning\ZetaCausalParameters.mqh>
#include <ZetaV7CALearner\Learning\ZetaCausalGraph.mqh>

struct CausalRecord
  {
   long id;
   datetime decision, deadline, available;
   int component, action;
   double propensity, capital, before_equity, after_equity, reward;
   double baseline, effect, raw[16], x[17];
  };
CausalRecord causal_records[];
long causal_handle=INVALID_HANDLE;
int causal_decision_file=INVALID_HANDLE,causal_label_file=INVALID_HANDLE;
int causal_update_file=INVALID_HANDLE,causal_path_file=INVALID_HANDLE;
int causal_completion_cursor=0,causal_update_cursor=0;
long causal_sequence=0,causal_updates=0,causal_faults=0,causal_abstentions=0;
uint causal_rng=0;
datetime causal_last_path_minute=0,causal_last_update_available=0;
double causal_positive_closed_swap=0;
long causal_mark_max_quote_age=0;
double causal_mu[16],causal_sd[16],causal_beta[17],causal_theta[17],causal_P[289];
string causal_directory="";
bool causal_ready=false;

bool CausalFault(const string reason)
  {
   ++causal_faults;
   PrintFormat("CAUSAL_FAULT role=%d tag=%s reason=%s last_error=%d",
               InpCausalRole,InpCausalRunTag,reason,GetLastError());
   EngageSafetyStop("causal evidence/model: "+reason);
   return(false);
  }

bool CausalLine(const int handle,const string line)
  {
   ResetLastError();
   const uint written=FileWriteString(handle,line+"\r\n");
   FileFlush(handle);
   if(written==0 || GetLastError()!=0)
      return(CausalFault("durable record write"));
   return(true);
  }

string CausalVector(const double &values[],const int count)
  {
   string result="";
   for(int i=0;i<count;++i)
     {
      if(i>0) result+=";";
      result+=DoubleToString(values[i],17);
     }
   return(result);
  }

bool CausalCheckpoint()
  {
   ++causal_sequence;
   const string path=causal_directory+"\\posterior-"+
                     (causal_sequence%2==0?"a":"b")+".csv";
   const int handle=FileOpen(path,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle==INVALID_HANDLE) return(CausalFault("posterior open"));
   bool ok=CausalLine(handle,"V7CA_STATE_1,"+InpCausalRunTag+","+
                     (string)InpCausalRole+","+(string)causal_sequence+","+
                     (string)causal_rng+","+(string)ArraySize(causal_records)+","+
                     (string)causal_completion_cursor+","+(string)causal_update_cursor+","+
                     (string)causal_updates+","+(string)causal_last_update_available+","+
                     DoubleToString(causal_positive_closed_swap,17));
   ok=CausalLine(handle,"MEAN,"+CausalVector(causal_mu,16)) && ok;
   ok=CausalLine(handle,"SD,"+CausalVector(causal_sd,16)) && ok;
   ok=CausalLine(handle,"BASELINE,"+CausalVector(causal_beta,17)) && ok;
   ok=CausalLine(handle,"EFFECT,"+CausalVector(causal_theta,17)) && ok;
   ok=CausalLine(handle,"COVARIANCE,"+CausalVector(causal_P,289)) && ok;
   for(int i=causal_update_cursor;i<ArraySize(causal_records);++i)
     {
      CausalRecord r=causal_records[i];
      ok=CausalLine(handle,"PENDING,"+(string)r.id+","+(string)r.decision+","+
                    (string)r.deadline+","+(string)r.available+","+(string)r.component+","+
                    (string)r.action+","+DoubleToString(r.propensity,17)+","+
                    DoubleToString(r.capital,17)+","+DoubleToString(r.before_equity,17)+","+
                    DoubleToString(r.after_equity,17)+","+DoubleToString(r.reward,17)+","+
                    DoubleToString(r.baseline,17)+","+DoubleToString(r.effect,17)+","+
                    CausalVector(r.raw,16)+","+CausalVector(r.x,17)) && ok;
     }
   ok=CausalLine(handle,"END,"+(string)causal_sequence) && ok;
   FileClose(handle);
   return(ok);
  }

bool CausalPreparePaths()
  {
   if(StringLen(InpCausalRunTag)<3 || StringLen(InpCausalRunTag)>64)
      return(false);
   for(int i=0;i<StringLen(InpCausalRunTag);++i)
     {
      const ushort c=StringGetCharacter(InpCausalRunTag,i);
      if(!((c>='a' && c<='z') || (c>='0' && c<='9') || c=='-'))
         return(false);
     }
   const string top="ZetaV7CALearner";
   const string base=top+"\\ca\\"+InpCausalRunTag;
   causal_directory=base+"\\learning";
   STATE_PATH_A=base+"\\state\\state-a.csv";
   STATE_PATH_B=base+"\\state\\state-b.csv";
   EVENT_PATH_A=base+"\\state\\events-a.csv";
   EVENT_PATH_B=base+"\\state\\events-b.csv";
   CURRENT_SNAPSHOT_PATH_A=base+"\\state\\current-a.csv";
   CURRENT_SNAPSHOT_PATH_B=base+"\\state\\current-b.csv";
   OWNERSHIP_PATH=base+"\\state\\runtime.lock";
   RESEARCH_OBSERVATION_DIRECTORY=base+"\\research";
   RESEARCH_OBSERVATION_STATE_PATH_A=base+"\\research\\research-state-a.csv";
   RESEARCH_OBSERVATION_STATE_PATH_B=base+"\\research\\research-state-b.csv";
   RESEARCH_CANDIDATE_LEDGER_PATH=base+"\\research\\research-candidates.csv";
   RESEARCH_LIFECYCLE_LEDGER_PATH=base+"\\research\\research-lifecycles.csv";
   if(FileIsExist(causal_directory+"\\decisions.csv") ||
      FileIsExist(STATE_PATH_A) || FileIsExist(STATE_PATH_B))
     {
      Print("CAUSAL_EXISTING_EPISODE_REFUSED ",InpCausalRunTag);
      return(false);
     }
   FolderCreate(top);
   FolderCreate(top+"\\ca");
   FolderCreate(base);FolderCreate(base+"\\state");
   FolderCreate(base+"\\research");FolderCreate(causal_directory);
   return(true);
  }

bool CausalInitialize()
  {
   if(InpCausalRole<0 || InpCausalRole>3 ||
      (InpCausalRole>=2 && !CAUSAL_FIT_READY) || InpCausalSeed==0)
      return(false);
   causal_rng=InpCausalSeed;
   ArrayCopy(causal_mu,CAUSAL_INITIAL_MEAN);ArrayCopy(causal_sd,CAUSAL_INITIAL_SD);
   ArrayCopy(causal_beta,CAUSAL_INITIAL_BASELINE);ArrayCopy(causal_theta,CAUSAL_INITIAL_EFFECT);
   ArrayCopy(causal_P,CAUSAL_INITIAL_COVARIANCE);
   causal_decision_file=FileOpen(causal_directory+"\\decisions.csv",FILE_WRITE|FILE_TXT|FILE_ANSI);
   causal_label_file=FileOpen(causal_directory+"\\labels.csv",FILE_WRITE|FILE_TXT|FILE_ANSI);
   causal_update_file=FileOpen(causal_directory+"\\updates.csv",FILE_WRITE|FILE_TXT|FILE_ANSI);
   causal_path_file=FileOpen(causal_directory+"\\equity.csv",FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(causal_decision_file==INVALID_HANDLE || causal_label_file==INVALID_HANDLE ||
      causal_update_file==INVALID_HANDLE || causal_path_file==INVALID_HANDLE)
      return(CausalFault("episode ledger open"));
   if(!CausalLine(causal_decision_file,"id,decision,component,action,propensity,capital,stress_before,baseline,effect,rng,updates,max_update_available,raw,x") ||
      !CausalLine(causal_label_file,"id,decision,deadline,available,stress_before,stress_after,capital,reward") ||
      !CausalLine(causal_update_file,"id,available,consumed,action,propensity,reward,baseline,pseudooutcome,effect_before,effect_after,updates") ||
      !CausalLine(causal_path_file,"server,actual_balance,actual_equity,original_stress_balance,conservative_stress_equity,positive_closed_swap,open_positions,day_multiplier,planned_risk,max_owned_quote_age_seconds"))
      return(false);
   if(InpCausalRole>=2)
     {
      causal_handle=OnnxCreateFromBuffer(CAUSAL_ONNX_BYTES,ONNX_USE_CPU_ONLY);
      const long xs[2]={1,17},ws[2]={17,2},ys[2]={1,2};
      if(causal_handle==INVALID_HANDLE || !OnnxSetInputShape(causal_handle,0,xs) ||
         !OnnxSetInputShape(causal_handle,1,ws) || !OnnxSetOutputShape(causal_handle,0,ys))
         return(CausalFault("ONNX initialization"));
     }
   causal_ready=true;
   return(CausalCheckpoint());
  }

void CausalExitAccounting(const ulong deal)
  {
   if(causal_ready)
      causal_positive_closed_swap+=MathMax(0.0,HistoryDealGetDouble(deal,DEAL_SWAP));
  }

bool CausalMarkedEquity(double &value,int &open_count)
  {
   if(execution_state.pending_reconcile) return(false);
   value=portfolio_state.stressed_balance-causal_positive_closed_swap;
   open_count=0;causal_mark_max_quote_age=0;
   for(int c=0;c<COMPONENT_COUNT;++c)
     {
      if(component_states[c].position_identifier==0) continue;
      ulong ticket=0;datetime opened=0;
      if(CountOwnedPositions(c,ticket,opened)!=1 || !PositionSelectByTicket(ticket) ||
         (ulong)PositionGetInteger(POSITION_IDENTIFIER)!=component_states[c].position_identifier)
         return(false);
      MqlTick tick={};const string symbol=component_definitions[c].symbol;
      if(!SymbolInfoTick(symbol,tick) || tick.bid<=0 || tick.ask<tick.bid ||
         tick.time>TimeCurrent())
         return(false);
      causal_mark_max_quote_age=MathMax(causal_mark_max_quote_age,(long)(TimeCurrent()-tick.time));
      const double volume=PositionGetDouble(POSITION_VOLUME);
      const double contract=SymbolInfoDouble(symbol,SYMBOL_TRADE_CONTRACT_SIZE);
      const double swap=PositionGetDouble(POSITION_SWAP);
      const double entry_cost=component_states[c].entry_transaction_cost;
      const double reserve=MathMax(component_states[c].entry_spread_price,tick.ask-tick.bid)*contract*volume+
                           component_states[c].entry_adverse_slippage+
                           MathMax(0.0,-entry_cost)+MathMax(0.0,-swap);
      value+=PositionGetDouble(POSITION_PROFIT)+MathMin(0.0,swap)+entry_cost-reserve;
      ++open_count;
     }
   return(MathIsValidNumber(value));
  }

void CausalObserve()
  {
   if(!causal_ready || causal_faults!=0) return;
   const datetime now=TimeCurrent();const datetime minute=now-now%60;
   const bool due=causal_completion_cursor<ArraySize(causal_records) &&
                  causal_records[causal_completion_cursor].deadline<=now;
   if(!due && minute==causal_last_path_minute) return;
   double equity=0;int open_count=0;
   if(!CausalMarkedEquity(equity,open_count)) return;
   if(minute!=causal_last_path_minute)
     {
      if(!CausalLine(causal_path_file,(string)now+","+
          DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE),12)+","+
          DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY),12)+","+
          DoubleToString(portfolio_state.stressed_balance,12)+","+DoubleToString(equity,12)+","+
          DoubleToString(causal_positive_closed_swap,12)+","+(string)open_count+","+
          (string)portfolio_state.day_volume_multiplier+","+DoubleToString(TrackedAggregatePlannedRisk(),12)+","+(string)causal_mark_max_quote_age)) return;
      causal_last_path_minute=minute;
     }
   bool changed=false;
   while(causal_completion_cursor<ArraySize(causal_records) &&
         causal_records[causal_completion_cursor].deadline<=now)
     {
      const int i=causal_completion_cursor;
      causal_records[i].available=now;causal_records[i].after_equity=equity;
      causal_records[i].reward=(equity-causal_records[i].before_equity)/causal_records[i].capital;
      CausalRecord r=causal_records[i];
      if(!MathIsValidNumber(r.reward) || !CausalLine(causal_label_file,(string)r.id+","+
          (string)r.decision+","+(string)r.deadline+","+(string)r.available+","+
          DoubleToString(r.before_equity,17)+","+DoubleToString(equity,17)+","+
          DoubleToString(r.capital,17)+","+DoubleToString(r.reward,17)))
        {CausalFault("reward completion");return;}
      ++causal_completion_cursor;changed=true;
     }
   if(changed) CausalCheckpoint();
  }

bool CausalLearnMature(const datetime decision)
  {
   while(causal_update_cursor<causal_completion_cursor &&
         causal_records[causal_update_cursor].available<decision)
     {
      CausalRecord r=causal_records[causal_update_cursor];
      if(InpCausalRole==3)
        {
         double px[17]={};double before=0,denom=1;
         for(int i=0;i<17;++i)
           {
            before+=causal_theta[i]*r.x[i];
            for(int j=0;j<17;++j) px[i]+=causal_P[i*17+j]*r.x[j];
            denom+=r.x[i]*px[i];
           }
         const double z=(r.action-r.propensity)*(r.reward-r.baseline)/
                        (r.propensity*(1-r.propensity));
         if(!MathIsValidNumber(z) || !MathIsValidNumber(denom) || denom<=0)
            return(CausalFault("causal update arithmetic"));
         for(int i=0;i<17;++i)
           {
            causal_theta[i]+=px[i]*(z-before)/denom;
            for(int j=0;j<17;++j) causal_P[i*17+j]-=px[i]*px[j]/denom;
           }
         double after=0;
         for(int i=0;i<17;++i)
           {
            if(!MathIsValidNumber(causal_theta[i]) || causal_P[i*17+i]<=0)
               return(CausalFault("posterior covariance/effect"));
            after+=causal_theta[i]*r.x[i];
            for(int j=0;j<17;++j)
               if(!MathIsValidNumber(causal_P[i*17+j])) return(CausalFault("posterior covariance"));
           }
         ++causal_updates;causal_last_update_available=r.available;
         if(!CausalLine(causal_update_file,(string)r.id+","+(string)r.available+","+
             (string)decision+","+(string)r.action+","+DoubleToString(r.propensity,17)+","+
             DoubleToString(r.reward,17)+","+DoubleToString(r.baseline,17)+","+
             DoubleToString(z,17)+","+DoubleToString(before,17)+","+
             DoubleToString(after,17)+","+(string)causal_updates)) return(false);
        }
      ++causal_update_cursor;
     }
   return(true);
  }

double CausalUniform()
  {
   causal_rng^=(causal_rng<<13);causal_rng^=(causal_rng>>17);causal_rng^=(causal_rng<<5);
   return((double)causal_rng/4294967296.0);
  }

bool CausalAdmission(const int component,const int direction,const double feature)
  {
   if(InpCausalRole==0) return(true);
   if(!causal_ready || causal_faults!=0) return(false);
   CausalObserve();
   const datetime now=TimeCurrent();
   if(!CausalLearnMature(now)) return(false);
   double equity=0;int open_count=0;
   const double capital=ConservativeRiskCapital();
   if(capital<=0 || !CausalMarkedEquity(equity,open_count))
      return(CausalFault("unavailable pre-treatment account context"));
   CausalRecord r={};r.id=ArraySize(causal_records)+1;r.decision=now;r.deadline=now+86400;
   r.component=component;r.capital=capital;r.before_equity=equity;
   const int index=(component==RC16_LONG?0:component==RC4_BOTH?1:
                    component==US100_CROSS?2:component==US30_PRESSURE?3:4);
   r.raw[index]=1;r.raw[5]=direction;r.raw[6]=feature;r.raw[7]=MathLog(capital/100.0);
   r.raw[8]=(ProjectStageBalance()-portfolio_state.stressed_balance)/capital;
   r.raw[9]=(AccountInfoDouble(ACCOUNT_EQUITY)-AccountInfoDouble(ACCOUNT_BALANCE))/capital;
   r.raw[10]=TrackedAggregatePlannedRisk()/capital;
   r.raw[11]=AccountInfoDouble(ACCOUNT_MARGIN_FREE)/AccountInfoDouble(ACCOUNT_EQUITY);
   r.raw[12]=(double)open_count/3.0;
   for(int c=0;c<COMPONENT_COUNT;++c)
     {
      if(component_definitions[c].symbol!=component_definitions[component].symbol ||
         component_states[c].position_identifier==0) continue;
      const int slot=(component_states[c].entry_direction==direction?13:14);
      r.raw[slot]+=component_states[c].entry_planned_risk_usd/capital;
     }
   if(execution_state.passive_pending_order>0 && component_definitions[component].symbol=="US100")
     {
      const int slot=(passive_pending_direction==direction?13:14);
      r.raw[slot]+=passive_pending_planned_risk_usd/capital;
     }
   MqlDateTime clock={};TimeToStruct(now,clock);r.raw[15]=(double)clock.hour/24.0;r.x[0]=1;
   for(int i=0;i<16;++i)
     {
      if(!MathIsValidNumber(r.raw[i]) || causal_sd[i]<=0) return(CausalFault("raw context"));
      r.x[i+1]=(r.raw[i]-causal_mu[i])/causal_sd[i];
     }
   if(InpCausalRole>=2)
     {
      matrixf x(1,17),w(17,2),y(1,2);
      for(int i=0;i<17;++i)
        {x[0][i]=(float)r.x[i];w[i][0]=(float)causal_beta[i];w[i][1]=(float)causal_theta[i];}
      if(!OnnxRun(causal_handle,ONNX_NO_CONVERSION,x,w,y)) return(CausalFault("ONNX inference"));
      r.baseline=(double)y[0][0];r.effect=(double)y[0][1];
      if(!MathIsValidNumber(r.baseline) || !MathIsValidNumber(r.effect)) return(CausalFault("ONNX output"));
     }
   r.propensity=(InpCausalRole==1?.5:InpCausalRole==2?(r.effect>0?1.0:0.0):(r.effect>0?.9:.1));
   r.action=(InpCausalRole==2?(r.effect>0?1:0):(CausalUniform()<r.propensity?1:0));
   const int n=ArraySize(causal_records);
   if(ArrayResize(causal_records,n+1)!=n+1) return(CausalFault("pending allocation"));
   causal_records[n]=r;
   if(!CausalLine(causal_decision_file,(string)r.id+","+(string)now+","+(string)component+","+
       (string)r.action+","+DoubleToString(r.propensity,17)+","+DoubleToString(capital,17)+","+
       DoubleToString(equity,17)+","+DoubleToString(r.baseline,17)+","+DoubleToString(r.effect,17)+","+
       (string)causal_rng+","+(string)causal_updates+","+(string)causal_last_update_available+","+
       CausalVector(r.raw,16)+","+CausalVector(r.x,17)) || !CausalCheckpoint()) return(false);
   if(r.action==0)
     {
      ++causal_abstentions;
      component_states[component].entry_check_result="CAUSAL_ABSTAIN";
      return(false);
     }
   return(true);
  }

void CausalFinish()
  {
   if(!causal_ready) return;
   CausalObserve();CausalCheckpoint();
   double equity=0;int open_count=0;const bool marked=CausalMarkedEquity(equity,open_count);
   if(!marked || open_count!=0) CausalFault("final native account mark or open position");
   PrintFormat("CAUSAL_RESULT role=%d tag=%s records=%d completed=%d consumed=%d updates=%I64d pending=%d abstentions=%I64d faults=%I64d mark_known=%d stress_equity=%.9f positive_closed_swap=%.9f open=%d rng=%u state_sequence=%I64d",
               InpCausalRole,InpCausalRunTag,ArraySize(causal_records),causal_completion_cursor,
               causal_update_cursor,causal_updates,ArraySize(causal_records)-causal_completion_cursor,
               causal_abstentions,causal_faults,(int)marked,equity,causal_positive_closed_swap,
               open_count,causal_rng,causal_sequence);
  }

void CausalShutdown()
  {
   if(causal_ready) CausalCheckpoint();
   if(causal_handle!=INVALID_HANDLE) OnnxRelease(causal_handle);
   if(causal_decision_file!=INVALID_HANDLE) FileClose(causal_decision_file);
   if(causal_label_file!=INVALID_HANDLE) FileClose(causal_label_file);
   if(causal_update_file!=INVALID_HANDLE) FileClose(causal_update_file);
   if(causal_path_file!=INVALID_HANDLE) FileClose(causal_path_file);
   causal_ready=false;
  }
#endif
