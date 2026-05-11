#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
SCRIPT = HERMES_HOME / "skills" / "minimal-evolution-system" / "scripts" / "evolution_memory.py"


def main() -> int:
    payload = json.load(sys.stdin)
    extra = payload.get("extra") or {}
    user_message = extra.get("user_message") or ""
    session_id = payload.get("session_id") or extra.get("session_id") or ""
    if not user_message or str(user_message).strip().startswith("/"):
        print("{}")
        return 0
    if not SCRIPT.exists():
        print("{}")
        return 0

    cmd = [
        "python3",
        str(SCRIPT),
        "retrieve",
        "--task",
        str(user_message),
        "--session-id",
        str(session_id),
        "--json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    if result.returncode != 0:
        print("{}")
        return 0

    data = json.loads(result.stdout or "{}")
    prompt_block = (data.get("prompt_block") or "").strip()
    evidence_block = (data.get("evidence_block") or "").strip()
    if not prompt_block or prompt_block == "无历史规则。":
        print("{}")
        return 0

    context = (
        "Historical operating rules retrieved from the local evolution memory. "
        "Use them when relevant, but current user instructions and verified facts take precedence:\n"
        f"{prompt_block}"
    )
    if evidence_block:
        context += (
            "\n\nThe following evidence explains where some rules came from. "
            "Use it to avoid blindly applying a rule outside its original failure mode:\n"
            f"{evidence_block}"
        )
    print(json.dumps({"context": context}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
