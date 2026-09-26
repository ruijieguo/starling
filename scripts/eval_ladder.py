#!/usr/bin/env python3
"""归因阶梯统一 runner(评测组合方案 §2 的支点)。

一条固定的六台阶阶梯,在**除"记忆层"外全部锁死**(backbone/embedder/
answer-prompt/judge/种子/语料 hash 相同)的前提下度量"这个数字是谁的功劳":

  S0 → S_rand → S_full → S_rag → S_star_oracle → S_star
                       └ 防守对照     └ 抽取税上界   └ 被测系统

  - 防守:S_star ≥ S_rag − α(不删检索、只叠认知层,不该更差)
  - 进攻:S_star − max(S_full, S_rag) > α(超两个上限才排除"窗口够大/检索够用")
  - 抽取税:S_star_oracle − S_star(gold 喂入 vs 真实 Extractor,隔离抽取质量)

本文件是 **PR-1**:先只打通 fixture-mode(离线、确定性、CI 可跑)的 runner
骨架——笛卡尔展开 (stage×backbone×seed)、多轮取中位数、Δ 计算、verdict 判定、
单一 JSON 产物。**real-mode(接 S_rag=vector_recall / S_star=ObserverRetriever)
是 PR-3 的 gated 真跑**,此处只留 sound 的接线点,不行使网络/`_core`。

  python scripts/eval_ladder.py --benchmark longmemeval \
      --corpus tests/data/eval_longmemeval/sessions.jsonl \
      --stages S0,S_rand,S_full,S_rag,S_star_oracle,S_star \
      --backbones fixtureA,fixtureB --seeds 0,1,2 --fixture-mode \
      --report build/ladder_longmemeval.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

# 六台阶的规范顺序(记忆层从少到多)。runner 只跑 --stages 选中的子集,
# 但判据引用固定语义角色(S_rag=防守对照,S_full=长上下文上限,
# S_star_oracle=抽取税上界,S_star=被测系统),故名字是契约不是自由字符串。
ALL_STAGES = ("S0", "S_rand", "S_full", "S_rag", "S_star_oracle", "S_star")

# 防守/进攻判据的容差带(fixture 用固定值;real-mode 由 judge 对抗审计
# 测出的"不可解读带"注入,见组合方案 §3 / impl-spec §3)。
DEFAULT_ALPHA = 0.05

# fixture-mode 的每台阶"技能率":一个确定性 mock answerer 的期望正确率,
# 刻意排成合理的阶梯形状,好让下游 Δ/verdict 逻辑有非平凡输入可咀嚼——
# 这是**骨架自测**,不是任何真实能力声明。real-mode 下这张表不被使用。
_FIXTURE_SKILL = {
    "S0": 0.30,            # 闭卷地板
    "S_rand": 0.35,        # 随机片段仅略高于地板
    "S_full": 0.82,        # 长上下文上限
    "S_rag": 0.80,         # 朴素 RAG(防守对照物)
    "S_star_oracle": 0.90, # gold 喂入 → 表征能力上界
    "S_star": 0.85,        # 被测系统(带抽取税,故 < oracle)
}


def median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def corpus_hash(records: list[dict]) -> str:
    """语料内容确定性 hash(可比性):同内容同 hash,内容变则变。

    与 eval_quality_baseline.corpus_hash 同构;此处独立实现以免 runner 被
    baseline 的阈值 import 链耦合(baseline 在 import 时读 P1/ToM 阈值常量)。
    real-mode 里抽取产物也要并入该 hash(见 impl-spec §2.3),防"换抽取模型偷偷刷分"。
    """
    blob = "\n".join(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in records)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def normalize_eval_time(value: str) -> str:
    """Native replay/ranking consumes UTC clock fields, without offset conversion."""
    from datetime import datetime, timezone

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("evaluation time must include a UTC offset")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ladder_prompt(record: dict, recalled: list[str]) -> str:
    """归因阶梯专用答题 prompt:**只喂 `recalled`(该台阶的记忆块),不喂
    record.history**。

    这是与 eval_longmemeval._build_answer_prompt 的关键差异:后者是纯长上下文
    baseline,把完整 history 无条件塞进每条 prompt——对 baseline 是对的。但归因
    阶梯的定义是"**除记忆块外全部锁死**",若各台阶 prompt 都带完整 history:
      - S0(闭卷地板)能直接从 history 读到答案 → 地板失真、不再闭卷;
      - S_rag/S_star 的"记忆块差异"被 always-present history 淹没 → 认知层净贡献
        (S_star − S_rag)信号归零;
      - S_full 的 history 会来两遍(recall_block 已把 history 拼进 block)。
    故 history 只能经 `recalled` 进入 prompt,且**仅 S_full 台阶的 block 含 history**
    (见 eval_ladder_pipeline.recall_block:S_full→全 history 行拼接,其余台阶→各自
    记忆块或空)。recall_block 已是每台阶唯一正确的上下文源,此处照单全收即可。
    """
    options_block = "\n".join(f"{i}. {opt}" for i, opt in enumerate(record["options"]))
    recall_block = "\n".join(f"- {r}" for r in recalled) if recalled else "(no memories recalled)"
    return (
        "You are answering a multiple-choice question using a memory system's recall.\n\n"
        "Recalled memories:\n"
        f"{recall_block}\n\n"
        f"Question: {record['question']}\n\n"
        "Options (0-based index):\n"
        f"{options_block}\n\n"
        "Respond with ONLY the integer index of the correct option. No explanation."
    )


def _ladder_prompt_free(record: dict, recalled: list[str]) -> str:
    """自由文本题(long_form/short_answer)的答题 prompt。

    与 `_ladder_prompt` 同一"**只喂 recalled、不喂 record.history**"契约(见其
    docstring:history 只能经该台阶的记忆块进入,否则闭卷地板失真、认知层净贡献信号
    被淹没)。差别仅在:要求 backbone 用自然语言作答(交给 judge 比对参考答案),
    而非输出 MC 下标。judge 的"接受率不确定性"由 eval_judge_audit 的 α_judge 度量。
    """
    recall_block = "\n".join(f"- {r}" for r in recalled) if recalled else "(no memories recalled)"
    return (
        "You are answering a question using only a memory system's recall.\n\n"
        "Recalled memories:\n"
        f"{recall_block}\n\n"
        f"Question: {record['question']}\n\n"
        "Answer concisely based ONLY on the recalled memories above. If the "
        "recalled memories do not contain the answer, reply that you don't know."
    )


def _fixture_correct(stage: str, item_id: str, seed: int) -> bool:
    """确定性 mock:是否答对,由 hash(stage,item,seed) 与台阶技能率比较决定。

    同 (stage,item,seed) 恒定 → 多轮可复现;跨 item 抖动 → 聚合出接近技能率
    的正确率。绝无网络/`_core`。"""
    skill = _FIXTURE_SKILL.get(stage, 0.5)
    h = hashlib.sha256(f"{stage}|{item_id}|{seed}".encode("utf-8")).hexdigest()
    draw = int(h[:8], 16) / 0xFFFFFFFF
    return draw < skill


def _accepts_backbone_arg(fn) -> bool:
    """extract 实现是否吃第三个 backbone 参数(按签名判定,不靠异常)。

    真工厂(make_real_extract_fn)吃 (adapter, record, backbone);离线测试的 mock
    只吃 (adapter, record)。签名不可 introspect(C 函数/内建)时保守返回 False,
    退回 2 参调用——宁可少传一个可选参数,也不冒 TypeError 掩盖真 bug 的风险。"""
    import inspect

    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    if any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in params.values()):
        return True
    positional = [p for p in params.values()
                  if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                                inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    return len(positional) >= 3


def _real_answer(stage: str, record: dict, seed: int, config: dict) -> bool:
    """real-mode 一题一 cell:装配记忆块 → 问 backbone → 判分(PR-3)。

    每台阶只换"喂给 answerer 的记忆块"来源(impl-spec §2.1):
      S0            → 空块
      S_rand        → 全库随机 k 行(同一 seed)
      S_full        → 全 history 行拼接
      S_rag         → SemanticRetriever.vector_recall(k)  [防守对照物]
      S_star_oracle → ObserverRetriever(mode="statements"),库里 statement 由 gold 喂入(绕开 Extractor)
      S_star        → ObserverRetriever(mode="statements"),库里 statement 由真实 Extractor 抽出
    然后按 answer_format 判分:MC→answerer 出下标做确定性 index 比对;自由文本→
    answerer 自然语言作答,交 config["judge"] 比对参考答案。

    **可测性接缝**:embedder 工厂与 answerer 都经 config 注入——
      - `config["core"]`:`_core` 模块(或离线测试的等价 stub)。
      - `config["make_pipeline"](db_path) -> (adapter, embedder, index)`:装配一个
        每题临时管线;real-mode 传 OpenAIEmbeddingAdapter,离线测试传 StubEmbeddingAdapter。
      - `config["extract"](adapter, item, backbone) -> None`:S_star 台阶把 raw_turns
        经真 Extractor 抽成带归属 statement;非 S_star 台阶不调用。backbone 按 cell
        传入(抽取产物须随 backbone 变化,否则跨 backbone 同号退化成假独立复现);
        旧式 2 参实现(离线 mock)自动回退兼容。
      - `config["answerer"](prompt, backbone) -> str`:问 backbone 作答(MC 出下标,
        自由文本出自然语言);real-mode 走 eval_longmemeval 的 HTTP 路径,离线测试传
        确定性 mock。
      - `config["judge"](question, reference, candidate, backbone) -> bool`:自由文本
        题判分——比对候选答案与参考答案是否语义等价;real-mode 走 LM judge,离线测试
        传确定性 mock。MC 题不调用。
    这样 `_real_answer` 的**装配逻辑**可离线测(见 test_eval_ladder_pipeline),
    真跑时未测的只剩 answerer/judge/Extractor 的网络部分。
    """
    import tempfile
    import time

    from eval_longmemeval import _parse_option_index
    import eval_ladder_pipeline as pipe

    core = config["core"]
    make_pipeline = config["make_pipeline"]
    answerer = config["answerer"]
    k = config.get("k", 10)
    now_iso = normalize_eval_time(config.get("now_iso", "2026-06-01T00:00:00Z"))
    replay_mode = config.get("star_replay_mode", "immediate")
    if replay_mode not in ("immediate", "sleep"):
        raise ValueError(f"unknown star_replay_mode: {replay_mode!r}")

    tmpdir = tempfile.mkdtemp(prefix=f"ladder_{stage}_")
    db_path = f"{tmpdir}/ladder.db"
    diagnostics = config.get("diagnostics")
    if diagnostics is not None:
        diagnostics.clear()
        diagnostics["db_path"] = db_path
    adapter, embedder, index = make_pipeline(db_path)
    ingest_start = time.perf_counter()

    # --- seed 库内容:S_star 走真 Extractor(带归属);oracle 用 gold;余用扁平 history ---
    if stage == "S_star":
        # extract 按 (adapter, record, backbone) 调用(S_star 抽取须随当前 backbone
        # 变化,否则跨 backbone 同号退化成假独立复现)。旧式 2 参实现(离线 mock)
        # 按**签名**判定回退——不用 try/except TypeError:那会把 extract 内部真实的
        # TypeError 误当"旧式签名"而静默重跑一次(掩盖 bug + 双花 API)。
        _ex = config["extract"]
        if _accepts_backbone_arg(_ex):
            extraction = _ex(adapter, record, config.get("backbone", ""))
        else:
            extraction = _ex(adapter, record)
        if diagnostics is not None:
            diagnostics["extraction"] = extraction
    elif stage == "S_star_oracle":
        gold = record.get("gold_statements") or []
        pipe.seed_gold_statements(db_path, record["item_id"], gold)
    else:
        pipe.seed_history_statements(
            db_path, record["item_id"], record.get("history", []),
            speaker_labels=stage == "S_rag" and config.get("rag_speaker_labels", False))

    replay = {"mode": replay_mode if stage == "S_star" else "not_applicable", "stats": {}}
    if stage == "S_star" and replay_mode == "sleep":
        # One native offline pass, with production defaults and no optional gist LLM.
        stats = core.ReplayScheduler(adapter).run_sleep(now_iso)
        replay["stats"] = {name: getattr(stats, name) for name in (
            "sampled", "compressed", "abstracted", "gist_candidates", "gist_failed",
            "gist_gated", "forced_consolidated", "ttl_archived", "replay_batch_id")}

    embedding = pipe.embed_seeded(core, adapter, embedder, index, now_iso)
    if diagnostics is not None:
        diagnostics.update(embedding=embedding, replay=replay,
                           ingest_seconds=time.perf_counter() - ingest_start)

    rb = pipe.recall_block(core, stage, adapter=adapter, embedder=embedder,
                           index=index, question=record["question"],
                           history=record.get("history", []), k=k, seed=seed,
                           now_iso=now_iso)
    if diagnostics is not None:
        diagnostics["recall"] = rb

    # 弃答题(is_abstain):planner 主动弃答且该题本无答案 → 记正确(认识论诚实)。
    if record.get("is_abstain"):
        return bool(rb["abstained"])

    recalled = [ln.lstrip("- ").strip() for ln in rb["block"].splitlines() if ln.strip()]

    # 打分岔路(按 answer_format):
    #   multiple_choice → answerer 出 MC 下标,确定性 index 比对(band=0.05)。
    #   long_form/short_answer → answerer 自然语言作答,交 judge 比对参考答案
    #     (judge 的接受率不确定性由 eval_judge_audit 的 α_judge 度量,band=α_judge)。
    if record.get("answer_format", "multiple_choice") == "multiple_choice":
        prompt = _ladder_prompt(record, recalled)
        if diagnostics is not None:
            diagnostics["prompt"] = prompt
        resp = answerer(prompt, config.get("backbone", ""))
        if diagnostics is not None:
            diagnostics["response"] = resp
        try:
            pred = _parse_option_index(resp, len(record["options"]))
        except ValueError:
            return False
        if diagnostics is not None:
            diagnostics["prediction"] = pred
        return pred == int(record["answer"])

    # 自由文本:judge(question, reference, candidate, backbone) -> bool。
    prompt = _ladder_prompt_free(record, recalled)
    if diagnostics is not None:
        diagnostics["prompt"] = prompt
    candidate = answerer(prompt, config.get("backbone", ""))
    if diagnostics is not None:
        diagnostics["response"] = candidate
    judge = config["judge"]
    return bool(judge(record["question"], str(record["answer"]), candidate,
                      config.get("backbone", "")))


# --------------------------- real-mode 工厂(gated 真跑)---------------------------
# _real_answer 的四个注入接缝(core/make_pipeline/extract/answerer)+ judge 的真实现。
# 这些函数是**唯一**行使网络的地方,且只在被调用时行使;构造工厂本身不发网络。
# 纪律:
#   - api_key 只从 env 读、只进 Authorization header,绝不入参数/日志/产物。
#   - 写入侧与检索侧**同一 embedder 实例**(embed_seeded 的 docstring 纪律)。
#   - chat 与 embeddings 常是不同 provider(推理 chat 模型无 embeddings 端点):
#     照 eval_longmemeval 的 env-swap 纪律临时把 OPENAI_* 指向 DASHSCOPE_*
#     建 embedder,建完立刻还原,免得污染后续 chat 调用。


def _build_real_embedder(core):
    """按 env-swap 纪律构造生产 embedder(qwen3.7-text-embedding 等)。

    DASHSCOPE_API_KEY 存在时:临时把 OPENAI_API_KEY/OPENAI_BASE_URL 指向 DashScope
    的 OpenAI 兼容 embeddings 端点 → 建 OpenAIEmbeddingAdapter → **立刻还原**,
    使随后的 chat(answerer/judge)仍走原 OPENAI_*。构造不发网络。"""
    import os

    if not os.environ.get("DASHSCOPE_API_KEY"):
        return core.OpenAIEmbeddingAdapter(core.OpenAIEmbeddingConfig.from_env())

    saved_key = os.environ.get("OPENAI_API_KEY")
    saved_base = os.environ.get("OPENAI_BASE_URL")
    os.environ["OPENAI_API_KEY"] = os.environ["DASHSCOPE_API_KEY"]
    os.environ["OPENAI_BASE_URL"] = os.environ.get("DASHSCOPE_BASE_URL", "")
    try:
        cfg = core.OpenAIEmbeddingConfig.from_env()
        cfg.model = os.environ.get("EMBEDDING_MODEL", "text-embedding-v3")
        cfg.dim = int(os.environ.get("EMBEDDING_DIM", "1024"))
        return core.OpenAIEmbeddingAdapter(cfg)
    finally:
        # 还原,绝不留下被改写的 OPENAI_*(否则 chat 会误发到 embeddings 端点)。
        if saved_key is not None:
            os.environ["OPENAI_API_KEY"] = saved_key
        if saved_base is not None:
            os.environ["OPENAI_BASE_URL"] = saved_base
        elif "OPENAI_BASE_URL" in os.environ:
            del os.environ["OPENAI_BASE_URL"]


# 每题一条临时管线;C++ keep_alive 需要 Python 侧持有 emb/idx/rt 引用,
# 否则析构后 retriever 拿到悬垂引用(离线测试同此纪律)。
_REAL_KEEPALIVE: list = []


def make_real_pipeline_fn(core):
    """make_pipeline(db_path) -> (adapter, embedder, index):真 embedder + 真库。"""
    from starling import runtime

    def _make(db_path):
        rt = runtime._build_local_store_sqlite_runtime(Path(db_path))
        rt.start()
        emb = _build_real_embedder(core)
        idx = core.SqliteBlobVectorIndex()
        _REAL_KEEPALIVE.append((rt, emb, idx))
        return rt.adapter, emb, idx

    return _make


def _build_extract_llm(core, model: str, provider: str):
    """构造抽取用 LLM adapter。

    provider="dashscope" 时**整体 env-swap** OPENAI_*→DASHSCOPE_* 再 from_env():
    chat Config 不向 Python 暴露 api_key(只在 from_env() 那一刻从 env 快照),故单改
    base_url/model 会拿 A 家 key 打 B 家端点 → 401 → C++ 静默返回空抽取
    (2026-08 实测)。构造完立刻还原,不污染后续 answerer/judge。"""
    import os

    def _mk():
        cfg = core.OpenAIAdapterConfig.from_env()
        if model:
            cfg.model = model
        return core.OpenAIAdapter(cfg)

    if provider != "dashscope" or not os.environ.get("DASHSCOPE_API_KEY"):
        return _mk()
    sk, sb = os.environ.get("OPENAI_API_KEY"), os.environ.get("OPENAI_BASE_URL")
    os.environ["OPENAI_API_KEY"] = os.environ["DASHSCOPE_API_KEY"]
    os.environ["OPENAI_BASE_URL"] = os.environ.get("DASHSCOPE_BASE_URL", "")
    try:
        return _mk()
    finally:
        if sk is not None:
            os.environ["OPENAI_API_KEY"] = sk
        if sb is not None:
            os.environ["OPENAI_BASE_URL"] = sb
        elif "OPENAI_BASE_URL" in os.environ:
            del os.environ["OPENAI_BASE_URL"]


def make_real_extract_fn(core, extract_model: str = "",
                         extract_provider: str = "openai",
                         extraction_config=None,
                         preserve_invalid_time: bool = False,
                         holder_isolation: bool = False):
    """extract(adapter, record, backbone) -> None:S_star 台阶用**真 Extractor**从
    history 抽出带归属的 statement(与 oracle 的 gold 喂入相对,二者差=抽取税)。

    走 memory_remember_extract_all(与 remember() 生产路径同一 C++ 入口),三个 prompt
    取 **ExtractionConfig 单一源**(python/starling/extractor/config.py,dashboard 的
    remember_extract 用的同一个对象)。绝不用 getattr 回退凑:belief/episodic/
    general_fact 是三个不同 prompt,拿 belief 顶替另两个会三倍烧 API 且语义错位
    (2026-08 冒烟实测:巨型 belief prompt × 50 turns 跑三遍 → 挂死 13 分钟)。

    backbone **按 cell 传入**而非构造时绑死:S_star 的抽取产物必须随当前 backbone
    变化,否则两个 backbone 的 S_star 共享同一套抽取结果,"≥2 backbone 同号"
    就退化成假独立复现(归因判据失效)。"""
    import os

    from starling.extractor.config import ExtractionConfig

    # The default keeps historical extraction byte-for-byte compatible.  A
    # structured-memory experiment must opt in through this native policy
    # carrier; Python does not inspect predicates or rewrite evidence.
    ex_cfg = extraction_config if extraction_config is not None else ExtractionConfig()
    native_policy = ex_cfg.to_native_policy()

    def _extract_one(adapter, llm, holder: str, payload_text: str) -> dict:
        """以 holder 为记忆主跑一遍三相 remember(prepare→extract→commit)。"""
        # SourceTurn rendering is native: it preserves source-owned metadata
        # and keeps Python from reimplementing evidence offsets or time rules.
        payload = payload_text.encode("utf-8")

        # **三相,与 remember() 生产路径一致**(python/starling/_memory_core.py):
        #   prepare  → 建 engram + 决定 should_extract
        #   extract  → 跑三条 LLM 抽取,返回 bundle(**不写库**)
        #   commit   → 在一个外层事务里把 bundle 落成 statements
        # 只调 extract_all 会让抽取白跑、库里 0 条 statement——S_star 便在空库上
        # 检索,分数崩到地板,测出来的不是被测系统而是"抽取没接上"
        # (2026-08 实测:extract_all 返回 25.5s 有 bundle,statements 仍是 0)。
        prepared = core.memory_remember_prepare(
            adapter, tenant_id="default", holder_id=holder, interlocutor="",
            # Reuse the engram registered by retain_source_turns.  A different
            # adapter/prefix would create a duplicate engram for the same
            # payload and make strict semantic source linking fail closed.
            adapter_name="source_turns", source_prefix=f"source-{holder}-",
            created_at_iso8601="2026-06-01T00:00:00Z", payload=payload)
        if not prepared.should_extract:
            return {"holder": holder, "outcome": prepared.outcome, "skipped": True}
        bundle = core.memory_remember_extract_all(
            adapter, llm,
            ex_cfg.belief_prompt,
            ex_cfg.episodic_prompt,
            ex_cfg.general_fact_prompt,
            holder, payload, policy=native_policy)
        receipt = json.loads(core.memory_remember_bundle_receipt(bundle))
        outcome = core.memory_remember_commit_all(
            adapter, llm, tenant_id="default", holder_id=holder,
            interlocutor="", prepared=prepared, extracted=bundle,
            policy=native_policy)
        if outcome["extraction_failed"]:
            raise RuntimeError(f"extraction failed after core retries for holder {holder!r}")
        return {"holder": holder, "receipt": receipt, **outcome}

    def _extract(adapter, record, backbone: str = "") -> list[dict]:
        """**按 speaker 分组**写入:每个说话人的发言合成一段,以该 speaker 为
        holder_id 各跑一遍三相 remember。

        为什么必须分组(2026-08 T7 首轮实测坐实):Starling 的 holder 语义是
        **单一记忆主**——src/extractor/extractor.cpp 明确写着 "Default (and
        historical) behaviour: the agent (the run arg) holds every extracted
        attitude",并注明 "the LLM's holder field is always the narrator" 故
        刻意忽略 LLM 抽出的 holder。于是把多人会话拼成一坨、holder 传单个值,
        会把所有说话人的语句都归到那一个 holder 名下(实测 LLM 正确抽出
        Mei×4/Leon×4/Josh×1,入库后 5 条全变 alice),说话人信息被抹平;
        planner 拿"Josh 如何处理职业话题"这类**跨说话人归属**问题去检索碎片,
        相似度过不了阈值 → 弃答 → S_star 崩到 0.176(低于 S_rand,近闭卷地板)。
        按 speaker 分组写入才是 Starling 语义下多方会话的正确用法。

        代价:每题从 1 次抽取变成 N 次(N=说话人数,实测 4~6),成本涨 N 倍。
        """
        model = extract_model or backbone
        llm = _build_extract_llm(core, model, extract_provider)
        by_speaker: dict[str, list[dict]] = {}
        for turn in record.get("history", []):
            spk = str(turn.get("speaker") or "unknown").strip() or "unknown"
            # Keep only the native SourceTurn contract fields. Dataset answer
            # and gold fields must never enter prompts or source receipts.
            by_speaker.setdefault(spk, []).append({
                "speaker": spk,
                "text": str(turn.get("text", "")),
                "session_id": (str(turn["session_index"])
                               if turn.get("session_index") is not None
                               else turn.get("session_id")),
                "turn_id": turn.get("turn_id"),
                "turn_index": turn.get("message_index", turn.get("turn_index")),
                "observed_at": turn.get("observed_at"),
            })
        if not by_speaker:
            return []
        # 稳定顺序(可复现):按说话人名排序,不依赖 dict 插入序。
        if holder_isolation:
            holder_inputs = []
            for spk in sorted(by_speaker):
                turns_json = json.dumps(by_speaker[spk], ensure_ascii=False, separators=(",", ":"))
                payload = core.claim_source_turn_payload(turns_json, preserve_invalid_time)
                holder_inputs.append({
                    "tenant_id": "default",
                    "holder_id": spk,
                    "interlocutor": "",
                    # Keep extraction statements on the exact engram already
                    # registered by retain_source_turns for this holder.
                    "adapter_name": "source_turns",
                    "source_prefix": f"source-{spk}-",
                    "created_at_iso8601": "2026-06-01T00:00:00Z",
                    "payload": payload.encode("utf-8"),
                })
            native_outcomes = core.memory_remember_holders(
                adapter, llm, ex_cfg.belief_prompt, ex_cfg.episodic_prompt,
                ex_cfg.general_fact_prompt, holder_inputs, policy=native_policy)
            outcomes = []
            for native in native_outcomes:
                outcome = dict(native)
                outcome["holder"] = outcome.pop("holder_id")
                receipt = outcome.get("receipt")
                if isinstance(receipt, str) and receipt:
                    outcome["receipt"] = json.loads(receipt)
                outcomes.append(outcome)
            return outcomes
        outcomes = []
        for spk in sorted(by_speaker):
            turns_json = json.dumps(by_speaker[spk], ensure_ascii=False, separators=(",", ":"))
            payload = core.claim_source_turn_payload(turns_json, preserve_invalid_time)
            outcomes.append(_extract_one(adapter, llm, spk, payload))
        return outcomes

    return _extract


def make_real_answerer_fn():
    """answerer(prompt, backbone) -> str:问 backbone 作答。网络仅在调用时发生。

    复用 judge 审计里同一条 proven chat 路径(eval_judge_audit._chat_completion),
    使 answerer/judge/干扰器三处的 HTTP 装配逐字节同源。max_tokens=512:推理模型
    要留出可见答案空间;MC 由 _parse_option_index 取首个合法下标,多余文本无妨。"""
    import eval_judge_audit as audit_mod

    def _answer(prompt: str, backbone: str) -> str:
        return audit_mod._chat_completion(prompt, backbone, max_tokens=512)

    return _answer


def build_real_config(core, k: int, seeds: list[int], router_gate: str,
                      backbones: list[str], embedding_model: str,
                      extract_model: str = "",
                      extract_provider: str = "openai") -> dict:
    """装配 real-mode 的 config(注入五个真工厂)。

    extract 不绑 backbone:它吃 (adapter, record, backbone),由 _real_answer 把当前
    cell 的 backbone 传进去(见 make_real_extract_fn 的假独立复现说明)。"""
    import eval_judge_audit as audit_mod

    return {
        "core": core,
        "make_pipeline": make_real_pipeline_fn(core),
        "extract": make_real_extract_fn(core, extract_model, extract_provider),
        "answerer": make_real_answerer_fn(),
        "judge": audit_mod.make_real_ladder_judge_fn(),
        "k": k,
        "now_iso": "2026-06-01T00:00:00Z",
        "star_replay_mode": "immediate",
        "rag_speaker_labels": False,
        "embedder": embedding_model,
        # 抽取层 provenance:抽取税是**该模型**的税,报告必须能读出来。
        "extract_model": extract_model or "(follows backbone)",
        "extract_provider": extract_provider,
        "router_gate": router_gate,
        "mode": "real",
        "seeds": seeds,
    }


# --------------------------- 逐题 journal(断点续跑)---------------------------
# 真跑一题 S_star 实测 ~26 分钟(belief prompt 占 80%),一个 cell 是几十题。
# 若只在 cell 边界落盘,中途一次 Clash 抖动/限流就丢掉几十小时——所以 journal
# 必须是**逐题**粒度:每题判完立刻 append 一行 JSONL,重启时按 key 跳过已完成。
# key = (stage, backbone, seed, item_id):这四元组唯一确定一次判分。
# 失败如实记为 error 行(不写 ok),重启会重试——绝不把失败静默计成 0 分。


def _journal_key(stage: str, backbone: str, seed: int, item_id: str) -> str:
    return f"{stage}|{backbone}|{seed}|{item_id}"


def load_journal(path: Path) -> dict[str, bool]:
    """读回已完成的判分:{key: ok}。坏行跳过(不让一行损坏毁掉整轮续跑)。

    只收 ok 是 bool 的行;error 行不计入 → 重启自动重试。"""
    done: dict[str, bool] = {}
    if not path.exists():
        return done
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = row.get("key")
        ok = row.get("ok")
        if isinstance(key, str) and isinstance(ok, bool):
            done[key] = ok
    return done


def append_journal(path: Path, row: dict) -> None:
    """append 一行并 flush+fsync:进程被 kill 也不丢已判的题。"""
    import os

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def run_cell(stage: str, backbone: str, seed: int, corpus: list[dict],
             fixture_mode: bool, config: dict,
             journal: Path | None = None,
             done: dict[str, bool] | None = None) -> dict:
    """一个 (stage,backbone,seed) 单元:逐题判分,按 subset 聚合正确率。

    journal 给定时逐题落盘 + 跳过 done 里已完成的题(断点续跑);
    抛错的题记 error 行并**排除出统计**(不计 0 分),重启后重试。"""
    per_subset: dict[str, list[int]] = {}
    total_c = total_n = 0
    for rec in corpus:
        subset = rec.get("subset", "default")
        key = _journal_key(stage, backbone, seed, rec["item_id"])
        if done is not None and key in done:
            ok = done[key]                      # 续跑:直接采信已落盘的判分
        elif fixture_mode:
            ok = _fixture_correct(stage, rec["item_id"], seed)
        else:
            # 注入当前 backbone,answerer 才知用哪个模型(多 backbone 同号归因命脉)。
            try:
                ok = _real_answer(stage, rec, seed, {**config, "backbone": backbone})
            except Exception as exc:            # noqa: BLE001 — 单题失败不毁整轮
                if journal is not None:
                    append_journal(journal, {
                        "key": key, "stage": stage, "backbone": backbone,
                        "seed": seed, "item_id": rec["item_id"],
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                print(f"  ! {key} FAILED: {type(exc).__name__}: {exc}",
                      file=sys.stderr, flush=True)
                continue                        # 排除出统计,绝不当 0 分
            if journal is not None:
                append_journal(journal, {
                    "key": key, "stage": stage, "backbone": backbone,
                    "seed": seed, "item_id": rec["item_id"], "ok": bool(ok),
                })
        per_subset.setdefault(subset, [0, 0])
        per_subset[subset][0] += int(ok)
        per_subset[subset][1] += 1
        total_c += int(ok)
        total_n += 1
    subset_scores = {s: (c / n if n else 0.0) for s, (c, n) in per_subset.items()}
    return {
        "stage": stage, "backbone": backbone, "seed": seed,
        "subset_scores": subset_scores,
        "overall": (total_c / total_n if total_n else 0.0),
        # 判分成功的题数(失败题被排除):产物里必须可见,否则 n 变小无声无息。
        "scored_items": total_n,
        # 写入成本 real-mode 必填(MemDelta 警示);fixture 无成本。
        "ingest_cost": None,
    }


def aggregate(cells: list[dict], stages: list[str], backbones: list[str],
              subsets: list[str]) -> dict:
    """对每 (stage,backbone) 在 seeds 上取中位数;再对 backbones 取中位数。

    返回 agg[stage][subset] = 跨 backbone 的中位数,以及 agg[stage][subset+'_by_bb']
    = 每 backbone 的中位数(用于"≥2 backbone 同号"归因判定)。"""
    agg: dict[str, dict[str, float]] = {}
    by_bb: dict[str, dict[str, dict[str, float]]] = {}
    for stage in stages:
        agg[stage] = {}
        by_bb[stage] = {}
        for subset in subsets + ["overall"]:
            bb_medians = []
            for bb in backbones:
                seed_vals = [
                    (c["subset_scores"].get(subset) if subset != "overall" else c["overall"])
                    for c in cells if c["stage"] == stage and c["backbone"] == bb
                ]
                seed_vals = [v for v in seed_vals if v is not None]
                if seed_vals:
                    m = median(seed_vals)
                    bb_medians.append(m)
                    by_bb[stage].setdefault(subset, {})[bb] = m
            agg[stage][subset] = median(bb_medians) if bb_medians else None
    return {"median": agg, "by_backbone": by_bb}


def _same_sign_backbones(by_bb: dict, stage_hi: str, stage_lo: str,
                         subset: str, alpha: float) -> int:
    """有多少个 backbone 上 (stage_hi − stage_lo) > alpha(归因坐实用)。"""
    hi = by_bb.get(stage_hi, {}).get(subset, {})
    lo = by_bb.get(stage_lo, {}).get(subset, {})
    return sum(1 for bb in hi if bb in lo and (hi[bb] - lo[bb]) > alpha)


def _subset_bands(corpus: list[dict], subsets: list[str], alpha: float,
                  judge_audit: dict | None) -> dict[str, float]:
    """每 subset 的**不可解读带**:Δ 小于此带一律记 `n.s.`,不作提升/不降证据。

    确定性打分(MC,index 比对)→ band=alpha(默认 0.05,评分无系统性误差)。
    judge 打分(自由文本)→ band=max(alpha, α_judge):judge 对"话题相邻但事实
    错误"答案的误接受率是分数的地噪(eval_judge_audit §3.1);无 judge 审计时
    诚实回退 alpha 并在报告标注 band 来源。判据从 corpus 的 answer_format 推导
    哪些 subset 是 judge 打分——subset 名不参与,零硬编码。"""
    judge_scored = {r.get("subset", "default") for r in corpus
                    if r.get("answer_format", "multiple_choice") != "multiple_choice"}
    subset_alpha = (judge_audit or {}).get("subset_alpha", {})
    bands: dict[str, float] = {}
    for s in subsets:
        if s in judge_scored:
            aj = subset_alpha.get(s)
            bands[s] = max(alpha, aj) if aj is not None else alpha
        else:
            bands[s] = alpha
    return bands


def classify(agg: dict, stages: list[str], subsets: list[str], alpha: float,
             subset_bands: dict[str, float] | None = None) -> list[dict]:
    """逐 subset 出防守/进攻判据(组合方案 §2 + impl-spec §4)。

    防守(需 S_rag & S_star):PASS+ / PASS(n.s.) / FAIL
    进攻(需 S_full/S_rag & S_star):CONFIRMED / PLAUSIBLE / none
    抽取税(需 S_star_oracle & S_star):S_star_oracle − S_star

    band 逐 subset 取(见 _subset_bands):MC=alpha、自由文本=max(alpha, α_judge)。
    subset_bands 缺省时全体回退 alpha(fixture 常量带)。"""
    med, by_bb = agg["median"], agg["by_backbone"]
    have = set(stages)
    out = []
    for subset in subsets:
        band = (subset_bands or {}).get(subset, alpha)
        row: dict = {"subset": subset, "band": band}
        s_rag = med.get("S_rag", {}).get(subset)
        s_star = med.get("S_star", {}).get(subset)
        s_full = med.get("S_full", {}).get(subset)
        s_oracle = med.get("S_star_oracle", {}).get(subset)

        # --- 防守判据 ---
        if {"S_rag", "S_star"} <= have and s_rag is not None and s_star is not None:
            d = s_star - s_rag
            n_same = _same_sign_backbones(by_bb, "S_star", "S_rag", subset, band)
            if d > band and n_same >= 2:
                verdict = "PASS+ (提升)"
            elif d > band:
                verdict = "PASS+ (提升, 单模型待复现)"
            elif d >= -band:
                verdict = "PASS (不降, n.s.)"
            else:
                verdict = "FAIL (回归)"
            row["defense"] = {"s_rag": s_rag, "s_star": s_star, "delta": d,
                              "backbones_same_sign": n_same, "verdict": verdict}

        # --- 进攻判据(超两个上限 + ≥2 backbone 同号)---
        if {"S_star"} <= have and s_star is not None and (s_full is not None or s_rag is not None):
            ceiling = max(x for x in (s_full, s_rag) if x is not None)
            d = s_star - ceiling
            # 同号计数针对"超过上限"的那个对照(取较高的 S_full/S_rag 作 lo 近似)
            lo_stage = "S_full" if (s_full is not None and (s_rag is None or s_full >= s_rag)) else "S_rag"
            n_same = _same_sign_backbones(by_bb, "S_star", lo_stage, subset, band)
            if d > max(band, 0.05) and n_same >= 2:
                verdict = "CONFIRMED"
            elif d > max(band, 0.05):
                verdict = "PLAUSIBLE (单模型待复现)"
            else:
                verdict = "none (未超上限)"
            row["attack"] = {"ceiling": ceiling, "s_star": s_star, "delta_vs_ceiling": d,
                             "ceiling_stage": lo_stage, "backbones_same_sign": n_same,
                             "verdict": verdict}

        # --- 抽取税 ---
        if {"S_star_oracle", "S_star"} <= have and s_oracle is not None and s_star is not None:
            row["extraction_tax"] = {"s_star_oracle": s_oracle, "s_star": s_star,
                                     "tax": s_oracle - s_star}
        out.append(row)
    return out


def _serializable_config(config: dict) -> dict:
    """产物里的 config 只保留可序列化的 provenance:callable/模块记成名字。

    real-mode 的 config 含 5 个注入工厂(core 模块 + make_pipeline/extract/
    answerer/judge),原样进 JSON 会让 json.dumps 抛 TypeError——那会在**跑完
    所有 cell、API 已花光**之后才炸,是最坏的失败时机。故在此净化。"""
    out: dict = {}
    for key, val in config.items():
        if callable(val) or hasattr(val, "__file__"):
            out[key] = getattr(val, "__name__", type(val).__name__)
        else:
            out[key] = val
    return out


def build_report(benchmark: str, corpus: list[dict], cells: list[dict],
                 stages: list[str], backbones: list[str], subsets: list[str],
                 alpha: float, config: dict, judge_audit: dict | None = None) -> dict:
    agg = aggregate(cells, stages, backbones, subsets)
    bands = _subset_bands(corpus, subsets, alpha, judge_audit)
    return {
        "benchmark": benchmark,
        "corpus_hash": corpus_hash(corpus),
        "config": _serializable_config(config),
        "stages": stages,
        "backbones": backbones,
        "subsets": subsets,
        "alpha": alpha,
        # 逐 subset 不可解读带:MC=alpha、自由文本=max(alpha, α_judge)(见 _subset_bands)。
        "subset_bands": bands,
        "cells": cells,
        "aggregate": agg["median"],
        "verdicts": classify(agg, stages, subsets, alpha, bands),
        # judge 对抗审计:real-mode 由 eval_judge_audit 注入(impl-spec §3);
        # fixture/无审计时为 None,band 全体回退 alpha 常量。
        "judge_audit": judge_audit,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="归因阶梯统一 runner(fixture-mode 骨架)。")
    p.add_argument("--benchmark", required=True,
                   help="基准名(longmemeval/locomo/beam/socialmem/memsyco/...)")
    p.add_argument("--adapter", default="auto",
                   help="语料适配器(eval_adapters.ADAPTERS 的键);auto=按 benchmark 推断,"
                        "passthrough=仅轻校验。socialmembench 需两表,由调用方预归一。")
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--stages", default=",".join(ALL_STAGES))
    p.add_argument("--backbones", default="fixtureA,fixtureB")
    p.add_argument("--seeds", default="0,1,2")
    p.add_argument("--alpha", type=float, default=DEFAULT_ALPHA)
    p.add_argument("--fixture-mode", action="store_true",
                   help="离线确定性 mock answerer(CI)。省略 = real-mode(需 --real-run)。")
    p.add_argument("--real-run", action="store_true",
                   help="显式行使真跑(真 embedder/answerer/judge/Extractor,花 API)。"
                        "与 --fixture-mode 互斥;两者都不给则拒跑(防误触网络)。")
    p.add_argument("--limit", type=int, default=0,
                   help="只跑前 N 题(0=全跑)。冒烟用:--limit 1。")
    p.add_argument("--embedding-model", default="",
                   help="real-mode 的 embedder 模型名(记入产物;实际由 EMBEDDING_MODEL "
                        "env 驱动,此处只做 provenance 标注)。")
    p.add_argument("--rag-speaker-labels", action="store_true",
                   help="Retain speaker labels in S_rag embedding and recall text.")
    p.add_argument("--star-replay-mode", choices=("immediate", "sleep"), default="immediate",
                   help="S_star lifecycle: immediate recall or one native sleep replay.")
    p.add_argument("--now-iso", default="2026-06-01T00:00:00Z",
                   help="Fixed embedding/replay/query time; record it with the run.")
    p.add_argument("--judge-audit", type=Path, default=None,
                   help="judge 对抗审计 JSON(eval_judge_audit 产物):注入 α_judge,"
                        "使自由文本 subset 的不可解读带 band=max(alpha, α_judge)。")
    p.add_argument("--router-gate", choices=("on", "off"), default="off",
                   help="§4 进攻项的路由门控双版(fixture 仅记录,不改分)。")
    p.add_argument("--report", type=Path, default=Path("build/ladder.json"))
    p.add_argument("--journal", type=Path, default=None,
                   help="断点续跑 journal(JSONL,逐题落盘)。重启同一命令会跳过已判分"
                        "的题;失败题会重试。真跑强烈建议指定。")
    p.add_argument("--extract-model", default="",
                   help="S_star 抽取层固定用的模型(与 answer backbone 解耦)。留空="
                        "跟随 backbone。给定时抽取产物跨 backbone 复用(成本主杠杆),"
                        "报告标注该模型——抽取税是该模型的税。")
    p.add_argument("--extract-provider", choices=("openai", "dashscope"),
                   default="openai",
                   help="抽取模型所在供应商。dashscope=构造抽取 adapter 时 env-swap "
                        "OPENAI_*→DASHSCOPE_*(chat Config 不向 Python 暴露 api_key,"
                        "只在 from_env() 那一刻从 env 快照,故必须整体切换),构造完还原。")
    args = p.parse_args(argv)

    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    unknown = [s for s in stages if s not in ALL_STAGES]
    if unknown:
        print(f"ERROR: unknown stage(s): {unknown}; valid={ALL_STAGES}", file=sys.stderr)
        return 1
    backbones = [b.strip() for b in args.backbones.split(",") if b.strip()]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]

    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr)
        return 1
    corpus = [json.loads(l) for l in args.corpus.read_text().splitlines() if l.strip()]
    if not corpus:
        print(f"ERROR: empty corpus: {args.corpus}", file=sys.stderr)
        return 1

    # 语料归一:过一遍进攻层适配器(PR-4)。默认 passthrough(longmemeval 形状),
    # 也顺带校验规范字段;--adapter 选 memsyco 等把异构语料归一成规范 record。
    # socialmembench 需两张表(qa+conversations),不走单文件 corpus 路径,故不在此。
    import eval_adapters
    adapter_fn = eval_adapters.ADAPTERS.get(args.adapter)
    if adapter_fn is None:
        print(f"ERROR: unknown adapter: {args.adapter}; "
              f"valid={sorted(eval_adapters.ADAPTERS)}", file=sys.stderr)
        return 1
    try:
        corpus = adapter_fn(corpus)
    except eval_adapters.AdapterError as e:
        print(f"ERROR: adapter {args.adapter} 归一失败: {e}", file=sys.stderr)
        return 1

    # --limit:冒烟/分批用,截断**在 subsets 推导之前**做,否则报告会声明
    # 语料里根本没跑到的 subset(band 与 verdict 就成了空壳)。
    if args.limit and args.limit > 0:
        corpus = corpus[:args.limit]

    subsets = sorted({r.get("subset", "default") for r in corpus})

    # 模式互斥 + 默认拒跑:两者都不给则拒(防误触网络花 API);都给则含义矛盾。
    if args.fixture_mode and args.real_run:
        print("ERROR: --fixture-mode 与 --real-run 互斥(前者离线 mock、后者真跑)。",
              file=sys.stderr)
        return 1
    if not args.fixture_mode and not args.real_run:
        print("ERROR: 未指定模式。--fixture-mode 跑离线骨架,或 --real-run 显式行使"
              "真跑(花 API、需 OPENAI_API_KEY)。", file=sys.stderr)
        return 1

    # judge 对抗审计产物(可选):注入 α_judge,让自由文本 subset 的不可解读带
    # band=max(alpha, α_judge)。缺省时诚实回退 alpha 并在报告里 judge_audit=None。
    judge_audit = None
    if args.judge_audit is not None:
        if not args.judge_audit.exists():
            print(f"ERROR: judge-audit not found: {args.judge_audit}", file=sys.stderr)
            return 1
        judge_audit = json.loads(args.judge_audit.read_text())

    if args.fixture_mode:
        config = {"embedder": "fixture", "k": 10, "judge": "fixture",
                  "router_gate": args.router_gate, "mode": "fixture",
                  "seeds": seeds}
    else:
        # 真跑:装配五个真工厂。构造不发网络(网络只在 cell 逐题调用时发生),
        # 但 OpenAIAdapterConfig.from_env() 会在 key 缺失时 fail-loud。
        from starling import _core
        config = build_real_config(
            _core, k=10, seeds=seeds, router_gate=args.router_gate,
            backbones=backbones,
            embedding_model=(args.embedding_model
                             or __import__("os").environ.get("EMBEDDING_MODEL", "")),
            extract_model=args.extract_model,
            extract_provider=args.extract_provider,
        )
        config.update(rag_speaker_labels=args.rag_speaker_labels,
                      star_replay_mode=args.star_replay_mode,
                      now_iso=normalize_eval_time(args.now_iso))
        print(f"[real-run] {len(corpus)} 题 × {len(stages)} 台阶 × "
              f"{len(backbones)} backbone × {len(seeds)} seed = "
              f"{len(corpus) * len(stages) * len(backbones) * len(seeds)} cells",
              file=sys.stderr)

    # 断点续跑:journal 逐题落盘,重启跳过已判分的题(见 load_journal)。
    journal = args.journal
    done = load_journal(journal) if journal is not None else None
    if done:
        print(f"[resume] journal 已有 {len(done)} 题判分,跳过重跑", file=sys.stderr)

    cells = []
    for stage in stages:
        for bb in backbones:
            for seed in seeds:
                if not args.fixture_mode:
                    print(f"[cell] {stage} × {bb} × seed{seed} ...",
                          file=sys.stderr, flush=True)
                cells.append(run_cell(stage, bb, seed, corpus, args.fixture_mode,
                                      config, journal=journal, done=done))

    report = build_report(args.benchmark, corpus, cells, stages, backbones,
                          subsets, args.alpha, config, judge_audit)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"Report written to {args.report}", file=sys.stderr)

    # 骨架自检:fixture 阶梯必须产出 sane 结构(S_star>S_rag、oracle≥star)。
    any_fail = any(
        r.get("defense", {}).get("verdict", "").startswith("FAIL")
        for r in report["verdicts"]
    )
    for r in report["verdicts"]:
        d = r.get("defense", {})
        a = r.get("attack", {})
        print(f"[{r['subset']}] defense={d.get('verdict','—')} "
              f"(Δ={d.get('delta', 0):+.3f}) | attack={a.get('verdict','—')} "
              f"(Δ_ceil={a.get('delta_vs_ceiling', 0):+.3f})")
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
