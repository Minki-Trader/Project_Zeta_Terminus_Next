"""Acquire immutable native M1 history from this family's bound MT5 runtime."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys

import numpy as np

from variance_signal import FAMILY, RAW, ROOT, digest, record


RUNTIME = ROOT / "optimization/runtime/v7-onnx-online-variance-standardization-v1-portable"
TERMINAL = RUNTIME / "terminal64.exe"
NATIVE_HISTORY = RAW / "native-history"
HISTORY_OBSERVATIONS = RAW / "history-observations"
START_EPOCH = 1704067200
END_EPOCH = 1767225599
SYMBOLS = ("US30", "US100", "US500")
MINIMUM_FREE_BYTES = 30 * 1024**3
MAXIMUM_RAW_BYTES = 1024**3
TAG_PATTERN = re.compile(r"selection-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
PRICE_FIELDS = ("open", "high", "low", "close")


def fail(message: str) -> None:
    raise RuntimeError(message)


def parse_tag(argv: list[str]) -> str:
    if len(argv) != 2:
        fail("usage: acquire_native_history.py selection-<tag>")
    tag = argv[1]
    if len(tag) > 64 or TAG_PATTERN.fullmatch(tag) is None:
        fail("observation tag must be selection-* using lowercase letters, digits, and hyphens")
    return tag


def parse_reader_pid() -> int:
    value = os.environ.get("V7_VS_READER_PID", "").strip()
    if re.fullmatch(r"[0-9]+", value) is None:
        fail("V7_VS_READER_PID is required and must be a numeric PID")
    pid = int(value)
    if pid <= 0 or pid > 0xFFFFFFFF:
        fail("V7_VS_READER_PID is outside the Windows PID range")
    return pid


def canonical(path: Path, *, file_expected: bool | None = None) -> Path:
    resolved = path.resolve(strict=True)
    if file_expected is True and not resolved.is_file():
        fail(f"expected file is unavailable: {path}")
    if file_expected is False and not resolved.is_dir():
        fail(f"expected directory is unavailable: {path}")
    return resolved


def same_windows_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


def running_executable(pid: int) -> Path:
    process_query_limited_information = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        fail("V7_VS_READER_PID is not an accessible running process")
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            fail("could not read the V7_VS_READER_PID executable path")
        return canonical(Path(buffer.value), file_expected=True)
    finally:
        kernel32.CloseHandle(handle)


def bind_reader_process(pid: int) -> Path:
    expected = canonical(TERMINAL, file_expected=True)
    actual = running_executable(pid)
    if not same_windows_path(actual, expected):
        fail("V7_VS_READER_PID does not execute this family's terminal64.exe")
    return expected


def terminal_root(value: str) -> Path:
    path = canonical(Path(value))
    if path.is_file() and path.name.casefold() == "terminal64.exe":
        return path.parent
    if not path.is_dir():
        fail("terminal_info runtime path is not a directory")
    return path


def bind_terminal_info(info: object) -> dict[str, object]:
    expected_root = canonical(RUNTIME, file_expected=False)
    path_value = str(getattr(info, "path"))
    data_path_value = str(getattr(info, "data_path"))
    build = int(getattr(info, "build"))
    if not same_windows_path(terminal_root(path_value), expected_root):
        fail("terminal_info.path is outside this family's physical runtime")
    if not same_windows_path(canonical(Path(data_path_value), file_expected=False), expected_root):
        fail("terminal_info.data_path is outside this family's physical runtime")
    if build <= 0:
        fail("terminal_info.build is invalid")
    return {"path": path_value, "data_path": data_path_value, "build": build}


def raw_total_bytes() -> int:
    if not RAW.exists():
        return 0
    return sum(path.stat().st_size for path in RAW.rglob("*") if path.is_file())


def require_storage_budget(additional_bytes: int = 0) -> tuple[int, int]:
    current_raw = raw_total_bytes()
    if current_raw > MAXIMUM_RAW_BYTES:
        fail("family RAW already exceeds the 1 GiB bound")
    if current_raw + additional_bytes > MAXIMUM_RAW_BYTES:
        fail("planned immutable output would exceed the 1 GiB RAW bound")
    free = shutil.disk_usage(ROOT).free
    if free < MINIMUM_FREE_BYTES or free - additional_bytes < MINIMUM_FREE_BYTES:
        fail("at least 30 GiB must remain free after the planned write")
    return current_raw, free


def validate_rates(symbol: str, rates: np.ndarray) -> None:
    if not isinstance(rates, np.ndarray) or rates.ndim != 1 or len(rates) == 0:
        fail(f"{symbol} returned no normal M1 input")
    fields = rates.dtype.names
    if fields is None or "time" not in fields or any(name not in fields for name in PRICE_FIELDS):
        fail(f"{symbol} returned an unexpected native rate schema")
    times = np.asarray(rates["time"], dtype=np.int64)
    if np.any(times < START_EPOCH) or np.any(times > END_EPOCH):
        fail(f"{symbol} timestamps are outside the requested native epoch bound")
    if len(times) > 1 and np.any(np.diff(times) <= 0):
        fail(f"{symbol} timestamps are not strictly monotone")
    for field in PRICE_FIELDS:
        if not np.isfinite(rates[field]).all():
            fail(f"{symbol} contains a nonfinite {field} value")


def npy_payload(rates: np.ndarray) -> bytes:
    output = io.BytesIO()
    np.save(output, rates, allow_pickle=False)
    return output.getvalue()


def payload_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def ensure_content_file(path: Path, payload: bytes, sha256: str) -> None:
    if path.exists():
        if not path.is_file() or path.stat().st_size != len(payload) or digest(path) != sha256:
            fail(f"content-addressed path has different bytes: {relative(path)}")
        return
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if not path.is_file() or path.stat().st_size != len(payload) or digest(path) != sha256:
            fail(f"content-addressed path raced with different bytes: {relative(path)}")
    if path.stat().st_size != len(payload) or digest(path) != sha256:
        fail(f"content-addressed write verification failed: {relative(path)}")


def write_observation_once(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        fail("observation tag already exists")


def acquire() -> int:
    tag = parse_tag(sys.argv)
    pid = parse_reader_pid()
    if FAMILY != Path(__file__).resolve().parent:
        fail("variance_signal family binding differs from this producer")
    expected_terminal = bind_reader_process(pid)
    observation_path = HISTORY_OBSERVATIONS / f"{tag}.json"
    if observation_path.exists():
        fail("observation tag already exists")
    require_storage_budget()

    import MetaTrader5 as mt5

    payloads: list[tuple[Path, bytes, str]] = []
    file_rows: list[dict[str, object]] = []
    terminal: dict[str, object] | None = None
    try:
        if not mt5.initialize(str(expected_terminal), portable=True, timeout=60_000):
            fail("MetaTrader5.initialize failed for the bound runtime")
        bind_reader_process(pid)
        info = mt5.terminal_info()
        if info is None:
            fail("terminal_info was unavailable from the bound runtime")
        terminal = bind_terminal_info(info)

        for symbol in SYMBOLS:
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, START_EPOCH, END_EPOCH)
            validate_rates(symbol, rates)
            payload = npy_payload(rates)
            sha256 = payload_sha256(payload)
            path = NATIVE_HISTORY / (
                f"{symbol}-M1-{START_EPOCH}-{END_EPOCH}-{sha256}.npy"
            )
            payloads.append((path, payload, sha256))
            file_rows.append(
                {
                    "symbol": symbol,
                    "timeframe": "M1",
                    "path": relative(path),
                    "sha256": sha256,
                    "bytes": len(payload),
                    "rows": int(len(rates)),
                    "first_epoch": int(rates["time"][0]),
                    "last_epoch": int(rates["time"][-1]),
                    "fields": list(rates.dtype.names or ()),
                    "dtype": rates.dtype.descr,
                }
            )
    finally:
        mt5.shutdown()

    if terminal is None:
        fail("bound terminal metadata was not captured")
    observed_utc = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    observation = {
        "schema": "v7-vs-native-history-observation-v1",
        "observation_tag": tag,
        "observed_utc": observed_utc,
        "request": {
            "symbols": list(SYMBOLS),
            "timeframe": "M1",
            "start_epoch": START_EPOCH,
            "end_epoch_inclusive": END_EPOCH,
        },
        "reader": {
            "pid": pid,
            "executable": relative(expected_terminal),
        },
        "runtime": {
            "path": relative(RUNTIME),
            "terminal_info_path": terminal["path"],
            "terminal_info_data_path": terminal["data_path"],
            "terminal_build": terminal["build"],
            "metatrader5_sdk_version": str(mt5.__version__),
        },
        "files": file_rows,
    }
    observation_payload = (
        json.dumps(observation, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")
    additional_bytes = len(observation_payload) + sum(
        len(payload) for path, payload, _ in payloads if not path.exists()
    )
    require_storage_budget(additional_bytes)

    NATIVE_HISTORY.mkdir(parents=True, exist_ok=True)
    HISTORY_OBSERVATIONS.mkdir(parents=True, exist_ok=True)
    if observation_path.exists():
        fail("observation tag already exists")
    for path, payload, sha256 in payloads:
        ensure_content_file(path, payload, sha256)
    write_observation_once(observation_path, observation_payload)

    for expected, _, sha256 in payloads:
        observed = record(expected)
        if observed["sha256"] != sha256:
            fail(f"final native-history record differs: {relative(expected)}")
    observed_record = record(observation_path)
    require_storage_budget()
    print(
        json.dumps(
            {
                "observation": observed_record,
                "reader_pid": pid,
                "terminal_build": terminal["build"],
                "metatrader5_sdk_version": str(mt5.__version__),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(acquire())
    except Exception as exc:
        print(f"native-history acquisition failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
