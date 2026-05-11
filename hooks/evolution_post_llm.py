#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
SCRIPT = HERMES_HOME / "skills" / "minimal-evolution-system" / "scripts" / "evolution_memory.py"
LOG_DIR = HERMES_HOME / "evolution-system" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "auto_critique.log"
SESSION_DIR = HERMES_HOME / "sessions"


def log_line(line: str) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def shorten(text: Any, limit: int = 500) -> str:
    s = " ".join(str(text or "").split())
    if len(s) <= limit:
        return s
    return s[: limit - 3] + "..."


def session_path(session_id: str) -> Path | None:
    if not session_id:
        return None
    direct = SESSION_DIR / f"session_{session_id}.json"
    if direct.exists():
        return direct
    matches = sorted(SESSION_DIR.glob(f"*{session_id}*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def summarize_session_trace(session_id: str, max_items: int = 18) -> str:
    path = session_path(session_id)
    if not path:
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    messages = data.get("messages") or []
    if not isinstance(messages, list):
        return ""

    lines = [f"Session trace summary(session={session_id}, file={path.name}):"]
    write_tool_seen = False
    terminal_seen = False
    for idx, msg in list(enumerate(messages))[-max_items:]:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "?")
        tool_calls = msg.get("tool_calls") or []
        if tool_calls:
            names = []
            for call in tool_calls:
                fn = (call.get("function") or {}) if isinstance(call, dict) else {}
                name = str(fn.get("name") or "?")
                names.append(name)
                if name in {"write_file", "apply_patch"}:
                    write_tool_seen = True
                if name in {"terminal", "execute_command", "exec_command", "execute_code"}:
                    terminal_seen = True
            lines.append(f"- #{idx} {role} tool calls: {', '.join(names)}")
            content = msg.get("content")
            if content:
                lines.append(f"  text: {shorten(content, 240)}")
            continue
        content = msg.get("content")
        if isinstance(content, list):
            content = " ".join(shorten(item, 160) for item in content)
        lines.append(f"- #{idx} {role}: {shorten(content, 420)}")
    lines.append(f"write evidence: write_file/apply_patch={write_tool_seen}, terminal/code={terminal_seen}")
    return "\n".join(lines)


def expand_reported_path(raw_path: str) -> Path | None:
    path = raw_path.strip().strip("`'\"，。；;)")
    if path.startswith("~/"):
        return Path.home() / path[2:]
    if path.startswith("/"):
        return Path(path)
    return None


def extract_reported_paths(text: str) -> list[str]:
    if not text:
        return []
    patterns = [
        r"~/Documents/notes/[^\s`'\"，。；;)]+",
        rf"{re.escape(str(Path.home()))}/Documents/notes/[^\s`'\"，。；;)]+",
        r"~Documents/notes/[^\s`'\"，。；;)]+",
    ]
    seen: set[str] = set()
    paths: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            if match not in seen:
                seen.add(match)
                paths.append(match)
    return paths


def file_claim_audit(assistant_response: str) -> str:
    paths = extract_reported_paths(str(assistant_response or ""))
    if not paths:
        return ""
    lines = ["File write audit:"]
    for raw in paths:
        if raw.startswith("~Documents/"):
            lines.append(f"- invalid path format: {raw}")
            continue
        expanded = expand_reported_path(raw)
        if expanded is None:
            lines.append(f"- cannot parse path: {raw}")
            continue
        lines.append(f"- {raw} -> {'exists' if expanded.exists() else 'missing'}")
    return "\n".join(lines)


def main() -> int:
    if not SCRIPT.exists():
        log_line(f"skip missing script: {SCRIPT}")
        return 0

    payload = json.load(sys.stdin)
    extra = payload.get("extra") or {}
    session_id = payload.get("session_id") or extra.get("session_id") or ""
    user_message = extra.get("user_message") or ""
    assistant_response = extra.get("assistant_response") or ""
    success = payload.get("success")
    if success is None:
        success = extra.get("success")
    if not user_message or not assistant_response:
        log_line("skip empty payload")
        return 0

    trace = summarize_session_trace(str(session_id))
    file_audit = file_claim_audit(str(assistant_response))
    critique_response = str(assistant_response)
    audit_parts = [part for part in [trace, file_audit] if part]
    if audit_parts:
        critique_response = (
            f"Final answer:\n{assistant_response}\n\n"
            "Audit the final answer together with the process evidence below. "
            "If the process shows a wrong guess, repeated slow tool, ignored constraint, "
            "or claimed file write with a missing file, extract a future-facing rule.\n"
            + "\n\n".join(audit_parts)
        )

    cmd = [
        "python3",
        str(SCRIPT),
        "auto-critique",
        "--user-message",
        str(user_message),
        "--assistant-response",
        critique_response,
        "--session-id",
        str(session_id),
        "--timeout",
        "120",
        "--json",
    ]
    if success is not None:
        cmd.extend(["--success", str(success)])
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=90)
    if result.returncode != 0:
        log_line(f"auto-critique failed: {result.stderr.strip() or result.stdout.strip()}")
        return 0
    log_line(result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
