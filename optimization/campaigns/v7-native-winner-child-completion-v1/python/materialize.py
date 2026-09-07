"""Materialize the four declared native assemblies from the one owned parent copy."""
from pathlib import Path
import hashlib
import json
import re
import shutil

FAMILY = Path(__file__).resolve().parents[1]
DECL = json.loads((FAMILY / 'evidence/DECLARATION_V1.json').read_bytes())
STATE = json.loads((FAMILY / 'models/initial-state.json').read_bytes())
MQL = FAMILY / 'mt5/MQL5'


def replace_function(source, name, body):
    start = source.index('void ' + name + '(')
    left = source.index('{', start)
    depth = 1
    end = left + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[:left] + '{\n' + body + '\n  }' + source[end:]


def main():
    records = []
    for role in DECL['roles']:
        inc = role['include']
        name = role['ea']
        target = MQL / 'Include' / inc
        for p in sorted((FAMILY / 'parent/MQL5/Include/ZetaTerminusNext').rglob('*.mqh')):
            s = p.read_text(encoding='utf-8-sig')
            s = s.replace('ZetaTerminusNext\\', inc + '\\')
            s = s.replace('zt-next-v7-rlo1-return-portfolio-v1', 'zt-opt-v7-wc-' + role['role'].lower() + '-v1')
            s = s.replace('ZT-PORT-NEXT-V7R-RLO1-20260907', role['portfolio'])
            s = s.replace('"7R1"', '"' + role['schema'] + '"')
            s = s.replace('ZT_NEXT_7R1_', 'ZT_WC_' + role['role'].upper() + '_')
            s = s.replace('NEXT-E03-V7R-RLO1-0bba2ca045fe', 'OPT-V7-WC-' + role['role'].upper() + '-V1')
            for j in range(6):
                s = s.replace(str(260907701 + j), str(role['magic_first'] + j))
            if p.name == 'ZetaDomain.mqh':
                s = s.replace('input double InpReferenceCapitalUSD', 'input string InpRunTag = "unset";\ninput double InpReferenceCapitalUSD')
                # Paths are assigned before the inherited OnInit executes.
                s = re.sub(r'const string ((?:STATE_PATH|EVENT_PATH|CURRENT_SNAPSHOT_PATH|RESEARCH_OBSERVATION_STATE_PATH)_[AB]|OWNERSHIP_PATH|RESEARCH_OBSERVATION_DIRECTORY|RESEARCH_CANDIDATE_LEDGER_PATH|RESEARCH_LIFECYCLE_LEDGER_PATH)\s*=\s*"[^"]*";', r'string \1 = "";', s)
                s = s.replace('#endif', '\n#define WC_ROLE ' + str(role['role_number']) + '\nconst ulong WC_MAGIC_FIRST=' + str(role['child_magic_first']) + ';\n'
                    'double WCReservedRisk();\nbool WCIsMagic(const ulong magic);\nbool WCAuditSelectedChild();\nbool WCAuditSelectedOrder();\n'
                    'void WCParentExit(const ResearchExitSnapshot &snapshot);\n#endif')
            elif p.name == 'ZetaPortfolioRisk.mqh':
                s = s.replace('double risk = MathMax(0.0, passive_pending_planned_risk_usd);', 'double risk = MathMax(0.0, passive_pending_planned_risk_usd) + WCReservedRisk();')
            elif p.name == 'ZetaOwnership.mqh':
                needle = '      bool matched = false;'
                s = s.replace(needle, '      if(WCIsMagic(magic))\n        {\n         if(!WCAuditSelectedChild()) return(false);\n         continue;\n        }\n' + needle, 1)
                needle = '      int stop_loss_component = -1;'
                s = s.replace(needle, '      if(WCIsMagic(magic))\n        {\n         if(!WCAuditSelectedOrder()) return(false);\n         continue;\n        }\n' + needle, 1)
            elif p.name == 'ZetaProtectionAndReconciliation.mqh':
                s = s.replace('    ResearchHandleExitDeal(research_exit);', '    ResearchHandleExitDeal(research_exit);\n    WCParentExit(research_exit);')
            elif p.name == 'ZetaStateAndEvents.mqh':
                s = replace_function(s, 'ResetTesterArtifacts', '   // Fresh native tags are required; previous evidence is never deleted.')
            out = target / p.relative_to(FAMILY / 'parent/MQL5/Include/ZetaTerminusNext')
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(s, encoding='utf-8', newline='\r\n')
        initial = ['// Exact approved 2024 initial fit; no refit or outcome-derived state.', 'double wc_mean[8]={' + ','.join(format(x, '.17g') for x in STATE['mean']) + '};',
                   'double wc_sd[8]={' + ','.join(format(x, '.17g') for x in STATE['sd']) + '};',
                   'double wc_initial_weights[17]={' + ','.join(format(x, '.17g') for x in STATE['weights']) + '};',
                   'double wc_initial_P[289]={' + ','.join(format(x, '.17g') for row in STATE['P'] for x in row) + '};']
        (target / 'WinnerChild').mkdir(exist_ok=True)
        (target / 'WinnerChild/InitialFit.mqh').write_text('\n'.join(initial) + '\n', encoding='utf-8', newline='\r\n')
        template = (FAMILY / 'native/WinnerChild.mqh').read_text(encoding='utf-8')
        (target / 'WinnerChild/WinnerChild.mqh').write_text(template.replace('@INCLUDE@', inc), encoding='utf-8', newline='\r\n')
        resource = MQL / 'Files' / inc / 'winner-child-kernel.onnx'
        resource.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FAMILY / 'models/winner-child-kernel.onnx', resource)
        p = FAMILY / 'parent/MQL5/Experts/ZetaTerminusNext/ZetaNextV7ReturnPortfolio.mq5'
        s = p.read_text(encoding='utf-8-sig').replace('ZetaTerminusNext\\', inc + '\\')
        s = s.replace('// The EA owns assembly', '#include <' + inc + '\\WinnerChild\\WinnerChild.mqh>\n\n// The EA owns assembly')
        s = s.replace('int OnInit()', 'int V7CoreOnInit()').replace('void OnTick()', 'void V7CoreOnTick()')
        start = s.index('   FolderCreate("ZetaTerminusNext");')
        end = s.index('   if(tester_mode)\n      ResetTesterArtifacts();', start)
        s = s[:start] + s[end:]
        s = s.replace('   PrintFormat("V7RR1_NATIVE', '   WCFinish();\n   PrintFormat("V7RR1_NATIVE', 1)
        s = s.replace('   ReleaseRuntimeOwnership();\n  }', '   WCShutdown();\n   ReleaseRuntimeOwnership();\n  }')
        s += '\nint OnInit()\n  {\n   if(!MQLInfoInteger(MQL_TESTER) || !WCInitialize()) return(INIT_FAILED);\n   return(V7CoreOnInit());\n  }\n\nvoid OnTick()\n  {\n   if(execution_state.runtime_ready) WCBeforeTick();\n   V7CoreOnTick();\n   if(execution_state.runtime_ready) WCAfterTick();\n  }\n'
        out = MQL / 'Experts' / (name + '.mq5')
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(s, encoding='utf-8', newline='\r\n')
        preset = (FAMILY / 'parent/MQL5/Presets/ZetaTerminusNext/next-v7-return.set').read_text(encoding='utf-8-sig')
        preset += '\nInpRunTag=unset\n'
        (MQL / 'Presets').mkdir(exist_ok=True)
        (MQL / 'Presets' / (name + '.set')).write_text(preset, encoding='utf-8', newline='\r\n')
    for p in sorted(MQL.rglob('*')):
        if p.is_file() and (p.suffix in ('.mq5', '.mqh', '.set', '.onnx')):
            records.append({'path':p.relative_to(FAMILY).as_posix(), 'bytes':p.stat().st_size, 'sha256':hashlib.sha256(p.read_bytes()).hexdigest().upper()})
    (FAMILY / 'evidence/MATERIALIZED_SOURCE_CURRENT.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    print('Materialized', len(records), 'owned source/resource files.')


if __name__ == '__main__':
    main()
