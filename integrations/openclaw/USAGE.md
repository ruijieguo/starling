# Starling 记忆插件 · 使用指南（OpenClaw 用户视角）

> 这份文档是给**使用** Starling 记忆的人看的——你想让自己的 OpenClaw agent
> 拥有跨会话的长期记忆。怎么搭建环境（dashboard、docker、构建）请看
> [`README.md`](README.md)；这里只讲**装好之后你怎么用**。

---

## 它给你带来什么

装上这个插件后，你的 OpenClaw agent 不再是"聊完就忘"。它获得一块**长期记忆**：

- **跨会话记住。** 今天告诉它的事，下次开新对话它还记得。
- **结构化的认知记忆，不是流水账。** Starling 把对话沉淀成"谁-相信-什么"的
  结构化事实（statement），而不是把整段聊天记录堆进一个 Markdown 文件。它能
  区分谁说的、是不是还成立、有没有被后来的话推翻。
- **自动工作，也能手动指挥。** 默认情况下它会自动回忆相关记忆、自动沉淀要点；
  你也可以在对话里直接让它"记住 / 找一下 / 忘掉"。

和 OpenClaw 自带的 Markdown 记忆（memory-core）相比：自带的是 agent 自己写
日记文件；Starling 是一个真正的记忆引擎，带语义检索、巩固、冲突处理。

---

## 开始之前（确认装好了）

你需要两样东西在运行：

1. **Starling dashboard**（记忆的"大脑"，跑在你的机器上）。
2. **OpenClaw + 本插件**（占据 `plugins.slots.memory` 槽）。

搭建步骤见 [`README.md` 的 Quick start](README.md#quick-start-docker-integration-5-steps)。
确认装好的一句话检查：

```bash
openclaw plugins inspect starling
# 看到 Status: loaded 就说明记忆已接通
```

> 关键前提：dashboard 必须**配好 embedder**（在 `~/.starling/starling.json` 里），
> 否则"按意思搜索"不工作。没配 embedder 时记忆能存进去，但搜不准。

---

## 你的 agent 现在会自动做两件事

这两件默认就开着，你**什么都不用做**：

### 1. 自动回忆（auto-recall）
每次你开始和 agent 说话，插件会先去 Starling 取一份"和当前相关的记忆"，悄悄
塞进 agent 的上下文。效果是：agent 像"想起了"你们以前聊过的相关内容，回答更
连贯，不用你每次重复背景。

### 2. 自动沉淀（auto-capture）
当一段对话变长、OpenClaw 准备压缩历史时，插件会把其中值得长期保留的内容写进
Starling。效果是：重要的事不会随着对话被压缩而丢失。

> 想关掉？把 `STARLING_AUTO_RECALL` / `STARLING_AUTO_CAPTURE` 设成 `false`
> （见[配置](#配置你关心的几项)）。

---

## 你可以主动让 agent 做的三件事

你不需要记任何命令——**用自然语言跟 agent 说就行**，agent 会调用对应的记忆工具。

### 记住一件事 → agent 调 `memory_store`
```
你：记一下，我习惯用 pnpm 而不是 npm。
agent：好的，已经记住你偏好用 pnpm。   （它在后台调了 memory_store）
```

### 回忆 → agent 调 `memory_search`
```
你：我之前说过我用哪个包管理器来着？
agent：你提过你习惯用 pnpm。           （它在后台调了 memory_search）
```

### 忘记 → agent 调 `memory_forget`
```
你：忘掉我包管理器的偏好吧，我换 bun 了。
agent：好的，已经把旧的偏好移除了。     （它在后台调了 memory_forget；
       底层是"逻辑删除"——记录转入 forgotten 态，不再被检索）
```

> 这三个工具（`memory_store` / `memory_search` / `memory_forget`）也会出现在
> agent 的工具列表里，agent 会按需自己调用，你通常不用点名。

---

## 怎么看自己的记忆

记忆存在 **Starling dashboard**（不在 OpenClaw）。三种查看方式：

**A. 浏览器打开 dashboard**（最直观）
启动 dashboard 时终端会打印一行 `http://127.0.0.1:<port>/#token=...`，直接打开，
在 Statements 面板里看所有记忆、过滤、看详情。

**B. 命令行查一条**
```bash
# 把 TOKEN 和 PORT 换成你自己的
curl -s "http://127.0.0.1:8799/api/statements?limit=20" \
  -H "Authorization: Bearer $STARLING_TOKEN" | python3 -m json.tool
```

**C. 自己搜一下**（验证"存进去了、搜得到"）
```bash
curl -s -X POST "http://127.0.0.1:8799/api/recall" \
  -H "Authorization: Bearer $STARLING_TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"包管理器","k":5,"holder":"agent"}' | python3 -m json.tool
```
> 注意那个 `"holder":"agent"`：记忆是按"持有者"分隔的，你手动搜时要带上和
> agent 写入时一样的 holder（默认 `agent`），否则搜不到。插件自己搜时会自动
> 带，这只在你手动调 API 时需要。

---

## 三个实际场景

**场景一·记住你的偏好和习惯**
你在不同对话里陆续告诉 agent：你用 pnpm、喜欢简洁的回答、时区在 UTC+8。
以后每次对话，agent 都会带着这些背景，不用你重复。

**场景二·积累一个项目的上下文**
你和 agent 一起做一个项目，过程中提到的决定、约定、踩过的坑，都被自动沉淀。
几天后回来，agent 还记得"我们当时为什么这么定"。

**场景三·更正过时的信息**
你之前说"数据库用 SQLite"，后来改成 Postgres。你直接跟 agent 说改了，它会
更新记忆；旧的不会再干扰回忆。（Starling 有冲突/再巩固机制处理这种更新。）

---

## 配置你关心的几项

这些通过环境变量设置（docker 用法见 README）。从使用者角度，你主要会动这几个：

| 设置 | 默认 | 你为什么会改它 |
| --- | --- | --- |
| `STARLING_AUTO_RECALL` | `true` | 不想让它自动往上下文塞记忆时设 `false` |
| `STARLING_AUTO_CAPTURE` | `true` | 不想自动沉淀对话时设 `false`（改成只手动 `memory_store`） |
| `STARLING_HOLDER` | `agent` | **区分不同 agent 的记忆**：给每个 agent 不同的 holder，它们的记忆就互不串（详见下） |
| `STARLING_TENANT` | `openclaw` | **隔离不同项目/用户**：不同 tenant 的记忆完全分开 |

**关于 holder（谁的记忆）：** 默认所有记忆都归在 `agent` 这个持有者名下，存和取
用同一个，所以开箱即用。如果你跑多个 agent 想让它们记忆分开，给每个 agent 配
不同的 `STARLING_HOLDER`——插件会保证它存和取都用自己的 holder，互不可见。

---

## 常见问题（FAQ）

**Q：我让它记住了，但马上问它又说不知道？**
两个原因：① 新记忆需要几秒"消化"——Starling 后台每隔一段时间（`tick`）才把新
记忆做成可被语义检索的向量。测试时可以把 dashboard 的 `STARLING_DASH_TICK_INTERVAL`
调短（比如 5 秒），或等一会儿再问。② dashboard 没配 embedder——语义搜索需要它。

**Q：记忆到底存在哪？**
存在 Starling dashboard 的数据库里（`~/.starling/dashboard.db` 或你指定的 DB
文件），**不在** OpenClaw 那边。换台机器、重装 OpenClaw，只要 dashboard 的库还在，
记忆就在。

**Q：怎么彻底清空全部记忆？**
最干净的办法是换一个空的 dashboard 数据库（启动时用
`STARLING_DASH_DB=/path/to/new.db`）。单条删除用对话里的"忘掉…"，或 dashboard UI。

**Q：多个 agent 会共享记忆吗？**
同一个 `tenant` + 同一个 `holder` 下的记忆是共享的；用不同 `holder` 或不同
`tenant` 就能隔开（见上面的配置）。

**Q：它会把我整段对话都存下来吗？**
不会存原始聊天记录。`memory_store` 和自动沉淀都经过 Starling 的抽取——它只留下
能结构化成事实的内容（"谁-怎样-什么"）。纯寒暄、没有明确事实的句子可能不产生
任何记忆（这时 `/api/remember` 会返回空的 `statement_ids`，属正常）。

**Q：dashboard 必须一直开着吗？**
是的，记忆的读写都走 dashboard。dashboard 没开时，插件**不会让你的 agent 报错
中断**——读操作返回空（agent 当作没有相关记忆继续），写操作进本地重试队列，等
dashboard 回来再补写。

---

## 当前阶段的诚实说明（早期版本）

这是 P3.b2 的首个可用版本，端到端打通（存 / 搜 / 忘 / 自动回忆 / 离线降级都验证
过），但有几处仍是 MVP，知道了能少踩坑：

- **语义搜索质量取决于 embedder。** 配好真实 embedder 时按意思检索；没配时退化到
  占位向量，能返回但不按相关度排。
- **自动沉淀比较"粗"。** 压缩前的自动 capture 目前抓的是最近一条用户消息，不是
  对整段对话做摘要。重要的事建议也用一句"记住…"显式存一下更稳。
- **抽取依赖 LLM，有时抓不到。** 关系型的事实（"X 的偏好是 Y"）抽得稳；模糊的
  提醒类句子可能不产生记忆。
- **自动回忆的"对话方"维度还简化。** auto-recall 目前以 agent 自身为视角取工作集，
  还没有针对"具体对话对方"的精细化（后续增强）。

遇到问题先看 [`README.md` 的 Troubleshooting](README.md#troubleshooting)——大多数
"存了搜不到"都是 holder 没对齐、没配 embedder、或还没 tick 这三件事之一。
