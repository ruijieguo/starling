"""WP0:官方评测口径(scripts/eval_official_protocol.py)的纯逻辑测试。

官方提示、解析与阈值语义取自匿名镜像里的评测源码快照(当数据读,不执行)。
这里用内联的最小提示夹具,不依赖 yaml 与归档文件;依赖归档官方文件的用例标 historical_eval。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"
_ARCHIVE = _ROOT / "build" / "official_socialmembench"


def _load(name: str):
    path = _SCRIPTS / f"{name}.py"
    if not path.exists():
        pytest.fail(f"scripts/{name}.py 尚不存在(功能缺失)")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PROMPTS = {
    "answer": {
        "multiple_choice": "MC-PROMPT\n[MEMORIES]\n{context}\n[QUESTION]\n{question}\n[OPTIONS]\n{options}\n",
        "open_ended": "OE-PROMPT\n[MEMORIES]\n{context}\n[QUESTION]\n{question}\n",
    },
    "llm_answer": {
        "multiple_choice": "LLM-MC\n[CONVERSATION]\n{context}\n[QUESTION]\n{question}\n[OPTIONS]\n{options}\n",
        "open_ended": "LLM-OE\n[CONVERSATION]\n{context}\n[QUESTION]\n{question}\n",
    },
    "llm_judge": {
        "system_prompt": "SYS-JUDGE",
        "user_prompt": 'Q: {question}\nGOLD: {golden_answer}\nGEN: {generated_answer}\n'
                       'Output JSON only:\n{{"score": 0.0, "rationale": "x"}}',
    },
}

MC_REC = {"item_id": "q1", "query_type": "Q4", "question": "Who offered wine pairings?",
          "answer_format": "multiple_choice", "options": ["Trevor", "Mia", "Diego", "Beth"], "answer": 2}
OE_REC = {"item_id": "q2", "query_type": "Q5", "question": "What did Femi know?",
          "answer_format": "long_form", "options": [], "answer": "Femi knew X."}
HISTORY = [
    {"speaker": "Femi", "text": "Quick question", "observed_at": "2025-05-05T11:04:00", "session_index": 1},
    {"speaker": "Marcus", "text": "I'd want to know", "observed_at": "2025-05-05T14:47:00", "session_index": 1},
    {"speaker": "Claudette", "text": "Morning", "observed_at": "2025-05-12T00:05:00", "session_index": 2},
    {"speaker": "Femi", "text": "Noon", "observed_at": "2025-05-12T12:30:00", "session_index": 2},
]


# ---------------------------- 答题提示 ----------------------------

def test_mc_prompt_formats_letter_options_and_bulleted_context():
    mod = _load("eval_official_protocol")
    p = mod.official_answer_prompt(PROMPTS, MC_REC, ["Femi: hi", "Mia: yo"])
    assert p.startswith("MC-PROMPT")
    assert "A. Trevor\nB. Mia\nC. Diego\nD. Beth" in p
    assert "- Femi: hi\n- Mia: yo" in p
    assert "Who offered wine pairings?" in p


def test_open_prompt_marks_empty_context_like_the_official_adapters():
    mod = _load("eval_official_protocol")
    p = mod.official_answer_prompt(PROMPTS, OE_REC, [])
    assert p.startswith("OE-PROMPT")
    assert "[No memories retrieved]" in p
    assert "What did Femi know?" in p


def test_full_context_uses_the_llm_answer_template_without_bullets():
    mod = _load("eval_official_protocol")
    ctx = "--- Session 1, 2025-05-05 ---\n\n[Session 1, 11:04am] Femi: hi\n"
    p_open = mod.official_answer_prompt(PROMPTS, OE_REC, [ctx], full_context=True)
    p_mc = mod.official_answer_prompt(PROMPTS, MC_REC, [ctx], full_context=True)
    assert p_open.startswith("LLM-OE") and p_mc.startswith("LLM-MC")
    assert ctx in p_open and "- --- Session" not in p_open


# ---------------------------- 全上下文格式 ----------------------------

def test_official_full_context_groups_sessions_with_twelve_hour_clock():
    mod = _load("eval_official_protocol")
    assert mod.official_full_context(HISTORY) == (
        "--- Session 1, 2025-05-05 ---\n\n"
        "[Session 1, 11:04am] Femi: Quick question\n"
        "[Session 1, 2:47pm] Marcus: I'd want to know\n\n"
        "--- Session 2, 2025-05-12 ---\n\n"
        "[Session 2, 12:05am] Claudette: Morning\n"
        "[Session 2, 12:30pm] Femi: Noon\n")


def test_full_context_falls_back_when_time_or_date_is_missing():
    mod = _load("eval_official_protocol")
    ctx = mod.official_full_context([{"speaker": "X", "text": "y", "observed_at": None, "session_index": 1}])
    assert ctx == "--- Session 1, session-01 ---\n\n[Session 1, 12:00am] X: y\n"


# ---------------------------- 选择题字母 ----------------------------

@pytest.mark.parametrize("text,letter", [
    ("A", "A"),
    ("b.", "B"),
    ("Answer: D", "D"),
    ("The answer is C", "C"),
    ("A good answer would be B.", "A"),   # 官方解析的已知怪癖:句首冠词 A 先命中,这里照搬而不修
])
def test_parse_official_mc_matches_the_official_parser(text, letter):
    mod = _load("eval_official_protocol")
    assert mod.parse_official_mc(text) == letter


def test_parse_official_mc_returns_the_text_when_no_letter_is_found():
    mod = _load("eval_official_protocol")
    assert mod.parse_official_mc("") == ""
    assert mod.parse_official_mc("I don't know") == "I DON'T KNOW"


def test_official_mc_correct_compares_against_the_option_index_letter():
    mod = _load("eval_official_protocol")
    assert mod.official_mc_correct("C", MC_REC) is True        # answer=2 -> C
    assert mod.official_mc_correct("B", MC_REC) is False
    assert mod.official_mc_correct("[FAILED]", MC_REC) is False   # 官方:方括号包裹视为失败
    assert mod.official_mc_correct("2", MC_REC) is False          # 下标写法在官方口径下不计对


# ---------------------------- 分项裁判 ----------------------------

def test_official_judge_prompts_render_system_and_user_without_double_braces():
    mod = _load("eval_official_protocol")
    system, user = mod.official_judge_prompts(PROMPTS, "Q?", "gold", "gen")
    assert system == "SYS-JUDGE"
    assert "Q: Q?" in user and "GOLD: gold" in user and "GEN: gen" in user
    assert '{"score": 0.0, "rationale": "x"}' in user and "{{" not in user


@pytest.mark.parametrize("content,score,status", [
    ('{"score": 0.8, "rationale": "close"}', 0.8, "ok"),
    ('```json\n{"score": 1.0, "rationale": "ok"}\n```', 1.0, "ok"),
    ('Sure: {"score": 0.4, "rationale": "r"} thanks', 0.4, "ok"),
    ('{"score": 1.7, "rationale": "r"}', 1.0, "ok"),
    ('{"score": -2, "rationale": "r"}', 0.0, "ok"),
    ("I'd give it 0.7", 0.7, "regex_fallback"),
    ('{"score": 0.5, "rationale": "broken', 0.5, "regex_fallback"),   # 被截断的回复:靠正则兜底,状态必须暴露
    ("no idea", 0.0, "parse_failed"),
])
def test_parse_official_judge_scores_and_flags_how_it_got_them(content, score, status):
    mod = _load("eval_official_protocol")
    got_score, _rationale, got_status = mod.parse_official_judge(content)
    assert (got_score, got_status) == (score, status)


def test_correct_threshold_is_point_seven():
    mod = _load("eval_official_protocol")
    assert mod.CORRECT_THRESHOLD == 0.7
    assert mod.official_is_correct(0.7) is True
    assert mod.official_is_correct(0.69) is False


def test_official_judge_fn_sends_system_prompt_with_thinking_off_and_returns_an_audit_record():
    mod = _load("eval_official_protocol")
    calls = []

    def chat(prompt, backbone, max_tokens, system=None, enable_thinking=None):
        calls.append({"prompt": prompt, "backbone": backbone, "max_tokens": max_tokens,
                      "system": system, "enable_thinking": enable_thinking})
        return '{"score": 0.9, "rationale": "close"}'

    out = mod.make_official_judge_fn(chat, PROMPTS)("Q?", "gold", "gen", "qwen-x")
    assert out == {"score": 0.9, "rationale": "close",
                   "raw": '{"score": 0.9, "rationale": "close"}', "status": "ok"}
    c = calls[0]
    assert c["system"] == "SYS-JUDGE" and c["enable_thinking"] is False
    assert c["max_tokens"] == 400 and c["backbone"] == "qwen-x"
    assert "GOLD: gold" in c["prompt"] and "GEN: gen" in c["prompt"]


def test_official_judge_fn_propagates_transport_errors_instead_of_scoring_zero():
    mod = _load("eval_official_protocol")

    def chat(*args, **kwargs):
        raise RuntimeError("连续 4 次失败")

    with pytest.raises(RuntimeError, match="连续 4 次失败"):
        mod.make_official_judge_fn(chat, PROMPTS)("q", "g", "c", "m")


# ---------------------------- 提示文件加载 ----------------------------

def test_load_official_prompts_rejects_a_digest_mismatch(tmp_path):
    pytest.importorskip("yaml")
    mod = _load("eval_official_protocol")
    f = tmp_path / "prompts.yaml"
    f.write_text("answer:\n  multiple_choice: x\n", encoding="utf-8")
    digest = hashlib.sha256(f.read_bytes()).hexdigest()
    assert mod.load_official_prompts(f, expected_sha256=digest)["answer"]["multiple_choice"] == "x"
    with pytest.raises(ValueError, match="sha256"):
        mod.load_official_prompts(f, expected_sha256="0" * 64)


@pytest.mark.historical_eval(reason="需要本机归档的官方提示文件 build/official_socialmembench")
def test_archived_official_prompts_render_with_the_real_templates():
    pytest.importorskip("yaml")
    mod = _load("eval_official_protocol")
    prompts = mod.load_official_prompts(
        _ARCHIVE / "eval_config_prompts.yaml",
        expected_sha256="c27a6eb5cd8f9b91c4bde30d50a90a578ba5f90f2efffeee43e71992747deb4a")
    assert "WHO said what" in mod.official_answer_prompt(prompts, OE_REC, ["Femi: hi"])
    _system, user = mod.official_judge_prompts(prompts, "Q", "G", "C")
    assert '"score"' in user and "{{" not in user


# ---------------------------- 共享 chat 辅助函数 ----------------------------

class _FakeResp:
    def __init__(self, text):
        self._body = json.dumps({"choices": [{"message": {"content": text}}]}).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _capture_chat_requests(monkeypatch):
    import urllib.request
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp("ok")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9/v1")
    return seen


def test_chat_completion_default_payload_is_unchanged(monkeypatch):
    """防线:新增可选参数不得改变既有调用的请求体(梯子既有裁判与作答依赖它)。"""
    audit = _load("eval_judge_audit")
    seen = _capture_chat_requests(monkeypatch)
    assert audit._chat_completion("P", "m1", 8) == "ok"
    body = seen["body"]
    assert body["messages"] == [{"role": "user", "content": "P"}]
    assert "enable_thinking" not in body
    assert body["max_tokens"] == 8 and body["temperature"] == 0 and body["model"] == "m1"


def test_chat_completion_carries_system_prompt_and_thinking_switch(monkeypatch):
    audit = _load("eval_judge_audit")
    seen = _capture_chat_requests(monkeypatch)
    audit._chat_completion("P", "m1", 8, system="S", enable_thinking=False)
    body = seen["body"]
    assert body["messages"] == [{"role": "system", "content": "S"}, {"role": "user", "content": "P"}]
    assert body["enable_thinking"] is False
