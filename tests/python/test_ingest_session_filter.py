import json

from starling.dashboard.ingest_filter import clean_turns, chunk_dialogue


def _lines(*objs):
    return [json.dumps(o) for o in objs]


def test_clean_keeps_dialogue_drops_thinking_tools_tool_results():
    lines = _lines(
        {"type": "user", "message": {"role": "user", "content": "Bob owns auth"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "secret reasoning"},
            {"type": "text", "text": "Got it, Bob owns auth."},
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls -la"}}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "file1 file2"}]}},
    )
    turns = clean_turns(lines)
    assert turns == [("user", "Bob owns auth"), ("assistant", "Got it, Bob owns auth.")]
    joined = "\n".join(t for _, t in turns)
    assert "secret reasoning" not in joined and "ls -la" not in joined and "file1" not in joined


def test_clean_strips_code_fences_and_long_lines():
    # codex 修正:spec 说去代码围栏 + 超长行,过滤必须真去(否则 commit 撒谎)。
    text = ("Here is the fix:\n```python\ndef f():\n    return 42\n```\nDone.\n"
            + "X" * 5000)   # 超长单行(命令 stdout 残留)
    lines = _lines({"type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}})
    turns = clean_turns(lines)
    kept = turns[0][1]
    assert "Here is the fix:" in kept and "Done." in kept
    assert "def f():" not in kept and "return 42" not in kept   # 围栏内容去掉
    assert "X" * 5000 not in kept                                # 超长行去掉


def test_chunk_splits_long_dialogue():
    turns = [("user", "x" * 5000), ("assistant", "y" * 5000)]
    chunks = chunk_dialogue(turns, max_chars=8000)
    assert len(chunks) >= 2 and all(len(c) <= 8000 + 200 for c in chunks)


def test_malformed_lines_skipped_not_raised():
    lines = ["{not json", json.dumps(
        {"type": "user", "message": {"role": "user", "content": "ok"}})]
    assert clean_turns(lines) == [("user", "ok")]


def test_user_list_tool_result_dropped():
    # 真实 transcript 里 89% 的 user 轮是 list:tool_result(工具输出噪声)——该丢。
    lines = _lines({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "cmd output"}]}})
    assert clean_turns(lines) == []


def test_user_list_text_kept():
    # 真实 transcript 里 1.5% 的 user 轮是 list:text(真用户文本)——之前被误丢,现在该留。
    lines = _lines({"type": "user", "message": {"role": "user", "content": [
        {"type": "text", "text": "Continue from where you left off."}]}})
    assert clean_turns(lines) == [("user", "Continue from where you left off.")]


def test_user_str_still_kept():
    lines = _lines({"type": "user", "message": {"role": "user", "content": "Bob owns auth"}})
    assert clean_turns(lines) == [("user", "Bob owns auth")]


def test_unclosed_fence():
    # 未闭合的 ``` 开头:_FENCE 非贪婪匹配要求成对反引号,单个不闭合不匹配 —— 原样穿过,不抛异常。
    text = "Before fence\n```python\ndef f():\n    return 1"
    lines = _lines({"type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}})
    assert clean_turns(lines) == [("assistant", text)]


def test_line_exactly_at_threshold():
    # _LONG_LINE=400 用 <= 语义:恰好 400 char 的行保留,401 char 的行剔除。
    at_400 = "a" * 400
    at_401 = "b" * 401
    text = f"{at_400}\n{at_401}"
    lines = _lines({"type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}})
    kept = clean_turns(lines)[0][1]
    assert at_400 in kept
    assert at_401 not in kept
