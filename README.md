# Minimal Evolution System for Hermes

Minimal Evolution System is a small local learning loop for Hermes Agent.

It does not fine-tune model weights. It gives Hermes a lightweight memory layer:
after a task finishes, Hermes can extract one reusable operating rule, store it in
SQLite, and retrieve relevant rules before the next similar task.

The goal is simple:

> Stop repeating the same mistake. Keep useful task experience in a local, auditable database.

## What You Get

After installation, Hermes gains:

- `/evo-report`: show how many reusable rules have been learned.
- `/evo-report-json`: same report as JSON.
- `/evo-backup`: back up the SQLite memory database.
- `/evo-clean`: remove very low-confidence rules.
- `/evo-reconcile`: merge similar rules and clean up duplicates.
- `pre_llm_call` hook: retrieve relevant rules before the model answers.
- `post_llm_call` hook: audit the answer after the task and store a future-facing rule.

The system stores data under:

```text
~/.hermes/evolution-system/
  memory.db
  session_state/
  backups/
  logs/
```

## Requirements

- Linux or macOS shell environment.
- Hermes Agent installed and working.
- Python 3.10+.
- SQLite support in Python, which is included in normal Python builds.
- A local or remote OpenAI-compatible model endpoint configured in Hermes.

Optional but recommended:

- `PyYAML` for automatic config editing in `install.sh`.
- Ollama or another local model server if you want the system to run fully locally.

Check quickly:

```bash
hermes --version
python3 --version
python3 -c "import sqlite3; print('sqlite ok')"
python3 -c "import yaml; print('yaml ok')"
```

If `yaml ok` fails, you can still install manually using the config snippet in
`examples/config-snippet.yaml`.

## Quick Install

Clone or copy this repository, then run:

```bash
cd minimal-evolution-system
./install.sh
```

The installer will:

1. Copy the skill into `~/.hermes/skills/minimal-evolution-system/`.
2. Copy hooks into `~/.hermes/agent-hooks/`.
3. Initialize `~/.hermes/evolution-system/memory.db`.
4. Back up your Hermes config.
5. Add quick commands and hooks to `~/.hermes/config.yaml`.

Then verify:

```bash
hermes hooks doctor
```

If you are installing on a headless machine or you already trust these hooks, use:

```bash
./install.sh --accept-hooks
```

That runs:

```bash
hermes --accept-hooks hooks doctor
```

## Install Into Another Hermes Profile

Hermes supports isolated profiles through `HERMES_HOME`.

To install into a custom profile:

```bash
HERMES_HOME=/path/to/.hermes ./install.sh
```

To use a custom config path:

```bash
HERMES_CONFIG=/path/to/config.yaml ./install.sh
```

## Copy Files Only

If you want to inspect the config before editing it:

```bash
./install.sh --no-config
```

Then manually merge `examples/config-snippet.yaml` into your Hermes config.

## Manual Install

Copy files:

```bash
mkdir -p ~/.hermes/skills/minimal-evolution-system/scripts
mkdir -p ~/.hermes/agent-hooks

cp SKILL.md ~/.hermes/skills/minimal-evolution-system/SKILL.md
cp scripts/evolution_memory.py ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py
cp hooks/evolution_pre_llm.py ~/.hermes/agent-hooks/evolution_pre_llm.py
cp hooks/evolution_post_llm.py ~/.hermes/agent-hooks/evolution_post_llm.py

chmod +x ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py
chmod +x ~/.hermes/agent-hooks/evolution_pre_llm.py
chmod +x ~/.hermes/agent-hooks/evolution_post_llm.py
```

Initialize the database:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py init-db
```

Add this to `~/.hermes/config.yaml`:

```yaml
quick_commands:
  evo-report:
    type: exec
    command: python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py report
  evo-report-json:
    type: exec
    command: python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py report --json
  evo-backup:
    type: exec
    command: python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py backup
  evo-clean:
    type: exec
    command: python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py cleanup
  evo-reconcile:
    type: exec
    command: python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py reconcile

hooks:
  pre_llm_call:
    - command: python3 ~/.hermes/agent-hooks/evolution_pre_llm.py
      timeout: 30
  post_llm_call:
    - command: python3 ~/.hermes/agent-hooks/evolution_post_llm.py
      timeout: 90
```

Then verify:

```bash
hermes hooks doctor
```

## How It Works

The system has three parts.

### 1. SQLite Rule Store

Rules are stored in:

```text
~/.hermes/evolution-system/memory.db
```

Each rule has:

- `domain_tag`: broad category such as `coding`, `research`, `writing`, `tool_use`, `ops`.
- `rule_learned`: the reusable operating rule.
- `what_worked`: optional short note about what worked.
- `what_failed`: optional short note about what failed.
- `confidence`: score from `0.0` to `1.0`.
- `use_count`: how often the rule was retrieved.
- `created_at` and `last_used`.

The schema is created automatically by:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py init-db
```

### 2. Pre-LLM Hook

Before Hermes calls the model, `hooks/evolution_pre_llm.py` receives the current task.

It runs:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py retrieve \
  --task "<current user task>" \
  --session-id "<hermes session id>" \
  --json
```

The retrieved rules are injected into the model context as guidance.

Important behavior:

- It skips slash commands.
- It fails open. If the database or script has a problem, it returns `{}` and Hermes continues normally.
- It only injects rules that match the current task by domain or keywords.
- Current user instructions still take priority over historical rules.

### 3. Post-LLM Hook

After Hermes finishes, `hooks/evolution_post_llm.py` receives:

- the user message
- the assistant response
- the session id
- task success metadata when available

It runs an automatic critique:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py auto-critique \
  --user-message "<task>" \
  --assistant-response "<answer>" \
  --session-id "<session id>" \
  --timeout 120 \
  --json
```

The critique model must output a JSON rule. The system then:

1. rejects weak rules
2. reviews rule quality
3. merges near-duplicates
4. adjusts confidence for previously retrieved rules
5. writes the result to SQLite
6. logs the audit under `~/.hermes/evolution-system/logs/auto_critique.log`

## Commands

### Report

```bash
/evo-report
```

Equivalent command:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py report
```

Example output:

```text
DB: /home/user/.hermes/evolution-system/memory.db
总规则数: 5
高质量规则数(confidence>0.7): 0
低质量待淘汰规则数(confidence<0.1): 0
近7天新增规则数: 5

领域分布:
- research: 3 条，平均置信度 0.6333
- coding: 1 条，平均置信度 0.5

复用最多的规则:
- [id=4] [domain=research] use_count=4 confidence=0.7: ...
```

### JSON Report

```bash
/evo-report-json
```

Equivalent command:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py report --json
```

Use this when you want to build dashboards or inspect the data programmatically.

### Backup

```bash
/evo-backup
```

Equivalent command:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py backup
```

Backups are written to:

```text
~/.hermes/evolution-system/backups/
```

### Cleanup

```bash
/evo-clean
```

Equivalent command:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py cleanup
```

This deletes rules with `confidence < 0.1`.

### Reconcile

```bash
/evo-reconcile
```

Equivalent command:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py reconcile
```

This merges similar rules and removes stale rules.

## Direct CLI Usage

Retrieve rules:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py retrieve \
  --task "debug a failing pytest test" \
  --json
```

Store a critique manually:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py store-critique \
  --task "debug a failing pytest test" \
  --result "fixed fixture setup and reran focused test" \
  --success true \
  --critique-json '{"rule_learned":"在调试失败测试时，应先复现最小失败用例再扩大测试范围；若失败无法稳定复现，此规则不适用。","domain_tag":"coding","confidence_delta":0.1}'
```

Run auto-critique manually:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py auto-critique \
  --user-message "debug a failing pytest test" \
  --assistant-response "fixed the fixture and verified the test" \
  --success true \
  --json
```

## Model Selection

`auto-critique` uses the model configured in Hermes by default.

The script tries to read:

```yaml
model:
  default: ...
providers:
  ...
```

from:

```text
${HERMES_HOME:-~/.hermes}/config.yaml
```

You can override it per command:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py auto-critique \
  --user-message "..." \
  --assistant-response "..." \
  --model "qwen3:8b" \
  --base-url "http://127.0.0.1:11434/v1" \
  --json
```

You can also set environment variables:

```bash
export EVOLUTION_MODEL=qwen3:8b
export EVOLUTION_BASE_URL=http://127.0.0.1:11434/v1
```

For local models, use a small or medium model if speed matters. The post hook runs after each completed task, so a very large local model can make Hermes feel slow.

## Security Model

This project adds shell hooks to Hermes.

That means Hermes will run local Python scripts on `pre_llm_call` and `post_llm_call`.

Before approving hooks, inspect:

```text
hooks/evolution_pre_llm.py
hooks/evolution_post_llm.py
scripts/evolution_memory.py
```

Then run:

```bash
hermes hooks doctor
```

The hooks are intentionally local:

- They write to `~/.hermes/evolution-system/`.
- They do not upload the SQLite database.
- They call your configured model endpoint for auto-critique.
- They fail open so Hermes can continue if the evolution system has an error.

The post hook sends the task and final answer to your configured model endpoint.
If your endpoint is remote, that text leaves your machine. If that matters, use a local model.

## Privacy

The SQLite database may contain:

- excerpts of task descriptions
- short result summaries
- reusable rules inferred from work
- small notes about what worked or failed

Do not publish `memory.db`.

The `.gitignore` excludes common SQLite database files, but check before pushing:

```bash
find . -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3'
```

## Performance Notes

The pre hook is usually fast because it only queries SQLite.

The post hook can be slower because it may call a model twice:

1. generate critique
2. review candidate rule

If tasks feel slow, use one of these options:

1. Use a smaller model for `EVOLUTION_MODEL`.
2. Increase the hook timeout if the model is slow.
3. Disable the post hook and use manual `store-critique`.
4. Keep only `/evo-report` and manual commands.

To disable only the post hook, remove this section from Hermes config:

```yaml
hooks:
  post_llm_call:
    - command: python3 ~/.hermes/agent-hooks/evolution_post_llm.py
      timeout: 90
```

## Troubleshooting

### `/evo-report` does not exist

Check config:

```bash
hermes config path
hermes config show | grep -n "evo-report"
```

If missing, merge `examples/config-snippet.yaml` into your config or rerun:

```bash
./install.sh
```

### Hooks are not approved

Run:

```bash
hermes hooks doctor
```

For non-interactive install:

```bash
hermes --accept-hooks hooks doctor
```

### Hook says command changed

Hermes tracks hook script contents for safety. If you edited a hook after approval, re-approve it:

```bash
hermes hooks doctor
```

### Post hook times out

Use a smaller critique model:

```bash
export EVOLUTION_MODEL=qwen3:8b
```

Or increase the timeout in config:

```yaml
hooks:
  post_llm_call:
    - command: python3 ~/.hermes/agent-hooks/evolution_post_llm.py
      timeout: 180
```

### Rules are too generic

Run:

```bash
/evo-reconcile
```

Then inspect:

```bash
/evo-report
```

The system already rejects many low-quality rules, but local models can still produce vague rules. Better critique models produce better memory.

### Database looks wrong

Back up first:

```bash
/evo-backup
```

Then inspect directly:

```bash
sqlite3 ~/.hermes/evolution-system/memory.db '.tables'
sqlite3 ~/.hermes/evolution-system/memory.db 'select id, domain_tag, confidence, rule_learned from memories order by id desc limit 10;'
```

## Uninstall

Remove the installed files:

```bash
rm -rf ~/.hermes/skills/minimal-evolution-system
rm -f ~/.hermes/agent-hooks/evolution_pre_llm.py
rm -f ~/.hermes/agent-hooks/evolution_post_llm.py
```

Remove these config entries from `~/.hermes/config.yaml`:

```yaml
quick_commands:
  evo-report:
  evo-report-json:
  evo-backup:
  evo-clean:
  evo-reconcile:

hooks:
  pre_llm_call:
    - command: python3 ~/.hermes/agent-hooks/evolution_pre_llm.py
  post_llm_call:
    - command: python3 ~/.hermes/agent-hooks/evolution_post_llm.py
```

The data remains at:

```text
~/.hermes/evolution-system/
```

Delete it only if you no longer need the learned rules:

```bash
rm -rf ~/.hermes/evolution-system
```

## Project Layout

```text
minimal-evolution-system/
  README.md
  SKILL.md
  install.sh
  scripts/
    evolution_memory.py
  hooks/
    evolution_pre_llm.py
    evolution_post_llm.py
  examples/
    config-snippet.yaml
    evo-report-example.txt
  .gitignore
```

## Design Boundaries

This system is intentionally small.

It does not:

- fine-tune or modify model weights
- replace Hermes memory
- guarantee task quality
- decide truth by itself
- sync memory to a cloud service
- publish your local database

It does:

- store reusable rules
- retrieve relevant rules before a task
- update confidence scores
- produce a report
- keep the implementation inspectable

## Recommended First Test

After install:

```bash
hermes
```

Run a small task that has an obvious lesson:

```text
帮我写一个简单说明：以后遇到 arXiv 论文任务，先确认标题和作者，再阅读正文。
```

Then run:

```text
/evo-report
```

If the hook and model ran successfully, you should see at least one rule or a log entry in:

```text
~/.hermes/evolution-system/logs/auto_critique.log
```

## Publishing Checklist

Before pushing this repository to GitHub:

```bash
python3 -m py_compile scripts/evolution_memory.py hooks/evolution_pre_llm.py hooks/evolution_post_llm.py
./install.sh --help
find . -name '__pycache__' -o -name '*.pyc' -o -name '*.db'
```

Do not commit:

- `memory.db`
- backups
- logs
- personal config files
- session files

## License

No license is included yet. Add a license before publishing publicly if you want others to reuse, modify, or redistribute the project clearly.
