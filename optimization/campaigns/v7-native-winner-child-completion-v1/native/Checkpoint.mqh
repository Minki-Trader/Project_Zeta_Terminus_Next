// Durable state belongs to this run and to one exact committed parent snapshot.
// The normal six native paths use fresh tags; resume never adopts a previous trial.
struct WCCheckpoint
  {
   int version;
   int role;
   ulong magic;
   uchar identity[32];
   long sequence;
   long core_sequence;
   long server;
   double core_actual;
   double core_stress;
   int parents;
   long faults;
   long inferences;
   long updates;
   long children;
   long closed_children;
   long labels;
   long deferred;
   long mark_minute;
   long deferred_minute;
   long last_forecast_D;
   int finished;
   double positive_swap;
   double child_actual;
   double child_stress;
   double mse_sum;
   double zero_mse_sum;
   double weights[17];
   double covariance[289];
  };
uchar wc_identity[32];
bool wc_checkpoint_ready=false;

bool WCIdentity()
  {
   uchar bytes[],key[],hashed[];
   StringToCharArray(PORTFOLIO_ID+"|"+SCHEMA_VERSION+"|"+EXECUTION_VERSION+"|"+wc_root,bytes,0,WHOLE_ARRAY,CP_UTF8);
   if(CryptEncode(CRYPT_HASH_SHA256,bytes,key,hashed)!=32) return(false);
   ArrayCopy(wc_identity,hashed);return(true);
  }

bool WCReadCheckpoint(const string path,WCCheckpoint &header,WCParent &parents[],uchar &payload[])
  {
   int handle=FileOpen(path,FILE_READ|FILE_BIN);
   if(handle==INVALID_HANDLE) return(false);
   ulong size=FileSize(handle);
   if(size<sizeof(WCCheckpoint)+32 || size>32*1024*1024) {FileClose(handle);return(false);}
   int length=(int)size-32;
   if(ArrayResize(payload,length)!=length) {FileClose(handle);return(false);}
   uchar stored[32],key[],computed[];
   uint read=FileReadArray(handle,payload,0,length);
   uint hash_read=FileReadArray(handle,stored,0,32);FileClose(handle);
   if(read!=(uint)length || hash_read!=32 || CryptEncode(CRYPT_HASH_SHA256,payload,key,computed)!=32 ||
      ArrayCompare(stored,computed)!=0 || !CharArrayToStruct(header,payload)) return(false);
   if(header.version!=2 || header.role!=WC_ROLE || header.magic!=WC_MAGIC_FIRST ||
      ArrayCompare(header.identity,wc_identity)!=0 || header.sequence<=0 || header.parents<0 || header.parents>10000 ||
      length!=(int)sizeof(WCCheckpoint)+header.parents*(int)sizeof(WCParent)) return(false);
   if(ArrayResize(parents,header.parents)!=header.parents) return(false);
   for(int j=0;j<header.parents;++j)
     {
      if(!CharArrayToStruct(parents[j],payload,(uint)(sizeof(WCCheckpoint)+j*sizeof(WCParent)))) return(false);
      if(parents[j].parent==0 || parents[j].component<0 || parents[j].component>=5 ||
         MathAbs(parents[j].direction)!=1 || parents[j].volume<=0 || parents[j].entry<=0 ||
         parents[j].original_stop<=0 || parents[j].parent_budget<=0) return(false);
     }
   for(int j=0;j<17;++j) if(!MathIsValidNumber(header.weights[j]) || !MathIsValidNumber(header.covariance[j*17+j]) || header.covariance[j*17+j]<=0) return(false);
   for(int j=0;j<289;++j) if(!MathIsValidNumber(header.covariance[j])) return(false);
   return(true);
  }

bool WCSave()
  {
   if(!wc_checkpoint_ready || !wc_dirty) return(true);
   WCCheckpoint header={};header.version=2;header.role=WC_ROLE;header.magic=WC_MAGIC_FIRST;
   ArrayCopy(header.identity,wc_identity);header.sequence=wc_sequence+1;
   header.core_sequence=state_sequence;header.server=(long)TimeCurrent();
   header.core_actual=portfolio_state.project_realized_net;header.core_stress=portfolio_state.stressed_balance;
   header.parents=ArraySize(wc_parents);header.faults=wc_faults;header.inferences=wc_inferences;
   header.updates=wc_updates;header.children=wc_children;header.closed_children=wc_closed_children;
   header.labels=wc_labels;header.deferred=wc_deferred;header.mark_minute=(long)wc_mark_minute;
   header.deferred_minute=(long)wc_deferred_minute;header.last_forecast_D=(long)wc_last_forecast_D;
   header.finished=(wc_finished?1:0);header.positive_swap=wc_positive_swap;header.child_actual=wc_child_actual;
   header.child_stress=wc_child_stress;header.mse_sum=wc_mse_sum;header.zero_mse_sum=wc_zero_mse_sum;
   ArrayCopy(header.weights,wc_weights);ArrayCopy(header.covariance,wc_P);
   int length=(int)sizeof(WCCheckpoint)+header.parents*(int)sizeof(WCParent);
   uchar payload[],key[],hashed[];
   if(ArrayResize(payload,length)!=length || !StructToCharArray(header,payload)) {WCFail("checkpoint allocation");return(false);}
   for(int j=0;j<header.parents;++j)
      if(!StructToCharArray(wc_parents[j],payload,(uint)(sizeof(WCCheckpoint)+j*sizeof(WCParent)))) {WCFail("checkpoint parent encoding");return(false);}
   if(CryptEncode(CRYPT_HASH_SHA256,payload,key,hashed)!=32) {WCFail("checkpoint content hash");return(false);}
   string path=wc_root+"\\state\\child-"+(header.sequence%2==0?"a":"b")+".bin";
   int handle=FileOpen(path,FILE_WRITE|FILE_BIN);
   if(handle==INVALID_HANDLE) {WCFail("checkpoint open");return(false);}
   uint written=FileWriteArray(handle,payload);uint hash_written=FileWriteArray(handle,hashed);
   FileFlush(handle);FileClose(handle);
   WCCheckpoint restored={};WCParent restored_parents[];uchar reread[];
   if(written!=(uint)length || hash_written!=32 || !WCReadCheckpoint(path,restored,restored_parents,reread) ||
      ArrayCompare(payload,reread)!=0) {WCFail("complete paired checkpoint readback");return(false);}
   wc_sequence=header.sequence;wc_dirty=false;return(true);
  }

bool WCCommitCore()
  {
   if(!wc_checkpoint_ready) return(true);
   wc_dirty=true;return(WCSave());
  }

bool WCBindCore(const bool recovered)
  {
   if(!InpResumeOwnedCheckpoint) return(!recovered);
   if(!recovered || state_sequence<=0) {WCFail("resume lacks a valid original core checkpoint");return(false);}
   WCCheckpoint chosen={};WCParent chosen_parents[];bool found=false;
   for(int slot=0;slot<2;++slot)
     {
      string path=wc_root+"\\state\\child-"+(slot==0?"a":"b")+".bin";
      WCCheckpoint candidate={};WCParent records[];uchar payload[];
      if(!WCReadCheckpoint(path,candidate,records,payload)) continue;
      if(candidate.core_sequence!=state_sequence || candidate.core_actual!=portfolio_state.project_realized_net ||
         candidate.core_stress!=portfolio_state.stressed_balance || candidate.server>(long)TimeCurrent() || candidate.finished!=0) continue;
      bool compatible=true;
      for(int n=0;n<ArraySize(records);++n)
         if(records[n].alive && component_states[records[n].component].position_identifier!=records[n].parent) compatible=false;
      if(!compatible) continue;
      if(!found || candidate.sequence>chosen.sequence)
        {chosen=candidate;ArrayCopy(chosen_parents,records);found=true;}
     }
   if(!found) {WCFail("no matching child/core checkpoint; no mixed-state or prior-trial adoption");return(false);}
   ArrayCopy(wc_parents,chosen_parents);ArrayResize(wc_active,0);
   for(int n=0;n<ArraySize(wc_parents);++n)
     {
      WCParent p=wc_parents[n];
      if(!p.alive && p.child==0 && p.shadow!=1 && p.attempted!=1) continue;
      int count=ArraySize(wc_active);if(ArrayResize(wc_active,count+1)!=count+1) {WCFail("recovery active allocation");return(false);}
      wc_active[count]=n;
     }
   wc_sequence=chosen.sequence;wc_faults=chosen.faults;wc_inferences=chosen.inferences;wc_updates=chosen.updates;
   wc_children=chosen.children;wc_closed_children=chosen.closed_children;wc_labels=chosen.labels;wc_deferred=chosen.deferred;
   wc_mark_minute=(datetime)chosen.mark_minute;wc_deferred_minute=(datetime)chosen.deferred_minute;
   wc_last_forecast_D=(datetime)chosen.last_forecast_D;wc_finished=(chosen.finished!=0);
   wc_positive_swap=chosen.positive_swap;wc_child_actual=chosen.child_actual;wc_child_stress=chosen.child_stress;
   wc_mse_sum=chosen.mse_sum;wc_zero_mse_sum=chosen.zero_mse_sum;
   ArrayCopy(wc_weights,chosen.weights);ArrayCopy(wc_P,chosen.covariance);
   wc_checkpoint_ready=true;wc_dirty=false;
   WCLog("PAIRED_CHECKPOINT_RESUME",-1,(double)state_sequence,(double)wc_sequence,(double)chosen.server);
   return(true);
  }
