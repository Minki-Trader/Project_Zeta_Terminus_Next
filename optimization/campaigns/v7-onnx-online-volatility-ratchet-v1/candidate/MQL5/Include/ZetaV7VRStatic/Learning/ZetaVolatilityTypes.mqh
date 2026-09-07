#ifndef ZETA_VOLATILITY_RATCHET_TYPES_MQH
#define ZETA_VOLATILITY_RATCHET_TYPES_MQH

// Owned by this tester-only candidate; no prior release state is adopted.
struct VRPositionState
  {
   ulong identifier;
   double entry_price;
   double initial_stop;
   double directional_peak;
   double expected_stop;
   double pending_stop;
   datetime last_bar;
  };
VRPositionState vr_positions[COMPONENT_COUNT];
long vr_forecasts = 0;
long vr_missing_prefixes = 0;
long vr_decisions = 0;
long vr_modify_intents = 0;
long vr_modify_adoptions = 0;
long vr_modify_refusals = 0;
long vr_errors = 0;
const string VR_MODEL_SHA = "84E8EB68B81059286DC5F3C3328693CFD52C9F4BA6DE178D01C0C0519AB624C8";

void ClearVRPosition(const int component)
  {
   ZeroMemory(vr_positions[component]);
  }

void ResetVRCounters()
  {
   vr_forecasts = 0;
   vr_missing_prefixes = 0;
   vr_decisions = 0;
   vr_modify_intents = 0;
   vr_modify_adoptions = 0;
   vr_modify_refusals = 0;
   vr_errors = 0;
  }

bool VRHasPending()
  {
   for(int i = 0; i < COMPONENT_COUNT; ++i)
      if(vr_positions[i].pending_stop > 0.0) return(true);
   return(false);
  }

bool VRProfitStopMatches(const int component, const int direction,
                         const double entry, const double volume,
                         const double broker_stop, const double tick_size)
  {
   if(component < 0 || component >= COMPONENT_COUNT || MathAbs(direction) != 1 ||
      !MathIsValidNumber(entry) || !MathIsValidNumber(volume) ||
      !MathIsValidNumber(broker_stop) || entry <= 0.0 || volume <= 0.0 ||
      broker_stop <= 0.0 || tick_size <= 0.0 ||
      component_states[component].entry_planned_risk_usd <= 0.0)
      return(false);
   const ulong identifier = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   const double tolerance = 0.5 * tick_size + 1.0e-9;
   if(identifier == 0 || identifier != vr_positions[component].identifier ||
      identifier != component_states[component].position_identifier ||
      direction != component_states[component].entry_direction ||
      MathAbs(entry - vr_positions[component].entry_price) > tolerance ||
      (double)direction * (entry - vr_positions[component].initial_stop) <= 0.0 ||
      (double)direction * (broker_stop - entry) <= component_states[component].entry_spread_price)
      return(false);
   const bool saved = (vr_positions[component].expected_stop > 0.0 &&
      MathAbs(broker_stop - vr_positions[component].expected_stop) <= tolerance &&
      MathAbs(broker_stop - component_states[component].entry_stop_loss) <= tolerance);
   const bool pending = (vr_positions[component].pending_stop > 0.0 &&
      MathAbs(broker_stop - vr_positions[component].pending_stop) <= tolerance &&
      (double)direction * (vr_positions[component].pending_stop -
                          vr_positions[component].expected_stop) >= tick_size - 1.0e-8);
   // Original admission risk is still reserved by the core. This branch grants
   // no risk credit and recognizes only the ticket-bound saved/pending SL.
   return(saved || pending);
  }

void WriteVRState(const int handle)
  {
   FileWrite(handle, "V7_VR_STATIC_STATE_V1", VR_MODEL_SHA, vr_forecasts,
      vr_missing_prefixes, vr_decisions, vr_modify_intents,
      vr_modify_adoptions, vr_modify_refusals, vr_errors);
   for(int i = 0; i < COMPONENT_COUNT; ++i)
      FileWrite(handle, i, (long)vr_positions[i].identifier,
         vr_positions[i].entry_price, vr_positions[i].initial_stop,
         vr_positions[i].directional_peak, vr_positions[i].expected_stop,
         vr_positions[i].pending_stop, (long)vr_positions[i].last_bar);
  }

bool ReadVRState(const int handle)
  {
   const string marker = FileReadString(handle);
   const string model_sha = FileReadString(handle);
   vr_forecasts = (long)FileReadNumber(handle);
   vr_missing_prefixes = (long)FileReadNumber(handle);
   vr_decisions = (long)FileReadNumber(handle);
   vr_modify_intents = (long)FileReadNumber(handle);
   vr_modify_adoptions = (long)FileReadNumber(handle);
   vr_modify_refusals = (long)FileReadNumber(handle);
   vr_errors = (long)FileReadNumber(handle);
   bool valid = (marker == "V7_VR_STATIC_STATE_V1" && model_sha == VR_MODEL_SHA &&
      vr_forecasts >= 0 && vr_missing_prefixes >= 0 && vr_decisions >= 0 &&
      vr_modify_intents >= 0 && vr_modify_adoptions >= 0 &&
      vr_modify_refusals >= 0 && vr_errors >= 0);
   for(int i = 0; i < COMPONENT_COUNT; ++i)
     {
      const int ordinal = (int)FileReadNumber(handle);
      vr_positions[i].identifier = (ulong)((long)FileReadNumber(handle));
      vr_positions[i].entry_price = FileReadNumber(handle);
      vr_positions[i].initial_stop = FileReadNumber(handle);
      vr_positions[i].directional_peak = FileReadNumber(handle);
      vr_positions[i].expected_stop = FileReadNumber(handle);
      vr_positions[i].pending_stop = FileReadNumber(handle);
      vr_positions[i].last_bar = (datetime)((long)FileReadNumber(handle));
      if(ordinal != i || !MathIsValidNumber(vr_positions[i].entry_price) ||
         !MathIsValidNumber(vr_positions[i].initial_stop) ||
         !MathIsValidNumber(vr_positions[i].directional_peak) ||
         !MathIsValidNumber(vr_positions[i].expected_stop) ||
         !MathIsValidNumber(vr_positions[i].pending_stop) ||
         vr_positions[i].last_bar < 0 || vr_positions[i].pending_stop < 0.0)
         valid = false;
      if(vr_positions[i].identifier > 0 &&
         (vr_positions[i].identifier != component_states[i].position_identifier ||
          vr_positions[i].entry_price <= 0.0 || vr_positions[i].initial_stop <= 0.0 ||
          vr_positions[i].expected_stop <= 0.0 ||
          (double)component_states[i].entry_direction *
          (vr_positions[i].entry_price - vr_positions[i].initial_stop) <= 0.0))
         valid = false;
      if(vr_positions[i].identifier == 0 &&
         (vr_positions[i].entry_price != 0.0 || vr_positions[i].initial_stop != 0.0 ||
          vr_positions[i].directional_peak != 0.0 || vr_positions[i].expected_stop != 0.0 ||
          vr_positions[i].pending_stop != 0.0 || vr_positions[i].last_bar != 0))
         valid = false;
     }
   return(valid);
  }

bool InitializeVRModel();
void ProcessVolatilityRatchet();
bool ResolveVRPending();
void CloseVRModel();

#endif
