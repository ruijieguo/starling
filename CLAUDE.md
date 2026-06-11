# Starling Memory — 仓库约定

## 架构边界(硬规则,2026-06-11 裁定)

**核心功能一律实现于 C++ 内核(`src/` + `include/starling/`);Python 层(`python/starling/`)只做应用适配。**

- 绑定层允许:绑定转发、签名归一(datetime/None 惯用法)、DTO 构造默认值、受控测试镜像(必须带 parity 钉测)、只读检视查询(dashboard)、prompt 等配置数据(单一源)。
- 绑定层禁止:算法、预算/裁剪策略、状态机、管线编排规则等核心语义。
- 越界判据:**换一种绑定语言是否需要重写该逻辑**——需要,就属于核心,放 C++。
- 先例:Working Set(预算分配/截断/渲染)曾落在 `python/starling/working_set.py`,已归位 `src/hippocampus/working_set.cpp`;规范全文见 `docs/design/system_design.md` §2.0 多语言绑定。

## 写入纪律

- 幂等去重不变式归**写入器**持有:审计/通知类写入(`OutboxWriter::append_already_delivered`、`PipelineLedger::record_attempt`)对重复键 INSERT OR IGNORE 静默丢弃;业务事件 `append` 撞键 fail-loud。调用方不得自建防重集合。
- 写后/订阅者路径用 SAVEPOINT,不用 BEGIN(见 `src/bus/subscriber_pump.cpp`)。

## 构建与测试

- canonical 构建:`python scripts/configure_build.py --build --test`(C++ + ctest);改 C++/绑定/migration 后必须再跑 `--python-editable` 重装 `_core`,只 `pip install -e .` 不够。
- 提交门:全量 ctest + `pytest tests/python` 绿;dashboard 前端另有 `npm run check` / `npx vitest run` / `npm run build`(在 `dashboard/web/`)。
- git:只用显式路径 `git add`(禁 `git add .`/`-A`);不用 `--no-verify`/`--amend`。
