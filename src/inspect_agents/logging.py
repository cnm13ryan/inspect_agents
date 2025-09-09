from __future__ import annotations

import json
import os
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

DEFAULT_LOG_DIR = ".inspect/logs"
REDACT_KEYS: set[str] = {"api_key", "authorization", "file_text", "content"}


def _ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _redact(obj: Any, key: str | None = None) -> Any:
    if isinstance(obj, dict):
        return {k: _redact(v, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v, key) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if key in REDACT_KEYS:
        try:
            if isinstance(obj, str) and obj:
                return "[REDACTED]"
        except Exception:
            return "[REDACTED]"
    return obj


def _event_to_dict(ev: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    # shallow attribute dump
    for k, v in vars(ev).items():
        data[k] = _redact(v, k)
    data["type"] = ev.__class__.__name__
    return data


def write_transcript(log_dir: str | None = None) -> str:
    """Write current Inspect transcript events to a JSONL log file.

    Returns the log file path. Redacts sensitive fields by default.
    """
    from inspect_ai.log._transcript import transcript

    log_dir = log_dir or os.getenv("INSPECT_LOG_DIR", DEFAULT_LOG_DIR)
    _ensure_dir(log_dir)
    file_path = str(Path(log_dir) / "events.jsonl")

    with open(file_path, "a", encoding="utf-8") as fp:
        for ev in transcript().events:
            try:
                fp.write(json.dumps(_event_to_dict(ev), ensure_ascii=False) + "\n")
            except Exception:
                # best-effort: write a minimal record
                fp.write(json.dumps({"type": ev.__class__.__name__}) + "\n")

    return file_path


def _canonical_json(obj: Any) -> str:
    """Return a canonical JSON string for hashing.

    - Sorted keys to ensure stable ordering
    - Compact separators to avoid whitespace variance
    - UTF-8 safe content (ensure_ascii=False)
    """
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _read_last_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        last = None
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                last = line
        if last:
            rec = json.loads(last)
            return rec.get("hash")
    except Exception:
        return None
    return None


def write_transcript_secure(log_dir: str | None = None, file: str = "events.sec.jsonl") -> str:
    """Write a tamper-evident transcript with a SHA-256 hash chain.

    Each line is a JSON record: {"prev_hash", "hash", "event"} where
    hash = SHA256(prev_hash || "|" || canonical_json(event)).

    Returns the log file path.
    """
    from inspect_ai.log._transcript import transcript

    log_dir = log_dir or os.getenv("INSPECT_LOG_DIR", DEFAULT_LOG_DIR)
    _ensure_dir(log_dir)
    file_path = Path(log_dir) / file

    # Continue an existing chain if the file already exists
    prev_hash = _read_last_hash(file_path) or ("0" * 64)

    with file_path.open("a", encoding="utf-8") as fp:
        for ev in transcript().events:
            try:
                ed = _event_to_dict(ev)
                canon = _canonical_json(ed)
                payload = f"{prev_hash}|{canon}".encode()
                h = sha256(payload).hexdigest()
                rec = {"prev_hash": prev_hash, "hash": h, "event": ed}
                fp.write(_canonical_json(rec) + "\n")
                prev_hash = h
            except Exception:
                # Best-effort: write a minimal record with broken marker
                payload = f"{prev_hash}|{{}}".encode()
                h = sha256(payload).hexdigest()
                rec = {"prev_hash": prev_hash, "hash": h, "event": {"type": ev.__class__.__name__}}
                fp.write(_canonical_json(rec) + "\n")
                prev_hash = h

    return str(file_path)


def verify_transcript(path: str) -> bool:
    """Verify a secure transcript hash chain.

    Returns True when the entire chain validates; otherwise False.
    Missing files or empty files are treated as valid (nothing to verify).
    """
    p = Path(path)
    if not p.exists():
        return True

    expected_prev = "0" * 64
    try:
        with p.open("r", encoding="utf-8") as fp:
            for line in fp:
                rec = json.loads(line)
                if not all(k in rec for k in ("prev_hash", "hash", "event")):
                    return False
                if rec["prev_hash"] != expected_prev:
                    return False
                canon_event = _canonical_json(rec["event"])
                h = sha256(f"{expected_prev}|{canon_event}".encode()).hexdigest()
                if rec["hash"] != h:
                    return False
                expected_prev = rec["hash"]
    except Exception:
        return False

    return True


__all__ = [
    "write_transcript",
    "DEFAULT_LOG_DIR",
    "write_transcript_secure",
    "verify_transcript",
]
