-- 成本持久化:extraction_attempt 记录每次 LLM 往返的 token 用量 + 时延。
-- LLMResponse(include/starling/extractor/llm_adapter.hpp)已在适配器(核心)采集
-- prompt/completion/total tokens 与 latency_ms;此前只在内存里,落库后 dashboard
-- 才能只读回溯单语句成本(/lens)与租户级历史成本(/vitals)。
--
-- 归属不变式(extractor.cpp):每个 attempt 迭代恰有一次 adapter_.extract(),但成功
-- 路径按 statement-span 写多行 success——故 take_cost() 只把整次调用成本记到该迭代
-- 首个写入行,其余行记 0,保证 SUM(total_tokens) 不重复计数。失败/解析失败行各自是
-- 该迭代唯一的 record_attempt,直接携带本次调用成本(失败响应也带 latency)。
--
-- NOT NULL DEFAULT 0:既有行(0027 之前)与 fake/未返回 usage 的端点统一记 0,诚实
-- 表示「无成本数据」而非 NULL 歧义。沿用 0022 的 ADD COLUMN ... NOT NULL DEFAULT 模式。
ALTER TABLE extraction_attempt ADD COLUMN prompt_tokens     INTEGER NOT NULL DEFAULT 0;
ALTER TABLE extraction_attempt ADD COLUMN completion_tokens INTEGER NOT NULL DEFAULT 0;
ALTER TABLE extraction_attempt ADD COLUMN total_tokens      INTEGER NOT NULL DEFAULT 0;
ALTER TABLE extraction_attempt ADD COLUMN latency_ms        INTEGER NOT NULL DEFAULT 0;
