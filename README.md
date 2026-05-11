# Minimal Evolution System

让 Hermes Agent 记住“做事经验”的一个小系统。

很多人第一次用 Agent 时会遇到同一个问题：它这次被你纠正了，下次却又犯同样的错。比如你提醒它“读论文前先确认标题和作者”，这轮它照做了；过几天你再让它读另一篇论文，它可能又先猜、再补救。

Minimal Evolution System 想解决的就是这个问题。

它不训练模型，也不改变模型参数。它只是给 Hermes 加一层很朴素的“经验本”：每次任务结束后，让 Agent 总结一条以后还会用得上的规则，存到本地 SQLite 数据库里；下次遇到相似任务时，再把相关规则提前拿出来提醒它。

一句话：

> 不是让模型变成另一个模型，而是让它少重复同一种错误。

## 适合谁

这个项目适合已经在使用 Hermes Agent，但希望它更稳定、更像“越用越顺手”的开发者。

你不需要懂机器学习，也不需要训练模型。你只需要知道：

- Hermes 是你正在用的 Agent。
- 这个项目会给 Hermes 增加几个本地脚本。
- 它会把一些可复用经验存到你自己的电脑里。
- 你可以随时查看、备份、清理这些经验。

它尤其适合这些场景：

- 你经常让 Agent 写代码、读文档、读论文、查资料。
- 你发现 Agent 经常在同类任务里重复犯错。
- 你不想每次都重新提醒“不要这样，要那样”。
- 你想要一个能看见、能备份、能删除的本地经验库。

## 它解决什么问题

普通 Agent 的一次对话通常是短期记忆。你在这轮对话里纠正它，它能听懂；但这个纠正很难稳定进入下一次任务。

Minimal Evolution System 做了三件小事：

1. 任务开始前，先查本地经验库，看有没有相关规则。
2. 任务结束后，回看这次任务，提炼一条可复用规则。
3. 用 `/evo-report` 让你看到系统到底记住了什么。

举个例子。

你让 Agent 读一篇 arXiv 论文。第一次它没有确认论文标题，直接根据链接猜内容，结果猜错了。你纠正它。

这套系统会尝试沉淀出类似规则：

```text
在阅读 arXiv/PDF 论文时，应先确认标题、作者和年份，再做主题判断；若用户只要求泛泛介绍论文库，此规则不适用。
```

下次你再让它读论文，这条规则会提前进入上下文，提醒它别再跳过元数据确认。

## 它不是什么

先说清楚边界很重要。

Minimal Evolution System 不是：

- 不是模型微调。
- 不是向量数据库。
- 不是知识库问答系统。
- 不是云同步服务。
- 不是让 Agent 自动变聪明的魔法。

它更像一个很小的“经验账本”：

- 记录规则。
- 按任务匹配规则。
- 根据使用结果调整规则置信度。
- 提供报告让人检查。

这也是它的优点：简单、本地、可读、可删。

## 安装前准备

你需要：

- 已安装并能正常运行 Hermes Agent。
- 系统里有 `python3`。
- Python 能使用 SQLite，普通 Python 一般都自带。
- 推荐有 `PyYAML`，这样安装脚本可以自动修改 Hermes 配置。

检查命令：

```bash
hermes --version
python3 --version
python3 -c "import sqlite3; print('sqlite ok')"
python3 -c "import yaml; print('yaml ok')"
```

如果最后一条失败，也可以安装，只是需要手动复制配置片段。

## 快速安装

进入项目目录：

```bash
cd minimal-evolution-system
```

运行安装脚本：

```bash
./install.sh
```

安装脚本会做这些事：

1. 把 skill 复制到 `~/.hermes/skills/minimal-evolution-system/`。
2. 把两个 hook 脚本复制到 `~/.hermes/agent-hooks/`。
3. 创建本地数据库 `~/.hermes/evolution-system/memory.db`。
4. 自动备份你的 Hermes 配置文件。
5. 在 Hermes 配置里加入 `/evo-report` 等命令。
6. 在 Hermes 配置里加入任务前后自动运行的 hook。

安装后运行：

```bash
hermes hooks doctor
```

这个命令会检查 hook 是否存在、是否被批准、是否能正常运行。

如果你在服务器上安装，或者你明确信任这些 hook，也可以直接运行：

```bash
./install.sh --accept-hooks
```

## 安装后怎么确认成功

打开 Hermes：

```bash
hermes
```

输入：

```text
/evo-report
```

第一次运行时，规则数可能是 0。这是正常的。

你会看到类似：

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

日志位置：

```text
~/.hermes/evolution-system/logs/auto_critique.log
```

## 日常怎么用

大多数时候你不需要特别操作。

正常和 Hermes 对话即可。系统会在后台做两件事：

- 任务开始前：找相关历史规则。
- 任务结束后：尝试总结新的规则。

你只需要偶尔看报告：

```text
/evo-report
```

常用命令：

```text
/evo-report       查看当前规则统计
/evo-report-json  输出 JSON 版本报告
/evo-backup       备份数据库
/evo-clean        删除低置信度规则
/evo-reconcile    合并相似规则
```

## 一个完整例子

假设你经常让 Agent 读论文。

你第一次发现它犯错：

```text
你刚才没有确认论文标题，直接根据 arXiv 链接猜论文内容了。
以后读论文前先确认标题、作者、年份，再开始分析。
```

任务结束后，系统会让模型从这次过程里提炼一条规则。它可能存成：

```text
在阅读论文任务中，应先确认标题、作者、年份和来源，再做主题判断；若用户只要求查找论文链接，此规则不适用。
```

下次你说：

```text
用 ljg-paper 阅读 https://arxiv.org/abs/xxxx.xxxxx
```

系统会在任务开始前查到这条规则，并提醒 Agent。

你不需要再重复提醒。

## 这个系统怎么工作

如果你只想使用，可以跳过这一节。

项目由三部分组成。

### 1. 经验数据库

数据库是一个本地 SQLite 文件：

```text
~/.hermes/evolution-system/memory.db
```

里面主要保存这些字段：

- `domain_tag`：规则属于哪个领域，比如 `coding`、`research`、`writing`。
- `rule_learned`：真正要复用的规则。
- `what_worked`：这次什么做法有效。
- `what_failed`：这次哪里失败了。
- `confidence`：规则置信度，范围是 0 到 1。
- `use_count`：这条规则被取出来用过几次。

### 2. 任务开始前的 hook

文件：

```text
hooks/evolution_pre_llm.py
```

它会在 Hermes 调用模型前运行。

它做的事很简单：

1. 读取当前用户任务。
2. 去 SQLite 里找相关规则。
3. 把匹配到的规则注入到本轮上下文。

如果它失败了，会返回空结果，不影响 Hermes 正常回答。

### 3. 任务结束后的 hook

文件：

```text
hooks/evolution_post_llm.py
```

它会在 Hermes 完成一次回答后运行。

它做的事是：

1. 读取用户任务和最终回答。
2. 可选地读取本轮过程摘要。
3. 调用你配置的模型做一次简短审计。
4. 提炼一条未来可复用规则。
5. 存入 SQLite。

这一步可能会慢一点，因为它需要再调用一次模型。

## 文件结构

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

## 手动安装

如果你不想让安装脚本修改配置，可以手动安装。

复制文件：

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

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py init-db
```

然后把 `examples/config-snippet.yaml` 里的内容合并到你的 Hermes 配置。

查看 Hermes 配置路径：

```bash
hermes config path
```

合并后运行：

```bash
hermes hooks doctor
```

## 安装到其他 Hermes 目录

Hermes 支持不同 profile。你可以通过 `HERMES_HOME` 指定安装位置：

```bash
HERMES_HOME=/path/to/.hermes ./install.sh
```

也可以指定配置文件：

```bash
HERMES_CONFIG=/path/to/config.yaml ./install.sh
```

只复制文件、不修改配置：

```bash
./install.sh --no-config
```

## 命令说明

### 查看报告

Hermes 里输入：

```text
/evo-report
```

命令行直接运行：

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py report
```

### 输出 JSON 报告

Hermes 里输入：

```text
/evo-report-json
```

命令行直接运行：

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py report --json
```

### 备份数据库

Hermes 里输入：

```text
/evo-backup
```

备份会放在：

```text
~/.hermes/evolution-system/backups/
```

### 清理低质量规则

Hermes 里输入：

```text
/evo-clean
```

它会删除 `confidence < 0.1` 的规则。

### 合并相似规则

Hermes 里输入：

```text
/evo-reconcile
```

当规则变多后，可以偶尔运行一次。

## 模型选择

这个系统默认读取 Hermes 当前配置里的模型。

如果你用的是本地模型，例如 Ollama，那么审计过程也会调用你的本地模型。

如果你觉得任务结束后卡顿，通常是因为 post hook 又调用了一次大模型。可以换一个小一点的模型专门做规则总结：

```bash
export EVOLUTION_MODEL=qwen3:8b
export EVOLUTION_BASE_URL=http://127.0.0.1:11434/v1
```

也可以在命令里临时指定：

```bash
python3 ~/.hermes/skills/minimal-evolution-system/scripts/evolution_memory.py auto-critique \
  --user-message "debug a failing test" \
  --assistant-response "fixed the fixture and verified the test" \
  --model "qwen3:8b" \
  --base-url "http://127.0.0.1:11434/v1" \
  --json
```

## 安全和隐私

这个项目会给 Hermes 添加 shell hooks。意思是：Hermes 在任务开始前和结束后，会运行本地 Python 脚本。

安装前建议你看这三个文件：

```text
scripts/evolution_memory.py
hooks/evolution_pre_llm.py
hooks/evolution_post_llm.py
```

这个项目默认把数据放在本地：

```text
~/.hermes/evolution-system/
```

它不会主动上传 `memory.db`。

但要注意：post hook 会把“任务内容”和“最终回答”发给你配置的模型做审计。如果你的模型是远程 API，这些内容会发到远程服务。如果你处理敏感内容，建议使用本地模型，或者关闭 post hook。

关闭 post hook 的方法：从 Hermes 配置里移除这一段：

```yaml
hooks:
  post_llm_call:
    - command: python3 ~/.hermes/agent-hooks/evolution_post_llm.py
      timeout: 90
```

## 性能说明

任务开始前的检索通常很快，因为只是查 SQLite。

任务结束后的审计可能慢，因为它会调用模型总结规则。

如果你觉得慢，可以：

1. 给 `EVOLUTION_MODEL` 设置一个小模型。
2. 增大 hook timeout。
3. 暂时关闭 post hook。
4. 只保留 `/evo-report` 和手动命令。

## 常见问题

### `/evo-report` 不存在

先确认配置：

```bash
hermes config path
```

然后看配置里是否有 `evo-report`。

如果没有，重新运行：

```bash
./install.sh
```

或者手动合并：

```text
examples/config-snippet.yaml
```

### `hermes hooks doctor` 提示 hook 未批准

运行：

```bash
hermes hooks doctor
```

按提示批准。

无交互环境可以用：

```bash
hermes --accept-hooks hooks doctor
```

### hook 超时

通常是模型太慢。

可以换小模型：

```bash
export EVOLUTION_MODEL=qwen3:8b
```

也可以把配置里的 `post_llm_call` timeout 从 `90` 改大：

```yaml
hooks:
  post_llm_call:
    - command: python3 ~/.hermes/agent-hooks/evolution_post_llm.py
      timeout: 180
```

### 规则太泛

运行：

```text
/evo-reconcile
```

然后再看：

```text
/evo-report
```

规则质量和你使用的模型有关。更好的模型通常能提炼出更具体的规则。

### 想直接看数据库

```bash
sqlite3 ~/.hermes/evolution-system/memory.db '.tables'
sqlite3 ~/.hermes/evolution-system/memory.db 'select id, domain_tag, confidence, rule_learned from memories order by id desc limit 10;'
```

## 卸载

删除安装文件：

```bash
rm -rf ~/.hermes/skills/minimal-evolution-system
rm -f ~/.hermes/agent-hooks/evolution_pre_llm.py
rm -f ~/.hermes/agent-hooks/evolution_post_llm.py
```

从 `~/.hermes/config.yaml` 删除这些配置：

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

```text
~/.hermes/evolution-system/
```

如果你确定不需要历史规则，可以删除：

```bash
rm -rf ~/.hermes/evolution-system
```

## 发布前检查

如果你要 fork 或二次发布，建议先跑：

```bash
python3 -m py_compile scripts/evolution_memory.py hooks/evolution_pre_llm.py hooks/evolution_post_llm.py
./install.sh --help
find . -name '__pycache__' -o -name '*.pyc' -o -name '*.db'
```

不要提交：

- `memory.db`
- 日志
- 备份数据库
- 个人 Hermes 配置
- 会话记录

## License

No license is included yet. Add a license before publishing publicly if you want others to reuse, modify, or redistribute the project clearly.
