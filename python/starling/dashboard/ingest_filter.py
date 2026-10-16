"""dogfood 子项 A:transcript 过滤 + 分块纯函数。

Claude Code 会话 transcript(jsonl)→ 清洗后的 (role, text) 对话轮 → 定长分块。
剔除 thinking / tool_use / tool_result / 代码围栏 / 超长行,只保留可读对话文本。
纯函数,无副作用(不碰文件/网络);由 worker(Task 3)消费。
"""
from __future__ import annotations

import json
import re

MAX_CHARS = 8000     # ~2000 token
_LONG_LINE = 400     # 超长单行阈值(命令 stdout / base64 残留)
_FENCE = re.compile(r"```.*?```", re.DOTALL)   # 代码围栏(含多行)


def _strip_code(text: str) -> str:
    text = _FENCE.sub(" ", text)                                   # 去代码围栏
    keep = [ln for ln in text.splitlines() if len(ln) <= _LONG_LINE]  # 去超长行
    return "\n".join(keep).strip()


def clean_turns(lines: list[str]) -> list[tuple[str, str]]:
    """jsonl 行 → [(role, text)]。保留 user 纯文本 + assistant text 块;剔除
    thinking / tool_use / tool_result / 代码围栏 / 超长行。"""
    out: list[tuple[str, str]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if not isinstance(ev, dict) or ev.get("type") not in ("user", "assistant"):
            continue
        msg = ev.get("message") or {}
        role, content = msg.get("role"), msg.get("content")
        if role == "user" and isinstance(content, str):
            text = _strip_code(content)
            if text:
                out.append(("user", text))
        elif role in ("user", "assistant") and isinstance(content, list):
            # 真实 transcript 里 user content 也可能是 list(如
            # [{"type":"tool_result",...}] 或 [{"type":"text",...}]);
            # 与 assistant 对齐:只取 text 块,其余(tool_result 等)丢弃。
            parts = [blk.get("text", "") for blk in content
                     if isinstance(blk, dict) and blk.get("type") == "text"]
            text = _strip_code("\n".join(p for p in parts if p))
            if text:
                out.append((role, text))
    return out


def _split_turn(prefix: str, text: str, max_chars: int) -> list[str]:
    """把 "<prefix><text>" 切成每段 <= max_chars 的若干段,优先在整行边界切;
    每段都带 prefix。单行本身超过预算时硬切(_strip_code 之后正常不会出现)。"""
    whole = prefix + text
    if len(whole) <= max_chars:
        return [whole]
    budget = max(1, max_chars - len(prefix))
    pieces: list[str] = []
    buf: list[str] = []
    size = 0
    for ln in text.split("\n"):
        while len(ln) > budget:                      # 极端:单行 > 预算
            if buf:
                pieces.append(prefix + "\n".join(buf)); buf, size = [], 0
            pieces.append(prefix + ln[:budget]); ln = ln[budget:]
        if buf and size + len(ln) > budget:
            pieces.append(prefix + "\n".join(buf)); buf, size = [], 0
        buf.append(ln); size += len(ln) + 1
    if buf:
        pieces.append(prefix + "\n".join(buf))
    return pieces


def chunk_dialogue(turns: list[tuple[str, str]], max_chars: int = MAX_CHARS) -> list[str]:
    """按 max_chars 分块。单个 turn 超过 max_chars 时先按行切成多段再装箱,
    保证每块长度 <= max_chars(此前单个长 turn 会整块漏过上限)。"""
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for role, text in turns:
        prefix = "User: " if role == "user" else "Assistant: "
        for line in _split_turn(prefix, text, max_chars):
            if buf and size + len(line) > max_chars:
                chunks.append("\n".join(buf)); buf, size = [], 0
            buf.append(line); size += len(line) + 1
    if buf:
        chunks.append("\n".join(buf))
    return chunks
