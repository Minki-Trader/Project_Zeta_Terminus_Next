"""Install this family's compiled roles and immutable normal Tester settings."""
from pathlib import Path
import json
import shutil
from variance_signal import FAMILY, ROOT, record

RUNTIME = ROOT / "optimization/runtime/v7-onnx-online-variance-standardization-v1-portable"
ROLES = {"control": "ZetaV7VSControl", "static": "ZetaV7VSStatic", "online": "ZetaV7VSOnline"}
RUNS = [("control", "selection-control-static-v1"), ("static", "selection-static-v1"),
        ("control", "selection-control-online-v1"), ("online", "selection-online-v1")]


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))


def main():
    result_path = FAMILY / "evidence/NATIVE_INSTALLATION_V1.json"
    if result_path.exists():
        raise RuntimeError("The native installation already exists.")
    if shutil.disk_usage(ROOT).free - 16 * 2**20 < 30 * 2**30:
        raise RuntimeError("The installed-source reserve is not funded.")
    installed = []
    compiles = []
    for role, namespace in ROLES.items():
        log = FAMILY / f"evidence/compile-{role}-v1.log"
        text = log.read_text(encoding="utf-16")
        if "Result: 0 errors, 0 warnings" not in text:
            raise RuntimeError(f"Incomplete normal compile: {role}")
        compiles.append({"role": role, "log": record(log),
                         "result": [line for line in text.splitlines() if line.startswith("Result:")][-1]})
        for category in ("Experts", "Include"):
            source_root = FAMILY / role / "MQL5" / category / namespace
            for source in sorted(source_root.rglob("*")):
                if source.is_file():
                    target = RUNTIME / "MQL5" / category / namespace / source.relative_to(source_root)
                    if target.exists():
                        raise RuntimeError("Refuse to overwrite an installed role file.")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                    expected, observed = record(source), record(target)
                    if expected["sha256"] != observed["sha256"]:
                        raise RuntimeError("Physical role copy differs.")
                    installed.append(observed)
    settings = []
    for role, tag in RUNS:
        namespace = ROLES[role]
        parent_set = FAMILY / role / "MQL5/Presets" / namespace / "next-v7-return.set"
        value = parent_set.read_text(encoding="utf-8-sig")
        value = "; Exact V7 settings; this family's native Tester role.\n" + "\n".join(
            line for line in value.splitlines() if not line.startswith(";")) + f"\nInpRunTag={tag}\n"
        own_set = FAMILY / "settings" / f"{tag}.set"
        write_new(own_set, value)
        installed_set = RUNTIME / "MQL5/Profiles/Tester" / own_set.name
        write_new(installed_set, value)
        ini = "\n".join([
            "[Common]", "KeepPrivate=1", "[Experts]", "Enabled=0", "AllowLiveTrading=0",
            "AllowDllImport=0", "[Charts]", "MaxBars=2000000", "[Tester]",
            f"Expert={namespace}\\ZetaNextV7ReturnPortfolio.ex5", f"ExpertParameters={own_set.name}",
            "Symbol=US30", "Period=M30", "Model=4", "ExecutionMode=0", "Optimization=0",
            "FromDate=2025.01.01", "ToDate=2026.01.01", "ForwardMode=0", "Deposit=100",
            "Currency=USD", "Leverage=100", "UseLocal=1", "UseRemote=0", "UseCloud=0",
            "Visual=0", "ReplaceReport=1", "ShutdownTerminal=1", f"Report=reports\\{tag}", ""])
        own_ini = FAMILY / "settings" / f"{tag}.ini"
        write_new(own_ini, ini)
        settings.append({"role": role, "tag": tag, "set": record(own_set),
                         "installed_set": record(installed_set), "ini": record(own_ini)})
        installed.append(record(installed_set))
    (RUNTIME / "reports").mkdir(exist_ok=True)
    reader_ini = FAMILY / "settings/selection-history-reader.ini"
    write_new(reader_ini, "[Common]\nKeepPrivate=1\n[Experts]\nEnabled=0\nAllowLiveTrading=0\n"
              "AllowDllImport=0\n[Charts]\nMaxBars=2000000\n[StartUp]\nSymbol=US30\nPeriod=M30\n")
    result = {"status": "OWN_COMPILED_ROLES_AND_ORDERED_FULL_2025_SETTINGS_INSTALLED",
              "normal_compiles": compiles, "installed": installed, "ordered_runs": settings,
              "history_reader_ini": record(reader_ini)}
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "installed_files": len(installed),
                      "compiles": [x["result"] for x in compiles]}))


if __name__ == "__main__":
    main()
