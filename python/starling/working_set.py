"""Working Set — 绑定转发(2026-06-11 边界归位)。

核心实现已迁入 C++ `starling::hippocampus::working_set`
(include/starling/hippocampus/working_set.hpp):优先级预算分配、码点级
截断、ContextBlock 渲染都在核心层。本模块仅为既有 Python 调用方保留
同名入口;新代码请直接用 `_core.working_set_assemble` /
`_core.build_working_set`。
"""
from __future__ import annotations

from starling import _core

# 数据类型与渲染语义见 C++ 头文件;这里是同一对象的绑定别名。
WorkingBlock = _core.WorkingBlock
ContextBlock = _core.ContextBlock


def assemble(sections: dict, token_budget: int) -> "_core.ContextBlock":
    """sections: label -> content。优先级 pending_commitments > persona >
    common_ground > relevant_memories > affect;超预算按码点截断并记入
    `truncated`。转发到 C++ 实现。"""
    return _core.working_set_assemble(sections, token_budget)
