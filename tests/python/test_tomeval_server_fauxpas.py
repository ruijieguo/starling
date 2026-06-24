"""Unit tests for the in-loop server's gated faux-pas injection helpers."""
import importlib.util

_spec = importlib.util.spec_from_file_location("tomeval_server", "scripts/starling_tomeval_server.py")
srv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(srv)


def test_classify_faux_pas():
    assert srv._wants_faux_pas("Does anyone say something inappropriate in this story?")
    assert srv._wants_faux_pas("Did someone commit a faux pas?")
    assert not srv._wants_faux_pas("Where does Anne think the ball is?")
    assert not srv._wants_faux_pas("What emotion does the friend feel?")


def test_format_faux_pas():
    class C:
        ignorant = "Bob"; theme = "ball"; state_dim = "location"
        stale_value = "table"; actual_value = "box"; who_knows = ["Alice", "Carol"]
    txt = srv._format_faux_pas([C()])
    assert "Bob" in txt and "table" in txt and "box" in txt and "Alice" in txt
