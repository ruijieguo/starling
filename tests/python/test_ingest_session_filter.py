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
        {"type": "user", "message": {"role": "user",
            "content": "<tool-result><content>file1 file2</content></tool-result>"}},
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
