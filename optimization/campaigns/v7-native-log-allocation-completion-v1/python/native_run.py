"""Own full-period MT5 economic execution and attributable artifact production.

Only the four prospectively declared full-2025 paths are executable here.
No strategy decision, model fitting, external signal, or Live operation is owned
by this producer. Economic interpretation remains with the sole root stream.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

FAMILY = Path(__file__).resolve().parents[1]
ROOT = FAMILY.parents[2]
RUNTIME = ROOT / "optimization/runtime/v7-native-log-allocation-completion-v1-portable"
RAW = ROOT / "optimization/artifacts/raw/v7-native-log-allocation-completion-v1"
EVIDENCE = FAMILY / "evidence"
ROLES = {
    "selection-control-static-v1": "Control",
    "selection-static-v1": "Static",
    "selection-control-online-v1": "Control",
    "selection-online-v1": "Online",
}
FLOOR = 30 * 1024**3
CAPS = {RUNTIME: int(3.5 * 1024**3), RAW: 1024**3, FAMILY: 64 * 1024**2}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def binding(path):
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
            "sha256": sha(path)}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def storage():
    sizes = {str(p.relative_to(ROOT)): sum(x.stat().st_size for x in p.rglob("*") if x.is_file())
             if p.exists() else 0 for p in CAPS}
    remaining = sum(max(0, cap - sizes[str(p.relative_to(ROOT))]) for p, cap in CAPS.items())
    free = shutil.disk_usage(ROOT).free
    return {"utc": utc(), "sizes": sizes, "free_bytes": free,
            "remaining_allowance_bytes": remaining, "funded": free >= FLOOR + remaining,
            "within_caps": all(sizes[str(p.relative_to(ROOT))] <= cap for p, cap in CAPS.items())}


def hidden(command, **kwargs):
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return subprocess.Popen(command, startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW, **kwargs)


def owners():
    command = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match "
               "'^(terminal64|metatester64|MetaEditor64)\\.exe$' } | "
               "Select-Object ProcessId,Name,ExecutablePath | ConvertTo-Json -Compress")
    p = hidden(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(timeout=30)
    if p.returncode:
        raise RuntimeError("Native owner metadata unavailable")
    rows = json.loads(out.decode("utf-8-sig") or "[]")
    return rows if isinstance(rows, list) else [rows]


def own_owners():
    return [v for v in owners() if v.get("ExecutablePath") and
            Path(v["ExecutablePath"]).resolve().is_relative_to(RUNTIME)]


def frozen_changes(freeze):
    changed = []
    for row in freeze["files"]:
        path = ROOT / row["path"]
        if not path.is_file() or path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
            changed.append(row["path"])
    return changed


def freeze_selection():
    target = EVIDENCE / "SELECTION_INPUT_FREEZE_V1.json"
    if target.exists():
        raise RuntimeError("Initial freeze already exists")
    if own_owners():
        raise RuntimeError("Own runtime must be stopped before initial freeze")
    budget = storage()
    if not budget["funded"] or not budget["within_caps"]:
        raise RuntimeError("Whole remaining selection storage is not funded")
    derivation = json.loads((EVIDENCE / "NATIVE_RUNTIME_DERIVATION_V1.json").read_text())
    paths = {ROOT / v["path"] for v in derivation["public_files"]}
    for sub in [FAMILY / "mt5", FAMILY / "models", FAMILY / "config"]:
        paths.update(p for p in sub.rglob("*") if p.is_file())
    for sub in [RUNTIME / "MQL5/Experts", RUNTIME / "MQL5/Profiles/Tester"]:
        paths.update(p for p in sub.rglob("*") if p.is_file())
    paths.update((RUNTIME / "MQL5/Include").glob("ZetaV7LA*/**/*.mqh"))
    paths.add(RUNTIME / "MQL5/Files/ZetaV7LA/allocation.onnx")
    paths.update([EVIDENCE / "DECLARATION_V1.json", EVIDENCE / "SELECTION_BAR_WARMUP_V1.json",
                  EVIDENCE / "SELECTION_PREPARATION_CONTRACTS_V1.json"])
    data = {"utc": utc(), "status": "FULL_ORDERED_2025_NATIVE_INPUTS_FROZEN_BEFORE_OUTCOMES",
            "files": [binding(p) for p in sorted(paths)], "ordered_runs": list(ROLES),
            "budget": budget, "history": "All copied canonical 2024/2025 HCC/HCS and 2025 TKC are frozen. "
            "Complete native past-bar byte hashes are recorded for every required timeframe. "
            "Mutable terminal bar caches are generated from these sources; full returned past bars are "
            "bound again after each completed native run. No 2026 candidate prices are requested.",
            "contracts": "Full symbols binary and three native START/END financing fingerprints must "
            "remain unchanged across the complete matrix; any drift requires a fresh complete matrix.",
            "private_connection_support": "Four own saved connection-support files, no disclosed contents or identifiers.",
            "producer": "The ordinary report producer can be completed during the first control. It never "
            "executes inside the EA; each output binds its producer separately.",
            "live_changes": False, "candidate_2026_values_opened": False}
    save(target, data)
    return {"files": len(data["files"]), "freeze": binding(target), "storage": budget}


def archive(tag, role, offsets, exit_code, freeze):
    target = RAW / "native" / tag
    target.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for path in RUNTIME.rglob("*.log"):
        rel = path.relative_to(RUNTIME).as_posix()
        start = offsets.get(rel, 0)
        with path.open("rb") as stream:
            stream.seek(start)
            content = stream.read()
        if content:
            out = target / "logs" / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(content)
            artifacts.append(binding(out))
    for path in (RUNTIME / "reports").glob(tag + "*"):
        if path.is_file():
            out = target / "reports" / path.name
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, out)
            artifacts.append(binding(out))
    for files in RUNTIME.glob("Tester/Agent-*/MQL5/Files"):
        source = files / ("ZetaV7LA" + role) / tag
        for path in source.rglob("*"):
            if path.is_file():
                out = target / "files" / path.relative_to(source)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, out)
                artifacts.append(binding(out))
    result = {"utc": utc(), "status": "COMPLETE_NATIVE_EPISODE_ARCHIVED_PENDING_ECONOMIC_INTERPRETATION",
              "tag": tag, "role": role, "exit_code": exit_code,
              "artifacts": artifacts, "changed_frozen_files": frozen_changes(freeze),
              "storage": storage(), "producer": binding(Path(__file__).resolve()),
              "economic_verdict": None, "history_after_observation": None}
    save(EVIDENCE / (tag + "-archive.json"), result)
    return result


def run(tag):
    role = ROLES[tag]
    if own_owners():
        raise RuntimeError("Own native process already running")
    start_file = EVIDENCE / (tag + "-start.json")
    if start_file.exists() or (RAW / "native" / tag).exists():
        raise RuntimeError("Fresh path tag is required; previous attempts remain immutable")
    order = list(ROLES)
    for previous in order[:order.index(tag)]:
        if not (EVIDENCE / (previous + "-archive.json")).is_file():
            raise RuntimeError("The prospectively fixed serial order must be completed")
    freeze_file = EVIDENCE / "SELECTION_INPUT_FREEZE_V1.json"
    freeze = json.loads(freeze_file.read_text())
    changed = frozen_changes(freeze)
    if changed:
        raise RuntimeError("Frozen native inputs changed: " + repr(changed))
    budget = storage()
    if not budget["funded"] or not budget["within_caps"]:
        raise RuntimeError("Whole remaining native selection growth is not funded")
    offsets = {p.relative_to(RUNTIME).as_posix(): p.stat().st_size for p in RUNTIME.rglob("*.log")}
    command = [str(RUNTIME / "terminal64.exe"), "/portable", "/config:" + str(FAMILY / "config" / (tag + ".ini"))]
    process = hidden(command, cwd=RUNTIME, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    save(start_file, {"utc": utc(), "tag": tag, "role": role, "pid": process.pid,
                      "runtime": RUNTIME.relative_to(ROOT).as_posix(), "command": command,
                      "freeze": binding(freeze_file), "changed_before": changed,
                      "storage": budget, "log_offsets": offsets,
                      "producer": binding(Path(__file__).resolve())})
    print(json.dumps({"event": "FULL_NATIVE_STARTED", "tag": tag, "pid": process.pid,
                      "free_bytes": budget["free_bytes"]}), flush=True)
    started = time.monotonic()
    with (EVIDENCE / (tag + "-storage.jsonl")).open("x", encoding="utf-8") as ledger:
        while process.poll() is None:
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
            budget = storage()
            ledger.write(json.dumps(budget) + "\n")
            ledger.flush()
            print(json.dumps({"event": "NATIVE_RUNNING", "tag": tag,
                              "elapsed_seconds": round(time.monotonic() - started),
                              "free_bytes": budget["free_bytes"]}), flush=True)
            if budget["free_bytes"] < FLOOR or not budget["within_caps"]:
                # This is a storage correction, never an adverse economic result.
                process.terminate()
                process.wait(timeout=30)
                save(EVIDENCE / (tag + "-storage-correction.json"), budget)
                break
    time.sleep(1)
    result = archive(tag, role, offsets, process.returncode, freeze)
    print(json.dumps({"event": "NATIVE_ARCHIVED", "tag": tag, "exit_code": process.returncode,
                      "artifacts": len(result["artifacts"]), "changed_inputs": result["changed_frozen_files"],
                      "free_bytes": result["storage"]["free_bytes"]}), flush=True)


if __name__ == "__main__":
    run(sys.argv[1])
