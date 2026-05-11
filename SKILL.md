---
name: minimal-evolution-system
description: Run a minimal local evolution loop for Hermes using SQLite-backed rules, pre-task memory retrieval, post-task self-critique, confidence updates, cleanup, and weekly reporting. Use when the user wants Hermes to accumulate reusable task rules over time without fine-tuning model weights.
metadata:
  hermes:
    tags: [memory, learning, sqlite, local, workflow]
    requires_toolsets: [hermes-cli]
---

# Minimal Evolution System

Use this skill when the user wants a local, weight-free learning loop:

1. retrieve relevant historical rules before a task
2. execute the task
3. run a structured self-critique after the task
4. write/update reusable rules in SQLite
5. keep the memory store healthy with cleanup and reporting

## Data location

- Database: `${HERMES_HOME:-~/.hermes}/evolution-system/memory.db`
- Session state: `${HERMES_HOME:-~/.hermes}/evolution-system/session_state/`
- Backups: `${HERMES_HOME:-~/.hermes}/evolution-system/backups/`
- Script: `${HERMES_SKILL_DIR}/scripts/evolution_memory.py`

## Core rule

Do not treat this skill as passive documentation. When the user asks to use the evolution system, actively run the retrieval and persistence steps with the script.

## Workflow

### 1. Before solving a task

Run:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/evolution_memory.py retrieve --task "<task>" --session-id "${HERMES_SESSION_ID}"
```

If `HERMES_SESSION_ID` is unavailable, omit it and let the script create a derived session key.

Use the returned rules as working guidance for the current task. If no rules are returned, continue normally.

### 2. Solve the task

Carry out the task as usual.

### 3. After the task

Produce a self-critique in this exact JSON shape:

```json
{
  "success": true,
  "what_worked": "本次有效的方法（1-2句）",
  "what_failed": null,
  "rule_learned": "遇到X情况应优先Y",
  "domain_tag": "coding",
  "confidence_delta": 0.1
}
```

Rules:

- `rule_learned` must be one actionable sentence
- prefer an imperative/operational rule
- `domain_tag` should be one short tag such as `coding`, `writing`, `research`, `tool_use`, `ops`
- on success use `0.1`
- on failure use `-0.2`

### 4. Persist the critique

Run:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/evolution_memory.py store-critique \
  --task "<task>" \
  --result "<short result summary>" \
  --success true \
  --session-id "${HERMES_SESSION_ID}" \
  --critique-json '<json>'
```

Use a short textual result summary unless the user specifically asks to persist a longer result.

### 5. Reporting and maintenance

Current report:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/evolution_memory.py report
```

Cleanup only:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/evolution_memory.py cleanup
```

Backup:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/evolution_memory.py backup
```

## When to use which command

- `retrieve`: at the start of any task that should benefit from prior experience
- `store-critique`: after the task when there is enough signal to learn from
- `report`: when the user asks how the system is evolving
- `backup`: before risky edits or as periodic maintenance
- `cleanup`: when the user wants to prune low-confidence rules

## Output behavior

When using this skill in a live task:

1. briefly say you are retrieving prior rules
2. run the retrieval script
3. do the task
4. summarize the critique you are about to store
5. run the persistence step

Do not dump raw database rows unless the user asks.
