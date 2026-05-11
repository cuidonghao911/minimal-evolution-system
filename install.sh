#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
CONFIG_PATH="${HERMES_CONFIG:-$HERMES_HOME/config.yaml}"
SKILL_DIR="$HERMES_HOME/skills/minimal-evolution-system"
HOOK_DIR="$HERMES_HOME/agent-hooks"
ACCEPT_HOOKS=0
CONFIGURE=1

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Options:
  --no-config       Copy files only; do not edit Hermes config.yaml.
  --accept-hooks    Run "hermes --accept-hooks hooks doctor" after writing config.
  -h, --help        Show this help.

Environment:
  HERMES_HOME       Hermes home directory. Default: ~/.hermes
  HERMES_CONFIG     Hermes config file. Default: $HERMES_HOME/config.yaml
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-config)
      CONFIGURE=0
      shift
      ;;
    --accept-hooks)
      ACCEPT_HOOKS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "$SKILL_DIR/scripts" "$HOOK_DIR" "$HERMES_HOME/evolution-system/logs"
cp "$ROOT_DIR/SKILL.md" "$SKILL_DIR/SKILL.md"
cp "$ROOT_DIR/scripts/evolution_memory.py" "$SKILL_DIR/scripts/evolution_memory.py"
cp "$ROOT_DIR/hooks/evolution_pre_llm.py" "$HOOK_DIR/evolution_pre_llm.py"
cp "$ROOT_DIR/hooks/evolution_post_llm.py" "$HOOK_DIR/evolution_post_llm.py"
chmod +x "$SKILL_DIR/scripts/evolution_memory.py" "$HOOK_DIR/evolution_pre_llm.py" "$HOOK_DIR/evolution_post_llm.py"

python3 "$SKILL_DIR/scripts/evolution_memory.py" init-db >/dev/null

if [[ "$CONFIGURE" -eq 1 ]]; then
  mkdir -p "$(dirname "$CONFIG_PATH")"
  [[ -f "$CONFIG_PATH" ]] || printf '{}\n' > "$CONFIG_PATH"
  cp "$CONFIG_PATH" "$CONFIG_PATH.bak-minimal-evolution-$(date +%Y%m%dT%H%M%S)"

  python3 - "$CONFIG_PATH" "$HERMES_HOME" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except Exception as exc:
    raise SystemExit(f"PyYAML is required to edit config automatically: {exc}")

config_path = Path(sys.argv[1]).expanduser()
hermes_home = Path(sys.argv[2]).expanduser()
raw = config_path.read_text(encoding="utf-8") if config_path.exists() else "{}\n"
cfg = yaml.safe_load(raw) if raw.strip() else {}
if cfg is None:
    cfg = {}
if not isinstance(cfg, dict):
    raise SystemExit(f"Config root must be a mapping: {config_path}")

script = hermes_home / "skills" / "minimal-evolution-system" / "scripts" / "evolution_memory.py"
pre = hermes_home / "agent-hooks" / "evolution_pre_llm.py"
post = hermes_home / "agent-hooks" / "evolution_post_llm.py"

quick = cfg.setdefault("quick_commands", {})
quick["evo-report"] = {"type": "exec", "command": f"python3 {script} report"}
quick["evo-report-json"] = {"type": "exec", "command": f"python3 {script} report --json"}
quick["evo-backup"] = {"type": "exec", "command": f"python3 {script} backup"}
quick["evo-clean"] = {"type": "exec", "command": f"python3 {script} cleanup"}
quick["evo-reconcile"] = {"type": "exec", "command": f"python3 {script} reconcile"}

hooks = cfg.setdefault("hooks", {})

def upsert_hook(event: str, command: str, timeout: int) -> None:
    items = hooks.get(event) or []
    if not isinstance(items, list):
        items = []
    filtered = []
    for item in items:
        if not isinstance(item, dict):
            continue
        existing = str(item.get("command", ""))
        if "evolution_pre_llm.py" in existing or "evolution_post_llm.py" in existing:
            continue
        filtered.append(item)
    filtered.append({"command": command, "timeout": timeout})
    hooks[event] = filtered

upsert_hook("pre_llm_call", f"python3 {pre}", 30)
upsert_hook("post_llm_call", f"python3 {post}", 150)

config_path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, width=100000), encoding="utf-8")
PY
fi

echo "Installed minimal-evolution-system into: $SKILL_DIR"
echo "Database initialized at: $HERMES_HOME/evolution-system/memory.db"

if [[ "$CONFIGURE" -eq 1 ]]; then
  echo "Hermes config updated: $CONFIG_PATH"
  if command -v hermes >/dev/null 2>&1; then
    if [[ "$ACCEPT_HOOKS" -eq 1 ]]; then
      hermes --accept-hooks hooks doctor
    else
      echo "Run this to verify and approve hooks:"
      echo "  hermes hooks doctor"
    fi
  else
    echo "Hermes CLI not found on PATH. Run 'hermes hooks doctor' after Hermes is available."
  fi
fi
