#ifndef ZETA_DENSITY_DOMAIN_MQH
#define ZETA_DENSITY_DOMAIN_MQH

#include <ZetaV7Density\Learning\DensityInitial.mqh>

input string InpNativeBinding = "";
bool density_failed = false;
bool density_initialized = false;
bool density_finished = false;
string density_root = "";
long density_onnx = INVALID_HANDLE;
long density_sequence = 0;
long density_state_sequence = 0;
long density_forecasts = 0;
long density_abstentions = 0;
long density_observations = 0;
long density_updates = 0;
long density_update_inferences = 0;
long density_ledger_bytes = 0;
long density_readbacks = 0;
long density_last_minute = -1;
long density_mark_rows = 0;
long density_exit_rows = 0;
int density_equity_handle = INVALID_HANDLE;
ulong density_equity_bytes = 0;
datetime density_last_applied_observation = 0;
double density_positive_swap = 0.0;
double density_conservative_peak = 100.0;
double density_conservative_closed_dd = 0.0;
double density_weights[6][2];
double density_means[6][2];
double density_variances[6][2];
double density_N[6][2];
double density_S[6][2];
double density_Q[6][2];
datetime density_last_bar[6];
double density_last_feature[6];
int density_last_passed[6];
int density_last_direction[6];

struct DensityPendingObservation
  {
   datetime observed;
   datetime bar;
   int component;
   double z;
   long serial;
  };
DensityPendingObservation density_pending[];

bool DensityInitializeOwnedPaths();
bool DensityInitialize();
void DensityFault(const string message);
bool DensityAllow(const int component,const double feature);
bool DensityCaptureObservation(const int component,const string stage);
bool DensitySaveCheckpoint();
void DensityRecordEquity(const bool force);
void DensityFlushEquity(const bool close);
void DensityRecordExit(const int component,const ulong deal,const long deal_msc,
                       const double actual,const double stressed);
void DensityFinishEvidence();
void DensityShutdown();

#endif
