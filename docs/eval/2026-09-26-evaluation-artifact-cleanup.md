# 本机 Starling 编译中间产物清理（2026-09-26）

## 结果

已删除 4,041 个可重新编译生成的中间文件。build目录分配空间从 25.001 GiB 降至 24.403 GiB，减少 **612.48 MiB**。这不是APFS卷实际物理可用空间测量。

## 边界

仅删除未被Git跟踪、未位于65个seal封存目录及其子目录、且不在frozen/runtime/native-runtime/source等证据目录内的CMake `.o`、`.o.d`、`.a` 文件：2287个对象文件、1692个依赖文件、62个静态链接库。保留全部数据库、原始模型回答、HTTP与费用回执、设计/诊断文档、日志、动态核心和测试可执行文件。未删除历史低分或失败评测；R6.7两个零请求准备快照也保留。

删除前只读检查未发现clang/cmake/ninja/make或Starling测试编译进程；未停止任何进程。每个候选文件先记录SHA-256和元数据，删除时重验且逐文件处理。后续首次编译需要重新生成这些文件。

## 验证与复现

删除后逐项核对 175,908 个保留文件的大小、时间、inode和链接信息，全部一致；207 个身份、封存和验证清单SHA-256一致。候选删除日志完整。清理本身无模型请求，未访问其他代码库。

- [清理策略与分类](../../build/eval_cleanup_20260926/plan.json)
- [候选文件及SHA-256](../../build/eval_cleanup_20260926/candidates.json)
- [逐文件删除回执](../../build/eval_cleanup_20260926/deletion-log.jsonl)
- [保留验证](../../build/eval_cleanup_20260926/verification.json)
- [R6.7清理后重哈希](../../build/eval_cleanup_20260926/r67-revalidation.json)

按用户要求先完成清理，再继续R6.8结构化选择调用修复；本报告不声称清理提升评测准确率。
