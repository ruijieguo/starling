<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../../../superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../../../superpowers/specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../../../superpowers/specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../../../superpowers/specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../../../superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../../../superpowers/specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# EngramStore

## 功能定义

EngramStore 是与 [Hippocampus](v20_06_hippocampus.md) / [Neocortex](v20_07_neocortex.md) 平级的全局证据子系统，存储 verbatim 原档，按 `retention_mode` 管理内容生命周期；审计元数据 append-only，内容是否可恢复由加密策略决定。它是 `Statement.evidence` 指向的物理目标，所有写入须经 [Bus](v20_05_bus.md)`.append_evidence`，不允许组件直接读写底层 blob。它不做：派生抽取、检索排序、业务逻辑路由。

---

## 输入

- Engram 写入请求（含 verbatim payload、source 元数据、retention_mode）
- SourceSpanRef 反查请求（按 engram_ref + chunk_index 取片段）
- crypto_erasure / redaction / legal_hold 请求

## 输出

- EngramRef（持久化 ID + 内容 hash）
- verbatim payload（按 retention_mode 决定是否可恢复）
- segment_map（P2+ 多片段元数据）
- crypto_erasure 反向传播事件（evidence.erased，触发依赖 Statement 进入 FORGOTTEN / REVIEW_REQUESTED）

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

合规引擎（[Governance](v20_05_governance.md)）持有状态迁移授权；EngramStore 本身不自主触发迁移，仅执行指令并追加 `audit_trail`。

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
    segment_map:            list[SourceSegment]    # P3 片段级 offset/role/speaker；P1 可为空
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
    # P1 最小字段
    engram_ref:   EngramRef
    chunk_index:  int
    observed_at:  datetime
    source_hash:  str
    # P3 片段级字段（需 segment_map 支撑）
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
多 Cognizer 可引用同一条 Engram。任一主体触发 `crypto_erasure` 时，"最严格访问者 wins"规则生效：共享记录须整体擦除或拆分引用后分别擦除，不得向其余 holder 继续暴露原文。refcount 维护由 EngramStore 内部执行；[Bus](v20_05_bus.md) 不感知具体引用计数，仅转发 Governance 授权令牌。

**相关子系统**

- [Bus](v20_05_bus.md)：`append_evidence` 唯一写入入口；`evidence.appended` 事件发布方。
- [Governance](v20_05_governance.md)：持有 retention 状态迁移授权；下发 crypto_erasure 指令。
- [Hippocampus](v20_06_hippocampus.md) / [Neocortex](v20_07_neocortex.md)：平级存储子系统，均通过 `Statement.evidence` 引用 EngramStore 中片段。
- [Retrieval](v20_13_retrieval.md)：通过 `SourceSpanRef` 反查 EngramStore 获取 verbatim 原档，拼装 Context Pack。
- [Substrate](v20_04_substrate.md)：物理底座（S3 / 本地 fs / Letta archival / memU Rust blob 层）。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
