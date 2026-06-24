import importlib.util
_spec = importlib.util.spec_from_file_location("srv", "scripts/starling_tomeval_server.py")
srv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(srv)

def test_answer_definitive_frame_no_reason_step():
    p = srv._build_answer_prompt("SYS", "USER", "FACTS")
    assert "FACTS" in p
    assert "reason step by step" not in p.lower()
    assert "do not re-derive" in p.lower() or "use them directly" in p.lower()

def test_answer_silent_when_no_memory():
    p = srv._build_answer_prompt("SYS", "USER", "")
    assert "FACTS" not in p
    assert "[" not in p  # no injected memory block

def test_thrash_guard():
    assert srv._thrashes(["cabbage", "cabbage", "hat", "hat", "cabbage"]) is True
    assert srv._thrashes(["basket", "basket", "box"]) is False
    assert srv._thrashes(["box"]) is False
    assert srv._thrashes([]) is False
