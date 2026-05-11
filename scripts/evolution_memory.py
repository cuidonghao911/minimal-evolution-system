#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sqlite3
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
STATE_DIR = HERMES_HOME / "evolution-system"
DB_PATH = STATE_DIR / "memory.db"
SESSION_DIR = STATE_DIR / "session_state"
BACKUP_DIR = STATE_DIR / "backups"
DEFAULT_MODEL = os.environ.get("EVOLUTION_MODEL", "qwen3:8b")
DEFAULT_BASE_URL = os.environ.get("EVOLUTION_BASE_URL", "http://127.0.0.1:11434/v1")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  domain_tag   TEXT    NOT NULL,
  rule_learned TEXT    NOT NULL,
  what_worked  TEXT,
  what_failed  TEXT,
  confidence   REAL    DEFAULT 0.5,
  use_count    INTEGER DEFAULT 0,
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_used    TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memories_domain_tag ON memories(domain_tag);
CREATE INDEX IF NOT EXISTS idx_memories_confidence ON memories(confidence);
CREATE INDEX IF NOT EXISTS idx_memories_rule_learned ON memories(rule_learned);

CREATE TABLE IF NOT EXISTS episodes (
  id                      INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_id               INTEGER,
  session_id              TEXT,
  task                    TEXT    NOT NULL,
  result                  TEXT,
  success                 INTEGER,
  root_cause              TEXT,
  counterfactual          TEXT,
  falsification_condition TEXT,
  evidence                TEXT,
  created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(memory_id) REFERENCES memories(id)
);

CREATE INDEX IF NOT EXISTS idx_episodes_memory_id ON episodes(memory_id);
CREATE INDEX IF NOT EXISTS idx_episodes_session_id ON episodes(session_id);
CREATE INDEX IF NOT EXISTS idx_episodes_created_at ON episodes(created_at);

CREATE VIEW IF NOT EXISTS stale_memories AS
  SELECT * FROM memories
  WHERE confidence < 0.1
  ORDER BY confidence ASC;
"""

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "is", "are", "be", "this", "that", "from", "by", "as", "at", "it",
    "请", "帮", "一下", "进行", "一个", "这次", "当前", "任务", "需要", "处理",
    "我们", "你", "我", "把", "和", "或", "在", "对", "给", "用", "是", "了",
}

DOMAIN_HINTS = {
    "coding": ["code", "python", "bug", "fix", "script", "api", "编程", "代码", "脚本", "调试"],
    "writing": ["write", "article", "essay", "summary", "文档", "写作", "总结", "润色"],
    "research": ["research", "paper", "arxiv", "pdf", "论文", "阅读", "查", "搜索", "验证", "compare", "分析", "调研"],
    "tool_use": ["tool", "cli", "terminal", "shell", "命令", "工具", "终端"],
    "ops": ["deploy", "docker", "systemd", "service", "服务器", "部署", "运维", "监控"],
}


@dataclass
class MemoryRow:
    id: int
    domain_tag: str
    rule_learned: str
    what_worked: str | None
    what_failed: str | None
    confidence: float
    use_count: int
    created_at: str | None
    last_used: str | None


def ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def connect_db() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> dict[str, Any]:
    with connect_db() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    return {"ok": True, "db_path": str(DB_PATH)}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def rule_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_./:-]{3,}", (text or "").lower())
    return {tok for tok in tokens if tok not in STOPWORDS}


def rule_similarity(a: str, b: str) -> float:
    ta = rule_tokens(a)
    tb = rule_tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    if not union:
        return 0.0
    return inter / union


def maybe_related_rules(a: str, b: str) -> bool:
    sim = rule_similarity(a, b)
    if sim >= 0.23:
        return True
    if a in b or b in a:
        return True
    shared = rule_tokens(a) & rule_tokens(b)
    return len(shared) >= 2


def extract_keywords(task: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_./:-]{3,}", task.lower())
    keywords: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in STOPWORDS:
            continue
        if token not in seen:
            seen.add(token)
            keywords.append(token)
    return keywords[:12]


def count_cjk_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


def specificity_score(rule: str, task: str = "") -> float:
    text = normalize_whitespace(rule)
    score = 0.0

    trigger_markers = ["遇到", "当", "如果", "连续", "一旦", "失败后", "命中", "搜索", "构造", "提取"]
    action_markers = ["应", "优先", "不要", "立即", "改用", "切换", "加入", "限制", "校验", "验证", "交叉验证"]

    if any(marker in text for marker in trigger_markers):
        score += 0.25
    if any(marker in text for marker in action_markers):
        score += 0.25

    # Longer rules are not always better, but very short summaries are often too vague.
    score += min(count_cjk_chars(text) / 40.0, 0.2)

    token_count = len(rule_tokens(text))
    score += min(token_count / 8.0, 0.15)

    if task:
        overlap = len(rule_tokens(text) & set(extract_keywords(task)))
        score += min(overlap * 0.08, 0.2)

    generic_suffixes = ["质量", "效率", "效果", "能力", "水平", "判断"]
    if any(text.endswith(suffix) for suffix in generic_suffixes):
        score -= 0.08

    return max(0.0, min(score, 1.0))


def infer_domain_tags(task: str) -> list[str]:
    text = task.lower()
    tags: list[str] = []
    for tag, hints in DOMAIN_HINTS.items():
        if any(hint in text for hint in hints):
            tags.append(tag)
    return tags or ["tool_use"]


def session_file(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", session_id).strip("-") or "default"
    return SESSION_DIR / f"{safe}.json"


def derive_session_id(task: str) -> str:
    base = "-".join(extract_keywords(task)[:6]) or "task"
    return f"derived-{base}"


def serialize_rows(rows: list[sqlite3.Row]) -> list[MemoryRow]:
    return [MemoryRow(**dict(row)) for row in rows]


def memory_score(row: MemoryRow, task: str = "") -> float:
    # Prefer precise, actionable rules over older generic summaries.
    confidence_part = row.confidence * 0.55
    use_count_part = min(math.log(row.use_count + 2.0) / 2.5, 0.2)
    specificity_part = specificity_score(row.rule_learned, task) * 0.35
    return confidence_part + use_count_part + specificity_part


def format_memories_for_prompt(rows: list[MemoryRow]) -> str:
    if not rows:
        return "无历史规则。"
    parts = []
    for row in rows:
        parts.append(
            f"- [id={row.id}] [domain={row.domain_tag}] [confidence={row.confidence:.2f}] "
            f"{row.rule_learned}"
        )
    return "\n".join(parts)


def format_evidence_for_prompt(evidence_by_memory_id: dict[int, str], max_chars: int = 380) -> str:
    lines = []
    for memory_id, evidence in evidence_by_memory_id.items():
        summary = normalize_whitespace(evidence)
        if not summary:
            continue
        if len(summary) > max_chars:
            summary = summary[: max_chars - 3] + "..."
        lines.append(f"  evidence for id={memory_id}: {summary}")
    return "\n".join(lines)


def retrieve(task: str, top_k: int, session_id: str | None, as_json: bool) -> dict[str, Any]:
    task = normalize_whitespace(task)
    keywords = extract_keywords(task)
    tags = infer_domain_tags(task)

    with connect_db() as conn:
        conn.executescript(SCHEMA_SQL)
        rows = serialize_rows(conn.execute("SELECT * FROM memories").fetchall())

        matched: list[MemoryRow] = []
        for row in rows:
            haystack = f"{row.rule_learned} {row.what_worked or ''} {row.what_failed or ''}".lower()
            if row.domain_tag in tags or any(keyword in haystack for keyword in keywords):
                matched.append(row)

        ranked = sorted(matched, key=lambda row: memory_score(row, task), reverse=True)[:top_k]
        evidence_by_memory_id: dict[int, str] = {}
        if ranked:
            placeholders = ",".join("?" for _ in ranked)
            episode_rows = conn.execute(
                f"""
                SELECT memory_id, root_cause, counterfactual, evidence
                FROM episodes
                WHERE memory_id IN ({placeholders})
                ORDER BY created_at DESC
                """,
                tuple(row.id for row in ranked),
            ).fetchall()
            for episode in episode_rows:
                memory_id = int(episode["memory_id"])
                if memory_id in evidence_by_memory_id:
                    continue
                evidence_by_memory_id[memory_id] = normalize_whitespace(
                    " | ".join(
                        part
                        for part in [
                            f"root_cause={episode['root_cause']}" if episode["root_cause"] else "",
                            f"counterfactual={episode['counterfactual']}" if episode["counterfactual"] else "",
                            f"evidence={episode['evidence']}" if episode["evidence"] else "",
                        ]
                        if part
                    )
                )
        now = datetime.now().isoformat(timespec="seconds")
        for row in ranked:
            conn.execute(
                "UPDATE memories SET use_count = use_count + 1, last_used = ? WHERE id = ?",
                (now, row.id),
            )
        conn.commit()

    sid = session_id or derive_session_id(task)
    state = {
        "session_id": sid,
        "task": task,
        "keywords": keywords,
        "domain_tags": tags,
        "retrieved_ids": [row.id for row in ranked],
        "retrieved_at": datetime.now().isoformat(timespec="seconds"),
    }
    session_file(sid).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = {
        "session_id": sid,
        "task": task,
        "keywords": keywords,
        "domain_tags": tags,
        "count": len(ranked),
        "memories": [row.__dict__ for row in ranked],
        "prompt_block": format_memories_for_prompt(ranked),
        "evidence_block": format_evidence_for_prompt(evidence_by_memory_id),
    }
    if as_json:
        return payload
    return {"text": payload["prompt_block"], **payload}


def load_session_state(session_id: str | None, task: str) -> dict[str, Any]:
    sid = session_id or derive_session_id(task)
    path = session_file(sid)
    if not path.exists():
        return {"session_id": sid, "task": task, "retrieved_ids": []}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_critique_json(raw: str) -> dict[str, Any]:
    critique = json.loads(raw)
    required = {"rule_learned", "domain_tag", "confidence_delta"}
    missing = required.difference(critique)
    if missing:
        raise ValueError(f"critique JSON missing keys: {sorted(missing)}")
    critique["rule_learned"] = normalize_whitespace(str(critique["rule_learned"]))
    critique["what_worked"] = None if critique.get("what_worked") is None else normalize_whitespace(str(critique["what_worked"]))
    critique["what_failed"] = None if critique.get("what_failed") is None else normalize_whitespace(str(critique["what_failed"]))
    critique["root_cause"] = None if critique.get("root_cause") is None else normalize_whitespace(str(critique["root_cause"]))
    critique["counterfactual"] = None if critique.get("counterfactual") is None else normalize_whitespace(str(critique["counterfactual"]))
    critique["falsification_condition"] = None if critique.get("falsification_condition") is None else normalize_whitespace(str(critique["falsification_condition"]))
    critique["domain_tag"] = normalize_whitespace(str(critique["domain_tag"])).lower()
    critique["confidence_delta"] = float(critique["confidence_delta"])
    if "success" in critique:
        critique["success"] = bool(critique["success"])
    if not critique["rule_learned"]:
        raise ValueError("rule_learned must not be empty")
    return critique


def are_rules_equivalent(a: str, b: str) -> bool:
    sim = rule_similarity(a, b)
    return sim >= 0.68 or a in b or b in a


def choose_better_rule(a: str, b: str) -> str:
    sa = specificity_score(a)
    sb = specificity_score(b)
    if sb > sa + 0.05:
        return b
    return a


def upsert_rule(conn: sqlite3.Connection, critique: dict[str, Any]) -> tuple[int, bool]:
    existing = conn.execute(
        "SELECT id, confidence FROM memories WHERE domain_tag = ? AND rule_learned = ? LIMIT 1",
        (critique["domain_tag"], critique["rule_learned"]),
    ).fetchone()
    if existing:
        new_conf = clamp(float(existing["confidence"]) + (critique["confidence_delta"] / 2.0))
        conn.execute(
            """
            UPDATE memories
            SET what_worked = ?, what_failed = ?, confidence = ?
            WHERE id = ?
            """,
            (critique["what_worked"], critique["what_failed"], new_conf, int(existing["id"])),
        )
        return int(existing["id"]), False

    cur = conn.execute(
        """
        INSERT INTO memories (domain_tag, rule_learned, what_worked, what_failed, confidence, use_count)
        VALUES (?, ?, ?, ?, 0.5, 0)
        """,
        (
            critique["domain_tag"],
            critique["rule_learned"],
            critique["what_worked"],
            critique["what_failed"],
        ),
    )
    return int(cur.lastrowid), True


def reconcile_candidate_against_existing(
    conn: sqlite3.Connection,
    critique: dict[str, Any],
    *,
    model: str | None,
    base_url: str | None,
    timeout: int,
) -> tuple[dict[str, Any], bool]:
    rows = conn.execute(
        """
        SELECT * FROM memories
        WHERE domain_tag = ?
        ORDER BY confidence DESC, use_count DESC, id ASC
        """,
        (critique["domain_tag"],),
    ).fetchall()
    candidate_rule = critique["rule_learned"]
    changed = False
    for row in rows:
        existing_id = int(row["id"])
        existing_rule = str(row["rule_learned"])
        if existing_rule == candidate_rule:
            continue
        if not are_rules_equivalent(candidate_rule, existing_rule):
            continue
        merged_rule = choose_better_rule(existing_rule, candidate_rule)
        conn.execute(
            """
            UPDATE memories
            SET rule_learned = ?, what_worked = COALESCE(?, what_worked), what_failed = ?, confidence = ?
            WHERE id = ?
            """,
            (
                merged_rule,
                critique["what_worked"],
                critique["what_failed"],
                clamp(max(float(row["confidence"]), 0.5) + 0.05),
                existing_id,
            ),
        )
        critique["_drop_new_rule"] = True
        critique["_resolved_existing_id"] = existing_id
        critique["rule_learned"] = merged_rule
        changed = True
        return critique, changed
    return critique, changed


def cleanup(conn: sqlite3.Connection | None = None) -> int:
    own_conn = conn is None
    if own_conn:
        conn = connect_db()
    assert conn is not None
    deleted = conn.execute("DELETE FROM memories WHERE confidence < 0.1").rowcount
    conn.commit()
    if own_conn:
        conn.close()
    return deleted


def store_critique(
    task: str,
    result: str,
    success: bool,
    critique_raw: str,
    session_id: str | None,
    evidence: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    timeout: int = 90,
) -> dict[str, Any]:
    task = normalize_whitespace(task)
    result = normalize_whitespace(result)
    critique = parse_critique_json(critique_raw)
    state = load_session_state(session_id, task)
    retrieved_ids = state.get("retrieved_ids", [])

    with connect_db() as conn:
        conn.executescript(SCHEMA_SQL)
        now = datetime.now().isoformat(timespec="seconds")
        updated_rules = []
        for memory_id in retrieved_ids:
            row = conn.execute("SELECT confidence FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if not row:
                continue
            new_conf = clamp(float(row["confidence"]) + critique["confidence_delta"])
            conn.execute(
                "UPDATE memories SET confidence = ?, last_used = ? WHERE id = ?",
                (new_conf, now, memory_id),
            )
            updated_rules.append({"id": memory_id, "confidence": round(new_conf, 4)})

        critique, reconciled = reconcile_candidate_against_existing(
            conn,
            critique,
            model=model,
            base_url=base_url,
            timeout=timeout,
        )
        if critique.get("_drop_new_rule"):
            rule_id = int(critique["_resolved_existing_id"])
            inserted = False
        elif critique.get("_resolved_existing_id"):
            rule_id = int(critique["_resolved_existing_id"])
            inserted = False
        else:
            rule_id, inserted = upsert_rule(conn, critique)
        conn.execute(
            """
            INSERT INTO episodes (
              memory_id, session_id, task, result, success, root_cause,
              counterfactual, falsification_condition, evidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id,
                state.get("session_id"),
                task,
                result,
                1 if success else 0,
                critique.get("root_cause"),
                critique.get("counterfactual"),
                critique.get("falsification_condition"),
                normalize_whitespace(evidence or ""),
            ),
        )
        deleted = cleanup(conn)
        conn.commit()

    audit = {
        "task": task,
        "result": result,
        "success": success,
        "critique": critique,
        "updated_rules": updated_rules,
        "rule_id": rule_id,
        "inserted": inserted,
        "reconciled": bool(critique.get("_drop_new_rule") or critique.get("_resolved_existing_id") or critique.get("_conflicted_rule_ids")),
        "conflicted_rule_ids": critique.get("_conflicted_rule_ids", []),
        "deleted_stale": deleted,
        "session_id": state.get("session_id"),
        "evidence_saved": bool(normalize_whitespace(evidence or "")),
    }
    audit_path = session_file(state.get("session_id", derive_session_id(task))).with_suffix(".last-critique.json")
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


def report(days: int, as_json: bool) -> dict[str, Any]:
    with connect_db() as conn:
        conn.executescript(SCHEMA_SQL)
        high_quality = conn.execute("SELECT COUNT(*) AS n FROM memories WHERE confidence > 0.7").fetchone()["n"]
        total = conn.execute("SELECT COUNT(*) AS n FROM memories").fetchone()["n"]
        episodes = conn.execute("SELECT COUNT(*) AS n FROM episodes").fetchone()["n"]
        stale = conn.execute("SELECT COUNT(*) AS n FROM stale_memories").fetchone()["n"]
        recent = conn.execute(
            "SELECT COUNT(*) AS n FROM memories WHERE created_at > datetime('now', ?)",
            (f"-{int(days)} days",),
        ).fetchone()["n"]
        domain_rows = conn.execute(
            """
            SELECT domain_tag, COUNT(*) AS count, ROUND(AVG(confidence), 4) AS avg_confidence
            FROM memories
            GROUP BY domain_tag
            ORDER BY count DESC, avg_confidence DESC
            """
        ).fetchall()
        top_rules = conn.execute(
            """
            SELECT id, domain_tag, rule_learned, use_count, ROUND(confidence, 4) AS confidence
            FROM memories
            ORDER BY use_count DESC, confidence DESC
            LIMIT 10
            """
        ).fetchall()

    payload = {
        "db_path": str(DB_PATH),
        "total_rules": total,
        "total_episodes": episodes,
        "high_quality_rules": high_quality,
        "stale_rules": stale,
        "recent_growth_days": days,
        "recent_growth": recent,
        "domains": [dict(row) for row in domain_rows],
        "top_rules": [dict(row) for row in top_rules],
    }
    if as_json:
        return payload
    lines = [
        f"DB: {payload['db_path']}",
        f"总规则数: {total}",
        f"错误现场数/episodes: {episodes}",
        f"高质量规则数(confidence>0.7): {high_quality}",
        f"低质量待淘汰规则数(confidence<0.1): {stale}",
        f"近{days}天新增规则数: {recent}",
        "",
        "领域分布:",
    ]
    for row in payload["domains"]:
        lines.append(f"- {row['domain_tag']}: {row['count']} 条，平均置信度 {row['avg_confidence']}")
    lines.append("")
    lines.append("复用最多的规则:")
    for row in payload["top_rules"]:
        lines.append(
            f"- [id={row['id']}] [domain={row['domain_tag']}] use_count={row['use_count']} "
            f"confidence={row['confidence']}: {row['rule_learned']}"
        )
    payload["text"] = "\n".join(lines)
    return payload


def backup() -> dict[str, Any]:
    ensure_dirs()
    if not DB_PATH.exists():
        init_db()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"memory_backup_{stamp}.db"
    shutil.copy2(DB_PATH, target)
    return {"ok": True, "backup_path": str(target)}


def load_runtime_model() -> tuple[str, str]:
    model = DEFAULT_MODEL
    base_url = DEFAULT_BASE_URL
    cfg_path = HERMES_HOME / "config.yaml"
    if cfg_path.exists():
        text = cfg_path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"(?m)^model:\n(?:[^\n]*\n)*?\s+default:\s*([^\n#]+)", text)
        if m:
            model = m.group(1).strip().strip("'\"")
        p = re.search(r"(?m)^\s+api:\s*(http[^\n#]+)", text)
        if p:
            raw = p.group(1).strip().strip("'\"")
            base_url = raw
    model = normalize_whitespace(model) or DEFAULT_MODEL
    base_url = normalize_whitespace(base_url.rstrip("/")) or DEFAULT_BASE_URL
    return model, base_url


def call_local_model_for_critique(
    user_message: str,
    assistant_response: str,
    success: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    model = model or load_runtime_model()[0]
    base_url = base_url or load_runtime_model()[1]
    success_value = normalize_whitespace(success or "unknown")
    prompt = f"""
你是一个从未见过这个任务执行过程的第三方审计员。
你能看到的只有：
  - 任务描述：{user_message}
  - 最终输出：{assistant_response}
  - 是否达到目标：{success_value}

请严格按以下步骤推理，不可跳步，并在输出前做充分、深入但隐藏的思考：

[Step 1 - 结果定性]
这个结果在客观上是否令人满意？具体差距在哪里？

[Step 2 - 根因定位]
哪一个具体环节最可能导致了这个结果？
只选一个最关键的，不要列清单。
优先检查这些系统性错误：未先验证来源元数据就猜测对象身份、关键数字没有出处、重复调用同一慢工具、文件路径格式错误、声称写入文件但未实际写入或文件不存在、用户明确约束未被执行。

[Step 3 - 反事实检验]
如果在那个环节换一种做法，结果是否会更好？
最可能的替代方案是什么？

[Step 4 - 规则提炼]
基于上述分析，提炼一条可复用规则。
格式严格要求：
"在[触发条件]下，应[具体行动]；若[反例条件]，此规则不适用。"

[Step 5 - 可证伪性检验]
下次什么样的失败结果，会证明这条规则是错的？
必须给出具体的可观测反例。

最终只输出合法 JSON：
{{
  "root_cause": "Step 2 结论，1句",
  "counterfactual": "Step 3 替代方案，1句",
  "rule_learned": "Step 4 的完整规则",
  "falsification_condition": "Step 5 的具体反例条件",
  "domain_tag": "coding|writing|research|tool_use|ops",
  "confidence_delta": 0.1 或 -0.2
}}

补充要求：
1. 不要输出复盘摘要，只输出最关键的一个决策拐点
2. 规则必须具体、可执行、可迁移，不能是空泛正确话
3. 优先提炼能改变下次流程的规则，而不是对本次输出风格做评价
4. 若结果明显未完成、拒绝、跑偏或没有解决请求，confidence_delta 必须为 -0.2
5. 若结果基本达到目标且规则具有复用价值，confidence_delta 才能为 0.1
""".strip()

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个严格输出 JSON 的第三方审计员。你会在内部做深入推理，但绝不暴露中间思考。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "stream": False,
    }
    req = urllib.request.Request(
        f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"critique model HTTP error {exc.code}: {detail[:500]}") from exc
    except Exception as exc:
        raise RuntimeError(f"critique model request failed: {exc}") from exc

    content = (
        payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise RuntimeError(f"critique model did not return JSON: {content[:500]}")
    return parse_critique_json(match.group(0))


def should_skip_auto_critique(user_message: str, assistant_response: str) -> tuple[bool, str]:
    msg = normalize_whitespace(user_message)
    reply = normalize_whitespace(assistant_response)
    if not msg or not reply:
        return True, "empty_message"
    if msg.startswith("/"):
        return True, "slash_command"
    if len(msg) < 8:
        return True, "too_short"
    if any(token in msg.lower() for token in ["谢谢", "好的", "收到", "嗯嗯", "ok", "thanks"]):
        if len(msg) <= 20:
            return True, "small_talk"
    return False, ""


def assess_rule_quality(rule: str) -> tuple[bool, str]:
    text = normalize_whitespace(rule)
    if not text:
        return False, "empty_rule"
    if len(text) < 12:
        return False, "too_short"
    structured_condition = bool(
        re.search(r"在[^\s，。；;]{2,}(下|时|后|中)", text)
        or re.search(r"若[^\s，。；;]{2,}", text)
        or re.search(r"当[^\s，。；;]{2,}", text)
        or re.search(r"如果[^\s，。；;]{2,}", text)
    )
    has_condition = structured_condition or any(
        token in text
        for token in [
            "遇到",
            "连续",
            "搜索",
            "提取失败",
            "命中",
            "任务",
            "请求",
            "场景",
        ]
    )
    has_action = any(token in text for token in ["应", "优先", "不要", "必须", "立即", "改用", "切换", "加入", "限制", "校验", "标注", "验证"])
    if not has_condition:
        return False, "missing_condition"
    if not has_action:
        return False, "missing_action"
    return True, "ok"


def review_rule_candidate(
    critique: dict[str, Any],
    user_message: str,
    assistant_response: str,
    model: str | None,
    base_url: str | None,
    timeout: int,
) -> dict[str, Any]:
    model = model or load_runtime_model()[0]
    base_url = base_url or load_runtime_model()[1]
    prompt = f"""
任务: {user_message}
执行结果: {assistant_response}

当前候选反思 JSON:
{json.dumps(critique, ensure_ascii=False)}

你是唯一的规则闸门。请判断这条规则应不应该进入长期记忆。

接受标准只有四条：
1. 这是一条面向未来任务的操作规则，不是本次任务摘要
2. 规则同时包含触发条件和动作建议
3. 规则足够具体，能指导下一次类似任务
4. 规则不是元建议，例如“答不上来就去搜索”这类空泛策略

只输出 JSON：
{{
  "accept": true,
  "normalized_rule": "若接受，给出最终规则；若拒绝，保持原句或留空",
  "domain_tag": "coding|writing|research|tool_use|ops",
  "reason": "一句简短理由"
}}
""".strip()
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个严格的规则审查器，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "stream": False,
    }
    req = urllib.request.Request(
        f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise RuntimeError(f"review model did not return JSON: {content[:500]}")
    data = json.loads(match.group(0))
    return {
        "accept": bool(data.get("accept", False)),
        "normalized_rule": normalize_whitespace(str(data.get("normalized_rule", "") or "")),
        "domain_tag": normalize_whitespace(str(data.get("domain_tag", "") or critique.get("domain_tag", ""))).lower(),
        "reason": normalize_whitespace(str(data.get("reason", "") or "")),
    }


def auto_critique(
    user_message: str,
    assistant_response: str,
    session_id: str | None,
    success: str | None,
    process_evidence: str | None,
    model: str | None,
    base_url: str | None,
    timeout: int,
) -> dict[str, Any]:
    skip, reason = should_skip_auto_critique(user_message, assistant_response)
    if skip:
        return {"skipped": True, "reason": reason}
    critique = call_local_model_for_critique(
        user_message=user_message,
        assistant_response=assistant_response,
        success=success,
        model=model,
        base_url=base_url,
        timeout=timeout,
    )
    ok, reason = assess_rule_quality(str(critique.get("rule_learned", "")))
    if not ok:
        return {"skipped": True, "reason": f"low_quality_rule:{reason}", "critique": critique}
    try:
        review = review_rule_candidate(
            critique=critique,
            user_message=user_message,
            assistant_response=assistant_response,
            model=model,
            base_url=base_url,
            timeout=timeout,
        )
    except Exception as exc:
        return {"skipped": True, "reason": f"review_failed:{exc}", "critique": critique}
    if not review["accept"]:
        return {"skipped": True, "reason": f"rejected_by_reviewer:{review['reason']}", "critique": critique}
    if review["normalized_rule"]:
        critique["rule_learned"] = review["normalized_rule"]
    if review["domain_tag"]:
        critique["domain_tag"] = review["domain_tag"]
    stored = store_critique(
        task=user_message,
        result=assistant_response[:1200],
        success=(str(success).lower() in {"1", "true", "yes", "y"}) if success is not None else bool(critique["confidence_delta"] > 0),
        critique_raw=json.dumps(critique, ensure_ascii=False),
        session_id=session_id,
        evidence=process_evidence,
        model=model,
        base_url=base_url,
        timeout=timeout,
    )
    return {"skipped": False, "critique": critique, "stored": stored}


def reconcile_database(model: str | None, base_url: str | None, timeout: int) -> dict[str, Any]:
    merged = 0
    deleted = 0
    with connect_db() as conn:
        conn.executescript(SCHEMA_SQL)
        rows = serialize_rows(conn.execute("SELECT * FROM memories ORDER BY domain_tag, id").fetchall())
        for i, row in enumerate(rows):
            for other in rows[i + 1:]:
                if row.domain_tag != other.domain_tag:
                    continue
                if row.id == other.id:
                    continue
                if not are_rules_equivalent(row.rule_learned, other.rule_learned):
                    continue
                keep_rule = choose_better_rule(row.rule_learned, other.rule_learned)
                keep_id = row.id if keep_rule == row.rule_learned else other.id
                drop_id = other.id if keep_id == row.id else row.id
                keep_conf = clamp(max(row.confidence, other.confidence) + 0.05)
                conn.execute(
                    "UPDATE memories SET rule_learned = ?, confidence = ? WHERE id = ?",
                    (keep_rule, keep_conf, keep_id),
                )
                conn.execute("DELETE FROM memories WHERE id = ?", (drop_id,))
                merged += 1
        deleted = cleanup(conn)
        conn.commit()
    return {"merged_pairs": merged, "conflicted_pairs": 0, "deleted_stale": deleted}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal evolution memory manager for Hermes.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Initialize the SQLite memory database.")

    p_retrieve = sub.add_parser("retrieve", help="Retrieve relevant memories for a task.")
    p_retrieve.add_argument("--task", required=True)
    p_retrieve.add_argument("--top-k", type=int, default=5)
    p_retrieve.add_argument("--session-id")
    p_retrieve.add_argument("--json", action="store_true")

    p_store = sub.add_parser("store-critique", help="Store critique and update confidence.")
    p_store.add_argument("--task", required=True)
    p_store.add_argument("--result", required=True)
    p_store.add_argument("--success", required=True)
    p_store.add_argument("--critique-json", required=True)
    p_store.add_argument("--session-id")
    p_store.add_argument("--evidence")

    p_report = sub.add_parser("report", help="Show evolution metrics.")
    p_report.add_argument("--days", type=int, default=7)
    p_report.add_argument("--json", action="store_true")

    p_cleanup = sub.add_parser("cleanup", help="Delete stale memories.")
    p_cleanup.add_argument("--json", action="store_true")

    p_backup = sub.add_parser("backup", help="Back up the SQLite database.")
    p_backup.add_argument("--json", action="store_true")

    p_auto = sub.add_parser("auto-critique", help="Generate critique via local model and store it.")
    p_auto.add_argument("--user-message", required=True)
    p_auto.add_argument("--assistant-response", required=True)
    p_auto.add_argument("--session-id")
    p_auto.add_argument("--success")
    p_auto.add_argument("--process-evidence")
    p_auto.add_argument("--model")
    p_auto.add_argument("--base-url")
    p_auto.add_argument("--timeout", type=int, default=90)
    p_auto.add_argument("--json", action="store_true")

    p_reconcile = sub.add_parser("reconcile", help="Merge similar rules and demote conflicting ones.")
    p_reconcile.add_argument("--model")
    p_reconcile.add_argument("--base-url")
    p_reconcile.add_argument("--timeout", type=int, default=120)
    p_reconcile.add_argument("--json", action="store_true")

    return parser.parse_args(argv)


def parse_success(raw: str) -> bool:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y"}:
        return True
    if value in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"invalid success flag: {raw}")


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.command == "init-db":
        payload = init_db()
    elif args.command == "retrieve":
        payload = retrieve(args.task, args.top_k, args.session_id, args.json)
    elif args.command == "store-critique":
        payload = store_critique(
            args.task,
            args.result,
            parse_success(args.success),
            args.critique_json,
            args.session_id,
            evidence=args.evidence,
        )
    elif args.command == "report":
        payload = report(args.days, args.json)
    elif args.command == "cleanup":
        deleted = cleanup()
        payload = {"deleted": deleted}
        if not args.json:
            payload["text"] = f"Deleted {deleted} stale memories"
    elif args.command == "backup":
        payload = backup()
    elif args.command == "auto-critique":
        payload = auto_critique(
            user_message=args.user_message,
            assistant_response=args.assistant_response,
            session_id=args.session_id,
            success=args.success,
            process_evidence=args.process_evidence,
            model=args.model,
            base_url=args.base_url,
            timeout=args.timeout,
        )
    elif args.command == "reconcile":
        payload = reconcile_database(args.model, args.base_url, args.timeout)
        if not args.json:
            payload["text"] = (
                f"Merged {payload['merged_pairs']} similar rule pairs, "
                f"demoted {payload['conflicted_pairs']} conflicting pairs, "
                f"deleted {payload['deleted_stale']} stale rules"
            )
    else:
        raise AssertionError("unreachable")

    if isinstance(payload, dict) and "text" in payload and not getattr(args, "json", False):
        print(payload["text"])
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
