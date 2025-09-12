import json
from pathlib import Path

from inspect_agents.logging import DEFAULT_LOG_DIR, verify_transcript, write_transcript_secure


def _fresh_transcript():
    # Create a fresh transcript to keep tests deterministic
    from inspect_ai.log._transcript import Transcript, init_transcript

    init_transcript(Transcript())


def _emit_tool_event(**kwargs):
    from inspect_ai.log._transcript import ToolEvent, transcript

    ev = ToolEvent(**kwargs)
    transcript()._event(ev)


def test_secure_transcript_chain_valid(tmp_path, monkeypatch):
    log_dir = Path(DEFAULT_LOG_DIR) / "secure-test"
    monkeypatch.setenv("INSPECT_LOG_DIR", str(log_dir))

    _fresh_transcript()

    _emit_tool_event(id="1", function="alpha", arguments={"x": 1})
    _emit_tool_event(id="2", function="beta", arguments={"y": 2})
    _emit_tool_event(id="3", function="gamma", arguments={"z": 3})

    out = write_transcript_secure()
    assert Path(out).exists()

    assert verify_transcript(out) is True


def test_secure_transcript_detects_tamper(monkeypatch):
    log_dir = Path(DEFAULT_LOG_DIR) / "secure-test-tamper"
    monkeypatch.setenv("INSPECT_LOG_DIR", str(log_dir))

    _fresh_transcript()

    _emit_tool_event(id="1", function="alpha", arguments={"x": 1})
    _emit_tool_event(id="2", function="beta", arguments={"y": 2})

    out = write_transcript_secure()
    p = Path(out)
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 2

    rec = json.loads(lines[0])
    # Tamper with the event content without updating hash
    rec["event"]["function"] = "alphx"
    lines[0] = json.dumps(rec, separators=(",", ":"), sort_keys=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_transcript(out) is False
