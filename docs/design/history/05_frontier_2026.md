# 05 — 2026 Frontier Papers

> 产出日期: 2026-05-05
> 方法: web_search_prime MCP 工具多轮检索
> 覆盖: ICLR 2026 MemAgent Workshop, AAAI 2026, EACL 2026, ToM4AI 2026, arXiv 2026

---

## 1. Human-Like Lifelong Memory: A Neuroscience-Grounded Architecture for Infinite Interaction

- **出处**: ICLR 2026 Workshop MemAgent (arxiv 2603.29023, OpenReview)
- **发表**: 2026-03-03, 最后修改 2026-03-23
- **链接**: https://arxiv.org/pdf/2603.29023 / https://openreview.net/forum?id=QufkvHbQs7

**核心贡献**: 提出 bio-inspired memory framework, 基于 Complementary Learning Systems (CLS) 理论 + CBT belief hierarchy, 实现:
- 快速海马编码 (rapid hippocampal encoding)
- 渐进式新皮质巩固 (gradual neocortical consolidation)

**对 Starling 的意义**: 
- 这是除 Starling 外罕见的显式 CLS 架构论文, 验证了 Hippocampus/Neocortex 双层分治的方向
- CBT belief hierarchy 与 Starling §7.4 Belief → Core Belief → Schema 层级对照
- ICLR 2026 workshop 同行认可, 可作为 §21 参考文献

---

## 2. Adaptive Theory of Mind for LLM-based Multi-Agent Coordination (A-ToM)

- **出处**: AAAI 2026 (arxiv 2603.16264)
- **链接**: https://arxiv.org/abs/2603.16264 / https://ojs.aaai.org/index.php/AAAI/article/view/40204

**核心贡献**:
- 提出首个 adaptive ToM agent, 可实时估计 partner 的 ToM order
- 基于 prior interactions 估计 partner 的可能 ToM order, 并利用此估计预测 partner 动作
- 解决"ToM order mismatch"问题 —— 固定 ToM order 在不同 partner/场景下适配性差

**对 Starling 的意义**:
- 直接验证 Starling §12 ToM Engine 的核心假设: ToM order 应动态调整而非硬编码
- A-ToM 的"实时 order 估计" = Starling `ToMDepthEstimator` 的理论先例
- AAAI 2026 正式接收, 可作为 §12 与 §21 的关键引用
- 建议在 §12.3 新增 "Adaptive ToM Order" 子节, 引用 A-ToM

---

## 3. ToM4AI 2026 Proceedings

- **出处**: arXiv 2603.18786
- **链接**: https://arxiv.org/pdf/2603.18786

**核心贡献**:
- ToM4AI 第二卷, curated anthology for ToM and AI research
- 涵盖: ToM evaluation benchmarks, multi-agent ToM architectures, BDI+ToM integration

**对 Starling 的意义**:
- 提供 ToM 领域的系统性文献综述, 可作为 Starling §12 设计依据的领域背书
- BDI+ToM 融合方向与 Starling 的 Cognizer (BDI) + ToM Engine 双层架构高度一致

---

## 4. Episodic Knowledge Binding: a New Challenge for LLM Continual Learning

- **出处**: OpenReview 2026 (ICLR 2026 workshop 或主会投稿)
- **链接**: https://openreview.net/forum?id=0gDKeKwFj6

**核心贡献**:
- 首次系统刻画 LLM 在 binding related episodes through time 上的失败模式
- LLM 擅长学习孤立事实, 但无法跨时间绑定相关 episodes —— 这是 parametric memory 的根本缺口
- 提出 Episodic Knowledge Binding 作为新的 benchmark 挑战

**对 Starling 的意义**:
- 直接证明 Starling EpisodicEvent + episodic_link 的架构必要性 —— 这不是 Starling 多余的复杂度, 而是 LLM 的真实弱点
- Binding 失败 → Starling §6.2 episodic_link (CAUSAL / TEMPORAL / SEMANTIC) 的设计依据
- 建议在 §6.2 引用此论文作为 episodic binding 的动机说明

---

## 5. Governing Evolving Memory in LLM Agents

- **出处**: arXiv 2603.11768 (2026-03)
- **链接**: https://arxiv.org/abs/2603.11768

**核心贡献**:
- 提出 agent memory 的三个 fundamental trade-offs:
  1. **Fidelity vs. Utility** — 原档保真 vs. 检索可用性
  2. **Stability vs. Plasticity** — 旧知识保持 vs. 新知识吸收
  3. **Privacy vs. Awareness** — 隐私边界 vs. 上下文感知

**对 Starling 的意义**:
- 三个 trade-off 直接映射到 Starling 的核心设计决策:
  - Trade-off 1: §3.8 Drawer (verbatim) vs §13 Retrieval (semantic)
  - Trade-off 2: §11 Reconsolidation 的 supersedes 链 + adaptive forgetting
  - Trade-off 3: §3.2 `visibility` / `retention_policy` + §19 风险治理
- 建议在 §19 风险章节引用此 paper 的三 trade-off 框架, 作为 Starling 设计权衡的理论依据

---

## 6. Amory: Coherent Narrative-Driven Agent Memory

- **出处**: EACL 2026 (aclanthology 2026.eacl-long.183)
- **链接**: https://aclanthology.org/2026.eacl-long.183/

**核心贡献**:
- 提出 narrative-driven memory: 以叙事连贯性 (narrative coherence) 作为 memory organization 的核心原则
- 与传统的 time-sorted / importance-sorted 组织方式不同, Amory 按叙事结构组织记忆

**对 Starling 的意义**:
- 与 Starling §6 EpisodicEvent + episodic_link 的叙事线 (storyline) 概念高度共振
- Narrative coherence 可以作为 Starling §13.5 Reranker 的额外排序维度
- 建议在 §6.3 引用 Amory 作为"情节组织按叙事而非纯时间线"的学术支撑

---

## 7. Knowledge Objects for Persistent LLM Memory

- **出处**: arXiv 2603.17781 (2026-03)
- **链接**: https://arxiv.org/pdf/2603.17781

**核心贡献**:
- 提出 Knowledge Objects 作为 persistent memory 的一等公民抽象
- 从 in-context memory (prompt 内存储) 向 persistent structured memory 的迁移路径

**对 Starling 的意义**:
- Knowledge Objects 抽象 ≈ Starling Statement 的替代方案, 可作为 §3.2 Statement 设计的对比参照
- "persistent over sessions"的设计目标与 Starling 的 Statement + ConsolidationState 一致
- 建议在 §3.2 注释中引用

---

## 8. Evaluating Theory of Mind and Internal Beliefs in LLM-Based Multi-Agent Systems

- **出处**: arXiv 2603.00142 (2026-03)
- **链接**: https://arxiv.org/abs/2603.00142 / https://dl.acm.org/doi/10.1007/978-3-032-09318-9_2

**核心贡献**:
- Novel multi-agent architecture integrating ToM, BDI-style internal beliefs, and symbolic solvers for logical verification
- 在 multi-agent 场景下评估 ToM 与 internal beliefs 的交互
- 使用 symbolic solvers 验证 logical consistency of beliefs

**对 Starling 的意义**:
- BDI + ToM + 符号验证三层架构 = Starling Cognizer (BDI) + ToM Engine + Validator 的学术参照
- Symbolic solver 验证 beliefs 一致性 → Starling §5.3 Belief Consistency Validator 的理论先例
- 建议在 §5.3 和 §12 引用

---

## 9. (补充) Infusing Theory of Mind into Socially Intelligent LLM Agents

- **出处**: arXiv 2509.22887 (2025-09, OpenReview)
- **链接**: https://arxiv.org/abs/2509.22887

**核心贡献**:
- 在 Sotopia interactive social evaluation benchmark 上验证 ToM infusion 的有效性
- 实验证明 ToM 能力显著提升 LLM agent 的社交智能

**对 Starling 的意义**:
- 为 Starling §12 ToM Engine 的社会交互场景提供 benchmark 参照
- Sotopia 可作为 Starling ToM 模块的评估 benchmark 候选

---

## 10. (补充) Zep: A Temporal Knowledge Graph Architecture for Agent Memory

- **出处**: arXiv 2501.13956 (2025-01)
- **链接**: https://arxiv.org/abs/2501.13956

**核心贡献**:
- Zep (基于 Graphiti) 的正式学术论文, 在 Deep Memory Retrieval (DMR) benchmark 上超越 MemGPT
- 系统描述 temporal knowledge graph 作为 agent memory layer 的架构

**对 Starling 的意义**:
- Graphiti 生态的学术背书, 验证 temporal KG 路线
- 建议在 §16.2 (graphiti 迁移路径) 引用

---

## 11. (补充) Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Applications

- **出处**: arXiv 2603.07670 (2026-03)
- **链接**: https://arxiv.org/html/2603.07670v1

**核心贡献**:
- 2026 年 agent memory 的结构化综述
- 覆盖 memory design, implementation, and evaluation in modern LLM-based agents
- 提供概念基础: "memory as a first-class primitive in future agentic intelligence"

**对 Starling 的意义**:
- 2026 年最新综述, 可作为 Starling §1 引言和 §21 参考文献的领域全景引用
- "memory as first-class primitive"与 Starling 的设计哲学一致

---

## 对 v4 设计的启示总结

| Paper | 影响 Starling 章节 | 关键动作 |
|-------|----------------|---------|
| Human-Like Lifelong Memory (2603.29023) | §1, §6, §7, §21 | 引用为 CLS 路线的学术背书 |
| A-ToM (2603.16264) | §12.3 (新增), §21 | 新增 "Adaptive ToM Order" 子节 |
| ToM4AI 2026 (2603.18786) | §12, §21 | 引用为 ToM 领域的系统性综述 |
| Episodic Knowledge Binding | §6.2, §21 | 引用为 episodic binding 动机 |
| Governing Evolving Memory (2603.11768) | §19, §21 | 引用三 trade-off 框架 |
| Amory (EACL 2026) | §6.3, §13.5, §21 | 引用 narrative coherence 概念 |
| Knowledge Objects (2603.17781) | §3.2, §21 | 对比参照 Statement 设计 |
| ToM + BDI Multi-Agent (2603.00142) | §5.3, §12, §21 | 引用 BDI+ToM+验证三层架构 |
| Infusing ToM (2509.22887) | §12, §21 | Sotopia benchmark 参照 |
| Zep/Graphiti (2501.13956) | §16.2, §21 | Graphiti 学术背书 |
| Agent Memory Survey (2603.07670) | §1, §21 | 领域全景引用 |
