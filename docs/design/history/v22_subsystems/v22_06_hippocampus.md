# Hippocampus

## 功能定义

Hippocampus 是快记忆子系统，承担 VOLATILE 状态 Statement 的写入缓冲、事件切分（EM-LLM 惊奇度阈值）、模式分离（反相似偏移 + MAY_OVERLAP_WITH 软边）、Working Set 渲染快照维护、Affect Buffer 优先级入队。它不做：长期语义存储（Neocortex 的事，见 [v22_07_neocortex.md](v22_07_neocortex.md)）、检索路由（见 [v22_05_bus.md](v22_05_bus.md)）、巩固决策（Replay Scheduler 的事，见 [v22_10_replay.md](v22_10_replay.md)）。它是逻辑分区，由 `consolidation_state` 标签区分，非物理表迁移目标（见 [v22_04_substrate.md](v22_04_substrate.md) §3 三层抽象）。

## 输入

- Bus 路由的 VOLATILE Statement（来自 statement.written 事件）
- EM-LLM 切分原始输入流（chunked Engram 内容）
- Working Set rebuild 请求（每回合对话触发）
- Affect Buffer 入队请求（高 salience 事件）

## 输出

- VOLATILE 分区持久化结果
- EpisodicEvent 边界（boundary_score 超阈值时切出新 episode）
- 模式分离结果（反相似偏移向量 + MAY_OVERLAP_WITH 软边）
- Working Set 快照（7 种 label 渲染产物，含 token 预算）
- Affect Buffer 优先级队列（供 Replay 采样）

## 主要流程

### 1. EM-LLM 事件切分

```
流式话语输入
  → LLM 在线计算 boundary_score = -log P(next | context)
  → boundary_score > θ_boundary
      → emit EpisodicEvent（含 boundary_score、episode_index、reference_time、statement_refs）
      → 继续积累下一段 context
```

- boundary_score 即负对数似然，反映当前话语相对上一段上下文的惊奇度。
- 跨阈值时刻即为 episode 边界，切出 EpisodicEvent 并写入 Episodes 分区。
- 该机制动机：LLM 的 parametric memory 擅长孤立事实，无法跨时间绑定相关 episodes（Episodic Knowledge Binding，OpenReview 2026），因此需外显 EpisodicEvent 与 episodic_link 结构。

### 2. 模式分离写入

```
新 Statement 到达
  → 查询 top-K 已有 Statement（余弦距离）
  → max_similarity > θ_sep ?
      是 → 反相似偏移：index_vector = orthogonalize(embedding, against=top_k_neighbors, strength=boost)
           → 建 MAY_OVERLAP_WITH 软边（记录 similarity 值），留巩固期再决策
      否 → index_vector = embedding（直接写）
```

- 默认保留细微差异，不做 UPDATE/NOOP（与 mem0 的根本区别）。
- MAY_OVERLAP_WITH 边由 Replay 巩固阶段决定是否合并或保留。

### 3. 模式补全（P2 引入，CA3 风格图游走）

```
partial cue 输入
  → vector_recall(cue, k=5) → seeds 集合（初始 activation=1.0）
  → 沿边类型（derived_from / evidence / OBSERVED_BY / SHARED_GROUND / MAY_OVERLAP_WITH）带权游走
  → 每步：next_act[target] += act[node] * edge_weight(kind) * decay
  → 合并 activation（取最大，不累加）
  → 终止条件：max(activation) < θ_propagate=0.05 OR 访问节点数 > 1000
  → 返回情节性子图（activation 最高的 K=20 个节点），超资源上限时标记 completion_truncated=true
```

- 返回情节性子图而非孤立 Statement。
- P1 不实现；P2 实现时上述资源边界作为单元测试约束。

### 4. Working Set 维护

```
每回合（per-turn）触发
  → 从 Persona（持久化结构）读取 self_model_anchor + traits
  → 从当前会话状态读取 interlocutor_persona / common_ground / pending_commitments
  → 按各 label 的 token_limit 截断
  → 渲染为 prompt block，注入本轮 LLM context
```

- 7 种 label 各有独立 token_limit 与 refresh_strategy。
- Working Set 是 view，Persona 是 model；前者跟 turn 走，后者由 Replay 周期更新（见 [v22_10_replay.md](v22_10_replay.md)）。

### 5. Affect Buffer 入队

```
Statement 写入事件（statement.written）触发
  → salience > θ_buffer ?
      是 → 加入优先级队列（priority = salience）
           → 队列满？
               是 → 比较新 stmt.salience vs 队列最低 salience
                    → 新 > 最低：替换最低（被替换者仍留 Hippocampus VOLATILE，不丢）
                    → 新 <= 最低：丢弃（stmt 仍在 VOLATILE）
      否 → 不入 Buffer
```

- Buffer 只存引用，不存 stmt 副本。
- Replay Scheduler Online 模式优先从 Buffer 取；Idle/Sleep 模式从 Hippocampus 全分区采样（见 [v22_10_replay.md](v22_10_replay.md)）。

## 核心算法

### 1. EM-LLM boundary_score

$$
\text{boundary\_score}(u_t) = -\log P(u_t \mid u_1, u_2, \ldots, u_{t-1})
$$

- $u_t$：第 $t$ 条话语（token 序列）。
- $P(\cdot \mid \text{context})$：LLM 在线推理的条件概率（token 级别 sum）。
- 超过阈值 $\theta_{\text{boundary}}$ 时切出 EpisodicEvent，boundary_score 直接赋给 `EpisodicEvent.boundary_score`。

### 2. 模式分离反相似偏移

设新 Statement 嵌入向量 $\mathbf{e}$，top-K 邻居集合 $\mathcal{N} = \{n_1, \ldots, n_K\}$，相似度上限 $\theta_{\text{sep}}$。

```
若 max_{n ∈ N} cos(e, n.embedding) > θ_sep：
    v_perp = e - Σ_i (e · n_i / ||n_i||²) * n_i   # Gram-Schmidt 正交化（多邻居版本）
    index_vector = normalize(e + strength * v_perp)
    对每个 n ∈ N：建 MAY_OVERLAP_WITH(new_stmt → n, similarity=cos(e, n.embedding))
否则：
    index_vector = e
```

- `orthogonalize(e, against=N, strength=s)`：将 $\mathbf{e}$ 沿各邻居方向去分量后加权叠回，使索引向量主动偏离邻居聚类（模拟 DG sparse coding）。
- `pattern_separation_boost`（即 strength）为可配置超参数。

### 3. CA3 风格图游走（pattern completion，P2）

```python
def pattern_completion(cue, budget=20):
    seeds = vector_recall(cue, k=5)
    activation = {s: 1.0 for s in seeds}
    visited = set(seeds)
    node_count = len(seeds)

    for step in range(budget):
        next_acts = {}
        for node, act in activation.items():
            for edge in node.edges:
                if edge.kind not in PROPAGATION_EDGE_TYPES:
                    continue
                w = edge_weight(edge.kind)
                contrib = act * w * decay
                if contrib < θ_propagate:
                    continue
                next_acts[edge.target] = max(
                    next_acts.get(edge.target, 0), contrib
                )
        # 合并（取最大，不累加）
        for node, act in next_acts.items():
            if node not in visited:
                node_count += 1
                visited.add(node)
            activation[node] = max(activation.get(node, 0), act)

        if node_count >= 1000:
            return _truncated_result(activation, K=20, truncated=True)
        if max(activation.values()) < θ_propagate:
            break

    return as_episodic_subgraph(activation, K=20)
```

- `PROPAGATION_EDGE_TYPES`：`{derived_from, evidence, OBSERVED_BY, SHARED_GROUND, MAY_OVERLAP_WITH}`。
- `θ_propagate = 0.05`（默认）；`decay` 为每步衰减系数。
- 资源上限：最多访问 1000 节点，超出时返回 top-K=20 + `completion_truncated=true`。

### 4. Affect Buffer 淘汰策略

```
容量 = C（可配置上限）
入队时：
    若 len(buffer) < C：直接 heappush(buffer, (-salience, stmt_ref))
    否则：
        min_salience_entry = heapmin(buffer)
        若 stmt.salience > min_salience_entry.salience：
            heapreplace(buffer, (-stmt.salience, stmt_ref))
            # 被替换者仍在 Hippocampus VOLATILE，不丢失
        否则：
            丢弃（stmt 仍在 VOLATILE）
```

- 优先级队列以 `-salience` 为 key（最小堆模拟最大堆）。
- 淘汰最低 salience，非最旧（区别于 FIFO 队列）。
- 借鉴 Anderson adaptive forgetting 机制。

## 数据结构

### EpisodicEvent

```python
@dataclass
class EpisodicEvent:
    episode_id: str                  # UUID
    boundary_score: float            # -log P(u_t | context)，切分阈值比较用
    episode_index: int               # 本会话内 episode 序号（单调递增）
    reference_time: datetime         # 事件发生时刻（ISO 8601）
    statement_refs: list[str]        # 指向 EngramStore 中 Statement 的 UUID 列表
    completion_truncated: bool = False  # pattern_completion 是否因资源上限截断
```

### WorkingSet（WorkingBlock 集合）

```python
@dataclass
class WorkingBlock:
    label: Literal[
        "self_persona",          # Persona.self_model_anchor + traits 的渲染
        "active_persona",        # 当前激活的角色/任务锚
        "current_goal",          # 当前会话目标
        "interlocutor_persona",  # 对话对象的推断模型
        "common_ground",         # 双方已确认的共享前提
        "norm_active",           # 激活中的规范/约束
        "pending_commitments",   # 尚未履行的承诺/行动项
    ]
    value: str                   # 渲染后的文本内容
    limit: int                   # token 上限（超出时截断）
    version: int                 # 乐观锁（并发写保护）
    refresh_strategy: Literal[
        "never",                 # 不自动刷新
        "per_turn",              # 每回合重建
        "per_session",           # 每会话重建
        "on_event",              # 触发事件时重建
    ]
```

- 7 种 label 中，`interlocutor_persona` / `common_ground` / `pending_commitments` 为 Starling 独有（主流开源系统无此三块）。
- Working Set 整体是 prompt 时刻的渲染快照（view），非持久化存储。

### AffectBufferEntry

```python
@dataclass
class AffectBufferEntry:
    priority: float              # = salience（越高越不被淘汰）
    stmt_ref: str                # EngramStore Statement UUID（只存引用）
    enqueued_at: datetime        # 入队时刻（调试用，不参与淘汰决策）

# 内部以最小堆维护（key = -priority）
# 容量上限：C（可配置）
```

### MAY_OVERLAP_WITH 边

```python
@dataclass
class MemoryEdge:
    kind: Literal["MAY_OVERLAP_WITH"]
    source_id: str               # Statement UUID（新写入的）
    target_id: str               # Statement UUID（已有邻居）
    similarity: float            # cos(source.embedding, target.embedding)，写入时刻计算
    created_at: datetime
    resolved: bool = False       # 巩固后置 True（Replay 决策合并或保留）
```

- 该边为软边，不阻止两端 Statement 独立存在。
- 巩固期（Replay）读取后更新 `resolved=True`，或删边并建 `DERIVED_FROM` 等强边。

## 相关概念

### VOLATILE 状态

`consolidation_state = VOLATILE`：Statement 刚写入 Hippocampus，尚未经历 Replay 巩固。VOLATILE Statement 保留细粒度原始形式，包括模式分离偏移后的 index_vector。另一合法值为 `REPLAYING_CONSOLIDATING`（巩固进行中，见 [v22_10_replay.md](v22_10_replay.md)）。

### EM-LLM 边界切分

利用 LLM 自身的条件概率计算话语惊奇度（负对数似然），无需外部分词器或固定窗口。边界由语义跳变驱动，天然对齐认知心理学的 event segmentation theory。

### 模式分离 vs 模式补全

| | 模式分离（Pattern Separation） | 模式补全（Pattern Completion） |
|---|---|---|
| 触发时机 | 写入时 | 检索时 |
| 目的 | 防止相似记忆混淆 | 从残缺线索恢复完整情节 |
| 生物对应 | 齿状回（DG）sparse coding | CA3 自联想回路 |
| 实现 | 反相似偏移 + MAY_OVERLAP_WITH | 图游走（Personalized PageRank 风格） |
| 阶段 | P1 实现 | P2 实现 |

### 反相似偏移

正交化（Gram-Schmidt）操作：将新 Statement 的嵌入向量沿已有邻居方向去分量，使索引向量主动偏离聚类中心。偏移强度由 `pattern_separation_boost` 控制。效果是索引空间更稀疏，减少错误召回，同时原始 embedding 不变（只有 index_vector 被修改）。

### Working Set vs Persona 的关系

- **Working Set**：每回合（per-turn）重建的 prompt 渲染快照，负责"此刻 LLM 需要看到什么"。跟 turn 走，token 数受 limit 约束，可频繁重建。
- **Persona**（见 [v22_07_neocortex.md](v22_07_neocortex.md) §3.6）：持久化结构，跨会话稳定，跟 cognizer 走，由 Replay 周期更新。
- 关系：Working Set 是 view，Persona 是 model。`self_persona` block 是 `Persona.self_model_anchor + Persona.traits` 的渲染投影。

### Affect Buffer vs Replay 优先级队列的关系

| | Affect Buffer | Replay Scheduler 优先级队列 |
|---|---|---|
| 性质 | 入口缓冲（数据结构） | 调度决策队列 |
| 内容 | salience > θ_buffer 的 stmt 引用 | 多来源采样结果（Buffer + VOLATILE 全区） |
| 淘汰策略 | 最低 salience 被替换 | 由 Replay Scheduler 调度策略决定 |
| 位置 | Hippocampus 内部 | Replay 子系统（见 [v22_10_replay.md](v22_10_replay.md)）|

Replay Scheduler 在 Online 模式优先消费 Affect Buffer；Idle/Sleep 模式从 Hippocampus 全分区采样。Buffer 满时被替换的 stmt 不丢失，仍留在 VOLATILE 区，只是不在快通道。

### Working Set 7 种 label 定义

| label | 内容 | 来源 | refresh_strategy |
|---|---|---|---|
| `self_persona` | Agent 自身身份、价值观、traits | Persona（持久化） | per_session 或 on_event |
| `active_persona` | 当前激活的角色或任务锚 | Persona + 任务上下文 | on_event |
| `current_goal` | 当前会话/任务的目标描述 | 会话状态 | per_turn |
| `interlocutor_persona` | 对话对象的推断模型（偏好、背景、立场） | 会话历史推断 | per_turn |
| `common_ground` | 双方已确认的共享前提与信念 | 会话历史推断 | per_turn |
| `norm_active` | 当前激活的规范、约束、协议 | 规范库 + 触发条件 | on_event |
| `pending_commitments` | 尚未履行的承诺、待办行动项 | 会话历史 + 任务追踪 | per_turn |

后三项（`interlocutor_persona` / `common_ground` / `pending_commitments`）为 Starling 独有，主流开源 memory 系统无此显式注入。
