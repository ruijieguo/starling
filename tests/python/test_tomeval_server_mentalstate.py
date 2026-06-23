"""Unit tests for the in-loop server's gated mental-state injection helpers."""
import importlib.util

_spec = importlib.util.spec_from_file_location("tomeval_server", "scripts/starling_tomeval_server.py")
srv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(srv)


def test_classify_targets_bdi_families():
    assert srv._wants_mental_state("What does Xiao Ming most likely do?")           # knowledge/intention
    assert srv._wants_mental_state("Where does Li Hua plan to spend the weekend?")  # desire/plan
    assert not srv._wants_mental_state("What emotion does the friend feel?")        # emotion -> gated off
    assert not srv._wants_mental_state("Where does Anne think the ball is?")        # belief -> chain/dump path


def test_format_mental_state_compact():
    class R:
        def __init__(s, subj, pred, obj): s.subject_id, s.predicate, s.object_value = subj, pred, obj
    class MS:
        beliefs=[R("ball","located_at","box")]; knowledge=[R("keys","knows","drawer")]
        desires=[R("weekend","prefers","outdoors")]; intentions=[]; commitments=[]; preferences=[]
    txt = srv._format_mental_state(MS())
    assert "drawer" in txt and "outdoors" in txt  # surfaces knowledge + desires (subject-keyed)
