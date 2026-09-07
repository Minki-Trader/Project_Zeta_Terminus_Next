#ifndef ZETA_NATIVE_ONLINE_LEARNING_MQH
#define ZETA_NATIVE_ONLINE_LEARNING_MQH

// Observational learner: no writes to trading state, orders or risk inputs.
#define NATIVE_ML_FEATURES 14
#define NATIVE_ML_PENDING 128
const string NATIVE_ML_GRAPH_SHA = "6873B125087E00863ABF5582FBB2FCFDD5B64214AD13FA97248146532281F190";
const string NATIVE_ML_ROOT = "ZetaV7MLLearner\\optimization\\native-learning\\learning\\";
struct NativeMLEntry
  {
   ulong identifier;
   double phi[NATIVE_ML_FEATURES];
   double prediction;
  };
struct NativeMLLabel
  {
   NativeMLEntry entry;
   int component;
   datetime available;
   long deal_msc;
   double raw;
   double clipped;
  };
NativeMLEntry native_ml_entries[COMPONENT_COUNT];
NativeMLLabel native_ml_pending[NATIVE_ML_PENDING];
double native_ml_weights[NATIVE_ML_FEATURES];
int native_ml_pending_count = 0;
int native_ml_trace = INVALID_HANDLE;
long native_ml_handle = INVALID_HANDLE;
long native_ml_forecasts = 0;
long native_ml_labels = 0;
long native_ml_updates = 0;
long native_ml_errors = 0;
long native_ml_checkpoint_sequence = 0;
double native_ml_raw_squared_error = 0.0;
double native_ml_clipped_squared_error = 0.0;
double native_ml_zero_squared_error = 0.0;

void NativeMLFault(const string reason)
  {
   ++native_ml_errors;
   if(native_ml_errors <= 8)
      PrintFormat("NATIVE_ML_FAULT reason=%s error=%d", reason, GetLastError());
  }

string NativeMLVector(const double &values[])
  {
   string result = "";
   for(int i = 0; i < NATIVE_ML_FEATURES; ++i)
      result += (i == 0 ? "" : "|") + DoubleToString(values[i], 12);
   return(result);
  }

void NativeMLTrace(const string event, const int component,
                   const NativeMLEntry &entry, const datetime available,
                   const long deal_msc, const double raw,
                   const double clipped, const string note)
  {
   if(native_ml_trace == INVALID_HANDLE)
      return;
   if(FileTell(native_ml_trace) > 16 * 1024 * 1024 - 4096)
     {
      NativeMLFault("trace_capacity");
      FileClose(native_ml_trace);
      native_ml_trace = INVALID_HANDLE;
      return;
     }
   if(FileWrite(native_ml_trace, event, (long)TimeCurrent(), component,
                entry.identifier, deal_msc, (long)available,
                DoubleToString(entry.prediction, 12), DoubleToString(raw, 12),
                DoubleToString(clipped, 12), native_ml_updates,
                NativeMLVector(entry.phi), NativeMLVector(native_ml_weights),
                note) == 0)
      NativeMLFault("trace_write");
   FileFlush(native_ml_trace);
  }

void NativeMLCheckpoint()
  {
   ++native_ml_checkpoint_sequence;
   const string path = NATIVE_ML_ROOT +
      (native_ml_checkpoint_sequence % 2 == 0 ? "checkpoint-a.csv" : "checkpoint-b.csv");
   const int handle = FileOpen(path, FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ, ',', CP_UTF8);
   if(handle == INVALID_HANDLE)
     {
      NativeMLFault("checkpoint_open");
      return;
     }
   bool written = FileWrite(handle, "NATIVE_ML_CHECKPOINT_V1", EXECUTION_VERSION,
                            NATIVE_ML_GRAPH_SHA, native_ml_checkpoint_sequence,
                            (long)TimeCurrent()) > 0;
   written = (FileWrite(handle, "COUNTERS", native_ml_forecasts, native_ml_labels,
                        native_ml_updates, native_ml_pending_count,
                        native_ml_errors, native_ml_raw_squared_error,
                        native_ml_clipped_squared_error,
                        native_ml_zero_squared_error) > 0 && written);
   written = (FileWrite(handle, "WEIGHTS", NativeMLVector(native_ml_weights)) > 0 && written);
   for(int c = 0; c < COMPONENT_COUNT; ++c)
      if(native_ml_entries[c].identifier != 0)
         written = (FileWrite(handle, "ACTIVE", c, native_ml_entries[c].identifier,
                              native_ml_entries[c].prediction,
                              NativeMLVector(native_ml_entries[c].phi)) > 0 && written);
   for(int p = 0; p < native_ml_pending_count; ++p)
      written = (FileWrite(handle, "PENDING", native_ml_pending[p].component,
                           native_ml_pending[p].entry.identifier,
                           (long)native_ml_pending[p].available,
                           native_ml_pending[p].deal_msc, native_ml_pending[p].raw,
                           native_ml_pending[p].clipped,
                           native_ml_pending[p].entry.prediction,
                           NativeMLVector(native_ml_pending[p].entry.phi)) > 0 && written);
   written = (FileWrite(handle, "END", native_ml_checkpoint_sequence) > 0 && written);
   FileFlush(handle);
   FileClose(handle);
   if(!written)
      NativeMLFault("checkpoint_write");
  }

bool NativeMLInitialize()
  {
   if(!MQLInfoInteger(MQL_TESTER))
      return(false);
   ArrayInitialize(native_ml_weights, 0.0);
   for(int c = 0; c < COMPONENT_COUNT; ++c)
      ZeroMemory(native_ml_entries[c]);
   FolderCreate("ZetaV7MLLearner\\optimization\\native-learning\\learning");
   // A fresh tester pass owns these paths; no previous learner state is adopted.
   native_ml_trace = FileOpen(NATIVE_ML_ROOT + "learning-events.csv",
                              FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ, ',', CP_UTF8);
   if(native_ml_trace == INVALID_HANDLE)
     {
      NativeMLFault("trace_open");
      return(false);
     }
   if(FileWrite(native_ml_trace, "event", "server_time", "component", "position_id",
                "deal_time_msc", "available_time", "entry_prediction", "raw_label",
                "clipped_label", "updates", "entry_features", "current_weights", "note") == 0)
      NativeMLFault("trace_header");
   native_ml_handle = OnnxCreateFromBuffer(NativeOnlineGraph, ONNX_DEFAULT);
   const long feature_shape[] = {1, NATIVE_ML_FEATURES};
   const long weight_shape[] = {NATIVE_ML_FEATURES, 1};
   const long output_shape[] = {1, 1};
   if(native_ml_handle == INVALID_HANDLE ||
      !OnnxSetInputShape(native_ml_handle, 0, feature_shape) ||
      !OnnxSetInputShape(native_ml_handle, 1, weight_shape) ||
      !OnnxSetOutputShape(native_ml_handle, 0, output_shape))
     {
      NativeMLFault("model_initialize");
      return(false);
     }
   NativeMLCheckpoint();
   PrintFormat("NATIVE_ML_START graph=%s features=%d initial_weights=zeros step=0.05 observational=1",
               NATIVE_ML_GRAPH_SHA, NATIVE_ML_FEATURES);
   return(native_ml_errors == 0);
  }

void NativeMLApplyMatured(const datetime now)
  {
   bool changed = false;
   int retained = 0;
   for(int p = 0; p < native_ml_pending_count; ++p)
     {
      // Availability is knowledge time. Strict inequality excludes same-second labels.
      if(native_ml_pending[p].available >= now)
        {
         if(retained != p)
            native_ml_pending[retained] = native_ml_pending[p];
         ++retained;
         continue;
        }
      const NativeMLLabel label = native_ml_pending[p];
      const double error = label.clipped - label.entry.prediction;
      double denominator = 1.0;
      for(int i = 0; i < NATIVE_ML_FEATURES; ++i)
         denominator += label.entry.phi[i] * label.entry.phi[i];
      for(int i = 0; i < NATIVE_ML_FEATURES; ++i)
         native_ml_weights[i] = MathMax(-2.0, MathMin(2.0,
            native_ml_weights[i] + 0.05 * error * label.entry.phi[i] / denominator));
      ++native_ml_updates;
      NativeMLTrace("UPDATE", label.component, label.entry, label.available,
                     label.deal_msc, label.raw, label.clipped, "strictly_later_event");
      changed = true;
     }
   native_ml_pending_count = retained;
   if(changed)
      NativeMLCheckpoint();
  }

void NativeMLBirth(const int component, const ulong identifier,
                   const double feature, const int direction,
                   const int prior_direction, const bool partial)
  {
   if(component < 0 || component >= COMPONENT_COUNT || identifier == 0 ||
      partial || !MathIsValidNumber(feature) || native_ml_entries[component].identifier != 0)
     {
      NativeMLFault("birth_identity_or_feature");
      return;
     }
   NativeMLApplyMatured(TimeCurrent());
   NativeMLEntry entry;
   ZeroMemory(entry);
   entry.identifier = identifier;
   entry.phi[component] = 1.0;
   entry.phi[COMPONENT_COUNT + component] = feature / (1.0 + MathAbs(feature));
   entry.phi[12] = (double)direction;
   entry.phi[13] = (double)(direction * prior_direction);
   matrixf features(1, NATIVE_ML_FEATURES);
   matrixf weights(NATIVE_ML_FEATURES, 1);
   matrixf score(1, 1);
   for(int i = 0; i < NATIVE_ML_FEATURES; ++i)
     {
      features[0][i] = (float)entry.phi[i];
      weights[i][0] = (float)native_ml_weights[i];
     }
   if(native_ml_handle == INVALID_HANDLE ||
      !OnnxRun(native_ml_handle, ONNX_NO_CONVERSION, features, weights, score) ||
      !MathIsValidNumber((double)score[0][0]))
     {
      NativeMLFault("inference");
      return;
     }
   entry.prediction = (double)score[0][0];
   native_ml_entries[component] = entry;
   ++native_ml_forecasts;
   NativeMLTrace("FORECAST", component, entry, 0, 0, 0.0, 0.0, "accepted_birth");
   NativeMLCheckpoint();
  }

void NativeMLClose(const int component, const ulong identifier,
                   const long deal_msc, const double stressed_net,
                   const double planned_risk, const bool partial)
  {
   if(component < 0 || component >= COMPONENT_COUNT || partial ||
      native_ml_entries[component].identifier != identifier || identifier == 0 ||
      !MathIsValidNumber(stressed_net) || !MathIsValidNumber(planned_risk) || planned_risk <= 0.0 ||
      native_ml_pending_count >= NATIVE_ML_PENDING)
     {
      NativeMLFault("close_identity_risk_or_capacity");
      return;
     }
   NativeMLLabel label;
   label.entry = native_ml_entries[component];
   label.component = component;
   label.available = (datetime)MathMax((double)TimeCurrent(), (double)(deal_msc / 1000));
   label.deal_msc = deal_msc;
   label.raw = stressed_net / planned_risk;
   label.clipped = MathMax(-2.0, MathMin(2.0, label.raw));
   const double raw_error = label.raw - label.entry.prediction;
   const double clipped_error = label.clipped - label.entry.prediction;
   native_ml_raw_squared_error += raw_error * raw_error;
   native_ml_clipped_squared_error += clipped_error * clipped_error;
   native_ml_zero_squared_error += label.clipped * label.clipped;
   native_ml_pending[native_ml_pending_count++] = label;
   ++native_ml_labels;
   NativeMLTrace("LABEL_QUEUED", component, label.entry, label.available,
                  deal_msc, label.raw, label.clipped, "loss_scored_before_update");
   ZeroMemory(native_ml_entries[component]);
   NativeMLCheckpoint();
  }

void NativeMLSummary()
  {
   NativeMLApplyMatured(TimeCurrent());
   NativeMLCheckpoint();
   int active = 0;
   for(int c = 0; c < COMPONENT_COUNT; ++c)
      if(native_ml_entries[c].identifier != 0)
         ++active;
   if(native_ml_forecasts != native_ml_labels + active ||
      native_ml_labels != native_ml_updates + native_ml_pending_count)
      NativeMLFault("lifecycle_accounting");
   const double denominator = MathMax(1.0, (double)native_ml_labels);
   PrintFormat("NATIVE_ML_RESULT forecasts=%I64d labels=%I64d updates=%I64d pending=%d active=%d errors=%I64d raw_mse=%.9f clipped_mse=%.9f zero_mse=%.9f weights=%s graph=%s",
               native_ml_forecasts, native_ml_labels, native_ml_updates,
               native_ml_pending_count, active, native_ml_errors,
               native_ml_raw_squared_error / denominator,
               native_ml_clipped_squared_error / denominator,
               native_ml_zero_squared_error / denominator,
               NativeMLVector(native_ml_weights), NATIVE_ML_GRAPH_SHA);
  }

void NativeMLRelease()
  {
   if(native_ml_trace != INVALID_HANDLE)
     {
      FileFlush(native_ml_trace);
      FileClose(native_ml_trace);
      native_ml_trace = INVALID_HANDLE;
     }
   if(native_ml_handle != INVALID_HANDLE)
     {
      OnnxRelease(native_ml_handle);
      native_ml_handle = INVALID_HANDLE;
     }
  }
#endif
