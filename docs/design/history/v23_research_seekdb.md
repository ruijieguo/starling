# seekdb 调研

## 调研时间

2026-05-19

## seekdb 识别

明确锁定一个项目：**OceanBase seekdb**（GitHub: `oceanbase/seekdb`）。
搜索其他同名项目的结果：

| 候选 | 结论 |
|---|---|
| **oceanbase/seekdb** | 唯一活跃、与"AI-native database / hybrid search"叙事完全匹配的项目。2025-11-14 v1.0.0 在 OceanBase 年会上正式开源。Apache 2.0。 |
| **SeekStorm** (Rust 全文搜索引擎) | 同样以 "seek" 前缀命名但完全不同——它是 Rust 写的纯 FTS 引擎，无向量、无 SQL，不是同一项目。**与本任务无关**。 |
| **openseek-AI/seekdb** | 搜索结果无可信记录；可能是误传或不存在。 |
| **seekdb 早期同名项目** | 历史上 SourceForge 等平台有少量同名条目，但当前生态全部指向 OceanBase 出品的这一个。 |

> 结论：本调研下文一律指 **OceanBase seekdb**。

---

## 主推项目核心信息

| 字段 | 值 |
|---|---|
| 全称 | OceanBase seekdb |
| GitHub URL | https://github.com/oceanbase/seekdb |
| 文档站 | https://www.oceanbase.ai/docs/seekdb-overview/ ， https://docs.seekdb.ai/ |
| 维护者 | OceanBase（蚂蚁集团 / Ant Group 系出，已分拆为独立公司） |
| Stars (2026-05) | 约 **2.5 k** 量级（搜索结果给出的近似值；非精确） |
| 第一次开源公开 | 2025-11-14（v1.0.0），2025-11-18 在 OceanBase 年会正式宣布 |
| 最新版本 | **v1.2.0**（2026-04-15） |
| 历史版本节奏 | v1.0.0 (2025-11) → v1.0.1 (2025-12) → v1.1.0 (2026-01) → v1.2.0 (2026-04) |
| License | **Apache 2.0** |
| 实现语言 | **C++**（fork 自 OceanBase observer 内核，CMake/build.sh，POSIX + Windows build 脚本 build.ps1） |
| 嵌入式 | ✅ 官方 README 自述"Embedded ✅ / Single-Node ✅ / Distributed ❌"，对标 Chroma / DuckDB |
| MySQL 兼容 | ✅（SQL 走 MySQL 协议端口 2881） |
| OLTP/OLAP | 两者都标 ✅（基于 OceanBase 双模引擎） |
| 多语言绑定 | Python（pyseekdb / pylibseekdb）、JS/TS（seekdb-js）、Go（ob-labs/seekdb-go），无独立 C++ 头文件 SDK 暴露 |
| 国际化文档 | 中英双文档（README + README_CN，docs 站中英都有） |
| 社区渠道 | Discord、GitHub Discussions、OceanBase ask 论坛、钉钉群 |

---

## 能力评估（逐项对照 Starling P1 需求）

### 1. 嵌入式 vs client-server

**关键发现**：seekdb 的"embedded"和 SQLite/DuckDB 意义上的 in-process **不完全等同**。

- 仓库结构是 OceanBase observer 改造：`src/observer/`、`src/storage/`、`src/rootserver/`，主入口编译产物是 `build_debug/src/observer/seekdb` —— **一个独立的 daemon 二进制**。
- "Embedded mode" 实际工作方式（从 `pyseekdb/src/pyseekdb/client/client_seekdb_embedded.py` 推断）：
  - Python 端 `import pylibseekdb as seekdb`；调 `seekdb.open(db_dir=...)`，`seekdb.connect(database=...)`。
  - 注释里有一条强约束：`pylibseekdb built with ABI=0 and onnxruntime built with ABI=1, so there's a conflict… pylibseekdb is built both with ABI=0 and the -Bsymbolic flag`。说明 pylibseekdb 是把 observer 内核**编译成共享库**通过 cffi 风格链接进 Python 进程的。
  - 这是真 in-process（不是 spawn subprocess），但是体量上等于把整个 OceanBase observer 链进你的进程。
- pylibseekdb **仅 Linux**：embedded client 的源码顶部明确写：`Note: Only available when pylibseekdb is installed (Linux only)`。macOS native 支持是 v1.1.0 (2026-01) 加上的，但 wheel 发布状态需要去 PyPI 核实；Windows 一律只能 server 模式。

**对 Starling 的影响**：
- 跨平台 in-process 集成只在 **Linux（glibc ≥ 2.28）** 上是干净的 in-process，**macOS** 是后加的（需要 v1.1.0+ 且需 PyPI/wheel 支持验证），**Windows 不支持 embedded**——必须 server 模式。
- "in-process" 但是 process 内会被链上 OceanBase observer 的全套堆栈（rootserver、logservice、palf、storage 等）。这跟 SQLite 那种"几百 KB amalgamation"的轻量级不是一个量级，更像把 DuckDB 全部库链进去——但比 DuckDB 重得多。
- 没有公开的 native C++ SDK header / lib（C++ 应用想直接 in-process 调用，得自己读 src/observer 暴露的接口或走 MySQL 协议）。**对一个 C++ 内核来说，这是一个严重的集成缺口**。

### 2. 关系/文档存储

- ✅ 完整 SQL（MySQL 兼容），autoincrement、二级索引、外键（OceanBase 风格）
- ✅ JSON 字段类型 + JSON 索引（README 列为一等公民）
- ✅ "HEAP organization table"（README 示例里出现）
- ✅ ACID 事务，README 写 "full ACID compliance"
- ✅ OLTP + OLAP（双引擎来自 OceanBase 血统）
- 可用 SQLAlchemy（pyseekdb README 建议高级用户 SQLAlchemy）

### 3. 向量索引

- ✅ Dense vector，**最高 16000 维**
- ✅ HNSW、HNSW_SQ（scalar quantization）、HNSW_BQ（binary quantization）—— 内存型
- ✅ IVF、IVF_PQ —— 磁盘型
- ✅ Sparse vector
- ✅ Manhattan / Euclidean / inner product / cosine 四种距离
- 底层 vector lib：README SQL 示例里 `VECTOR INDEX idx_vec (embedding) WITH(... LIB=vsag)`，明确用 **VSAG**（OceanBase 自研 vector lib，已开源）
- 用 VectorDBBench 跑过自家基准（[文档](https://www.oceanbase.ai/docs/ob-vector-search-bench-test/)），但搜索结果没给具体 QPS/latency 数字，需要去自家文档实跑核实

### 4. 全文检索

- ✅ FULLTEXT INDEX 语法（SQL `MATCH ... AGAINST`）
- ✅ BM25 评分
- ✅ 多种 tokenizer（中文 `ik` 等）
- ✅ Hybrid Index：vector + FTS 联合（README `DBMS_HYBRID_SEARCH` API、SQL 层"`ORDER BY vector_distance APPROXIMATE`"）

### 5. 事务模型

- ✅ ACID（基于 OceanBase storage + logservice）
- ✅ 跨表原子提交：MVCC + redo log（OceanBase 一直是这套）
- ✅ outbox 模式可用：跨表事务 INSERT 一次就行
- 隔离级别：MySQL 兼容（默认 REPEATABLE READ）
- v1.2.0 加了"primary-standby replication with async log sync"

### 6. 持久化

- 数据落 `db_dir` 目录（多文件），不是单文件
- v1.1.0 把默认数据文件从 2 GB 压到 32 MB（说明早期对小数据集不友好，已修）
- v1.1.0 还加了"FORK TABLE"做 copy-on-write 克隆；v1.2.0 扩展到 Fork Database、Table Diff & Merge（Git 风格数据工作流，对 memory 应用挺有意思）

### 7. 多语言绑定

| 语言 | SDK | 嵌入式支持 | 备注 |
|---|---|---|---|
| **Python** | `pyseekdb` (PyPI) | ✅（Linux only via `pylibseekdb`） | collection-first API, Chroma-style；server mode 走 pymysql |
| **JS / TS** | `seekdb-js` (GitHub) | ✅ embedded + server | TypeScript native, 类型完备 |
| **Go** | `goseekdb` (`ob-labs/seekdb-go`) | ❌ **未支持 embedded**，仅 server | 远程连接 |
| **C / C++** | ❌ **无公开 SDK 头文件**；只能链 `pylibseekdb` (private ABI) 或走 MySQL 协议 | n/a | **对 Starling C++ 内核是缺口** |
| **Java** | 走 MySQL JDBC | server only | n/a |
| **Rust** | 走 MySQL crate | server only | n/a |

### 8. 性能

- **公开 benchmark**：seekdb 文档站给了 VectorDBBench 跑法（Performance1536D50K dataset, HNSW），但是搜索结果里**没拿到具体 QPS / p99 数字**。需要本地或 README 直接看。
- 早期推广文章说"1C2G 起步就能跑"（VectorDBBench 最小硬件），用于宣传低门槛。
- OceanBase 引擎本身在 sysbench OLTP 上是工业级；继承下来的 OLTP 性能在 100-1000 QPS 单行写需求面前**绰绰有余**（OceanBase 单机轻松 10k+ QPS）。
- 向量 ANN p99：10⁶ 量级用 HNSW 应该达到 <50 ms，但 seekdb 没公开具体数字，**风险点**。

---

## 与 SQLite + LanceDB + DuckDB 三件套对比

| 维度 | SQLite | LanceDB | DuckDB | seekdb | seekdb 能否替代 |
|---|---|---|---|---|---|
| OLTP（点写、行更新） | ✅ 工业级 | ⚠️ append-only | ❌ | ✅ OceanBase 血统 | ✅ |
| 关系 SQL | ✅ | ⚠️ 简单 | ✅ | ✅ MySQL 兼容 | ✅（但是 MySQL 方言不是 SQLite 方言） |
| JSON 字段 + 索引 | ⚠️ JSON1 | ✅ | ✅ | ✅ + JSON index | ✅ |
| 向量 ANN | ❌（需 sqlite-vec/vss） | ✅ 核心 | ⚠️ 扩展 | ✅ HNSW/IVF + VSAG | ✅ |
| BM25 FTS | ✅ FTS5 | ⚠️ | ✅ FTS extension | ✅ + 多 tokenizer | ✅ |
| Hybrid search | 拼凑 | ⚠️ | 拼凑 | ✅ 原生 + APPROXIMATE | ✅ |
| ACID | ✅ | ⚠️ | ✅ | ✅ | ✅ |
| 单进程 in-process | ✅ 极轻 | ✅ 中等 | ✅ 轻 | ⚠️ 重（observer 链入） | ⚠️ |
| 跨平台（mac/lin/win）embedded | ✅ all | ✅ all | ✅ all | ⚠️ Linux + macOS(v1.1+)，**Windows 无 embedded** | ⚠️ |
| C/C++ in-process API | ✅ amalgamation | ✅ Rust C ABI | ✅ C++ amalgamation | ❌ **无公开 C++ SDK** | ❌ |
| 二进制体积 | <1 MB | ~30 MB | ~30 MB | 估 100 MB+（observer + deps） | ⚠️ |
| 冷启动延迟 | 毫秒 | <1 s | <1 s | 秒级（observer 启动） | ⚠️ |
| License | Public Domain | Apache 2.0 | MIT | Apache 2.0 | ✅ |
| 项目成熟度 | 25 年 | 2-3 年 | 4-5 年 | **<6 个月开源**，但内核 OceanBase 10+ 年 | ⚠️ 看角度 |

**汇总判断**：

1. **功能合并面**：seekdb 在 SQL/JSON/向量/FTS/事务上**单引擎覆盖了三件套**，技术上是真的"一个引擎打四个"。
2. **embedded 集成面**：seekdb 的 embedded 比那三件套**重得多**且**跨平台 / C++ 绑定明显缺位**。SQLite 是 amalgamation 链一个 .c；DuckDB 是 amalgamation 链一个 .cpp；LanceDB 是 Rust C ABI；seekdb 是把 OceanBase observer 链进来。
3. **C++ 内核集成的硬伤**：**seekdb 没有公开的 C/C++ SDK header**。Starling 是 C++ 内核，目前的可选路径：
   - (a) 让 C++ 内核走 MySQL 协议本地 socket 连 seekdb daemon —— 等于回到 client-server，不是真 in-process。
   - (b) 链 `pylibseekdb` 的私有 ABI —— **不推荐**，那是 Python wheel 的内部 binding，未承诺向 C++ 用户稳定。
   - (c) 自己从 `src/observer` 暴露接口编译——属于 fork 工程，成本巨大。

---

## 已知坑 / 风险

| 风险 | 等级 | 描述 |
|---|---|---|
| **C++ in-process 集成缺口** | 🔴 高 | 无公开 C++ SDK；走 MySQL 协议本地 socket 会丢失"in-process"语义；链 pylibseekdb 是 Python ABI 不承诺给 C++ 用。 |
| **Windows embedded 不支持** | 🟡 中 | 跨平台需求时只能 server 模式；如果 Starling 目标用户含 Windows 桌面，这是死线。 |
| **macOS embedded 是 v1.1.0+ 新加** | 🟡 中 | 需要核实 PyPI wheel 是否真有 darwin 版本，以及在 Apple Silicon (aarch64) 上的稳定性。 |
| **二进制体积 + 启动延迟** | 🟡 中 | observer 全套链入，体积估上百 MB，冷启动秒级。对 SQLite-style 轻量 embedded 期望不友好。 |
| **跨版本 in-place 升级被禁** | 🟡 中 | v1.0→v1.1、v1.1→v1.2 **都不支持 in-place 升级**，需要 OBDUMPER/OBLOADER 逻辑迁移。对发布周期 < 1 年的项目，**迁移成本是真实负担**。 |
| **开源年龄 <6 个月** | 🟡 中 | 真实 OSS 项目寿命到 2026-05 也就 6 个月。社区 issues / 第三方文章 / 生产案例都非常少（即使 HN 有 3 篇讨论也都很轻）。 |
| **公开 benchmark 数字不透明** | 🟡 中 | 自家 VectorDBBench 没给具体 p99/QPS；需要自己跑才知道 10⁶ 向量、混合 SQL+FTS 工作负载下的真实表现。 |
| **Stars 量级偏低** | 🟢 低 | 约 2.5k 量级，OceanBase 母品牌背书够，但社区还在早期。 |
| **多 client SDK 不齐** | 🟢 低 | Python 全 / JS embedded 全 / Go 仅 server / C++ 缺。 |
| **底层等于 OceanBase 单机** | 🟢 低 | 内核是 OceanBase observer 单机版剪裁，工程上信誉好，但代码量大（cmake build 是规模工程，不是 SQLite-style 单文件）。 |
| **依赖 onnxruntime** | 🟢 低 | pylibseekdb 注释提及与 onnxruntime 的 ABI 冲突已 hack 处理。说明默认依赖 ML 运行时（embedding function 用），增加了依赖面。 |

---

## 是否推荐 seekdb + LadybugDB 作为 P1 方案？

### 短答

**条件性推荐——前提是接受三件事：(1) Linux/macOS 优先，Windows 走 server 模式；(2) Starling C++ 内核以 MySQL local socket 接入 seekdb daemon（不是真 in-process），或愿意承担私有 ABI 链接风险；(3) 接受 v1 系列升级路径有断点。**

信心等级：**中 (5/10)**

理由：
- **功能维度 9/10**：seekdb 在单引擎里把 OLTP + JSON + 向量 + BM25 + Hybrid 都做了，**是市面上少数真的"一个引擎打四个"** 的开源项目。Apache 2.0 license 没坑。OceanBase 内核底座工程信誉硬。
- **集成维度 3/10**：但是 Starling 是 **C++ 内核**——这恰好是 seekdb 唯一**没**做 SDK 的语言。要么走本地 MySQL 协议（牺牲 in-process 性能优势 + 增加 1 个外部进程依赖），要么去链 pylibseekdb 的私有 ABI（脆弱）。
- **成熟度维度 4/10**：开源不到 6 个月，每两三个月一个不能 in-place 升级的大版本，生产案例几乎没有公开。

### 如条件推荐（替代什么、保留什么）

**用 seekdb 替代**：
- ❌ SQLite (OLTP) → ✅ seekdb 关系表
- ❌ LanceDB (向量) → ✅ seekdb HNSW/IVF/VSAG
- ❌ DuckDB (OLAP/查询) → ✅ seekdb OLAP 引擎 + JSON

**保留**：
- ✅ **LadybugDB**（KV / 嵌入式高性能 KV，没被 seekdb 覆盖的 layer 保持原样）
- ⚠️ 如果还有时序、图、对象存储这些 layer，seekdb 不替代

**集成路径建议**：
1. **本地 socket 模式（推荐起步路径）**：C++ 内核启动时 fork 一个 seekdb observer 子进程，监听 Unix domain socket（或 localhost:2881），用 MySQL C++ 客户端（如 mariadb-connector-c, libmysqlclient）连接。**优点**：稳定、官方 SDK 路径、不依赖私有 ABI、跨平台一致。**缺点**：多一个进程、损失 ~10-50 µs 协议 hop、需要进程生命周期管理。
2. **平台策略**：Linux 用 daemon 子进程；macOS 跑同样的模式；Windows 也用 daemon（反正 embedded 不支持，干脆全平台统一）。
3. **保留逃生口**：把数据访问层抽象成 trait/接口，万一 seekdb 后续不靠谱，可以平移回 SQLite/LanceDB/DuckDB 组合。**v1 升级断点说明前两年内迁移成本很真实**。
4. **先做一个 spike**：用 1 周时间在 C++ 内核里跑通 MySQL local socket 接入 + 10⁶ 向量插入和检索，测出真实 QPS/p99，再决定是否承诺为 P1 方案。

### 如不推荐（备选方案）

如果 (a) Windows embedded 是硬需求，(b) C++ in-process（不是 socket）是硬需求，(c) 不能容忍 v1 升级断点 —— 那么**回到 SQLite + LanceDB + DuckDB + LadybugDB 四件套**，工程上虽然胶水多但每一件都成熟 5-25 年。

折中方案：**SQLite (sqlite-vec 扩展) + LadybugDB**。sqlite-vec 是 SQLite 官方风格的向量扩展，全平台 C amalgamation，能把 SQL + 向量收到 SQLite 一个引擎里；FTS5 + JSON1 也已经在 SQLite 内。结果是三件套（SQLite-with-extensions + LadybugDB），比 seekdb 简单、比四件套合并。

---

## 参考资料

1. [oceanbase/seekdb GitHub repository](https://github.com/oceanbase/seekdb) - 主仓库 + README
2. [oceanbase/seekdb Releases](https://github.com/oceanbase/seekdb/releases) - v1.0.0 (2025-11-14) → v1.2.0 (2026-04-15)
3. [oceanbase/pyseekdb GitHub](https://github.com/oceanbase/pyseekdb) - Python SDK 源码（已 zread 读 README + `client_seekdb_embedded.py`）
4. [pyseekdb on PyPI](https://pypi.org/project/pyseekdb/)
5. [pylibseekdb on PyPI](https://pypi.org/project/pylibseekdb/0.0.1.dev2) - 底层 C++ binding wheel
6. [oceanbase/seekdb-js (GitHub)](https://github.com/oceanbase/seekdb-js) - JS/TS SDK
7. [goseekdb (pkg.go.dev)](https://pkg.go.dev/github.com/ob-labs/seekdb-go) - Go SDK（仅 server mode）
8. [seekdb overview docs](https://www.oceanbase.ai/docs/seekdb-overview/)
9. [Vector index overview](https://www.oceanbase.ai/docs/vector-index-overview/) - HNSW/HNSW_SQ/HNSW_BQ/IVF/IVF_PQ
10. [VectorDBBench testing guide](https://www.oceanbase.ai/docs/ob-vector-search-bench-test/)
11. [Experience embedded seekdb with Python SDK V1.0.0](https://docs.seekdb.ai/docs/V1.0.0/using-seekdb-in-python-sdk/) - 平台限制：Linux glibc≥2.28, Python 3.11+
12. [MarkTechPost 报道 (2025-11-26)](https://www.marktechpost.com/2025/11/26/oceanbase-releases-seekdb-an-open-source-ai-native-hybrid-search-database-for-multi-model-rag-and-ai-agents/)
13. [OceanBase 2025 年会发布稿 (PR Newswire / Yahoo Finance)](https://finance.yahoo.com/news/oceanbase-unveils-open-sources-ai-100700284.html) - 2025-11-18
14. [Hacker News thread #46019453](https://news.ycombinator.com/item?id=46019453) - 初次发布讨论
15. [Hacker News thread #46041747](https://news.ycombinator.com/item?id=46041747)
16. [Hacker News thread #46154860](https://news.ycombinator.com/item?id=46154860)
17. [r/machinelearningnews discussion](https://www.reddit.com/r/machinelearningnews/comments/1p7wmar/oceanbase_opensources_seekdb_an_open_source_ai/) - 社区讨论少
18. ["From Complex to Simple: How We Built seekdb"](https://en.oceanbase.com/blog/23848834048) - OceanBase 官方设计博客（fetch 时被 429 限流，未能拿到完整原文）
