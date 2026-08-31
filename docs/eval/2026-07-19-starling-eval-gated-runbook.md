# Starling 评测组合 — gated 真跑操作手册

> 配套:
> - `2026-07-19-starling-eval-portfolio.md`(两段式组合方案 + 归因阶梯)
> - `2026-07-19-starling-eval-impl-spec.md`(实现规格 + 数据可得性核实)
> - `2026-07-19-starling-locomo-longmemeval-beam-eval-plan.md`(三件套接入细节)
>
> 本文是**给在有 API key + 网络 + 真实数据的环境里真跑的人**的操作手册。离线、
> 可进 CI 的评测基础设施(PR-0~PR-4)已完备且全绿;剩下的是接真模型/真数据的
> gated 真跑,本质不是"再写代码",而是"拿这套基础设施去跑并核对数字"。

---

## 0. 落盘清单(PR-0 ~ PR-4,均已 sha256 + compile + pytest 验证)

| 文件 | 角色 |
|---|---|
| `scripts/eval_ladder.py` | 六台阶归因阶梯统一 runner(fixture + real-mode `_real_answer`) |
| `scripts/eval_ladder_pipeline.py` | real-mode 检索装配层(seed/embed/recall_block,离线可测) |
| `scripts/eval_judge_audit.py` | judge 对抗审计(算 α_judge 不可解读带) |
| `scripts/eval_scorecard.py` | 两段式记分卡 reporter(judge band 门 + 可比性门) |
| `scripts/eval_adapters.py` | 进攻层语料适配器(passthrough / socialmembench / memsyco) |
| `tests/python/test_eval_ladder_sstar_reachable.py` | S_star 全路径离线可达(PR-0) |
| `tests/python/test_eval_ladder.py` | runner 纯逻辑(聚合/判据) |
| `tests/python/test_eval_ladder_pipeline.py` | 六台阶检索装配离线验证 |
| `tests/python/test_eval_ladder_realmode_offline.py` | `_real_answer` 装配接线离线验证 |
| `tests/python/test_eval_judge_audit.py` / `test_eval_scorecard.py` / `test_eval_adapters.py` | 诚信脊柱 + 适配器 |

CI 只跑 fixture-mode(离线确定性);real-mode 全量是 **non-CI 的人值守 gated 真跑**。

---

## 1. 真跑前置

1. **环境**:`OPENAI_API_KEY`(或 `DASHSCOPE_API_KEY` + `DASHSCOPE_BASE_URL`),
   `EMBEDDING_MODEL`/`EMBEDDING_DIM`(默认 text-embedding-v3 / 1024),`CHAT_MODEL`。
2. **网络**:本机 Clash TUN 会制造 SSL/EOF/黑洞抖动(见内存 `clash-tun-owns-all-network-flakiness`)。
   真跑前先 `dig` 看 fake-ip + `curl` 裸测供应商端点;真跑中每次 LLM 调用带重试。
3. **`_core` 已装**:改过 C++/绑定则先 `python scripts/configure_build.py --build --test --python-editable`。

---

## 2. real-mode 需要注入的 4 个 config 工厂

`eval_ladder._real_answer` 经 `config` 注入(可测性接缝,离线测已验证装配逻辑):

| key | 类型 | real-mode 实现 | 离线测试实现 |
|---|---|---|---|
| `core` | module | `from starling import _core` | 同(或 stub) |
| `make_pipeline` | `(db_path)->(adapter,emb,index)` | `OpenAIEmbeddingAdapter` + `SqliteBlobVectorIndex` | `StubEmbeddingAdapter(8)` |
| `extract` | `(adapter,item)->None` | 真 Extractor 从 `raw_turns` 抽带归属 statement | mock 直插一条带归属 statement |
| `answerer` | `(prompt,backbone)->str` | eval_longmemeval 的 HTTP `/chat/completions` 路径 | 确定性 mock |

**写入侧与检索侧必须同一 embedder 实例**(DashboardEngine rebuild_embedder 纪律);
embedder 标识必须进 `corpus_hash`(MemDelta:换 embedder 能逆转结论)。

---

## 3. 逐基准真跑步骤

### 3.1 达标层(防守):LoCoMo / LongMemEval-S / BEAM-{100K,500K}
1. 下载语料 → 经 `eval_adapters.adapt_passthrough` 归一(或按实际 schema 补适配器)。
2. `python scripts/eval_ladder.py --benchmark longmemeval --corpus <path> \
   --stages S0,S_rand,S_full,S_rag,S_star_oracle,S_star \
   --backbones <m1>,<m2>,<m3> --seeds 0,1,2,3,4 --report build/ladder_lme.json`
   (去掉 `--fixture-mode` = real-mode;当前 runner 的 real-mode main 装配需按 §2 注入工厂)。
3. 判据:逐子集 `S_star ≥ S_rag − α_judge`(不追聚合 SOTA)。

### 3.2 judge 对抗审计(每基准先跑,产出 α_judge)
`python scripts/eval_judge_audit.py --benchmark longmemeval --corpus <path> --k 3 \
  --report build/judge_audit_lme.json`
→ α_judge 注入记分卡作不可解读带;若 α_judge > 0.40 触发 JUDGE UNUSABLE,换更强
judge 或结构化评分(Penfield 在 LoCoMo 实测 62.81%)。

### 3.3 进攻层:SocialMemBench(HF anon4data,首选,Starling 主场)
1. `datasets`/`pandas` 读 4 个 parquet(networks/personas/conversations/qa)。
2. **按实际列名校验** `adapt_socialmembench` 的字段映射(文档 schema 未字节级核对,
   实际列名对不上会 fail-loud——这是设计,不是 bug)。
3. `adapt_socialmembench(qa_rows, conversation_rows)` → 规范 record → runner。
4. 期望:多方归属/视角题上 `S_star − max(S_full,S_rag)` 显著为正(竞品结构盲区)。

### 3.4 进攻层:MemSyco-Bench(GitHub XMUDepLIT,MIT,JSONL)
1. 读 JSONL → `adapt_memsyco(rows)`;`valid_memory→gold_statements`(喂 oracle 台阶)。
2. 期望:记忆-证据冲突/弃答子集上 S_star 显著超上限。

### 3.5 追加确证:STALE(需自跑生成,有前置成本)
填 `.env` 的 API key → 跑官方 5 步生成管线产出 `outputs/*_MAIN.json` →
用官方 `full_eval_performance.py` 的 SR/PR/IPA 口径。生成配置 hash 进 corpus_hash。

---

## 4. 出记分卡
`python scripts/eval_scorecard.py --ladder build/ladder_*.json \
  --judge-audit build/judge_audit_*.json --out build/scorecard.md`
→ 防守层(不降)+ 进攻层(大升)两段;|Δ| < α_judge 标 n.s.;embedder 不一致告警;
组合级判定 = 防守无 FAIL **且** 进攻 ≥3 CONFIRMED(含 ≥1 非 HiToM)。

---

## 5. 真跑后必做的诚实核对(对应调研的方法论警示)
1. **抽取税**:看每个进攻基准的 `S_star_oracle − S_star`。若 oracle ≫ star,失败
   归因到 Extractor(尤其多方对话/OOD 叙事),不是表征——按机制强度(oracle)+
   可部署强度(star)双报。
2. **标注核查**:每基准分层抽样 ~50 题人工核 gold,报本地错误率;高错误子集设
   诚实上限 = 1−e。
3. **写入成本**:记分卡 `ingest_cost` 必填(MemDelta:写入成本占 agent 执行 80%+ 却普遍不报)。
4. **不达标就如实降级主张**(如"仅 HiToM 与 SocialMemBench 上确证,余项待复现"),不修辞化。
