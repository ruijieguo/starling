# P2.a 社会心智 Schema 里程碑 — 设计规格

**Status**: Draft for review
**Author**: Auto Mode (Subagent-Driven Development)
**Date**: 2026-05-26
**Spec source**: `docs/design/system_design.md` §16.3 / `subsystems_design/08_cognizer.md` / `09_tom.md` / `13_retrieval.md` §"perspective filter 位序" / `05_bus.md` §5（canonical_conflict_key）

---

## 1. 目标

按 roadmap §16.3 P2 准入条件，P2.a 完成 4 周内 **新增 2 个子系统 + 扩展 2 个子系统 + 加 2 个 eval harness**：

| 工作分块 | 子系统 / 非子系统 | 输出 |
|---|---|---|
| **新建 08_cognizer** | Cognizer Hub + RelationEdge + KnowledgeFrontier 五类 | 4 张表、~1800 行 C++ + 250 行 Python wrapper |
| **新建 09_tom** | ToM Engine + perspective_take + 4 Mentalizing Primitives + BeliefTracker (Outbox subscriber) + ToMDepthEstimator + 双限流 | 2 张表、~2500 行 C++ + 300 行 Python wrapper |
| **扩展 05_bus** | ConflictProbe 4-kind 唯一性收尾（§16.3-5） | 1 张迁移、~280 行 C++ |
| **扩展 13_retrieval** | basic_retrieve 接入 filter_by_frontier（默认 off）| ~150 行 C++ |
| **非子系统：extractor v12 prompt** | 加 explicit_negation 识别（带回滚 fallback） | ~250 行 |
| **非子系统：ToMBench harness** | first-order easy subset × 3 round | ~400 行 Python |
| **非子系统：FANToM harness** | 1k 抽样 × 3 round（fixed seed） | ~500 行 Python |

P2.a 关闭门槛：
1. 9 个新增 P2.a CRITICAL 全绿（5 / 1 / 3 分布于 cognizer / bus / tom）
2. P1 13 CRITICAL 不回归（§16.3-2 强约束）
3. P1 §15.3.3 EVAL F1 不回归（v12 prompt 跌阈值即回滚 v11，见 §F.2）
4. ToMBench first-order easy subset accuracy ≥ 0.55（最后一轮）
5. FANToM 1k × 3 round 全跑通 + 三类 question_type accuracy 标准差 ≤ 0.05
6. ci_static_scan 仍然 clean，无 `starling::testing` 引用泄漏到 production roots

---

## 2. 非目标

- **CommonGround pool writer**: 加 schema 表 + 空 read API，writer 留 P2.b
- **5 / 7 Mentalizing Primitives**: P2.a 仅交付 4 个（believe / know / misalign / shared）；what_does_X_think_Y_believes / predict_X_would / who_committed 留后续
- **ToM 2 阶 nesting_depth=2 持久化决策**: ToMDepthEstimator 是纯查询工具；StatementWriter 自决；P2.b 接 BeliefTracker writer
- **Replay / Reconsolidation / Prospective Loop**: P2.b / P2.c
- **完整 RuntimeHealth 仪表盘 / 自动背压**: P2 后期 / P3
- **PDDL 形式化 belief base / multi-agent 信任传播**: P3+
- **ToMDepthEstimator 真模型**: P2.a 仅简单 7d 计数 heuristic，真 model 留 P3
- **Cognizer Persona Container**: 表存在但 P2.a 不动 writer，P2.b 接 Replay 后 profile 阶段才生效

---

## 3. 子系统状态变化

### 3.1 P2.a 启动前（M0.7 close + 4 follow-ups 后）

| 子系统 | 状态 |
|---|---|
| 04_substrate | ✅ 有代码 |
| 05_bus | ✅ 有代码 |
| 05_governance | ⚠️ 部分（preflight 存在，ScopedWorkGate 待 P2+） |
| 06_engramstore | ✅ 有代码 |
| 06_hippocampus | ⛔ 空 |
| 07_neocortex | ⛔ 空 |
| **08_cognizer** | ⛔ 空 → P2.a 新建 |
| **09_tom** | ⛔ 空 → P2.a 新建 |
| 10_replay | ⛔ 空 |
| 11_reconsolidation | ⛔ 空 |
| 12_prospective | ⛔ 空 |
| 13_retrieval | ✅ 有代码 |

**有代码子系统数**：5 / 12

### 3.2 P2.a 完成后

| 变化 | 数量 |
|---|---|
| 新增子系统 | 2（08_cognizer, 09_tom） |
| 扩展现有子系统 | 2（05_bus, 13_retrieval） |
| 完成后有代码子系统数 | **7 / 12** |
| 仍为空（P2.b 起步范围） | 5（06_hippocampus, 07_neocortex, 10_replay, 11_reconsolidation, 12_prospective） |

---

## 4. 架构总览

```
┌─ 08_cognizer (新) ─────────────────────────────────────────┐
│  cognizers 表 + UUID5(kind, external_id) 注册              │
│  alias 归一: trim + space-collapse + ASCII case-fold        │
│  CognizerHub class (register / lookup_by_alias / upsert)    │
│  RelationEdge: Fiske 4-mode + multi-dim trust + valid_*     │
│  KnowledgeFrontier 五类: presence_log / explicit_told /    │
│    accessible_source / membership / explicit_not_told       │
│  visible_engrams_at(target, time): 五路并集 - 减集          │
└────────────────┬────────────────────────────────────────────┘
                 │ FK soft-join on holder_id
                 ▼
┌─ statements (P1 既有) ──────────────────────────────────────┐
│  + nesting_depth 列从摆设变 load-bearing                    │
│  + holder_id → cognizers.id (TEXT，应用层校验)             │
└─────────────────────────────────────────────────────────────┘
       │                                            │
       ▼                                            ▼
┌─ 05_bus 扩展 ──────────────┐    ┌─ 09_tom (新) ─────────────────────────────┐
│  ConflictProbe 4-kind      │    │  ToMEngine.perspective_take(target,time)  │
│    已实现 (M0.5/M0.7)      │    │    → Context{visible, target_beliefs, cg} │
│  + canonical_conflict_key   │    │    visible 委托 KnowledgeFrontier         │
│    列 + partial UNIQUE     │    │    target_beliefs 直查 statements 子图    │
│    索引 (§16.3-5)          │    │    cg 走 common_ground 表(P2.a 总返回空) │
│  + UNIQUE 违反 noop+WARN   │    │  4 Mentalizing Primitives:                │
│  + 异步 backfill (Bus.write│    │    what_does_X_believe / does_X_know(三态)│
│    commit 后 tick 100/批)  │    │    find_misalignment / shared_with        │
└────────────────────────────┘    │  BeliefTracker (Outbox subscriber)        │
       │                          │    tick-driven, 6 event handler           │
       │                          │    与 backfill 同位 Bus.write 后触发      │
       │                          │  ToMDepthEstimator (free function)        │
       │                          │    7d 窗口 + 1h 缓存 TTL                  │
       │                          │  双限流: 链长复用 05_bus / 10min 窗口     │
       │                          └────────────────┬──────────────────────────┘
       │                                           │
       └─────────────┬─────────────────────────────┘
                     ▼
┌─ 13_retrieval 扩展 ────────────────────────────────────────┐
│  basic_retrieve 加 apply_frontier_filter 参数 (默认 False) │
│  开启时: SQL 加 EXISTS 子查询调 visible_engrams_at         │
│  RetrievalReceipt.filters_applied 增 frontier_applied +    │
│    frontier_masked_count（10 → 12 项）                     │
│  P1 13 CRITICAL 零改（默认 off 保兼容）                    │
└────────────────────────────────────────────────────────────┘
                     ▲
                     │ 主消费者
┌────────────────────┴───────────────────────────────────────┐
│  非子系统：eval / extractor 工作                           │
│  • scripts/eval_tom_bench.py: ToMBench first-order easy    │
│    × 3 round, accuracy ≥ 0.55                             │
│  • scripts/eval_fantom.py: FANToM 1k 抽样 × 3 round       │
│    fixed seed, stddev ≤ 0.05                              │
│  • extractor v12 prompt: explicit_negation 识别            │
│    fallback path: 跌 P1 EVAL F1 阈值 → 回滚 v11，         │
│    explicit_not_told 在 P2.a 永久空（P2.b 重启用）         │
└────────────────────────────────────────────────────────────┘
```

---

## 5. Schema delta

### 5.1 migrations/0008_cognizer_schema.sql

新表 4 张 + statements.holder_id backfill 路径。

**cognizers 主表**：
```sql
CREATE TABLE cognizers (
    id TEXT NOT NULL,                              -- UUID5(kStarlingCognizerNamespace, kind+":"+external_id)
    tenant_id TEXT NOT NULL DEFAULT 'default',
    kind TEXT NOT NULL CHECK (kind IN
        ('self','human','agent','group','role','external')),
    canonical_name TEXT NOT NULL,
    canonical_name_normalized TEXT NOT NULL,       -- trim + space-collapse + ASCII case-fold
    aliases_json TEXT NOT NULL DEFAULT '[]',
    aliases_normalized_json TEXT NOT NULL DEFAULT '[]',
    external_id TEXT NOT NULL,
    trust_priors_json TEXT NOT NULL DEFAULT '{}',
    permissions_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (id, tenant_id)
);
CREATE INDEX idx_cognizers_canonical_normalized
    ON cognizers(tenant_id, canonical_name_normalized);
CREATE INDEX idx_cognizers_external_id
    ON cognizers(tenant_id, kind, external_id);
```

**cognizer_relations**（Fiske 4-mode）：
```sql
CREATE TABLE cognizer_relations (
    id TEXT PRIMARY KEY,                           -- random 32-hex
    tenant_id TEXT NOT NULL,
    a_id TEXT NOT NULL,                            -- holder/observer
    b_id TEXT NOT NULL,
    fiske_weights_json TEXT NOT NULL DEFAULT '{}', -- {communal,authority,equality,market: float}, 和 == 1.0±1e-6
    affinity REAL NOT NULL DEFAULT 0.5 CHECK (affinity >= 0.0 AND affinity <= 1.0),
    trust_json TEXT NOT NULL DEFAULT '{}',         -- {context: float}
    power_asymmetry REAL NOT NULL DEFAULT 0.0,
    interaction_history_ref TEXT,
    valid_from TEXT,
    valid_to TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_relations_a    ON cognizer_relations(tenant_id, a_id);
CREATE INDEX idx_relations_pair ON cognizer_relations(tenant_id, a_id, b_id);
```

**cognizer_presence_log**（KnowledgeFrontier presence_log 派生）：
```sql
CREATE TABLE cognizer_presence_log (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    cognizer_id TEXT NOT NULL,
    engram_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,                     -- = engram.created_at
    channel TEXT NOT NULL DEFAULT 'default'
);
CREATE INDEX idx_presence_log_cognizer_time
    ON cognizer_presence_log(tenant_id, cognizer_id, observed_at);
```

**cognizer_frontier_facts**（explicit_told / not_told / accessible_source / membership 四类）：
```sql
CREATE TABLE cognizer_frontier_facts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    cognizer_id TEXT NOT NULL,
    statement_id TEXT,                             -- explicit_told / not_told 用
    source_engram_id TEXT,                         -- 各类用作 engram 锚点
    fact_kind TEXT NOT NULL CHECK (fact_kind IN
        ('explicit_told','explicit_not_told','accessible_source','membership')),
    asserted_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'       -- accessible_source 存 adapter_name；membership 存 group_id
);
CREATE INDEX idx_frontier_facts_cognizer
    ON cognizer_frontier_facts(tenant_id, cognizer_id, fact_kind);
CREATE INDEX idx_frontier_facts_statement
    ON cognizer_frontier_facts(tenant_id, statement_id);
```

**Backfill on migration apply**（同事务）：
```sql
-- 已有 statements 中所有不同 (tenant_id, holder_id) → cognizers
INSERT OR IGNORE INTO cognizers (
    id, tenant_id, kind, canonical_name, canonical_name_normalized,
    aliases_json, aliases_normalized_json, external_id,
    created_at, last_seen_at
)
SELECT
    lower(hex(randomblob(16))),                   -- 占位，新写入由 Hub 算 UUID5
    s.tenant_id,
    'human',
    s.holder_id,
    lower(trim(s.holder_id)),                     -- 简单 normalize（无 collapse_consecutive_whitespace 在 SQLite 内）
    json_array(s.holder_id),
    json_array(lower(trim(s.holder_id))),
    s.holder_id,
    COALESCE(MIN(s.created_at), '2026-05-26T00:00:00Z'),
    COALESCE(MAX(s.updated_at), '2026-05-26T00:00:00Z')
FROM statements s
GROUP BY s.tenant_id, s.holder_id;

-- subject_kind='cognizer' 的 subject 同样 backfill
INSERT OR IGNORE INTO cognizers (...)
SELECT ... FROM statements WHERE subject_kind='cognizer';
```

> **风险**：SQLite 内的 normalize 比应用层 normalize 弱（无 ASCII case-fold 完整规则、无连续空白合并）。Backfilled 行的 normalized 列在第一次 Hub::register 同 alias 时会被检测出 mismatch → Hub 应当透明更新 normalized 列与 application 层版本一致。

### 5.2 migrations/0009_conflict_key_unique.sql

```sql
-- statement_edges 加列
ALTER TABLE statement_edges ADD COLUMN canonical_conflict_key TEXT;

-- partial UNIQUE 索引：仅 conflicts_with 边 + 非空 key
CREATE UNIQUE INDEX idx_conflict_edges_key_unique
    ON statement_edges(tenant_id, canonical_conflict_key)
    WHERE edge_kind = 'conflicts_with' AND canonical_conflict_key IS NOT NULL;

-- backfill 进度跟踪表（singleton）
CREATE TABLE conflict_key_backfill_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_edge_id TEXT,
    rows_backfilled INTEGER NOT NULL DEFAULT 0,
    rows_deduped INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    completed_at TEXT,                             -- NULL = 进行中
    last_updated_at TEXT NOT NULL
);
INSERT INTO conflict_key_backfill_state (id, started_at, last_updated_at)
    VALUES (1, '2026-05-26T00:00:00Z', '2026-05-26T00:00:00Z');
```

Backfill 工具实现见 §6.2。

### 5.3 migrations/0010_tom_belief_tracker.sql

```sql
CREATE TABLE tom_belief_tracker_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO tom_belief_tracker_checkpoint (id, last_processed_outbox_sequence, last_updated_at)
    VALUES (1, 0, '2026-05-26T00:00:00Z');

CREATE TABLE tom_depth_estimator_cache (
    tenant_id TEXT NOT NULL,
    partner_id TEXT NOT NULL,
    nesting_depth_1_count_7d INTEGER NOT NULL DEFAULT 0,
    last_recomputed_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, partner_id)
);

-- common_ground pool: P2.a 加表，writer 留 P2.b
CREATE TABLE common_ground (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    statement_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN
        ('asserted_unack','grounded','suspected_diverge','expired','recanted')),
    parties_json TEXT NOT NULL DEFAULT '[]',
    grounded_at TEXT,
    last_confirmed_at TEXT,
    superseded_by TEXT,
    expired_at TEXT,
    audit_actor TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_common_ground_status
    ON common_ground(tenant_id, status);
CREATE INDEX idx_common_ground_statement
    ON common_ground(tenant_id, statement_id);
```

### 5.4 statements 列变化

无 schema 改动。`nesting_depth` 列 M0.1 已存在；P2.a 让它真正 load-bearing：StatementWriter 在 INSERT 前由 nesting_depth_writer 计算（§7.6）。

---

## 6. 子系统 1：08_cognizer

### 6.1 文件清单

```
include/starling/cognizer/
  cognizer.hpp                  # POD: Cognizer / RelationEdge / KnowledgeFrontier 类型
  cognizer_hub.hpp              # Hub class
  knowledge_frontier.hpp        # 五类记录 + visible_engrams_at
  uuid5.hpp                     # RFC 4122 §4.3

src/cognizer/
  cognizer_hub.cpp              # register / lookup / upsert_relation
  alias_normalizer.cpp          # trim + space-collapse + ASCII case-fold
  relation_edge_writer.cpp      # Fiske 4-mode upsert + 不变量校验
  knowledge_frontier.cpp        # 五类 record + 五路 visible_engrams_at
  uuid5.cpp                     # SHA-1 namespace + name → UUID5

include/starling/version.hpp    # 加 kStarlingCognizerNamespace 常量

bindings/python/module.cpp      # 暴露 CognizerHub, Cognizer, RelationEdge

python/starling/cognizer/
  __init__.py                   # 公共 API
  builders.py                   # for_human / for_agent / for_group / ... 便利构造器
```

### 6.2 CognizerHub class

```cpp
namespace starling::cognizer {

class CognizerHub {
public:
    explicit CognizerHub(persistence::SqliteAdapter& adapter);

    Cognizer register_cognizer(const CognizerRegistration& req);
    std::optional<std::string> lookup_by_alias(
        std::string_view tenant_id, std::string_view alias) const;
    std::optional<Cognizer> get(std::string_view id, std::string_view tenant_id) const;
    void update_last_seen_at(std::string_view id, std::string_view tenant_id,
                              std::string_view at_iso8601);

    RelationEdge upsert_relation(const RelationEdgeInput& req);
    std::vector<RelationEdge> relations_of(
        std::string_view cognizer_id, std::string_view tenant_id) const;

private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace
```

`register_cognizer` 内部:
1. 计算 UUID5(kStarlingCognizerNamespace, kind || "\x1f" || external_id)
2. INSERT OR IGNORE 到 cognizers 表
3. 若 INSERT 跳过（已存在）→ UPDATE last_seen_at + aliases_json + aliases_normalized_json（如果有新 alias）
4. 若 alias 命中其他 cognizer → throw `AliasCollision(existing_id, alias)`
5. 若 kind=group 且 tenant_id="default" 且未显式声明 → throw `GroupTenantImplicit`

### 6.3 alias_normalizer

```cpp
// src/cognizer/alias_normalizer.cpp
namespace starling::cognizer {

std::string normalize_alias(std::string_view raw) {
    std::string s(raw);
    s = trim(s);                         // \t \n \r \v \f 空格首尾
    s = collapse_consecutive_whitespace(s);  // 多个 \s+ → 单个空格
    s = ascii_case_fold(s);              // ASCII 字母 → 小写；CJK / accented 不变
    return s;
}

bool is_alias_match(std::string_view stored_normalized, std::string_view query) {
    return stored_normalized == normalize_alias(query);
}

}  // namespace
```

存储原始 + normalized 两份；lookup 用 normalized。

### 6.4 UUID5 namespace

`include/starling/version.hpp` 末尾添加：

```cpp
namespace starling {

// UUID5 namespace for cognizer ids. Computed once with:
//   uuid.uuid5(uuid.NAMESPACE_DNS, "starling-cognizer-v1")
// in Python (RFC 4122 §4.3 standard derivation). Frozen here as a
// project-wide constant. Changing this value invalidates every
// cognizer.id in production storage; do NOT modify after P2.a release.
inline constexpr std::string_view kStarlingCognizerNamespace =
    "aacf67e8-1495-5cef-ac22-dd0bd73dd1af";

}  // namespace
```

### 6.5 KnowledgeFrontier

```cpp
class KnowledgeFrontier {
public:
    explicit KnowledgeFrontier(persistence::SqliteAdapter& adapter);

    // 五类 record API（由 BeliefTracker / extractor 触发）:
    void record_presence_from_statement(
        std::string_view tenant_id,
        const std::vector<std::string>& perceived_by,
        std::string_view engram_id, std::string_view observed_at,
        persistence::Connection& conn);

    void record_explicit_told(
        std::string_view tenant_id,
        const std::vector<std::string>& perceived_by,
        std::string_view statement_id, std::string_view source_engram_id,
        std::string_view observed_at,
        persistence::Connection& conn);

    void record_accessible_source(
        std::string_view tenant_id, std::string_view cognizer_id,
        std::string_view adapter_name, std::string_view engram_id,
        std::string_view observed_at,
        persistence::Connection& conn);

    void record_group_membership(
        std::string_view tenant_id, std::string_view cognizer_id,
        std::string_view group_id, std::string_view at_iso8601,
        persistence::Connection& conn);

    void record_explicit_negation(
        std::string_view tenant_id, std::string_view cognizer_id,
        std::string_view referenced_statement_id, std::string_view source_engram_id,
        std::string_view observed_at,
        persistence::Connection& conn);

    // 查询: 五路并集 - explicit_not_told 减集
    std::unordered_set<std::string> visible_engrams_at(
        std::string_view tenant_id, std::string_view cognizer_id,
        std::string_view as_of_iso8601) const;
};
```

`visible_engrams_at` SQL：

```sql
SELECT engram_id FROM cognizer_presence_log
 WHERE tenant_id=? AND cognizer_id=? AND observed_at <= ?
UNION
SELECT source_engram_id FROM cognizer_frontier_facts
 WHERE tenant_id=? AND cognizer_id=?
   AND fact_kind IN ('explicit_told','accessible_source','membership')
   AND asserted_at <= ?
EXCEPT
SELECT source_engram_id FROM cognizer_frontier_facts
 WHERE tenant_id=? AND cognizer_id=?
   AND fact_kind = 'explicit_not_told'
   AND asserted_at <= ?
```

### 6.6 RelationEdge

```cpp
struct RelationEdge {
    std::string id;
    std::string tenant_id;
    std::string a_id;
    std::string b_id;
    std::unordered_map<FiskeMode, double> fiske_weights;  // sum == 1.0 ± 1e-6
    double affinity;                                      // 0..1
    std::unordered_map<std::string, double> trust;        // {context: float}
    double power_asymmetry;
    std::optional<std::string> interaction_history_ref;
    std::optional<std::string> valid_from;
    std::optional<std::string> valid_to;
    std::string created_at;
    std::string updated_at;
};

enum class FiskeMode { Communal, Authority, Equality, Market };
```

`upsert_relation` 不变量：
- `sum(fiske_weights) ∈ [1.0 - 1e-6, 1.0 + 1e-6]` 否则 `FiskeWeightsInvalid`
- `0 ≤ affinity ≤ 1`
- 同 `(tenant_id, a_id, b_id, valid_from)` 三元组 → ON CONFLICT REPLACE

### 6.7 错误类型

```cpp
namespace starling::cognizer {

class AliasCollision : public std::runtime_error {
public:
    std::string existing_id;
    std::string alias;
    AliasCollision(std::string id, std::string a)
        : std::runtime_error("alias collides with existing cognizer"),
          existing_id(std::move(id)), alias(std::move(a)) {}
};

class FiskeWeightsInvalid : public std::invalid_argument {
public:
    FiskeWeightsInvalid()
        : std::invalid_argument("fiske_weights must sum to 1.0 ± 1e-6") {}
};

class GroupTenantImplicit : public std::invalid_argument {
public:
    GroupTenantImplicit()
        : std::invalid_argument(
            "kind=group requires explicit tenant_id (08_cognizer.md:139); 'default' implicit rejected") {}
};

class CognizerNotFound : public std::invalid_argument { /* ... */ };

}  // namespace
```

---

## 7. 子系统 2：09_tom

### 7.1 文件清单

```
include/starling/tom/
  tom_engine.hpp                # ToMEngine + Context
  belief_tracker.hpp            # BeliefTracker (Outbox subscriber)
  mentalizing.hpp               # 4 Primitives 公共 API
  depth_estimator.hpp           # free function
  common_ground.hpp             # 空 read API + POD（writer 留 P2.b）

src/tom/
  tom_engine.cpp                # perspective_take 实现
  belief_tracker.cpp            # tick + checkpoint
  belief_tracker_handlers.cpp   # 6 个 event_type 处理
  mentalizing_believe.cpp       # what_does_X_believe
  mentalizing_know.cpp          # does_X_know(三态)
  mentalizing_misalign.cpp      # find_misalignment
  mentalizing_shared.cpp        # shared_with
  depth_estimator.cpp           # 7d 计数 + 1h TTL 缓存
  nesting_depth_writer.cpp      # StatementWriter 写时计算
  rate_limiter.cpp              # 10min 窗口去抖
  common_ground.cpp             # 空 read（总返回空 vector）

bindings/python/module.cpp      # 暴露 ToMEngine / BeliefTracker / Primitives
python/starling/tom/
  __init__.py
  primitives.py                 # 4 Primitive 便利包装
```

### 7.2 ToMEngine

```cpp
class ToMEngine {
public:
    ToMEngine(persistence::SqliteAdapter& adapter,
              cognizer::CognizerHub& hub,
              cognizer::KnowledgeFrontier& frontier);

    Context perspective_take(
        std::string_view target_cognizer_id,
        std::string_view tenant_id,
        std::string_view as_of_iso8601) const;
};

struct Context {
    std::vector<std::string> visible_engram_ids;   // KnowledgeFrontier::visible_engrams_at
    std::vector<retrieval::StatementRow> target_beliefs;  // SELECT WHERE holder=target
    std::vector<CommonGroundEntry> cg;             // P2.a 总返回空
};
```

`perspective_take` 实现:
1. `visible = frontier.visible_engrams_at(target, tenant_id, as_of)`
2. `target_beliefs = SELECT * FROM statements WHERE tenant_id=? AND holder_id=target AND time-anchored AND consolidation_state IN ('consolidated','archived') AND review_status NOT IN ('rejected','pending_review')`
3. `cg = common_ground::query(adapter_, self_id, target, tenant_id, as_of)` → 总返回空 list（P2.a）
4. 返回 `Context{visible, target_beliefs, cg}`

`self_id` 从 `RuntimeConfig.self_cognizer_id` 读，缺省 `"system_self"`。

### 7.3 BeliefTracker

```cpp
class BeliefTracker {
public:
    BeliefTracker(persistence::SqliteAdapter& adapter,
                  cognizer::CognizerHub& hub,
                  cognizer::KnowledgeFrontier& frontier);

    TrackerStats run_once();                        // 处理 last_checkpoint+1 到 max
    TrackerStats backfill_from_sequence_zero();     // 全量补处理（启动期）
};

struct TrackerStats {
    int events_processed = 0;
    int frontier_facts_written = 0;
    int trust_prior_updates = 0;
    int last_seen_updates = 0;
    int presence_log_writes = 0;
};
```

**6 个 event handler**：

| event_type | 处理 |
|---|---|
| `statement.written` | `record_explicit_told`(perceived_by[], statement_id) + `record_presence_from_statement`(perceived_by[], engram_id) + `update_last_seen_at`(perceived_by[]) + `record_explicit_negation`(若 stmt 含 negation_target) |
| `statement.archived` | 不处理（P2.a） |
| `statement.superseded` | 不处理（P2.a） |
| `evidence.appended` | `record_accessible_source`(holder, engram.adapter_name, engram_id) |
| `commitment.fulfilled` | trust_priors[holder][target] += 0.05（P2.c 才会 emit；P2.a handler 留 stub）|
| `commitment.broken` | trust_priors[holder][target] -= 0.05（同上）|

**触发**：与 §8.2 conflict_key backfill 同位 — Bus.write commit 后调用 `belief_tracker::tick_one_batch()`。

### 7.4 4 Mentalizing Primitives

| API | 输出 | 主算法 |
|---|---|---|
| `what_does_X_believe(adapter, x, about_y, tenant, as_of)` | `vector<StatementRow>` | SELECT WHERE holder=x AND subject=y AND time-anchored |
| `does_X_know(adapter, frontier, x, fact, tenant, as_of)` | `KnowsResult { FullKnowledge, NotKnown, Unknowable }` | 详见下 |
| `find_misalignment(adapter, x, y, subject, tenant, as_of)` | `Misalignment { only_x, only_y, confidence_diverges }` | 两次 what_does_X_believe + 对齐 |
| `shared_with(adapter, members, tenant, as_of)` | `vector<SharedFact>` | 全 members 都有同 (subject, predicate, canonical_object_hash, polarity) |

**`does_X_know` 三态算法**：
1. Direct query: `SELECT 1 FROM statements WHERE holder=x AND subject=fact.subject AND predicate=fact.predicate AND canonical_object_hash=fact.canonical_object_hash AND polarity='pos' AND time-anchored` → 命中 → `FullKnowledge`
2. 否则: `evidence_set = SELECT engram_id FROM ... evidence_json LIKE '%fact_evidence%'`
3. `visible = KnowledgeFrontier::visible_engrams_at(x, time)`
4. `evidence_set ∩ visible ≠ ∅` → `NotKnown`（应可调用但未显式断言）
5. 否则 → `Unknowable`（frontier 不可达）

### 7.5 ToMDepthEstimator (free function)

```cpp
namespace starling::tom::depth_estimator {

int estimate(
    persistence::Connection& conn,
    std::string_view partner_cognizer_id,
    std::string_view tenant_id,
    std::string_view as_of_iso8601);

}  // namespace
```

实现:
1. 查 `tom_depth_estimator_cache` WHERE tenant=? AND partner=?
2. 缓存命中且 `last_recomputed_at + 1h > now` → 返回缓存值
3. 缓存未命中或过期: 重算
   ```sql
   SELECT COUNT(*) FROM statements
    WHERE tenant_id=? AND holder_id=?
      AND nesting_depth = 1
      AND observed_at >= ?       -- as_of - 7 days
      AND observed_at <= ?
      AND consolidation_state IN ('consolidated','archived')
   ```
4. count ≥ 3 → 返回 2；count ∈ [1,2] → 返回 1；count = 0 → 返回 0
5. UPSERT 缓存表

### 7.6 nesting_depth_writer

```cpp
namespace starling::tom::nesting_depth_writer {

int compute_nesting_depth(
    persistence::Connection& conn,
    const extractor::ExtractedStatement& s);

}  // namespace
```

实现:
1. 若 `s.object_kind != "statement"` → 返回 0
2. 否则 `parent_id = s.object_value`
3. SQL: `SELECT nesting_depth FROM statements WHERE id=parent_id LIMIT 1`
4. 命中 → 返回 `parent.nesting_depth + 1`
5. 未命中（parent 不存在）→ 抛 `NestingDepthOverflow`（写入失败）

StatementWriter 集成（§8.1 调用方）:

```cpp
int computed = nesting_depth_writer::compute_nesting_depth(conn, s);
if (computed >= 2) {
    int est = depth_estimator::estimate(conn, s.holder_id, s.holder_tenant_id, s.observed_at);
    if (est < 2) {
        // partner 似乎不到二阶 → transient only, 不持久化
        return StatementWriteRejected{reason = "tom_depth_partner_lower_order",
                                       transient_only = true};
    }
}
if (computed > 2) {
    throw NestingDepthOverflow("nesting_depth > 2 hard limit");
}
// 双限流: tom_inferred 同 key 10min 窗口 1 条
if (s.provenance == "tom_inferred" &&
    !rate_limiter::allow_tom_inferred_write(conn, ...)) {
    return StatementWriteRejected{transient_only = true};
}
```

### 7.7 rate_limiter

```cpp
bool rate_limiter::allow_tom_inferred_write(
    persistence::Connection& conn,
    std::string_view holder_id, std::string_view subject_id,
    std::string_view predicate, std::string_view canonical_object_hash,
    std::string_view tenant_id);
```

实现:
```sql
SELECT 1 FROM statements
 WHERE provenance='tom_inferred'
   AND tenant_id=? AND holder_id=? AND subject_id=?
   AND predicate=? AND canonical_object_hash=?
   AND observed_at >= ?            -- now - 600s
 LIMIT 1
```

无命中 → 允许；有命中 → 拒绝（返回 false）。

链长限流复用 05_bus 的 `compute_child_chain` + `CausationOverflow`（M0.7 既有），09_tom 不重复实现。

### 7.8 错误类型

```cpp
namespace starling::tom {

class TrackerEventFailed : public std::runtime_error { ... };
class NestingDepthOverflow : public std::runtime_error { ... };

}  // namespace
```

---

## 8. 子系统扩展 1：05_bus

### 8.1 改动概要

P2.a 在 05_bus 上的工作只是补完 §16.3-5（CONFLICTS_WITH 边唯一性）。`canonical_conflict_key_hex` 7-tuple SHA-256 已在 M0.5 实现并锁定（`include/starling/bus/conflict_key.hpp`），无需重做。

### 8.2 数据流（P2.a 后）

```
Bus::write()
    │
    ▼
ConflictProbe::scan() (M0.5/M0.7 既有)
    │
    ├─ 无 match → 仅 statement.written
    │
    ├─ DirectContradiction / Superseding
    │     → apply_supersedes_atomic()
    │         → insert_statement_edge(..., "supersedes", nullopt)
    │         → emit statement.archived + statement.superseded
    │
    ├─ PartialOverlap / Adjacent
    │     → insert_statement_edge(..., "conflicts_with", conflict_key_hex) ◀── 改动
    │         ├─ 首次 → INSERT 成功
    │         └─ SQLITE_CONSTRAINT (UNIQUE 违反) → 
    │               std::fprintf(stderr, "[bus.conflict_key] WARN ...");
    │               return; (noop)
    │     → emit belief.conflict (idempotency_key 自带 10s 窗口去抖)
    │
    └─ MildCorrection → confidence bump（无边）

Bus::write commit (主事务结束)
    │
    ├─→ conflict_key_backfill::tick_one_batch(conn, 100)  ◀── 新增（与 09_tom 同位）
    │     仅当 conflict_key_backfill_state.completed_at IS NULL
    │     SAVEPOINT 内进行；失败回滚不影响主写入
    │
    └─→ belief_tracker::tick_one_batch(adapter, hub, frontier)  ◀── 新增
          复用同样 tick 模型
```

### 8.3 backfill 工具

```cpp
namespace starling::bus::conflict_key_backfill {

bool is_complete(persistence::Connection& conn);
TickStats tick_one_batch(persistence::Connection& conn, int batch_size);

}  // namespace
```

`tick_one_batch` 算法:
1. 检查 `conflict_key_backfill_state.completed_at IS NOT NULL` → 短路返回
2. 从 `last_processed_edge_id` 起 SELECT 下一批 N 行 conflicts_with 边（按 id 排序）
3. 对每行：JOIN statements 取 7-tuple → 调 `canonical_conflict_key_hex(stmt)`
4. UPDATE statement_edges SET canonical_conflict_key=? WHERE id=?
5. 若 UPDATE 触发 UNIQUE 违反（已存在等价 key）→ DELETE 这一行（去重计数 +1）
6. 更新 `conflict_key_backfill_state.last_processed_edge_id` + counters
7. 若本批返回 0 行 → 标 `completed_at = now`

每次 Bus.write commit 摊一批 → 在中等流量下 ~分钟级完成；空闲系统下 backfill 需被推动（接受）。

### 8.4 边写入路径修改

```cpp
// src/bus/bus.cpp 既有 insert_statement_edge() 加第 6 参
void insert_statement_edge(
    persistence::Connection& conn,
    std::string_view src_id, std::string_view dst_id,
    std::string_view tenant_id, std::string_view edge_kind,
    std::optional<std::string> canonical_conflict_key);  // 新增
```

调用点:
- `apply_supersedes_atomic` 内 supersedes 边 → 第 6 参传 `std::nullopt`
- `partial_overlap` / `adjacent` 分支 → 传入 `match->conflict_key_hex`

UNIQUE 冲突处理:
```cpp
const int rc = sqlite3_step(stmt.get());
if (rc == SQLITE_CONSTRAINT && canonical_conflict_key.has_value()) {
    std::fprintf(stderr,
        "[bus.conflict_key] WARN dedup hit on canonical_conflict_key=%s "
        "(edge_kind=conflicts_with, tenant=%s); existing edge retained.\n",
        canonical_conflict_key->c_str(),
        std::string(tenant_id).c_str());
    return;
}
if (rc != SQLITE_DONE) throw make_sqlite_error(...);
```

---

## 9. 子系统扩展 2：13_retrieval

### 9.1 改动概要

`basic_retrieve` 加可选 `apply_frontier_filter` 参数，默认 `false` 保 P1 13 CRITICAL 兼容。

### 9.2 接口扩展

```cpp
// include/starling/retrieval/basic_retriever.hpp
struct BasicRetrieverParams {
    // 现有字段保留（10 个 filters_applied 维度的 input）
    bool apply_frontier_filter = false;            // 新增
};
```

### 9.3 SQL 扩展

当 `apply_frontier_filter=true` 时，`basic_retriever.cpp` 在主 SELECT 末尾追加:

```sql
   AND EXISTS (
       SELECT 1
         FROM ( -- visible_engrams_at(holder, as_of) inline 子查询
             SELECT engram_id FROM cognizer_presence_log
              WHERE tenant_id=?1 AND cognizer_id=?2 AND observed_at <= ?5
             UNION
             SELECT source_engram_id FROM cognizer_frontier_facts
              WHERE tenant_id=?1 AND cognizer_id=?2
                AND fact_kind IN ('explicit_told','accessible_source','membership')
                AND asserted_at <= ?5
             EXCEPT
             SELECT source_engram_id FROM cognizer_frontier_facts
              WHERE tenant_id=?1 AND cognizer_id=?2
                AND fact_kind = 'explicit_not_told'
                AND asserted_at <= ?5
         ) AS visible
        WHERE statements.evidence_json LIKE '%' || visible.engram_id || '%'
   )
```

性能预算：1k engrams + 100 cognizers fixed query ≤ 50ms。如果跌出预算，加 materialized 索引或拆分查询。

### 9.4 RetrievalReceipt.filters_applied 扩展

```cpp
// include/starling/retrieval/retrieval_receipt.hpp 内
struct RetrievalReceipt {
    // 现有字段...
    bool frontier_applied = false;        // 新增
    int frontier_masked_count = 0;        // 新增
};
```

filters_applied list 从 10 项变 12 项:
```python
{
    # ... 既有 10 项 ...
    "frontier_applied": "true" or "false",
    "frontier_masked_count": "<N>",
}
```

`frontier_masked_count` 是过滤后被排除的 statement 数（pre-filter total - post-filter total）。

### 9.5 Python wrapper

```python
def basic_retrieve(
    adapter, *,
    tenant_id, holder, subject, predicate, as_of,
    holder_perspective=None,
    apply_frontier_filter=False,        # 新增 kwarg
    trace_id=None, query_id=None,
) -> BasicRetrieveResult: ...
```

P1 13 CRITICAL 测试不传 `apply_frontier_filter` → 默认 False → 行为零变化 ✅

---

## 10. 非子系统：extractor v12 prompt（带 fallback）

### 10.1 设计

v12 在 v11 基础上加一条规则识别 "X 不知道 Y" / "我没告诉 Bob" 等否定式句式，输出带新字段的 statement:

```python
# v12 增量规则示例输出:
{
    "holder": "self",
    "subject": "Bob",
    "predicate": "knows",
    "object": "<the_fact_text>",
    "polarity": "NEG",
    "negation_subject": "Bob",       # 新字段
    "nesting_depth": 1
}
```

`negation_subject` 字段透传到 `statements.metadata`（或新加一列；plan 阶段决定）。

BeliefTracker handler 见 §7.3：当看到 `statement.written` event 且 stmt 含 `negation_subject` → 调 `KnowledgeFrontier::record_explicit_negation`.

### 10.2 EVAL 风险与 fallback

P2.a plan 在 v12 落地后**强制运行**:
- 3 round P1 §15.3.3 EVAL（既有 50 record corpus，5 个阈值）

**Fallback 决策树**：

| EVAL 结果 | 路径 |
|---|---|
| 5 阈值全过 | v12 留下；BeliefTracker 调 record_explicit_negation；五类 frontier 全部 active ✅ |
| 任一阈值跌 | git revert v12 回 v11；`KnowledgeFrontier::record_explicit_negation` 实现保留但 BeliefTracker handler 内的调用注释关闭；`cognizer_frontier_facts.fact_kind='explicit_not_told'` 在 P2.a 内永久空（P2.b 重启用） |

P2.a CRITICAL TC-FRONTIER-FIVE-WAY 不依赖 v12 — 测试通过 SQL 直接 INSERT explicit_not_told 行验证 visible_engrams_at 五路逻辑（不走 extractor 路径）。

---

## 11. 非子系统：ToMBench eval harness

### 11.1 数据

- 来源：HuggingFace `Sky-Lin/ToMBench` 的 first-order subset
- 落地路径：`tests/data/eval_tom_bench/first_order.jsonl`
- 仅取 `ability ∈ {unexpected-outcome, desire, persuade, world-knowledge}` 子集 → P2.a 4 primitive 可覆盖；false-belief 等需 depth=2 reader 的子集留 P3
- 估计样本数 ~400

### 11.2 Harness

```bash
python scripts/eval_tom_bench.py \
    --corpus tests/data/eval_tom_bench/first_order.jsonl \
    --rounds 3 \
    --report build/eval_tom_bench.md \
    --backend openai \
    --model gpt-4o-mini
```

工作流程:
1. 读 JSONL
2. 对每个 question:
   a. CognizerHub.register 该 story 中的所有角色
   b. 用 extractor 把故事陈述抽取成 statements（走真 P2.a 路径）
   c. 调 BeliefTracker tick 同步 frontier
   d. perspective_take + 选合适 primitive (基于 question.ability):
      - `unexpected-outcome` → `does_X_know(fact)` 三态
      - `desire` → `what_does_X_believe(about=desire_target)`
      - `persuade` → `find_misalignment(between=[X,Y], about=Z)`
      - `world-knowledge` → 直接 SELECT FROM statements
   e. 把结果 map 到候选答案（基于关键词 / similarity）
3. accuracy per round → `build/eval_tom_bench.md` 表格

### 11.3 阈值

最后一轮 first-order easy subset accuracy ≥ **0.55**（保守值；GPT-4 baseline ~0.63）。低于阈值 → P2.a milestone close BLOCKED。

---

## 12. 非子系统：FANToM eval harness

### 12.1 数据

- 来源：HuggingFace `skywalker023/fantom`
- 落地路径：`tests/data/eval_fantom/conversations.jsonl`（10k 全量入 git，但 .gitignore 大于 100MB → 加 LFS 或 fetch 脚本）
- 实际跑 1k 抽样：`random.seed(20260526); random.sample(all, 1000)`

### 12.2 Harness

```bash
python scripts/eval_fantom.py \
    --corpus tests/data/eval_fantom/conversations.jsonl \
    --rounds 3 \
    --sample-size 1000 \
    --seed 20260526 \
    --report build/eval_fantom.md \
    --backend openai \
    --model gpt-4o-mini \
    --question-types factual,belief,answerability
```

工作流程:
1. fixed seed 抽 1000 conversations
2. 对每个 conversation:
   a. CognizerHub.register 全部 participants
   b. 按 turns 时序 extractor 抽取 + BeliefTracker tick
      - 关键: perceived_by 设为该 turn 的 audience（FANToM 数据自带）
      - 当 FANToM 标记 "X left the room" → KnowledgeFrontier::record_explicit_negation 标 explicit_not_told
   c. 对每个 question (factual / belief / answerability):
      - factual: SELECT statements 直接答
      - belief: what_does_X_believe + 比对
      - answerability: does_X_know(三态) → FullKnowledge="yes" / NotKnown="maybe" / Unknowable="no"
3. accuracy per round per question_type
4. 三 round stddev per question_type

### 12.3 验收门槛（spec §16.3-2 "准备完毕"）

- 100% 题目跑通（无崩溃 / 无 timeout）
- 三 round per-question-type accuracy stddev ≤ 0.05
- 实际 accuracy 不限定阈值，作为 P3 baseline 记录
- 输出 `build/eval_fantom.md` 含每 round 详细数据 + summary 表

低于上述任一 → P2.a milestone close BLOCKED。

---

## 13. 测试策略

### 13.1 9 个 P2.a CRITICAL（按子系统分布）

#### 08_cognizer (5 个 CRITICAL)

| ID | 测试文件 | 验证 |
|---|---|---|
| TC-COG-REGISTER | `tests/python/test_tc_cog_register.py` | 注册两次同 (kind, external_id) 返回同 UUID5 id；last_seen_at 刷新 |
| TC-COG-ALIAS-MERGE | `tests/python/test_tc_cog_alias_merge.py` | 写 cognizer A alias=["alice"]; 写 cognizer B 同 alias=["alice"] / "Alice" / "alice "（normalize 后等价）→ AliasCollision |
| TC-COG-CROSS-TENANT | `tests/python/test_tc_cog_cross_tenant.py` | for_group(tenant_id=未指定) → GroupTenantImplicit |
| TC-RELATION-FISKE | `tests/python/test_tc_relation_fiske.py` | upsert_relation 4 mode 权重和 != 1 → FiskeWeightsInvalid；正确 round-trip |
| TC-FRONTIER-FIVE-WAY | `tests/python/test_tc_frontier_five_way.py` | 直接 INSERT 五类 frontier_facts → visible_engrams_at 返回正确并集 - 减集 |

#### 05_bus (1 个 CRITICAL)

| ID | 测试文件 | 验证 |
|---|---|---|
| TC-CONFLICT-KEY-UNIQUE | `tests/python/test_tc_conflict_key_unique.py` | 写 3 条 partial_overlap statements → 仅 1 条 conflicts_with 边落地（UNIQUE 起作用）|

#### 09_tom (3 个 CRITICAL)

| ID | 测试文件 | 验证 |
|---|---|---|
| TC-PERSPECTIVE-RUNTIME | `tests/python/test_tc_perspective_runtime.py` | perspective_take(alice, t).visible_engram_ids 与 frontier.visible_engrams_at(alice, t) 一致；target_beliefs 与直接 SELECT holder=alice 一致；cg=[] |
| TC-MENTAL-BELIEVE | `tests/python/test_tc_mental_believe.py` | 多 holder 数据下 what_does_X_believe(X) 仅返回 X 的 statements；as_of 边界正确 |
| TC-MENTAL-MISALIGN | `tests/python/test_tc_mental_misalign.py` | alice/bob 对 carol 的分歧 → find_misalignment 正确分组 only_x / only_y / confidence_diverges |

### 13.2 非 CRITICAL roll-up（覆盖运行时正确性）

包含但不限于：
- `test_belief_tracker_idempotent.py`：tick 多次结果不变
- `test_belief_tracker_checkpoint.py`：重启后从 checkpoint+1 恢复
- `test_depth_estimator_cache.py`：1h TTL
- `test_nesting_depth_writer.cpp`：object_kind='statement' 自动 +1
- `test_rate_limiter_10min_window.py`：tom_inferred 同 key 10min 窗口
- `test_conflict_key_backfill.cpp`：迁移后 backfill 正确性
- `test_basic_retrieve_frontier_integration.py`：frontier 过滤端到端
- `test_v12_prompt_negation.py`：10 个 negation fixture（v12 落地后）
- `test_eval_tom_bench_harness.py` / `test_eval_fantom_harness.py`：harness 自测

### 13.3 P1 回归保护

P2.a CI pipeline 每次跑：
- ctest 全量（M0.7 close 时 255/255）
- pytest 全量（M0.7 close + follow-ups 时 331/13）
- ci_static_scan.py（无 starling::testing 泄漏）
- 3 round P1 §15.3.3 EVAL（仅当 v12 prompt 改动时强制；§10.2 fallback 决策由此处触发）

### 13.4 性能基准

非阻塞但需在 plan 阶段验证：

| 路径 | 预算 |
|---|---|
| basic_retrieve + frontier (1k engram, 100 cognizer) | ≤ 50ms |
| BeliefTracker tick_one_batch (50 events) | ≤ 100ms |
| ToMDepthEstimator.estimate (cache miss) | ≤ 10ms |
| ToMDepthEstimator.estimate (cache hit) | ≤ 1ms |
| perspective_take | ≤ 30ms |
| ToMBench 1 round | ≤ 30 min |
| FANToM 1 round (1k items) | ≤ 30 min |

---

## 14. 错误与不变量

### 14.1 不变量清单

| 不变量 | 实现位置 | 检查时机 |
|---|---|---|
| `cognizers.id == UUID5(kStarlingCognizerNamespace, kind+"\x1f"+external_id)` | CognizerHub::register_cognizer | 写入前 |
| `cognizers.aliases_normalized_json` per entry == `normalize_alias(aliases_json[i])` | CognizerHub::register_cognizer | 写入前 |
| `kind=group → tenant_id !="default" 或显式 tenant_explicitly_set=true` | CognizerHub::register_cognizer | 写入前 |
| `sum(cognizer_relations.fiske_weights) ∈ [1.0±1e-6]` | CognizerHub::upsert_relation | 写入前 |
| `affinity ∈ [0,1]` | SQL CHECK + Hub 校验 | 双层 |
| `statement_edges WHERE edge_kind='conflicts_with' AND canonical_conflict_key IS NOT NULL` 对 (tenant_id, canonical_conflict_key) 唯一 | SQL partial UNIQUE 索引 | DB 层 |
| ~~`statements.nesting_depth ≤ 2`（P2.a 硬上限）~~ → 任意多阶（2026-06-17 拆三阶认知帽，改 cycle 护栏 + 软上限 `max_nesting_depth`=32；见 `2026-06-17-arbitrary-multi-order-tom-design.md`） | nesting_depth_writer + StatementWriter | 写入前 |
| BeliefTracker 处理事件时单 outbox_sequence 仅 advance checkpoint 一次（idempotent） | run_once 用 SAVEPOINT | tick 时 |
| `tom_belief_tracker_checkpoint`/`conflict_key_backfill_state` 是 singleton（id=1） | SQL CHECK constraint | DB 层 |
| common_ground 表存在但 P2.a 内 INSERT 路径不执行 | spec annotation + 无 writer 代码 | 静态 |

### 14.2 错误类型汇总

| 类型 | 来源 | 触发 |
|---|---|---|
| `cognizer::AliasCollision` | CognizerHub::register_cognizer | normalized alias 命中其他 cognizer |
| `cognizer::FiskeWeightsInvalid` | CognizerHub::upsert_relation | sum != 1.0±1e-6 |
| `cognizer::GroupTenantImplicit` | CognizerHub::register_cognizer | kind=group + tenant 隐式 default |
| `cognizer::CognizerNotFound` | CognizerHub::get / ToMEngine::perspective_take | id 不存在 |
| `tom::TrackerEventFailed` | BeliefTracker handler | event 处理失败但需继续后续 events |
| `tom::NestingDepthOverflow` | nesting_depth_writer | parent 不存在 / 计算结果 > 2 |
| `bus::CausationOverflow` (M0.7 既有) | compute_child_chain | causation_chain 长度 > 3 |

---

## 15. 实施顺序约束

P2.a plan 必须按以下偏序执行（plan 阶段细化为 task 列表）：

1. **必须先于其他**: migration 0008（cognizers 表）；其后所有 cognizer-依赖代码才有 schema
2. **必须先于其他**: include/starling/version.hpp 加 kStarlingCognizerNamespace（uuid5.cpp 依赖）
3. **08_cognizer 完整** → 09_tom 才能开工（ToMEngine 直接依赖 CognizerHub + KnowledgeFrontier）
4. **09_tom BeliefTracker 上线** → 13_retrieval frontier 接入才有意义（否则 frontier 表始终空）
5. **05_bus §16.3-5 改动** 与 cognizer / tom 完全独立，可并行（plan 内可重排）
6. **v12 prompt** 必须在 BeliefTracker handler 完成后落 → EVAL 风险才能被检验
7. **ToMBench / FANToM harness** 必须在 4 Mentalizing primitives + perspective_take 完成后才能跑
8. **9 个 CRITICAL** 在对应子系统完成后立即写，不堆到最后

---

## 16. P2 准入对照（§16.3）

| 项 | P2.a 后状态 |
|---|---|
| §16.3-1 ProfileCapability cross_partition_transaction | P1 local-store 单分区天然 true ✅ |
| §16.3-2 ToMBench + FANToM 准备完毕 | §11/§12 双 harness + 跑完 ✅ |
| §16.3-3 Projection repair safety | P2.b（不在 P2.a） |
| §16.3-4 Reconsolidation 再巩固窗口配置 | P2.b |
| §16.3-5 CONFLICTS_WITH 边唯一性 | §8.2 ConflictProbe 收尾 ✅ |
| §16.3-6 Projection Index repair guard | P2.b |
| §16.3-7 Replay 状态机契约 | P2.b |
| §16.3-8 Commitment 契约 | P2.c |
| §16.3-9 Reconsolidation 兼容性 | P2.b（P2.a 不破坏 P1 同步路径，TC-NEW-CONFLICT-SEVERE 仍跑通 ✅）|
| §16.3-10 评测加载 | §11/§12 替代 §15.3.3 50 sample 作为 P2 后权威 ✅ |

§16.3 中 -2 / -5 / -9 / -10 是 P2.a 直接覆盖的；其余项 P2.b / P2.c 才接。

---

## 17. 工作量与风险

### 17.1 代码量预估

| 块 | LOC |
|---|---|
| 08_cognizer C++ | ~1800 |
| 09_tom C++ | ~2500 |
| 05_bus 改动 | ~280 |
| 13_retrieval 改动 | ~150 |
| Migrations | ~250 SQL |
| Python wrappers | ~600 |
| Eval harness | ~900 |
| Tests | ~2500 |
| spec / plan | ~1100 markdown |

**Production code**: ~6000 行；**Tests**: ~2500 行；**Spec/Plan**: ~1100 行。

M0.7 同尺寸是 ~3800 prod + ~3000 test。P2.a 是 1.6× M0.7。

### 17.2 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| v12 prompt 跌 P1 EVAL F1 阈值 | 中 | §10.2 fallback 决策树（回滚 v11，frontier explicit_not_told 留空到 P2.b）|
| `basic_retrieve + frontier` 性能 > 50ms | 中 | plan 阶段 micro-benchmark；超预算则加 materialized 索引 |
| ToMBench accuracy < 0.55 | 中 | 仅取 4 primitive 能覆盖的 easy subset；spec 阈值是保守值 |
| FANToM stddev > 0.05 | 低 | fixed seed 保 reproducibility；偏差大说明 LLM 不稳，不是 harness 问题 |
| Backfill stuck（系统空闲） | 低 | 接受；plan 阶段加 force_complete API 供运维触发 |
| BeliefTracker 性能拖慢 Bus.write | 中 | tick 用 SAVEPOINT 隔离，失败不影响主写入；batch_size 可调 |
| Cognizer FK soft-join 漂移（应用层校验缺失） | 低 | 9 个 CRITICAL 中 TC-COG-REGISTER + TC-COG-ALIAS-MERGE 守门 |

---

## 18. 元数据

- **里程碑代号**: P2.a
- **roadmap 行**: `docs/superpowers/plans/2026-05-23-roadmap.md` 第 71 行（P2.a 社会心智 Schema）
- **预估周期**: 4 周（roadmap 给的范围；按 brainstorm 阶段决策不拆分）
- **分支策略**: worktree-p2-a-social-mind 隔离 worktree，--no-ff 合并 main
- **依赖**: M0.7 close 后 4 follow-ups（commits `3042a2a / ff7b1f6 / b462c5a / 437b59a`）
- **后继**: P2.b 类脑动力学（Hippocampus / Neocortex / Replay / Reconsolidation / CommonGround writer）

---

## 19. 修订记录

- **2026-05-26 v1**: 初版 spec，基于 14 个 brainstorming 决策点 + Section A→F 调整后的最终设计。
