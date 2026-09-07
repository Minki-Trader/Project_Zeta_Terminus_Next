"""Produce the three physically independent, tester-only V7 native sources."""
from pathlib import Path
import json
import re
import shutil
from variance_signal import FAMILY, ROOT, digest, record


def write_native(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))


def main():
    authoring = FAMILY / "source"
    for name in ("ZetaVSForecast.mqh", "ZetaVSAccountPath.mqh"):
        if not (authoring / name).is_file():
            raise RuntimeError(f"Required own source is incomplete: {name}")
    if (FAMILY / "evidence/NATIVE_SOURCE_DERIVATION_V1.json").exists():
        raise RuntimeError("The one-time native derivation already exists.")
    if shutil.disk_usage(ROOT).free - 52 * 2**20 < 30 * 2**30:
        raise RuntimeError("Own source reserve is not funded.")
    frozen = json.loads((FAMILY / "evidence/MODEL_FREEZE_V1.json").read_text())
    for item in frozen["source_model"]:
        if digest(ROOT / item["path"]) != item["sha256"]:
            raise RuntimeError("The fixed forecast model or producer changed.")
    model = json.loads((FAMILY / "model/initial.json").read_text())
    kinds = ("cross", "return", "passive")
    model_header = "#ifndef ZETA_VS_MODEL_MQH\n#define ZETA_VS_MODEL_MQH\n"
    for key, name, width in (("mean", "VS_MEAN", 7), ("sd", "VS_SD", 7),
                             ("weights", "VS_INITIAL_WEIGHTS", 8)):
        rows = ["{" + ",".join(format(x, ".17g") for x in model[k][key]) + "}" for k in kinds]
        model_header += f"const double {name}[3][{width}]={{" + ",\n".join(rows) + "};\n"
    model_header += "const uchar VS_MODEL_BYTES[]={" + ",".join(str(x) for x in (FAMILY / "model/variance.onnx").read_bytes()) + "};\n#endif\n"
    write_native(authoring / "ZetaVSModel.mqh", model_header)
    neutral = ROOT / "optimization/runtime/v7-unit-reinvestment-v1-portable/MQL5/Include"
    standard = [p for p in neutral.rglob("*") if p.is_file() and
                not p.relative_to(neutral).parts[0].startswith("Zeta")]
    if len(standard) != 262:
        raise RuntimeError("Unexpected physical neutral Include inventory.")
    roles = {"control": (0, "ZetaV7VSControl", "C", 260901940),
             "static": (1, "ZetaV7VSStatic", "S", 260901950),
             "online": (2, "ZetaV7VSOnline", "O", 260901960)}
    results = {}
    for role, (mode, namespace, suffix, magic_base) in roles.items():
        role_root = FAMILY / role / "MQL5"
        if role_root.exists():
            raise RuntimeError("Refuse to overwrite an existing native role.")
        for source in (FAMILY / "parent/MQL5").rglob("*"):
            if not source.is_file() or source.suffix.lower() not in (".mq5", ".mqh", ".set"):
                continue
            target = role_root / str(source.relative_to(FAMILY / "parent/MQL5")).replace("ZetaTerminusNext", namespace)
            text = source.read_text(encoding="utf-8-sig").replace("ZetaTerminusNext", namespace)
            text = text.replace("zt-next-v7-rlo1-return-portfolio-v1", f"zt-v7-vs-{role}-v1")
            text = text.replace("NEXT-E03-V7R-RLO1-0bba2ca045fe", f"OPT-V7-VS-{role.upper()}-20260907")
            text = text.replace("ZT-PORT-NEXT-V7R-RLO1-20260907", f"ZT-OPT-V7-VS-{role.upper()}-20260907")
            text = text.replace('"7R1"', f'"7VS1{suffix}"').replace("ZT_NEXT_7R1", f"ZT_NEXT_7VS1{suffix}")
            for j in range(1, 7):
                text = text.replace(str(260907700 + j), str(magic_base + j))
            if source.name == "ZetaDomain.mqh":
                tag = "selection-control-static-v1" if role == "control" else f"selection-{role}-v1"
                additions = (f'input string InpRunTag="{tag}";\nconst int VS_MODE={mode};\n'
                             f'const string VS_ROOT="{namespace}\\\\vs\\\\"+InpRunTag;\n'
                             'bool VSEntryFeature(const int kind,double &feature);\n'
                             'void VSRecordPositiveClosedSwap(const double swap);\n')
                text = text.replace("input double InpReferenceCapitalUSD", additions + "\ninput double InpReferenceCapitalUSD", 1)
                prefix = re.escape(namespace + r"\\live\\v7r-rlo1")
                text = re.sub('"' + prefix + r'([^"\n]*)"', lambda m: 'VS_ROOT+"' + m.group(1) + '"', text)
                text = text.replace('const string RESEARCH_OBSERVATION_SCHEMA =\n   "zeta-next-v7r-rlo1-observation-v1";',
                                    f'const string RESEARCH_OBSERVATION_SCHEMA =\n   "zeta-v7-vs-{role}-observation-v1";')
                if mode:
                    text = text.replace('"ref100-base0.01-step150', '"vs-ex-ante-entry-sd-ref100-base0.01-step150', 1)
            if source.name in ("ZetaCross.mqh", "ZetaReturn.mqh", "ZetaPassive.mqh"):
                kind, component, variable = {"ZetaCross.mqh": (0, "US100_CROSS", "feature"),
                    "ZetaReturn.mqh": (1, "US30_RETURN_REV_LONG", "feature"),
                    "ZetaPassive.mqh": (2, "US100_PASSIVE_LIMIT", "state")}[source.name]
                marker = "   const bool signal_passed ="
                if text.count(marker) != 1:
                    raise RuntimeError("Entry integration boundary is ambiguous.")
                block = (f'   if(!VSEntryFeature({kind},{variable}))\n     {{\n'
                         f'      component_states[{component}].entry_check_result="DATA_UNAVAILABLE";\n'
                         '      return;\n     }\n')
                text = text.replace(marker, block + marker, 1)
            if source.name == "ZetaProtectionAndReconciliation.mqh":
                marker = "   portfolio_state.project_realized_net += deal_net;"
                if text.count(marker) != 1:
                    raise RuntimeError("Accepted exit-deal accounting hook is ambiguous.")
                text = text.replace(marker, "   VSRecordPositiveClosedSwap(HistoryDealGetDouble(deal,DEAL_SWAP));\n" + marker, 1)
            if source.suffix.lower() == ".mq5":
                marker = "// The EA owns assembly and the inherited event ordering only."
                extra = (f'#include <{namespace}\\Observation\\ZetaVSForecast.mqh>\n'
                         f'#include <{namespace}\\Observation\\ZetaVSAccountPath.mqh>\n'
                         'bool vs_finished=false;\n'
                         'void VSFinish() { if(!vs_finished) { VSAccountEnd(); VSForecastEnd(); vs_finished=true; } }\n')
                text = text.replace(marker, extra + "\n" + marker, 1)
                text = text.replace("int OnInit()\n  {", "int OnInit()\n  {\n   if(!MQLInfoInteger(MQL_TESTER)) return(INIT_FAILED);\n"
                    "   if(StringLen(InpRunTag)<1 || StringLen(InpRunTag)>48) return(INIT_PARAMETERS_INCORRECT);\n"
                    "   for(int n=0;n<StringLen(InpRunTag);++n) { const ushort c=StringGetCharacter(InpRunTag,n);\n"
                    "      if(!((c>='a' && c<='z') || (c>='0' && c<='9') || c=='-')) return(INIT_PARAMETERS_INCORRECT); }\n"
                    "   if(FileIsExist(STATE_PATH_A) || FileIsExist(STATE_PATH_B) || FileIsExist(RESEARCH_CANDIDATE_LEDGER_PATH) ||\n"
                    "      FileIsExist(RESEARCH_LIFECYCLE_LEDGER_PATH) || FileIsExist(VS_ROOT+\"\\\\equity.csv\") ||\n"
                    "      FileIsExist(VS_ROOT+\"\\\\forecasts.csv\")) return(INIT_FAILED);", 1)
                start = text.index(f'   FolderCreate("{namespace}");')
                end = text.index("   if(!AcquireRuntimeOwnership())", start)
                text = text[:start] + (f'   FolderCreate("{namespace}");\n'
                        f'   FolderCreate("{namespace}\\\\vs");\n'
                        '   FolderCreate(VS_ROOT); FolderCreate(VS_ROOT+"\\\\state"); FolderCreate(VS_ROOT+"\\\\research");\n') + text[end:]
                marker = "   return(INIT_SUCCEEDED);"
                text = text.replace(marker, '   if(!execution_state.runtime_ready || !VSAccountInit(VS_ROOT) || !VSForecastInit(VS_ROOT))\n'
                    '     { ReleaseRuntimeOwnership(); return(INIT_FAILED); }\n' + marker, 1)
                text = text.replace("void OnTick()\n", "void VSOriginalOnTick()\n", 1)
                text = text.replace("double OnTester()\n  {", "double OnTester()\n  {\n   VSFinish();", 1)
                text = text.replace("void OnDeinit(const int reason)\n  {", "void OnDeinit(const int reason)\n  {\n   VSFinish();", 1)
                text += "\nvoid OnTick()\n  {\n   VSRefresh();\n   VSOriginalOnTick();\n   VSAccountObserve(false);\n  }\n"
            write_native(target, text)
        include = role_root / "Include"
        for source in standard:
            target = include / source.relative_to(neutral)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if digest(source) != digest(target):
                raise RuntimeError("Neutral standard Include copy changed bytes.")
        for name in ("ZetaVSForecast.mqh", "ZetaVSAccountPath.mqh", "ZetaVSModel.mqh"):
            target = include / namespace / "Observation" / name
            shutil.copy2(authoring / name, target)
        results[role] = {"namespace": namespace, "mode": mode,
            "magic": [magic_base + 1, magic_base + 6], "standard_include_files": len(standard),
            "files": [record(p) for p in sorted(role_root.rglob("*")) if p.is_file()]}
    evidence = {"status": "THREE_FRESH_PHYSICAL_TESTER_ONLY_ROLES_DERIVED_BEFORE_COMPILE",
                "fixed_model": record(FAMILY / "model/initial.json"),
                "onnx": record(FAMILY / "model/variance.onnx"),
                "authoring_sources": [record(p) for p in sorted(authoring.iterdir())],
                "roles": results, "closed_candidate_source_imported": False,
                "live_changes": False}
    (FAMILY / "evidence/NATIVE_SOURCE_DERIVATION_V1.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": evidence["status"], "roles": list(roles),
                      "source_bytes": sum(p.stat().st_size for p in FAMILY.rglob("*") if p.is_file())}))


if __name__ == "__main__":
    main()
