"""Author the campaign's three fresh original-V7-derived native assemblies."""
from pathlib import Path
import json
import re
import shutil
from datetime import datetime, timezone

from fit_density import FAMILY, ROOT, ref, save

BASELINE = ROOT/'optimization/baseline/NEXT-E03-V7R-RLO1-0bba2ca045fe'
PARENT = FAMILY/'parent'
MQL = FAMILY/'mt5/MQL5'
OWN = MQL/'Include/ZetaV7Density'
ROLES = [('CONTROL', 'ZetaV7DensityControl', 2609081201),
         ('STATIC', 'ZetaV7DensityStatic', 2609081301),
         ('ONLINE', 'ZetaV7DensityOnline', 2609081401)]


def emit(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('Original authoring anchor differs: '+old[:80])
    return text.replace(old, new, 1)


def main():
    receipt = FAMILY/'evidence/ONE_TIME_ORIGINAL_PARENT_COPY_V1.json'
    if not receipt.exists():
        if PARENT.exists():
            raise RuntimeError('Unattributed parent already exists')
        shutil.copytree(BASELINE, PARENT)
        rows = []
        for p in sorted(BASELINE.rglob('*')):
            if p.is_file():
                q = PARENT/p.relative_to(BASELINE)
                if ref(p)['sha256'] != ref(q)['sha256']:
                    raise RuntimeError('One-time parent copy mismatch')
                rows.append({'source': ref(p), 'copy': ref(q)})
        save(receipt, {'utc': datetime.now(timezone.utc).isoformat(), 'files': rows})
    else:
        for row in json.loads(receipt.read_bytes())['files']:
            if ref(ROOT/row['copy']['path']) != row['copy']:
                raise RuntimeError('Frozen own parent changed')
    for source in (PARENT/'MQL5/Include/ZetaTerminusNext').rglob('*.mqh'):
        emit(OWN/source.relative_to(PARENT/'MQL5/Include/ZetaTerminusNext'), source.read_text())
    domain_path = OWN/'Domain/ZetaDomain.mqh'
    domain = domain_path.read_text()
    domain = domain.replace('input double InpReferenceCapitalUSD', 'input string InpRunTag = "";\ninput double InpReferenceCapitalUSD', 1)
    domain = domain.replace('"zt-next-v7-rlo1-return-portfolio-v1"', 'DENSITY_EXECUTION')
    domain = domain.replace('"7R1"', 'DENSITY_SCHEMA')
    domain = domain.replace('"NEXT-E03-V7R-RLO1-0bba2ca045fe"', 'DENSITY_RELEASE')
    domain = domain.replace('"ZT-PORT-NEXT-V7R-RLO1-20260907"', 'DENSITY_PORTFOLIO')
    domain = domain.replace('"ZT_NEXT_7R1_STATE_V1"', 'DENSITY_STATE_MARKER')
    domain = domain.replace('"ZT_NEXT_7R1_OBSERVATION_STATE_V1"', 'DENSITY_RESEARCH_MARKER')
    path_rows = re.findall(r'const string (\w+)\s*=\s*"(ZetaTerminusNext\\\\live\\\\v7r-rlo1[^"\n]*)";', domain)
    if len(path_rows) != 12:
        raise RuntimeError('Original owned path count differs')
    for name, original in path_rows:
        domain = re.sub(r'const string '+name+r'\s*=\s*"[^"]+";', 'string '+name+' = "";', domain, count=1)
    for index in range(6):
        domain = domain.replace(str(260907701+index)+';', '(DENSITY_MAGIC_FIRST+'+str(index)+');', 1)
    emit(domain_path, domain)

    fit = json.loads((FAMILY/'models/initial_fit_v1.json').read_bytes())
    initial = '#ifndef ZETA_DENSITY_INITIAL_MQH\n#define ZETA_DENSITY_INITIAL_MQH\n'
    initial += 'const string DENSITY_FIT_SHA = "'+ref(FAMILY/'models/initial_fit_v1.json')['sha256']+'";\n'
    initial += 'const string DENSITY_GRAPH_SHA = "'+ref(FAMILY/'models/input_density_v1.onnx')['sha256']+'";\n'
    # Rows: transform mean/scale, cutoff, mixture weights/means/variances, N/S/Q.
    values = []
    for row in fit['components']:
        values.append([row['mean'], row['scale'], row['cutoff']]+row['weights']+row['means']+row['variances']+
                      row['initial_N']+row['initial_S']+row['initial_Q'])
    initial += 'const double DENSITY_INITIAL[6][15] = {\n'+',\n'.join(
        '   {'+', '.join(format(x, '.17g') for x in row)+'}' for row in values)+'\n};\n#endif\n'
    emit(OWN/'Learning/DensityInitial.mqh', initial)
    resource = MQL/'Files/V7InputDensity/input_density_v1.onnx'
    resource.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FAMILY/'models/input_density_v1.onnx', resource)

    original = (PARENT/'MQL5/Experts/ZetaTerminusNext/ZetaNextV7ReturnPortfolio.mq5').read_text()
    assembly = original.replace('ZetaTerminusNext\\', 'ZetaV7Density\\')
    assembly = assembly.replace('#include <ZetaV7Density\\Domain\\ZetaDomain.mqh>',
        '#include <ZetaV7Density\\Domain\\ZetaDomain.mqh>\n#include <ZetaV7Density\\Learning\\DensityDomain.mqh>')
    assembly = assembly.replace('// The EA owns assembly', '#include <ZetaV7Density\\Learning\\DensityLearning.mqh>\n#include <ZetaV7Density\\Learning\\DensityEvidence.mqh>\n\n// The EA owns assembly')
    start = assembly.index('   FolderCreate("ZetaTerminusNext");')
    end = assembly.index('   if(!AcquireRuntimeOwnership())', start)
    assembly = assembly[:start]+'   if(!DensityInitializeOwnedPaths())\n      return(INIT_FAILED);\n'+assembly[end:]
    assembly = replace_once(assembly, '   if(!InitializeConnectedRuntime())\n      PrintFormat',
        '   if(!DensityInitialize())\n     {\n      ReleaseRuntimeOwnership();\n      return(INIT_FAILED);\n     }\n   if(!InitializeConnectedRuntime())\n      PrintFormat')
    assembly = replace_once(assembly,
        '      if(!tester_clock_dispatch && !transaction_gate &&\n         !tester_retry_dispatch)\n         return;',
        '      if(!tester_clock_dispatch && !transaction_gate &&\n         !tester_retry_dispatch)\n        {\n         DensityRecordEquity(false);\n         return;\n        }')
    assembly = replace_once(assembly,
        '         TesterDataRetryRequired(current_server, us100_m15_bar);\n  }',
        '         TesterDataRetryRequired(current_server, us100_m15_bar);\n   DensityRecordEquity(false);\n  }')
    assembly = replace_once(assembly, 'double OnTester()\n  {', 'double OnTester()\n  {\n   DensityFinishEvidence();')
    assembly = replace_once(assembly, '      (portfolio_state.safety_stopped || persistence_failed ||',
        '      (density_failed || portfolio_state.safety_stopped || persistence_failed ||')
    assembly = replace_once(assembly, 'void OnDeinit(const int reason)\n  {',
        'void OnDeinit(const int reason)\n  {\n   DensityShutdown();')
    for index, (role, name, magic) in enumerate(ROLES):
        prefix = (f'#define DENSITY_ROLE {index}\n#define DENSITY_EA_NAME "{name}"\n'
                  f'#define DENSITY_MAGIC_FIRST {magic}\n#define DENSITY_SCHEMA "DENS1{role}"\n'
                  f'#define DENSITY_EXECUTION "zt-opt-v7-input-density-{role.lower()}-v1"\n'
                  f'#define DENSITY_RELEASE "OPT-V7-INPUT-DENSITY-{role}-V1"\n'
                  f'#define DENSITY_PORTFOLIO "ZT-OPT-V7-INPUT-DENSITY-{role}-20260908"\n'
                  f'#define DENSITY_STATE_MARKER "DENSITY_{role}_CORE_V1"\n'
                  f'#define DENSITY_RESEARCH_MARKER "DENSITY_{role}_RESEARCH_V1"\n'
                  '#resource "\\\\Files\\\\V7InputDensity\\\\input_density_v1.onnx" as uchar DensityOnnxBytes[]\n')
        emit(MQL/'Experts'/(name+'.mq5'), prefix+assembly)
    paths = 'bool DensityInitializeOwnedPaths()\n  {\n   if(!tester_mode || StringLen(InpRunTag)<1 || StringLen(InpRunTag)>48)\n      return(false);\n'
    paths += '   for(int i=0;i<StringLen(InpRunTag);++i)\n     {\n      ushort c=StringGetCharacter(InpRunTag,i);\n      if(!((c>=48 && c<=57)||(c>=65 && c<=90)||(c>=97 && c<=122)||c==45))\n         return(false);\n     }\n'
    paths += '   density_root=DENSITY_EA_NAME+"\\\\"+InpRunTag;\n'
    for name, original in path_rows:
        suffix = original[len('ZetaTerminusNext\\\\live\\\\v7r-rlo1'):]
        paths += '   '+name+'=density_root+"'+suffix+'";\n'
    paths += '   string previous;\n   long finder=FileFindFirst(density_root+"\\\\*",previous);\n   if(finder!=INVALID_HANDLE)\n     {\n      FileFindClose(finder);\n      Print("DENSITY_FRESH_START_REFUSED existing owned namespace");\n      return(false);\n     }\n'
    paths += '   FolderCreate(DENSITY_EA_NAME);\n   FolderCreate(density_root);\n   FolderCreate(density_root+"\\\\state");\n   FolderCreate(density_root+"\\\\research");\n   FolderCreate(density_root+"\\\\learning");\n'
    paths += '   int marker=FileOpen(density_root+"\\\\started.bin",FILE_WRITE|FILE_BIN);\n   if(marker==INVALID_HANDLE) return(false);\n   uint written=FileWriteLong(marker,(long)TimeCurrent());\n   FileFlush(marker);\n   FileClose(marker);\n   return(written==8);\n  }\n'
    emit(OWN/'Learning/DensityPaths.mqh', paths)

    path = OWN/'Execution/ZetaOrders.mqh'
    s = path.read_text()
    s = replace_once(s, '                   const double feature)\n  {\n   MarketEntryPlan plan',
        '                   const double feature)\n  {\n   if(!DensityAllow(component,feature))\n     {\n      if(density_failed) component_states[component].entry_check_result="DENSITY_CORRECTION_REQUIRED";\n      return(false);\n     }\n   MarketEntryPlan plan')
    emit(path, s)
    path = OWN/'Strategies/ZetaPassive.mqh'
    s = path.read_text()
    s = replace_once(s, '                       const datetime expiration)\n  {',
        '                       const datetime expiration)\n  {\n   if(!DensityAllow(US100_PASSIVE_LIMIT,state))\n     {\n      if(density_failed) component_states[US100_PASSIVE_LIMIT].entry_check_result="DENSITY_CORRECTION_REQUIRED";\n      return(false);\n     }')
    emit(path, s)
    path = OWN/'Portfolio/ZetaPortfolioRisk.mqh'
    s = replace_once(path.read_text(), '   return(NewEntriesAuthorized() &&',
                     '   return(!density_failed && NewEntriesAuthorized() &&')
    emit(path, s)
    path = OWN/'Observation/ZetaResearchObservation.mqh'
    s = path.read_text()
    anchor = '      ResearchWarnAndDrop("candidate ledger write returned zero");\n      return(false);\n     }\n   return(true);'
    s = replace_once(s, anchor, '      ResearchWarnAndDrop("candidate ledger write returned zero");\n      return(false);\n     }\n   return(DensityCaptureObservation(component,stage));')
    emit(path, s)
    path = OWN/'Execution/ZetaProtectionAndReconciliation.mqh'
    s = replace_once(path.read_text(), '    SaveState();\n    ResearchHandleExitDeal(research_exit);',
        '    const bool density_exit_core_saved=SaveState();\n    if(density_exit_core_saved && !persistence_failed)\n       DensityRecordExit(component,deal,deal_time_msc,deal_net,stressed_net);\n    else\n       DensityFault("original exit state was not durably saved");\n    ResearchHandleExitDeal(research_exit);')
    emit(path, s)
    print('FRESH_ORIGINAL_ASSEMBLIES_AUTHORED', len(ROLES), flush=True)


if __name__ == '__main__':
    main()
