#!/usr/bin/env bash
# 抽取 prompt 改动的统一质量门(缺陷 3 / follow-up)。
#
# 背景:改 prompt 该跑的门散在两个脚本里,没有单一入口 —— 将来 prompt 漂移不会被
# 自动提醒。本脚本把它们串起来:
#   1. 三维回归门   eval_quality_baseline.py --check(belief/gf/tom F1 相对基线)
#   2. subject_kind 子门 eval_subject_kind.py(cognizer/entity 分类准确率,PR1 核心)
# 任一门失败 → 整体非零退出。真 LLM,不进 CI(Clash 黑洞换时刻重跑)。
#
# 用法(改 prompt「后」跑):
#   OPENAI_API_KEY=... OPENAI_BASE_URL=... bash scripts/eval_prompt_gate.sh
#
# 注意:三维基线须已存在(先在「改 prompt 前」跑过 --update)。见各脚本 --help。
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"

if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "ERROR: OPENAI_API_KEY 未设(不打印 key)" >&2
    exit 2
fi

fail=0

echo "=== 门 1/2: 三维回归 (belief/gf/tom F1 vs baseline) ===" >&2
if ! "$PY" "$ROOT/scripts/eval_quality_baseline.py" --check "$@"; then
    echo "!! 三维回归门 FAILED" >&2
    fail=1
fi

echo "" >&2
echo "=== 门 2/2: subject_kind 分类子门 (cognizer/entity 准确率) ===" >&2
if ! "$PY" "$ROOT/scripts/eval_subject_kind.py"; then
    echo "!! subject_kind 子门 FAILED" >&2
    fail=1
fi

echo "" >&2
if [ "$fail" -eq 0 ]; then
    echo "=== 全部门通过 ===" >&2
else
    echo "=== 有门未通过 —— 回 prompt 修正(不是放宽阈值) ===" >&2
fi
exit "$fail"
