# 本机 Starling 评测产物清理记录

记录时间：2026-09-22T17:46:00.623666+08:00。状态：已完成清理并验证。

## 清理边界

本次仅清理当前 Starling 工作区 `build/` 内确认无用的评测产物。保留正式 baseline、所有当前文档或脚本直接引用的结果及其跨目录依赖、存在有效答题结果的其他历史运行、当前构建与测试产物，以及 R4.0—R4.4 全部目录。未将低准确率作为删除理由。

候选要求：无源码、文档或其他 build 结果中的目录引用；无 Git 跟踪文件和指向候选的外部符号链接；已验证为过时离线 smoke、失败运行、明确失效或被替代的运行，或无引用临时数据库。

进程列表只读检查未获可用结果（沙箱限制，越界查询自动审核超时）。改用终态元数据、文件指纹和删除时非阻塞文件锁检查；R4.4 无条件排除，不依赖进程列表判断。

候选 20 个目录、11,984 个文件，文件分配空间共 1.931 GiB。

## 删除清单

| 目录（均位于 build/） | 文件分配空间 MiB | 原因 |
| --- | ---: | --- |
| `socialmem_20260911_admission_smoke` | 69.8 | 旧离线 smoke，无外部引用；后续 smoke_v2 和正式运行保留 |
| `socialmem_20260912_chinese_unicode_smoke` | 95.8 | 旧离线 smoke，无外部引用；正式运行保留 |
| `socialmem_20260912_json_mode_smoke` | 95.8 | 旧离线 smoke，无外部引用；final_smoke 和正式运行保留 |
| `socialmem_20260912_optimization_real` | 87.0 | manifest 明确 failed，答题结果为空；real_final 保留 |
| `socialmem_20260912_optimization_real_retry` | 87.1 | manifest 明确 failed，答题结果为空；real_final 保留 |
| `socialmem_20260912_optimization_smoke` | 95.7 | 旧离线 smoke，无外部引用；正式 final 运行保留 |
| `socialmem_20260913_protocol_boundary_final_smoke` | 94.2 | 旧离线 smoke，无外部引用；validated_smoke 和正式运行保留 |
| `socialmem_20260913_protocol_boundary_smoke` | 98.8 | 旧离线 smoke，无外部引用；validated_smoke 和正式运行保留 |
| `socialmem_20260914_protocol_recovery_a_offline_invalid_editable` | 173.2 | INVALID.json 明确身份无效，external_calls=0 |
| `socialmem_20260914_protocol_recovery_b_offline_invalid_editable` | 173.2 | INVALID.json 明确身份无效，external_calls=0 |
| `socialmem_20260918_answer_capacity` | 105.0 | superseded-no-requests.json 明确已被 v2 替代，provider_requests=0 |
| `socialmem_20260919_structured_eval_dns_failed` | 169.1 | DNS 失败旧运行，sources 的 57 题全部技术失败；正式 structured_eval 保留 |
| `socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_layout_r23` | 71.2 | 57 题全部技术失败，无有效答题结果；_net 运行保留 |
| `socialmem_20260920_structured_eval_source_turn_baseline` | 71.2 | 57 题全部技术失败，无外部引用 |
| `socialmem_20260920_structured_eval_source_turn_baseline_net` | 71.2 | 57 题全部技术失败，无外部引用 |
| `socialmem_20260921_r34_offline_scratch` | 1.6 | 仅 3 份临时数据库，无文档、脚本或其他结果引用 |
| `socialmem_20260921_structured_eval_hybrid_coverage_r33_evidence_coverage` | 82.7 | 57 题全部技术失败；_net 正式运行保留 |
| `socialmem_20260921_structured_eval_hybrid_holder_isolation_r35` | 143.6 | 57 题全部技术失败；_dashscope 正式运行保留 |
| `socialmem_claim_contract_review_smoke` | 95.8 | 旧离线 smoke，无外部引用；final_smoke 保留 |
| `socialmem_claim_contract_smoke` | 95.6 | 旧离线 smoke，无外部引用；final_smoke 保留 |

## 留痕与验证

审计目录：`build/eval_cleanup_20260922/`。包含完整候选文件清单及 SHA-256、保留文件元数据、R4 系列封存与身份文件哈希、引用扫描结果和诊断摘要。诊断摘要只用于记录删除理由，不是完整备份；删除后这些废弃目录不能原样重放。

执行时再次检查候选文件未变化并持有已有运行锁，再按显式目录清单删除。执行后检查目录消失、保留文件完整、R4 系列封存文件哈希不变，并记录 `du` 前后占用。APFS 快照或克隆可能影响实际卷可用空间，目录占用减少量与物理磁盘释放量不混用。

## 执行结果

已删除 20 个目录、11,984 个文件。删除前成功获取 6 个已有运行锁，候选文件清单、元数据与 SHA-256 全部一致。

即时 `du -sk build` 统计：20.211 GiB → 18.280 GiB，目录分配空间减少 1.931 GiB（约 2.07 GB）。此处是目录占用统计，未测量 APFS 卷的实际物理释放量。审计记录另占少量空间，已包含在清理后统计内。

逐项复核 117,059 个保留文件：缺失 0、元数据变化 0；核验 38 个 R4 系列身份与封存文件哈希：不一致 0。R4.4 目录完整保留。Git 状态相对执行前只新增本清理报告。

完整验证结果：`build/eval_cleanup_20260922/verification.json`；逐目录删除日志：`build/eval_cleanup_20260922/deletion-log.jsonl`。

## 第二轮：继续清理临时产物

记录时间：2026-09-22T18:39:21.120475+08:00。状态：已删除并完成验证。继续清理已确认与当前 Starling 任务有关的 `/private/tmp` 临时文件。当前系统 pytest 工作目录完整保留。

本轮发现 `/private/tmp/starling_r35_py/starling/_core.cpython-314-darwin.so` 被 R3.5 正式运行的 `identity.json` 引用，且与 `build/r35_py` 的模块字节不同，因此保留。未引用但有有效答题结果的历史运行继续保留。

| 路径 | 分配空间 MiB | 删除依据 |
| --- | ---: | --- |
| `/private/tmp/starling_pytest_socialmem` | 10.000 | 9 月 20 日旧测试夹具；对应 tests/python/test_eval_ladder_pipeline.py，非当前 pytest 目录 |
| `/private/tmp/starling-task2-preview.CIQsqs` | 0.000 | 旧预览目录；只含 10 个空子目录 |
| `/private/tmp/starling_eval_refs.txt` | 0.012 | 上轮清理生成的引用扫描中间清单；完整引用清单已归档 |
| `/private/tmp/starling-eval-cleanup-inventory.json` | 0.191 | 已归档到 build/eval_cleanup_20260922/inventory.json |
| `/private/tmp/starling-eval-cleanup-dependencies.json` | 0.004 | 已归档到 build/eval_cleanup_20260922/dependencies.json |
| `/private/tmp/starling-eval-cleanup-selected.json` | 0.023 | 已归档到 build/eval_cleanup_20260922/candidates.json |

合计 6 个路径、23 个普通文件、18 个内部符号链接，目录占用约 10.230 MiB。原始清理清单已确认与归档 JSON 语义一致；额外保存原始引用列表。候选文件校验值与保留文件校验值见 `build/eval_cleanup_20260922/phase2/`。

第二轮执行结果：6 个候选路径已全部删除，清理占用 10.230 MiB；39 个关键文件哈希一致，117,059 个保留 build 文件元数据未改变，当前系统 pytest 的 1,318 个目录项未改变。保留 R3.5 临时绑定、R4.4 和正式评测证据。

两轮累计删除 22 个目录及 4 个独立临时文件；按第一轮 build 即时占用差值与第二轮临时路径删除前占用合计，清理约 1.941 GiB（2.08 GB）。该数值不等于实际 APFS 卷可用空间增量。剩余较大产物均按证据保留规则保留，本轮未进一步删除。
