#!/usr/bin/env python3
"""WP0:SocialMemBench 官方评测口径的纯函数实现(本文件不发网络)。

来源:匿名镜像 https://anonymous.4open.science/r/SocialMemBench 的评测源码快照(2026-10-10 取回)。
官方数据集与评测代码按 CC BY 4.0 发布(镜像 LICENSE;论文脚注称流水线为 MIT)。本文件不含官方
提示文本,运行时按路径与摘要读取;解析与阈值语义是对官方 evaluator / answerer 行为的重新实现,
不是拷贝。与官方的差异:
  - 裁判请求失败时抛出,不像官方那样吞成 0 分(梯子对抛错的题写 error 行并排除出统计);
  - 裁判回复解析暴露状态 ok / regex_fallback / parse_failed,不静默;
  - 官方评测器的循环有选择题与开放题顺序错位的缺陷,这里逐题独立打分。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

CORRECT_THRESHOLD = 0.7        # 官方 evaluator:分数大于等于 0.7 记「正确」(附带计数,头条指标是均分)
JUDGE_MAX_TOKENS = 400
_LETTERS = "ABCD"


def load_official_prompts(path, expected_sha256: str | None = None) -> dict:
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(f"official prompts sha256 mismatch: expected {expected_sha256}, got {digest}")
    import yaml   # 惰性导入:只有真正读提示文件时才需要
    return yaml.safe_load(raw)


def _option_lines(options: list) -> str:
    if len(options) > len(_LETTERS):
        raise ValueError(f"官方口径只支持至多 {len(_LETTERS)} 个选项,实得 {len(options)}")
    return "\n".join(f"{_LETTERS[i]}. {opt}" for i, opt in enumerate(options))


def official_answer_prompt(prompts: dict, record: dict, recalled: list[str], *,
                           full_context: bool = False) -> str:
    """官方作答提示。记忆系统条件用 `answer` 模板,全上下文条件用 `llm_answer` 模板。"""
    is_mc = record.get("answer_format", "multiple_choice") == "multiple_choice"
    section = "llm_answer" if full_context else "answer"
    template = prompts[section]["multiple_choice" if is_mc else "open_ended"]
    if full_context:
        context = "\n".join(recalled)
    elif recalled:
        context = "\n".join(f"- {line}" for line in recalled)
    else:
        context = "[No memories retrieved]"
    fields = {"context": context, "question": record["question"]}
    if is_mc:
        fields["options"] = _option_lines(record["options"])
    return template.format(**fields)


def _parse_time(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _clock(moment: datetime | None) -> str:
    if moment is None:
        return "12:00am"
    return f"{moment.hour % 12 or 12}:{moment.minute:02d}{'am' if moment.hour < 12 else 'pm'}"


def official_full_context(history: list[dict]) -> str:
    """官方全上下文基线的写法:`--- Session N, 日期 ---` 头加 `[Session N, 2:47pm] 说话人: 正文`。
    日期取该会话首轮的日期,与官方按会话日期的写法不逐字相同。"""
    order: list[int] = []
    sessions: dict[int, list[dict]] = {}
    for turn in history:
        idx = int(turn.get("session_index") or 1)
        if idx not in sessions:
            sessions[idx] = []
            order.append(idx)
        sessions[idx].append(turn)
    lines: list[str] = []
    for idx in order:
        turns = sessions[idx]
        first = _parse_time(turns[0].get("observed_at"))
        date = first.date().isoformat() if first else f"session-{idx:02d}"
        lines.append(f"--- Session {idx}, {date} ---")
        lines.append("")
        for turn in turns:
            clock = _clock(_parse_time(turn.get("observed_at")))
            lines.append(f"[Session {idx}, {clock}] {turn.get('speaker')}: {turn.get('text')}")
        lines.append("")
    return "\n".join(lines)


def parse_official_mc(response: str) -> str:
    """移植官方 evaluator 的字母解析,包括句首冠词 A 先命中的已知怪癖(不修)。"""
    text = response.strip().upper()
    if not text:
        return ""
    if len(text) == 1 and text in _LETTERS:
        return text
    match = re.search(r"\b([ABCD])[.):,\s]", text)
    if match:
        return match.group(1)
    match = re.search(r"(?:answer|choice|option|select)[:\s]+([ABCD])\b", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    if text[0] in _LETTERS and (len(text) == 1 or not text[1].isalpha()):
        return text[0]
    if text[-1] in _LETTERS and (len(text) == 1 or not text[-2].isalpha()):
        return text[-1]
    return text


def official_mc_correct(response: str, record: dict) -> bool:
    generated = response.strip()
    if generated.startswith("[") and generated.endswith("]"):    # 官方:方括号包裹视为失败
        return False
    return parse_official_mc(generated) == _LETTERS[int(record["answer"])]


def official_judge_prompts(prompts: dict, question: str, golden: str, generated: str) -> tuple[str, str]:
    judge = prompts["llm_judge"]
    user = judge["user_prompt"].format(question=question, golden_answer=golden, generated_answer=generated)
    return judge["system_prompt"], user


def _clamp(score: float) -> float:
    if not math.isfinite(score):
        raise ValueError("non-finite score")
    return max(0.0, min(1.0, score))


def parse_official_judge(content: str) -> tuple[float, str, str]:
    """返回 (分数, 理由, 状态)。状态 ok=整段 JSON 可解析;regex_fallback=靠正则取到数字;
    parse_failed=什么都没取到(分数 0)。"""
    try:
        if "```json" in content:
            start = content.find("```json") + 7
            body = content[start:content.find("```", start)].strip()
        elif "```" in content:
            start = content.find("```") + 3
            body = content[start:content.find("```", start)].strip()
        elif "{" in content and "}" in content:
            body = content[content.find("{"):content.rfind("}") + 1]
        else:
            body = content
        result = json.loads(body)
        return _clamp(float(result.get("score", 0.0))), str(result.get("rationale", "")), "ok"
    except (json.JSONDecodeError, KeyError, ValueError, TypeError, AttributeError):
        match = re.search(r"\b(0\.\d+|1\.0|0|1)\b", content)
        if match:
            return _clamp(float(match.group(1))), "parsed from text", "regex_fallback"
        return 0.0, "parse failed", "parse_failed"


def official_is_correct(score: float) -> bool:
    return score >= CORRECT_THRESHOLD


def make_official_judge_fn(chat: Callable[..., str], prompts: dict, *,
                           max_tokens: int = JUDGE_MAX_TOKENS) -> Callable[[str, str, str, str], dict]:
    """返回 (question, reference, candidate, backbone) -> {score, rationale, raw, status}。
    请求失败直接抛出,不吞成 0 分。"""
    def judge(question: str, reference: str, candidate: str, backbone: str) -> dict[str, Any]:
        system, user = official_judge_prompts(prompts, question, reference, candidate)
        raw = chat(user, backbone, max_tokens, system=system, enable_thinking=False)
        score, rationale, status = parse_official_judge(raw)
        return {"score": score, "rationale": rationale, "raw": raw, "status": status}

    return judge
