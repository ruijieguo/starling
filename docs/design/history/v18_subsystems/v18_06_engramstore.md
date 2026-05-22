# EngramStore

## 功能定义

EngramStore 是与 [Hippocampus](v18_06_hippocampus.md) / [Neocortex](v18_07_neocortex.md) 平级的全局证据子系统，存储 verbatim 原档，按 `retention_mode` 管理内容生命周期；审计元数据 append-only，内容是否可恢复由加密策略决定。它是 `Statement.evidence` 指向的物理目标，所有写入须经 [Bus](v18_05_bus.md)`.append_evidence`，不允许组件直接读写底层 blob。它不做：派生抽取、检索排序、业务逻辑路由。

---

## 主要流程

### 1. append_evidence 写入

```
客户端
  → Bus.append_evidence(source, content, source_kind, adapter_name,
                         ingest_mode, declared_transformations,
                         privacy_class, perceived_by,
                         retention_mode, source_trust)
      → EvidenceValidator
          ├─ source_kind + ingest_policy 先行计算
          │     NO_STORE → 仅写 audit event，不创建 Engram，终止
          │     REQUIRE_REVIEW → 创建 Engram，review_status=PENDING_REVIEW
          │     STORE / STORE_METADATA_ONLY → 继续
          ├─ 幂等检查：(adapter_name, source_item_id, version, chunk_index)
          │     已存在 → 返回已有 EngramRef，不重复写
          └─ declared_transformations 合法性校验
      → EngramStore.put(engram)
          ├─ 生成 per-record encryption key（生产 profile 必须）
          ├─ 加密 content → content_ciphertext
          ├─ 计算 content_hash（sha256；含 declared_transformations 域）
          ├─ 持久化 Engram（S3 / 本地 fs / Letta archival / memU Rust blob）
          └─ 返回 EngramRef
      → outbox.append(evidence.appended)   ← 同事务提交
  → [异步] Extractor 消费 evidence.appended → 生成 Statement
```

`metadata_only` 模式不满足"verbatim evidence"要求：高影响 Statement 须至少一条 `byte_preserving` 或外部可信 evidence 才能自动 `APPROVED`；Context Pack 须标注 `evidence_kind=metadata_only`，不得包装成一手原文。

### 2. 检索回流

```
Retrieval Planner
  → 从 Statement.evidence 取 SourceSpanRef
  → EngramStore.get(engram_ref)
      ├─ retention_mode == crypto_erasure → 返回 ERASED（仅 content_hash + erased_at）
      ├─ retention_mode == redacted_retain → 返回 redacted_content（无原文）
      └─ 其余 → 解密 content_ciphertext，返回 verbatim 原档
  → 按 SourceSpanRef.(chunk_index / span_start / span_end) 定位片段
  → 拼装 Context Pack
```

`segment_map` 中无对应 `segment_id` 的 offset 引用视为非法，Retrieval 须拒绝并记录 audit event。

### 3. retention_mode 生命周期状态迁移

```
新建 Engram
  retention_mode = policy.choose(source, content, jurisdiction)
        ↓
  audit_retain ──── 到期 ────→ crypto_erasure
  legal_hold   ──── 解冻令 ──→ audit_retain 或 crypto_erasure
  redacted_retain            （终态；原文已替换）
  crypto_erasure             （终态；密钥已销毁）
```

合规引擎（[Governance](v18_05_governance.md)）持有状态迁移授权；EngramStore 本身不自主触发迁移，仅执行指令并追加 `audit_trail`。

### 4. crypto_erasure 反向传播

```
Governance → EngramStore.erase(engram_id)
  → 销毁 encryption key（key shredding）
  → content_ciphertext 置 None；保留 content_hash + erased_at
  → EvidenceRef.status = ERASED（Statement.evidence 引用不删除）
  → [异步] Compliance Engine 事务写 outbox：
        evidence.erased
          → 直接抽取自该 Engram 且无其他未擦除 evidence 的 Statement
              → statement.forgotten（Statement 进入 FORGOTTEN）
          → 仅 derived_from 依赖上述 Statement 且无独立 evidence 的派生 Statement
              → statement.review_requested 或 statement.forgotten
                （按影响级别；默认只传播一层，避免认知链雪崩）
          → 有独立未擦除 evidence 的 Statement
              → confidence 下调 + Context Pack 标注"部分证据已擦除"
```

共享 Engram（多 Cognizer 引用同一条记录）：任一主体触发 `crypto_erasure` 时，共享记录须拆分引用或整体加密擦除，不得继续向其他 holder 暴露原文（最严格访问者 wins）。

---

## 核心算法

### 1. per-record encryption key 生成与 key shredding

每条 Engram 在 `put` 时生成独立对称密钥（AES-256-GCM 或等价），加密 `content_ciphertext`；密钥引用写入 `key_ref`，存放于与 blob 隔离的 KMS / keystore。

`crypto_erasure` 执行路径：

```
EngramStore.erase(engram_id)
  → KMS.delete_key(key_ref)          # 不可逆销毁密钥
  → Engram.key_ref = None
  → Engram.content_ciphertext = None # 或保留密文（无密钥则不可解）
  → 保留 content_hash / audit_trail / source / metadata
```

`content_hash` 作为不可恢复证明：在原文不可访问的情况下仍可验证"曾存在该内容"并出具合规报告。生产 profile 须在 adapter conformance test 中证明 key shredding 后密文无法还原。

### 2. retention_mode 状态机

```
状态              合法后继                   触发条件
─────────────────────────────────────────────────────────
legal_hold      → legal_hold（保持）         解冻令缺失
legal_hold      → audit_retain              合规解冻授权
legal_hold      → crypto_erasure            合规强制清除授权
audit_retain    → audit_retain（保持）       retention_policy 未到期
audit_retain    → crypto_erasure            到期或删除权请求
redacted_retain （终态）                     原文已不可恢复（脱敏文本替换）
crypto_erasure  （终态）                     密钥已销毁，内容不可恢复
```

状态迁移须由 Governance 授权事件驱动；EngramStore 不接受无 audit event 的原地修改。

### 3. crypto_erasure 反向传播仅一层的判定逻辑

传播层级控制防止单次擦除引发认知链雪崩：

```
propagate_erasure(erased_engram_id, depth=0, max_depth=1):
  for stmt in statements_referencing(erased_engram_id):
    remaining_evidence = [e for e in stmt.evidence if e.status != ERASED]
    if not remaining_evidence:
      stmt.review_status = FORGOTTEN
      emit statement.forgotten
      if depth < max_depth:
        for derived in stmts_derived_from(stmt):
          derived_remaining = [e for e in derived.evidence if e.status != ERASED]
          if not derived_remaining:
            derived.review_status = (FORGOTTEN if high_impact else REVIEW_REQUESTED)
            emit statement.forgotten / statement.review_requested
          # depth+1 == max_depth：不再递归
    else:
      stmt.confidence = recalculate_confidence(remaining_evidence)
      annotate_context_pack(stmt, "部分证据已擦除")
```

`max_depth=1` 为系统默认值；Governance 可在特定合规场景（如 GDPR right-to-erasure full purge）显式请求深度递归，须附加审计授权令牌。

---

## 数据结构

```python
class EngramRetentionMode(str, Enum):
    LEGAL_HOLD      = "legal_hold"       # 密文 + 密钥均保留；禁止 purge；访问须审计
    AUDIT_RETAIN    = "audit_retain"     # 保留密文；按 retention_policy 到期转 crypto_erasure
    REDACTED_RETAIN = "redacted_retain"  # 原文替换为脱敏文本；保留 hash；仅可恢复脱敏片段
    CRYPTO_ERASURE  = "crypto_erasure"   # 密钥销毁；内容不可恢复；仅 hash + 元数据留存

class SourceKind(str, Enum):
    USER_INPUT        = "user_input"
    EXTERNAL_DOC      = "external_doc"
    TOOL_OBSERVATION  = "tool_observation"
    SYSTEM_INTERNAL   = "system_internal"
    OBSERVER_AGENT    = "observer_agent"
    REPLAY_OUTPUT     = "replay_output"

class IngestPolicy(str, Enum):
    STORE               = "store"
    NO_STORE            = "no_store"              # 不创建 Engram，只写 audit event
    STORE_METADATA_ONLY = "store_metadata_only"
    REQUIRE_REVIEW      = "require_review"

class Engram:
    id:                     UUID
    source:                 SourceRef
    source_kind:            SourceKind
    ingest_policy:          IngestPolicy
    adapter_name:           Optional[str]          # 写入源适配器名称；直写须用 "direct_api"
    adapter_version:        Optional[str]
    ingest_mode:            Literal["chunked_content", "whole_record", "metadata_only"]
    declared_transformations: list[str]            # 空集才可声明 byte_preserving
    privacy_class:          Literal["public", "internal", "personal", "sensitive", "regulated"]
    byte_preserving:        bool                   # 仅 declared_transformations=[] 且 conformance test 通过时为 true
    content_ciphertext:     Optional[bytes]        # crypto_erasure 后为 None
    redacted_content:       Optional[str]          # redacted_retain 使用
    content_hash:           str                    # sha256；永远保留；含 declared_transformations 域
    retention_mode:         EngramRetentionMode
    key_ref:                Optional[KeyRef]       # 内容密钥引用；crypto_erasure 后销毁
    chunk_index:            int
    speaker:                Optional[CognizerRef]
    timestamp:              datetime
    source_time_range:      Optional[TimeRange]    # 源记录覆盖的真实时间范围；可跨多消息/episode
    segment_map:            list[SourceSegment]    # P2+ 片段级 offset/role/speaker；P0 可为空
    audit_trail:            list[AuditEventRef]    # append-only

class SourceSegment(BaseModel):
    segment_id:   str
    chunk_index:  int
    span_start:   Optional[int]
    span_end:     Optional[int]
    role:         Optional[Literal["user", "assistant", "tool", "system", "document"]]
    speaker:      Optional[CognizerRef]
    observed_at:  datetime
    content_hash: str

class EngramRef(BaseModel):
    engram_id:    UUID
    content_hash: str                              # 快速完整性验证
    retention_mode: EngramRetentionMode

class SourceSpanRef(BaseModel):
    # P0 最小字段
    engram_ref:   EngramRef
    chunk_index:  int
    observed_at:  datetime
    source_hash:  str
    # P2+ 片段级字段（需 segment_map 支撑）
    segment_id:   Optional[str]
    span_start:   Optional[int]
    span_end:     Optional[int]

class TemporalAnchor(BaseModel):
    """Statement 时间定位锚；由 Extractor 从 Engram.source_time_range 派生。"""
    engram_ref:      EngramRef
    observed_at:     datetime
    source_time_range: Optional[TimeRange]
    review_status:   Literal["CONFIRMED", "INFERRED_UNREVIEWED", "DISPUTED"]
    # adapter 无法给出片段级时间时，Engram.timestamp 作 fallback，
    # 所有相对时间抽取默认 review_status=INFERRED_UNREVIEWED
```

---

## 相关概念

**verbatim 原档 vs 派生 Statement**
Engram 存储原始输入字节（或其加密/脱敏形式）；Statement 是由 Extractor 从 Engram 抽取的结构化命题。两者之间存在 `evidence` 引用链，原档不可由 LLM 自造或合并生成。`ingest_mode=metadata_only` 的 Engram 不满足 verbatim 要求。

**evidence_hash**
`content_hash`（sha256）永久保留，即使内容不可恢复。用于：合规报告（证明"曾存在"）、`EvidenceRef.status=ERASED` 后的完整性追溯、防止 silent hash collision。`declared_transformations` 列表纳入 hash 域，确保不同 normalization pipeline 的同源字节产生不同 hash。

**crypto_erasure / key shredding / per-record key**
每条 Engram 持有独立对称密钥，存于与 blob 隔离的 KMS。`crypto_erasure` 通过销毁密钥（key shredding）使密文永久不可解，而非物理删除字节。生产 profile 须证明 key shredding 不可逆方能声明支持此模式。

**retention_mode 四值**
见"数据结构"节 `EngramRetentionMode` 枚举及其语义注释。四值均为终态或单向迁移；`legal_hold` 是唯一可向其他模式迁移的非终态。

**ERASED / REDACTED / FORGOTTEN 三态**

| 术语 | 作用域 | 含义 |
|---|---|---|
| `ERASED` | `EvidenceRef.status` | 对应 Engram 的内容已不可恢复（crypto_erasure 后置位） |
| `REDACTED` | Engram 内容层 | 原文被脱敏文本替换（`redacted_retain` 模式） |
| `FORGOTTEN` | Statement.review_status | Statement 失去所有有效 evidence，不再参与检索与推断 |

**shared engram refcount**
多 Cognizer 可引用同一条 Engram。任一主体触发 `crypto_erasure` 时，"最严格访问者 wins"规则生效：共享记录须整体擦除或拆分引用后分别擦除，不得向其余 holder 继续暴露原文。refcount 维护由 EngramStore 内部执行；[Bus](v18_05_bus.md) 不感知具体引用计数，仅转发 Governance 授权令牌。

**相关子系统**

- [Bus](v18_05_bus.md)：`append_evidence` 唯一写入入口；`evidence.appended` 事件发布方。
- [Governance](v18_05_governance.md)：持有 retention 状态迁移授权；下发 crypto_erasure 指令。
- [Hippocampus](v18_06_hippocampus.md) / [Neocortex](v18_07_neocortex.md)：平级存储子系统，均通过 `Statement.evidence` 引用 EngramStore 中片段。
- [Retrieval](v18_13_retrieval.md)：通过 `SourceSpanRef` 反查 EngramStore 获取 verbatim 原档，拼装 Context Pack。
- [Substrate](v18_04_substrate.md)：物理底座（S3 / 本地 fs / Letta archival / memU Rust blob 层）。
