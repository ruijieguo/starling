# P2.d 模式补全（Pattern Completion / CA3 风格图游走）设计

**里程碑**：P2.d（P2 收尾三里程碑之首，见 [2026-05-31-p2-completion-scope.md](../plans/2026-05-31-p2-completion-scope.md)）
**日期**：2026-05-31
**状态**：设计已 user approved，待 writing-plans
**依赖**：M0.9 向量基础层（PatternSeparator + `MAY_OVERLAP_WITH` 边 + `SemanticRetriever` + `SqliteBlobVectorIndex`）已合并 main（HEAD 8ceda47）
**权威算法来源**：`docs/design/subsystems_design/06_hippocampus.md` §3「CA3 风格图游走（pattern completion）」（伪代码 lines 126–158）

---

## 0. 背景与目标

roadmap P2.b 出货项明列「模式分离/补全（反相似偏移 + PPR 图游走）」。M0.9 只落地了**模式分离**（DG 反相似偏移 + `MAY_OVERLAP_WITH` 软边），**补全顺延**（system_design §16.5「模式补全 CA3 风格（PPR 图游走）| P2（收尾 P2.d）」）。

P2.d 补齐补全：给定部分线索（cue），从向量召回的种子出发，沿关联边做**带权 spreading-activation 图游走**，返回 activation 最高的情节性子图。Hippocampus 设计文档把它称作「Personalized PageRank 风格」——其具体算法即设计 §3 的 spreading-activation（取最大不累加），本 spec 照此实现，不另造 PPR 阻尼/teleport 变体。

**目标一句话**：交付独立的 `PatternCompletor` 检索器（新 `pattern_completion` recall 模式），纯在线、隐私先行、与设计 §3 伪代码逐行对应，资源边界可单测。

---

## 1. 范围

**范围内（P2.d 交付）：**
- `PatternCompletor` 类 + spreading-activation 游走（设计 §3 算法）
- 新 `pattern_completion` recall 模式（独立检索器，组合 `SemanticRetriever` 拿种子）
- 严格逐跳隐私过滤、对称边反向遍历、存储相似度边权
- pybind 绑定 + C++ 单测 + Python smoke
- **纯在线，无 migration**（边与 `idx_edges_src/dst` 索引现成）
- 可配置全 5 类传播边集（当前仅 `MAY_OVERLAP_WITH` live，余 4 类 inert 占位）

**明确范围外（→后续里程碑）：**
- PPR 缓存 / 预聚合 per-cognizer 子图（P3，system_design §16.2-6 / L1984）
- populate 4 类预留传播边（`derived_from / evidence / OBSERVED_BY / SHARED_GROUND`，来自别的子系统/里程碑；P2.d 只接线不灌数据）
- EM-LLM 事件切分 / episodic 边界 / `segment_map`（P3.c）
- 把 `pattern_completion` 接进 Working Set / `Memory` 门面（**P2.e**，P2.d 只交付独立能力 + 绑定）
- QueryIntent 检索规划分发（P3.a）、seekdb 后端（P3）

---

## 2. 算法（spreading activation，照设计 §3）

```
complete(cue, scope):
    seeds = vector_recall(cue, k=seed_k)          # 隐私先行的向量召回
    若 seeds.degraded: return {degraded=true, rows=seeds}   # 无 embedder/向量 → 不游走
    activation = { s.id: 1.0 for s in seeds }
    visited    = { s.id for s in seeds }
    for step in range(budget):
        frontier = activation 的全部节点 id
        edges    = 每跳边扩展 SQL(frontier, scope)          # §6,严格逐跳过滤 + 对称反向
        next = {}
        for (src, target, kind, stored_weight) in edges:
            contrib = activation[src] * edge_weight(kind, stored_weight) * decay   # §5
            if contrib < theta_propagate: continue
            next[target] = max(next.get(target, 0), contrib)   # 取最大不累加
        for (node, act) in next:
            if node not in visited: visited.add(node)          # node_count 增
            activation[node] = max(activation.get(node, 0), act)
        if len(visited) >= node_cap:
            return top_k(activation, result_k, truncated=true)
        if max(activation.values()) < theta_propagate:
            break
    return top_k(activation, result_k)             # 情节性子图,种子 activation=1.0 居顶
```

- **合并取最大不累加**（步内 `next` + 跨步 `activation` 都 max）。
- 终止：`visited ≥ node_cap` → 截断 `completion_truncated=true`；或 `max(activation) < theta_propagate` → 收敛 break。
- 种子 activation=1.0 自然落在 top-K 顶部，结果即「种子 + 补全节点」的情节性子图。

---

## 3. 组件与类型

新增文件（全部在 `retrieval/` 下，镜像 `SemanticRetriever` 独立类模式）：

| 文件 | 职责 |
|---|---|
| `include/starling/retrieval/pattern_completor.hpp` | 类 + 参数/结果结构 |
| `src/retrieval/pattern_completor.cpp` | 游走主体 + 每跳边扩展 SQL |
| `tests/cpp/test_pattern_completor.cpp` | 资源边界 + 隐私 + 算法单测 |
| `bindings/python/module.cpp`（改） | `PatternCompletor` 绑定 |
| `tests/python/test_pattern_completion.py` | Python 端到端 smoke |

```cpp
namespace starling::retrieval {

struct PatternCompletionParams {
    std::string tenant_id, holder_id, holder_perspective;  // perspective "" = any
    std::string cue_text;          // 部分线索 → 嵌入 → 种子
    int seed_k = 5;                // 种子数(vector_recall k)
    int budget = 20;               // 最大传播步数
    int result_k = 20;             // 返回 top-K
    int node_cap = 1000;           // 访问节点上限
    double theta_propagate = 0.05;
    double decay = 0.5;            // 每步衰减(§5)
    std::string trace_id, query_id;
};

struct CompletionScored { StatementRow row; double activation; };

struct CompletionResult {
    std::vector<CompletionScored> rows;   // activation 降序, ≤ result_k
    bool completion_truncated = false;     // 访问节点 > node_cap
    bool degraded = false;                 // 无 embedder/向量 → 不游走
};

class PatternCompletor {
public:
    PatternCompletor(persistence::SqliteAdapter&, SemanticRetriever& seeds);
    CompletionResult complete(persistence::Connection&, const PatternCompletionParams&);
    persistence::Connection& connection() { return adapter_.connection(); }
private:
    persistence::SqliteAdapter& adapter_;
    SemanticRetriever& seeds_;
};
}  // namespace starling::retrieval
```

**组合而非继承**：`PatternCompletor` 持 `SemanticRetriever&` 拿种子，自身只负责多跳游走，职责单一。

**pybind 模式**（对齐 `SemanticRetriever` 绑定）：构造取 `SqliteAdapter& + SemanticRetriever&`，`py::keep_alive<1,2>() / <1,3>()` 引用保活；`complete` lambda 内用 `self.connection()` 屏蔽 `Connection&`，Python 端 conn-free。

---

## 4. 数据流

```
complete(cue_text, scope)
  1. seeds = seeds_.vector_recall(cue_text, k=seed_k)   // 复用隐私先行向量召回
        └─ degraded → CompletionResult{degraded=true, rows=种子(可能空)},不游走
  2. activation = { seed.id: 1.0 }, visited = seeds
  3. for step in budget:
        frontier = activation 节点 id 集合 → JSON 数组
        每跳一条批量 SQL(json_each(frontier) ⋈ statement_edges ⋈ statements,§6)
        贡献 contrib = act[src] × edge_weight(kind, stored_weight) × decay,跌破 θ 跳过
        next/activation 取最大合并;新节点计入 node_count
        node_count ≥ node_cap → 截断 top-K, truncated=true
        max(activation) < θ → break
  4. 返回 top result_k(activation 降序) as CompletionResult
```

批量边扩展用 `json_each(?frontier)`：避免大 IN-list / 动态 SQL（SQLite ≥3.46 自带 JSON1）。

---

## 5. 边权与参数

**边权（偏离伪代码字面：用每边存储权重 × 类型乘子）**

设计伪代码写 `w = edge_weight(edge.kind)`（纯类型常量）。但 `MAY_OVERLAP_WITH` 边在 `statement_edges.weight` 存了每边余弦相似度（模式分离写入时记的）。本设计改为：

```
edge_weight(kind, stored_weight) = kind_multiplier(kind) × clamp(stored_weight, 0, 1)
```

- `MAY_OVERLAP_WITH`：`kind_multiplier=1.0`，`stored_weight`=余弦相似度 → 传播强度=实际语义贴近度（贴 CA3 联想强度）。
- 4 类预留边（当前零行）：`weight` 列默认 1.0，`kind_multiplier` 默认 1.0 → populate 后满权传播，后续可调。
- `clamp(·,0,1)`：相似度异常/负值 → 0（跳过），防脏数据放大激活。

`kind_multiplier` 为可配置 map，默认全 1.0：

| edge_kind | 当前是否 populate | 默认 multiplier | 对称性 |
|---|---|---|---|
| MAY_OVERLAP_WITH | ✅ M0.9 | 1.0 | 对称（前向+反向遍历） |
| derived_from | ❌ 预留 | 1.0 | 前向（src→dst） |
| evidence | ❌ 预留 | 1.0 | 前向 |
| OBSERVED_BY | ❌ 预留 | 1.0 | 前向 |
| SHARED_GROUND | ❌ 预留 | 1.0 | 前向 |

**decay = 0.5**：每跳贡献减半。与 θ_propagate=0.05 + 权重 ≤1.0 联动：`0.5^n < 0.05` ⟹ n≈4.3，激活约 5 跳自然衰竭。故 **θ_propagate 是真正终止器**，`budget=20` 是宽松上限，`node_cap=1000` 是资源护栏，三者职责不重叠。

**参数总表（全部可配，默认来自设计 §3，decay 由本 spec 补默认）**

| 参数 | 默认 | 来源 |
|---|---|---|
| `seed_k` | 5 | 设计：vector_recall(cue, k=5) |
| `theta_propagate` | 0.05 | 设计 |
| `decay` | 0.5 | 本 spec（设计只说"每步衰减系数"） |
| `budget` | 20 | 设计 |
| `result_k` | 20 | 设计 |
| `node_cap` | 1000 | 设计 |

---

## 6. 隐私（严格逐跳）+ 每跳边扩展 SQL

**隐私不变式**（用户选定 A）：

> 任何进入 `activation` 的节点，都通过了与种子**完全相同**的 scope 谓词（tenant + holder + perspective + visible_only）。
> 归纳：种子由 `vector_recall` 隐私过滤；每跳只接纳通过谓词的 target ⟹ 全程无查询者不可见节点能影响激活或出现在输出。

故每跳只需过滤 **target(dst)节点**——源节点已在前沿、必然已通过谓词。scope 谓词逐字对齐 `SqliteBlobVectorIndex::search_topk`（同一隐私边界，Retrieval 设计「perspective filter 必须在语义排序之前执行，不可绕过」）。

**每跳边扩展 SQL（前向 + 对称边反向 UNION ALL）：**

```sql
-- 前向:前沿作 src,target=dst(所有传播边)
SELECT f.value AS src_id, e.dst_id AS target_id, e.edge_kind, e.weight
  FROM json_each(?1) f                                   -- ?1 = 前沿 id JSON 数组
  JOIN statement_edges e
       ON e.tenant_id = ?2 AND e.src_id = f.value         -- idx_edges_src
  JOIN statements s
       ON s.id = e.dst_id AND s.tenant_id = e.tenant_id   -- 同租户硬绑
 WHERE e.edge_kind IN ('MAY_OVERLAP_WITH','derived_from','evidence','OBSERVED_BY','SHARED_GROUND')
   AND (?3 = '' OR s.holder_id = ?3)
   AND (?4 = '' OR s.holder_perspective = ?4)
   AND s.consolidation_state IN ('consolidated','archived')
   AND s.review_status NOT IN ('rejected','pending_review')
UNION ALL
-- 反向:前沿作 dst,target=src(仅对称边)
SELECT f.value AS src_id, e.src_id AS target_id, e.edge_kind, e.weight
  FROM json_each(?1) f
  JOIN statement_edges e
       ON e.tenant_id = ?2 AND e.dst_id = f.value          -- idx_edges_dst
  JOIN statements s
       ON s.id = e.src_id AND s.tenant_id = e.tenant_id
 WHERE e.edge_kind IN ('MAY_OVERLAP_WITH')                 -- 对称边集
   AND (?3 = '' OR s.holder_id = ?3)
   AND (?4 = '' OR s.holder_perspective = ?4)
   AND s.consolidation_state IN ('consolidated','archived')
   AND s.review_status NOT IN ('rejected','pending_review');
```

C++ 循环对 UNION 结果按 target max-merge。

**强制项：**
- `visible_only` 恒为 true——和 `vector_recall` 一样**永不放宽**，无 `visible_only=false` 路径。
- 租户经 `e.tenant_id=?2` + `s.tenant_id=e.tenant_id` 双重锁；`statements` PK `(id, tenant_id)` 保证 target 同租户。
- `MAY_OVERLAP_WITH` 对称→前向+反向；4 类预留边默认前向，populate 时再定对称性。
- `supersedes / conflicts_with` **不在**传播边集（冲突不互相强化，设计已排除）。

---

## 7. 截断 / 降级 / 错误

| 情形 | 行为 |
|---|---|
| 访问节点 ≥ `node_cap`(1000) | 返回当前 activation 的 top-`result_k`，`completion_truncated=true` |
| 种子 degraded（无 embedder / 无向量） | 不游走，`degraded=true`，`rows`=种子行（可能空） |
| cue 命中种子但无传播边 | 返回种子本身（activation=1.0），`truncated=false`、`degraded=false` |
| SQL 错误 | 抛 `make_sqlite_error`（与全栈一致），不静默吞 |

`CompletionResult` 刻意最小（`rows / completion_truncated / degraded`），镜像 `SemanticResult` 的 degraded 语义；不在本期建完整 `RetrievalReceipt`（属检索规划 P3.a）。

---

## 8. 测试

**C++ 单测（设计 §3 要求资源边界做成单测约束）：**
- `node_cap` 截断：造 >1000 可达节点 → `completion_truncated=true` 且结果 ≤ `result_k`
- θ_propagate 收敛：衰减链 → 激活跌破 0.05 即停（有限跳）
- **max 不累加**：菱形图（两路径到同一节点）→ activation = max 而非 sum
- **隐私严格逐跳（核心）**：overlap 边连到别 holder/perspective 陈述 → 该节点**不在结果、未参与传播**
- 租户隔离：跨租户边不可桥
- 对称反向：边写 src=A,dst=B；种子=B → A 可达
- 边权用存储相似度：同源两条 overlap（0.9 vs 0.5）→ 高权 target 激活更高
- degraded：无 embedder → 不游走
- 种子-only：无边 → 结果=种子

**Python smoke：** 绑定端到端（写若干 statement → 触发嵌入 → overlap 边 → `complete(cue)` 返回补全子图）。

**回归红线：** M0.9 `vector_recall`/`SemanticRetriever` 不动；M0.8 + P2.a–c 全绿；`statement_edges`/`statements` schema 不改（纯读）；单一 `starling_tests`；`ctest` 全绿。

---

## 9. 实施约束（注入 writing-plans）

- worktree 隔离（`worktree-p2-d-pattern-completion`），从 main HEAD 切出
- `starling_core` 显式 `target_sources` append `src/retrieval/pattern_completor.cpp`（在 `src/prospective/policy_engine.cpp` 后）；`starling_tests` append `tests/cpp/test_pattern_completor.cpp`
- pybind/绑定改动后刷新 `_core.so`：`cmake --build build` + `cmake --install build --prefix .venv/lib/python3.14/site-packages` + `pip install -e . --no-deps --force-reinstall`（`cmake --install` 是关键）
- SQL helpers：`bus::detail::bind_sv` / `make_sqlite_error`、`persistence::StmtHandle`、checked `sqlite3_prepare_v2`；参考 `semantic_retriever.cpp` / `sqlite_blob_vector_index.cpp`
- `:memory:` SQLite（unit）/ `tmp_path` + `relax_preflight_for_m0_3`（runtime fixture）
- 无 `--no-verify` / `--amend`；plan 文件 untracked 直到 milestone close；API key env-only
- **纯读 + 纯在线，无 migration**（最高现存 migration 0021 不变）

---

## 10. 验收

- `PatternCompletor` 落地，`pattern_completion` 走通 cue → 种子 → 游走 → top-K 子图
- 8 项 C++ 单测 + Python smoke 全绿（含资源边界 + 隐私严格逐跳 + max 不累加 + 对称反向）
- M0.8 + M0.9 + P2.a–c 无回归；`ctest` 全绿
- 隐私不变式经测试验证：无跨视角/跨租户节点泄露进 activation 或输出
