"""Execute and archive one declared full native economic run in this family."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from variance_signal import FAMILY, ROOT, RAW, record
from prepare_selection import RUNTIME, ROLES

RUNS = [("control", "selection-control-static-v2"), ("static", "selection-static-v2"),
        ("control", "selection-control-online-v2"), ("online", "selection-online-v2")]


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def bytes_under(root):
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) if root.exists() else 0


def json_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as out:
        json.dump(value, out, indent=2)
        out.write("\n")


def hidden_process(command, **kwargs):
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return subprocess.Popen(command, startupinfo=startup, **kwargs)


def runtime_owner_pids():
    # Operating process metadata only; never SDK account or trade context.
    command = "Get-Process terminal64 -ErrorAction SilentlyContinue | Select-Object Id,Path | ConvertTo-Json -Compress"
    p = hidden_process(["powershell.exe", "-NoProfile", "-Command", command], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    rows = json.loads(out) if out.strip() else []
    if isinstance(rows, dict):
        rows = [rows]
    expected = str((RUNTIME / "terminal64.exe").resolve()).casefold()
    return [int(x["Id"]) for x in rows if str(x.get("Path", "")).casefold() == expected]


def current_binding(frozen):
    actual, changed = [], []
    for expected in frozen["files"]:
        path = ROOT / expected["path"]
        observed = record(path) if path.is_file() else {"path": expected["path"], "missing": True}
        actual.append(observed)
        if observed != expected:
            changed.append({"expected": expected, "observed": observed})
    return {"files": actual, "changed": changed}


def require_budget():
    runtime_bytes = bytes_under(RUNTIME)
    raw_bytes = bytes_under(RAW)
    free = shutil.disk_usage(ROOT).free
    remaining = max(0, 4.25 * 2**30 - runtime_bytes) + max(0, 2**30 - raw_bytes)
    if runtime_bytes > 4.25 * 2**30 or raw_bytes > 2**30 or free - remaining < 30 * 2**30:
        raise RuntimeError("Full remaining native/storage allowance is not funded above 30 GiB.")
    return {"runtime_bytes": runtime_bytes, "raw_bytes": raw_bytes,
            "free_bytes": free, "remaining_allowance_bytes": int(remaining)}


def log_paths():
    return sorted(set(list((RUNTIME / "logs").glob("*.log")) +
                      list((RUNTIME / "Tester/logs").glob("*.log")) +
                      list((RUNTIME / "Tester").glob("Agent-*/logs/*.log"))))


def log_slice(path, offset):
    with path.open("rb") as stream:
        prefix = stream.read(2)
        stream.seek(offset)
        raw = stream.read()
    encoding = "utf-16-le" if prefix == b"\xff\xfe" else "utf-8"
    return raw.decode(encoding, errors="replace").lstrip("\ufeff")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {tag for _, tag in RUNS}:
        raise RuntimeError("Specify one of the four prospectively declared selection run tags.")
    tag = sys.argv[1]
    role = next(role for role, value in RUNS if value == tag)
    namespace = ROLES[role]
    archive = RAW / "native" / tag
    start_path = FAMILY / "evidence" / f"{tag}-start.json"
    end_path = FAMILY / "evidence" / f"{tag}-archive.json"
    if archive.exists() or start_path.exists() or end_path.exists():
        raise RuntimeError("A native attempt already exists; preserve it before any explicit correction.")
    if runtime_owner_pids():
        raise RuntimeError("The own runtime already has a terminal owner.")
    frozen_path = FAMILY / "evidence/SELECTION_INPUT_FREEZE_V2.json"
    frozen = json.loads(frozen_path.read_text())
    before = current_binding(frozen)
    if before["changed"]:
        raise RuntimeError("A frozen exercised source/model/setting/input changed before the native run.")
    budget = require_budget()
    offsets = {str(path.relative_to(RUNTIME)): path.stat().st_size for path in log_paths()}
    own_output = f"{namespace}/vs/{tag}"
    if any((p / "MQL5/Files" / own_output).exists() for p in (RUNTIME / "Tester").glob("Agent-*")):
        raise RuntimeError("Own native output is not fresh.")
    command = [str(RUNTIME / "terminal64.exe"), "/portable",
               f'/config:{FAMILY / "settings" / (tag + ".ini")}']
    process = hidden_process(command, cwd=RUNTIME)
    json_new(start_path, {"utc": utc(), "tag": tag, "role": role, "pid": process.pid,
                         "runtime": str(RUNTIME.relative_to(ROOT)), "command": command,
                         "freeze": record(frozen_path), "frozen_file_count": len(before["files"]),
                         "changed_before": [], "storage": budget, "log_offsets": offsets})
    print(json.dumps({"status": "FULL_2025_NATIVE_STARTED", "tag": tag, "pid": process.pid}), flush=True)
    next_notice = time.monotonic() + 60
    while process.poll() is None:
        time.sleep(2)
        if time.monotonic() >= next_notice:
            current = require_budget()
            print(json.dumps({"status": "NATIVE_RUNNING", "tag": tag, "pid": process.pid,
                              "utc": utc(), "storage": current}), flush=True)
            next_notice = time.monotonic() + 60
    if runtime_owner_pids():
        raise RuntimeError("A terminal owner remains after the launched process exited.")
    folders = [p / "MQL5/Files" / own_output for p in (RUNTIME / "Tester").glob("Agent-*")
               if (p / "MQL5/Files" / own_output).exists()]
    if len(folders) != 1:
        raise RuntimeError(f"Native output ownership is incomplete: {len(folders)} roots; attempt start is preserved.")
    reports = sorted((RUNTIME / "reports").glob(tag + ".*"))
    episodes = {"terminal-episode.log": [], "tester-episode.log": [], "agent-episode.log": []}
    for path in log_paths():
        relative = str(path.relative_to(RUNTIME))
        offset = offsets.get(relative, 0)
        if path.stat().st_size < offset:
            raise RuntimeError("An operating log was truncated during this run.")
        if path.stat().st_size == offset:
            continue
        destination = ("agent-episode.log" if "Agent-" in relative else
                       "tester-episode.log" if relative.startswith("Tester") else "terminal-episode.log")
        if path.name == "metaeditor.log":
            continue
        episodes[destination].append(log_slice(path, offset))
    additional = bytes_under(folders[0]) + sum(x.stat().st_size for x in reports) + sum(
        len("\n".join(lines).encode("utf-8")) for lines in episodes.values()) + 2**20
    if bytes_under(RAW) + additional > 2**30 or shutil.disk_usage(ROOT).free - additional < 30 * 2**30:
        raise RuntimeError("Immutable native archive is not funded; preserve own runtime outputs.")
    archive.mkdir(parents=True, exist_ok=False)
    shutil.copytree(folders[0], archive / "Files")
    for path in reports:
        suffix = path.suffix.lower()
        shutil.copyfile(path, archive / ("report.html" if suffix in (".htm", ".html") else "report" + suffix))
    for filename, lines in episodes.items():
        (archive / filename).write_text("\n".join(lines), encoding="utf-8")
    artifacts = [record(path) for path in sorted(archive.rglob("*")) if path.is_file()]
    after = current_binding(frozen)
    result = {"status": "NATIVE_COMPLETE_ARCHIVED_PENDING_FULL_ECONOMIC_HISTORY_BINDING",
              "utc": utc(), "tag": tag, "role": role, "exit_code": process.returncode,
              "artifacts": artifacts, "changed_frozen_files": after["changed"],
              "frozen_file_count": len(after["files"]), "storage": require_budget(),
              "economic_verdict": None, "history_after_observation": None}
    json_new(end_path, result)
    print(json.dumps({"status": result["status"], "tag": tag, "artifacts": len(artifacts),
                      "changed_frozen_files": len(after["changed"])}), flush=True)


if __name__ == "__main__":
    main()
