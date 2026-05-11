# Minimal Evolution System

让 Hermes Agent 记住“做事经验”的一个小系统。
A small system that helps Hermes Agent remember practical lessons from past work.

---

## 项目理念 / Philosophy

很多人第一次用 Agent 时会遇到同一个问题：这次你纠正了它，下次它还是可能犯同样的错。

比如你提醒它：“读论文前先确认标题和作者。”这轮它照做了。过几天你让它读另一篇论文，它可能又先猜、再补救。

Minimal Evolution System 想解决的就是这个问题。

Many people run into the same problem when using an agent: you correct it once, but it may repeat the same mistake in a later task.

For example, you tell it: "Before reading a paper, confirm the title and authors first." It follows the rule in this session. A few days later, on another paper, it may guess first and fix the mistake later.

Minimal Evolution System is built for that gap.

它不训练模型，也不改变模型参数。它只是给 Hermes 加一层很朴素的“经验本”：每次任务结束后，让 Agent 总结一条以后还会用得上的规则，并保存这条规则来自哪次任务、什么失败现场、什么反事实做法；下次遇到相似任务时，再把相关规则和证据提前拿出来提醒它。

It does not train the model or change model weights. It adds a simple "experience notebook" to Hermes: after a task finishes, the agent extracts one reusable rule and stores where that rule came from, what failed, and what would have worked instead. Before a similar future task, it retrieves the relevant rule together with supporting evidence.

一句话：

In one sentence:

> 不是让模型变成另一个模型，而是让它少重复同一种错误。
> It does not turn the model into a different model. It helps the model repeat fewer mistakes.

---

## 适合谁 / Who This Is For

这个项目适合已经在使用 Hermes Agent，但希望它更稳定、更像“越用越顺手”的开发者。

This project is for developers who already use Hermes Agent and want it to become more stable and easier to work with over time.

你不需要懂机器学习，也不需要训练模型。你只需要知道：

You do not need machine learning knowledge. You do not need to train a model. You only need to know:

- Hermes 是你正在用的 Agent。
  Hermes is the agent you are already using.
- 这个项目会给 Hermes 增加几个本地脚本。
  This project adds a few local scripts to Hermes.
- 它会把一些可复用经验存到你自己的电脑里。
  It stores reusable lessons on your own machine.
- 你可以随时查看、备份、清理这些经验。
  You can inspect, back up, and clean those lessons at any time.

它尤其适合这些场景：

It is especially useful when:

- 你经常让 Agent 写代码、读文档、读论文、查资料。
  You often ask an agent to write code, read documents, read papers, or do research.
- 你发现 Agent 经常在同类任务里重复犯错。
  You notice the agent repeating the same kind of mistake.
- 你不想每次都重新提醒“不要这样，要那样”。
  You do not want to repeat the same instruction again and again.
- 你想要一个能看见、能备份、能删除的本地经验库。
  You want a local memory store that is visible, backed up, and removable.

---

## 它解决什么问题 / What Problem It Solves

普通 Agent 的一次对话通常是短期记忆。你在这轮对话里纠正它，它能听懂；但这个纠正很难稳定进入下一次任务。

Most agent conversations are short-term memory. The agent can follow your correction in the current session, but that correction often does not reliably carry into future work.

Minimal Evolution System 做了三件小事：

Minimal Evolution System does three simple things:

1. 任务开始前，先查本地经验库，看有没有相关规则。
   Before a task starts, it checks the local experience database for relevant rules.
2. 任务结束后，回看这次任务，提炼一条可复用规则。
   After a task ends, it reviews the task and extracts one reusable rule.
3. 用 `/evo-report` 让你看到系统到底记住了什么。
   With `/evo-report`, you can see what the system has actually remembered.

举个例子。

Example:

你让 Agent 读一篇 arXiv 论文。第一次它没有确认论文标题，直接根据链接猜内容，结果猜错了。你纠正它。

You ask the agent to read an arXiv paper. The first time, it does not confirm the paper title and guesses based on the link. It guesses wrong. You correct it.

这套系统会尝试沉淀出类似规则：

The system may store a rule like:

```text
在阅读 arXiv/PDF 论文时，应先确认标题、作者和年份，再做主题判断；若用户只要求泛泛介绍论文库，此规则不适用。
```

English meaning:

```text
When reading an arXiv/PDF paper, first confirm the title, authors, and year before judging the topic; if the user only asks for a general introduction to a paper database, this rule does not apply.
```

下次你再让它读论文，这条规则会提前进入上下文，提醒它别再跳过元数据确认。

Next time you ask it to read a paper, this rule is injected before the model answers, reminding it not to skip metadata verification.

---

## 它不是什么 / What It Is Not

先说清楚边界很重要。

It is important to be clear about the boundaries.

Minimal Evolution System 不是：

Minimal Evolution System is not:

- 不是模型微调。
  It is not model fine-tuning.
- 不是向量数据库。
  It is not a vector database.
- 不是知识库问答系统。
  It is not a knowledge-base QA system.
- 不是云同步服务。
  It is not a cloud sync service.
- 不是让 Agent 自动变聪明的魔法。
  It is not magic that automatically makes an agent smart.

它更像一个很小的“经验账本”：

It is closer to a small experience ledger:

- 记录规则和错误现场。
  Record rules and the failure episodes behind them.
- 按任务匹配规则。
  Match rules to tasks.
- 根据使用结果调整规则置信度。
  Adjust rule confidence over time.
- 提供报告让人检查。
  Provide reports for human inspection.

这也是它的优点：简单、本地、可读、可删。

That is also the advantage: simple, local, readable, and removable.

---

## 安装前准备 / Requirements

你需要：

You need:

- 已安装并能正常运行 Hermes Agent。
  Hermes Agent installed and working.
- 系统里有 `python3`。
  `python3` available on your system.
- Python 能使用 SQLite，普通 Python 一般都自带。
  Python SQLite support, which is included in normal Python builds.
- 推荐有 `PyYAML`，这样安装脚本可以自动修改 Hermes 配置。
  `PyYAML` is recommended so the installer can edit Hermes config automatically.

检查命令：

Check:

```bash
hermes --version
python3 --version
python3 -c "import sqlite3; print('sqlite ok')"
python3 -c "import yaml; print('yaml ok')"
```

如果最后一条失败，也可以安装，只是需要手动复制配置片段。

If the last command fails, you can still install manually by copying the config snippet.

---

## 快速安装 / Quick Install

进入项目目录：

Go into the project directory:

```bash
cd minimal-evolution-system
```

运行安装脚本：

Run the installer:

```bash
./install.sh
```

安装脚本会做这些事：

The installer will:

1. 把 skill 复制到 `~/.hermes/skills/minimal-evolution-system/`。
   Copy the skill to `~/.hermes/skills/minimal-evolution-system/`.
2. 把两个 hook 脚本复制到 `~/.hermes/agent-hooks/`。
   Copy two hook scripts to `~/.hermes/agent-hooks/`.
3. 创建本地数据库 `~/.hermes/evolution-system/memory.db`。
   Create the local database at `~/.hermes/evolution-system/memory.db`.
4. 自动备份你的 Hermes 配置文件。
   Back up your Hermes config file.
5. 在 Hermes 配置里加入 `/evo-report` 等命令。
   Add commands such as `/evo-report` to Hermes config.
6. 在 Hermes 配置里加入任务前后自动运行的 hook。
   Add hooks that run before and after tasks.

安装后运行：

After installation, run:

```bash
hermes hooks doctor
```

这个命令会检查 hook 是否存在、是否被批准、是否能正常运行。

This checks whether the hooks exist, are approved, and can run successfully.

如果你在服务器上安装，或者你明确信任这些 hook，也可以直接运行：

If you are installing on a server or already trust these hooks:

```bash
./install.sh --accept-hooks
```

---

## 安装后怎么确认成功 / Verify Installation

打开 Hermes：

Start Hermes:

```bash
hermes
```

输入：

Type:

```text
/evo-report
```

第一次运行时，规则数可能是 0。这是正常的。

The first report may show 0 rules. That is normal.

你会看到类似：

You should see something like:

```text
DB: /home/user/.hermes/evolution-system/memory.db
总规则数: 0
高质量规则数(confidence>0.7): 0
低质量待淘汰规则数(confidence<0.1): 0
近7天新增规则数: 0

领域分布:

复用最多的规则:
```

再做一个小任务，然后过一会儿再运行 `/evo-report`，就可以看到是否有规则沉淀。

Run a small task, then run `/evo-report` again later to see whether any rule was stored.

日志位置：

Log location:

```text
~/.hermes/evolution-system/logs/auto_critique.log
```

---

## 日常怎么用 / Daily Usage

大多数时候你不需要特别操作。

Most of the time, you do not need to do anything special.

正常和 Hermes 对话即可。系统会在后台做两件事：

Use Hermes normally. The system does two things in the background:

- 任务开始前：找相关历史规则。
  Before a task: find relevant historical rules.
- 任务结束后：尝试总结新的规则。
  After a task: try to summarize a new rule.

你只需要偶尔看报告：

You only need to check the report occasionally:

```text
/evo-report
```

常用命令：

Common commands:

```text
/evo-report       查看当前规则统计 / Show current rule statistics
/evo-report-json  输出 JSON 版本报告 / Output report as JSON
/evo-backup       备份数据库 / Back up the database
/evo-clean        删除低置信度规则 / Delete low-confidence rules
/evo-reconcile    合并相似规则 / Merge similar rules
```

---

## 一个完整例子 / Full Example

假设你经常让 Agent 读论文。

Suppose you often ask the agent to read papers.

你第一次发现它犯错：

The first time, you notice a mistake:

```text
你刚才没有确认论文标题，直接根据 arXiv 链接猜论文内容了。
以后读论文前先确认标题、作者、年份，再开始分析。
```

English meaning:

```text
You did not confirm the paper title. You guessed the paper content from the arXiv link.
In future paper-reading tasks, confirm title, authors, and year first, then analyze.
```

任务结束后，系统会让模型从这次过程里提炼一条规则。它可能存成：

After the task, the system asks the model to extract a reusable rule. It may store:

```text
在阅读论文任务中，应先确认标题、作者、年份和来源，再做主题判断；若用户只要求查找论文链接，此规则不适用。
```

English meaning:

```text
In paper-reading tasks, first confirm title, authors, year, and source before judging the topic; if the user only asks to find a paper link, this rule does not apply.
```

下次你说：

Next time you say:

```text
用 ljg-paper 阅读 https://arxiv.org/abs/xxxx.xxxxx
```

系统会在任务开始前查到这条规则，并提醒 Agent。

The system retrieves this rule before the task and reminds the agent.

你不需要再重复提醒。

You do not need to repeat the same correction.

---

## 这个系统怎么工作 / How It Works

如果你只想使用，可以跳过这一节。

If you only want to use the system, you can skip this section.

项目由三部分组成。

The project has three parts.

### 1. 经验数据库 / Experience Database

数据库是一个本地 SQLite 文件：

The database is a local SQLite file:

```text
~/.hermes/evolution-system/memory.db
```

里面主要有两类记录：

It mainly stores two kinds of records:

第一类是 `memories`，也就是下次要复用的规则：

The first kind is `memories`, the reusable rules for future tasks:

- `domain_tag`：规则属于哪个领域，比如 `coding`、`research`、`writing`。
  The domain of the rule, such as `coding`, `research`, or `writing`.
- `rule_learned`：真正要复用的规则。
  The reusable rule.
- `what_worked`：这次什么做法有效。
  What worked in this task.
- `what_failed`：这次哪里失败了。
  What failed in this task.
- `confidence`：规则置信度，范围是 0 到 1。
  Confidence score from 0 to 1.
- `use_count`：这条规则被取出来用过几次。
  How many times the rule has been retrieved.

第二类是 `episodes`，也就是规则背后的错误现场：

The second kind is `episodes`, the failure episodes behind the rules:

- `task`：当时用户让 Agent 做什么。
  What the user asked the agent to do.
- `result`：当时 Agent 最终给出的结果摘要。
  A summary of the final result.
- `root_cause`：最可能的失败根因。
  The most likely root cause.
- `counterfactual`：如果重来一次，更好的做法是什么。
  What should have been done instead.
- `evidence`：过程证据，例如慢工具、错误路径、文件写入审计。
  Process evidence, such as slow tools, wrong paths, or file-write audit results.

这样做的目的，是避免系统只记住一句抽象规则，却忘了这条规则是从哪个失败场景里来的。

This prevents the system from remembering only an abstract rule while forgetting the failure case that created it.

### 2. 任务开始前的 hook / Before-Task Hook

文件：

File:

```text
hooks/evolution_pre_llm.py
```

它会在 Hermes 调用模型前运行。

It runs before Hermes calls the model.

它做的事很简单：

It does three simple things:

1. 读取当前用户任务。
   Read the current user task.
2. 去 SQLite 里找相关规则。
   Search SQLite for relevant rules.
3. 找到这些规则最近一次对应的错误现场。
   Find the latest failure episode behind those rules.
4. 把匹配到的规则和证据注入到本轮上下文。
   Inject matching rules and evidence into the current context.

如果它失败了，会返回空结果，不影响 Hermes 正常回答。

If it fails, it returns an empty result and Hermes continues normally.

### 3. 任务结束后的 hook / After-Task Hook

文件：

File:

```text
hooks/evolution_post_llm.py
```

它会在 Hermes 完成一次回答后运行。

It runs after Hermes finishes an answer.

它做的事是：

It does the following:

1. 读取用户任务和最终回答。
   Read the user task and final answer.
2. 可选地读取本轮过程摘要。
   Optionally read a short trace of the session.
3. 调用你配置的模型做一次简短审计。
   Ask your configured model to audit the task briefly.
4. 提炼一条未来可复用规则。
   Extract one future-facing reusable rule.
5. 把规则存入 `memories`。
   Store the rule in `memories`.
6. 把本次错误现场、根因、反事实和过程证据存入 `episodes`。
   Store the failure episode, root cause, counterfactual, and process evidence in `episodes`.

这一步可能会慢一点，因为它需要再调用一次模型。

This step may be slower because it calls a model again.

---

## 文件结构 / Project Layout

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

---

## 手动安装 / Manual Install

如果你不想让安装脚本修改配置，可以手动安装。

If you do not want the installer to edit your config, install manually.

复制文件：

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

初始化数据库：

Initialize the database:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py init-db
```

然后把 `examples/config-snippet.yaml` 里的内容合并到你的 Hermes 配置。

Then merge `examples/config-snippet.yaml` into your Hermes config.

查看 Hermes 配置路径：

Find your Hermes config path:

```bash
hermes config path
```

合并后运行：

After merging, run:

```bash
hermes hooks doctor
```

---

## 安装到其他 Hermes 目录 / Install Into Another Hermes Directory

Hermes 支持不同 profile。你可以通过 `HERMES_HOME` 指定安装位置：

Hermes supports different profiles. Use `HERMES_HOME` to choose the target location:

```bash
HERMES_HOME=/path/to/.hermes ./install.sh
```

也可以指定配置文件：

You can also specify the config file:

```bash
HERMES_CONFIG=/path/to/config.yaml ./install.sh
```

只复制文件、不修改配置：

Copy files only, without editing config:

```bash
./install.sh --no-config
```

---

## 命令说明 / Commands

### 查看报告 / Report

Hermes 里输入：

In Hermes:

```text
/evo-report
```

命令行直接运行：

From shell:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py report
```

### 输出 JSON 报告 / JSON Report

Hermes 里输入：

In Hermes:

```text
/evo-report-json
```

命令行直接运行：

From shell:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py report --json
```

### 备份数据库 / Backup

Hermes 里输入：

In Hermes:

```text
/evo-backup
```

备份会放在：

Backups are written to:

```text
~/.hermes/evolution-system/backups/
```

### 清理低质量规则 / Clean Low-Confidence Rules

Hermes 里输入：

In Hermes:

```text
/evo-clean
```

它会删除 `confidence < 0.1` 的规则。

It deletes rules with `confidence < 0.1`.

### 合并相似规则 / Reconcile Similar Rules

Hermes 里输入：

In Hermes:

```text
/evo-reconcile
```

当规则变多后，可以偶尔运行一次。

Run this occasionally after many rules accumulate.

---

## 模型选择 / Model Selection

这个系统默认读取 Hermes 当前配置里的模型。

By default, this system uses the model configured in Hermes.

如果你用的是本地模型，例如 Ollama，那么审计过程也会调用你的本地模型。

If you use a local model, such as Ollama, the audit step will use your local model too.

如果你觉得任务结束后卡顿，通常是因为 post hook 又调用了一次大模型。可以换一个小一点的模型专门做规则总结：

If tasks feel slow after completion, the post hook may be calling a large model again. You can use a smaller model for rule summarization:

```bash
export EVOLUTION_MODEL=qwen3:8b
export EVOLUTION_BASE_URL=http://127.0.0.1:11434/v1
```

也可以在命令里临时指定：

You can also override it per command:

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py auto-critique \
  --user-message "debug a failing test" \
  --assistant-response "fixed the fixture and verified the test" \
  --model "qwen3:8b" \
  --base-url "http://127.0.0.1:11434/v1" \
  --json
```

---

## 安全和隐私 / Security and Privacy

这个项目会给 Hermes 添加 shell hooks。意思是：Hermes 在任务开始前和结束后，会运行本地 Python 脚本。

This project adds shell hooks to Hermes. That means Hermes runs local Python scripts before and after tasks.

安装前建议你看这三个文件：

Before approving hooks, inspect:

```text
scripts/evolution_memory.py
hooks/evolution_pre_llm.py
hooks/evolution_post_llm.py
```

这个项目默认把数据放在本地：

By default, data is stored locally:

```text
~/.hermes/evolution-system/
```

它不会主动上传 `memory.db`。

It does not upload `memory.db`.

但要注意：post hook 会把“任务内容”和“最终回答”发给你配置的模型做审计。如果你的模型是远程 API，这些内容会发到远程服务。如果你处理敏感内容，建议使用本地模型，或者关闭 post hook。

Important: the post hook sends the task and final answer to your configured model for auditing. If your model endpoint is remote, that text leaves your machine. For sensitive work, use a local model or disable the post hook.

关闭 post hook 的方法：从 Hermes 配置里移除这一段：

To disable the post hook, remove this section from Hermes config:

```yaml
hooks:
  post_llm_call:
    - command: python3 ~/.hermes/agent-hooks/evolution_post_llm.py
      timeout: 90
```

---

## 性能说明 / Performance Notes

任务开始前的检索通常很快，因为只是查 SQLite。

Before-task retrieval is usually fast because it only queries SQLite.

任务结束后的审计可能慢，因为它会调用模型总结规则。

After-task auditing can be slower because it calls a model to summarize a rule.

如果你觉得慢，可以：

If it feels slow:

1. 给 `EVOLUTION_MODEL` 设置一个小模型。
   Set `EVOLUTION_MODEL` to a smaller model.
2. 增大 hook timeout。
   Increase the hook timeout.
3. 暂时关闭 post hook。
   Temporarily disable the post hook.
4. 只保留 `/evo-report` 和手动命令。
   Keep only `/evo-report` and manual commands.

---

## 常见问题 / FAQ

### `/evo-report` 不存在 / `/evo-report` Does Not Exist

先确认配置：

Check the config path:

```bash
hermes config path
```

然后看配置里是否有 `evo-report`。

Then check whether `evo-report` exists in the config.

如果没有，重新运行：

If missing, rerun:

```bash
./install.sh
```

或者手动合并：

Or manually merge:

```text
examples/config-snippet.yaml
```

### `hermes hooks doctor` 提示 hook 未批准 / Hooks Are Not Approved

运行：

Run:

```bash
hermes hooks doctor
```

按提示批准。

Approve when prompted.

无交互环境可以用：

For non-interactive environments:

```bash
hermes --accept-hooks hooks doctor
```

### hook 超时 / Hook Timeout

通常是模型太慢。

Usually this means the model is too slow.

可以换小模型：

Use a smaller model:

```bash
export EVOLUTION_MODEL=qwen3:8b
```

也可以把配置里的 `post_llm_call` timeout 从 `90` 改大：

Or increase `post_llm_call` timeout:

```yaml
hooks:
  post_llm_call:
    - command: python3 ~/.hermes/agent-hooks/evolution_post_llm.py
      timeout: 180
```

### 规则太泛 / Rules Are Too Generic

运行：

Run:

```text
/evo-reconcile
```

然后再看：

Then check:

```text
/evo-report
```

规则质量和你使用的模型有关。更好的模型通常能提炼出更具体的规则。

Rule quality depends on the model you use. Better models usually extract more specific rules.

### 想直接看数据库 / Inspect the Database Directly

```bash
sqlite3 ~/.hermes/evolution-system/memory.db '.tables'
sqlite3 ~/.hermes/evolution-system/memory.db 'select id, domain_tag, confidence, rule_learned from memories order by id desc limit 10;'
```

---

## 卸载 / Uninstall

删除安装文件：

Remove installed files:

```bash
rm -rf ~/.hermes/skills/minimal-evolution-system
rm -f ~/.hermes/agent-hooks/evolution_pre_llm.py
rm -f ~/.hermes/agent-hooks/evolution_post_llm.py
```

从 `~/.hermes/config.yaml` 删除这些配置：

Remove these entries from `~/.hermes/config.yaml`:

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

数据目录默认保留：

The data directory is left in place by default:

```text
~/.hermes/evolution-system/
```

如果你确定不需要历史规则，可以删除：

If you no longer need the rules:

```bash
rm -rf ~/.hermes/evolution-system
```

---

## 发布前检查 / Publishing Checklist

如果你要 fork 或二次发布，建议先跑：

Before forking or publishing changes, run:

```bash
python3 -m py_compile scripts/evolution_memory.py hooks/evolution_pre_llm.py hooks/evolution_post_llm.py
./install.sh --help
find . -name '__pycache__' -o -name '*.pyc' -o -name '*.db'
```

不要提交：

Do not commit:

- `memory.db`
- 日志 / logs
- 备份数据库 / database backups
- 个人 Hermes 配置 / personal Hermes config
- 会话记录 / session files

---

## License

No license is included yet. Add a license before publishing publicly if you want others to reuse, modify, or redistribute the project clearly.
