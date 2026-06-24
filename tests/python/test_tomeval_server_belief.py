"""Unit tests for the in-loop server's gated belief/knowledge digest injection helpers."""
import importlib.util

_spec = importlib.util.spec_from_file_location("srv", "scripts/starling_tomeval_server.py")
srv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(srv)


def test_wants_belief_digest():
    assert srv._wants_belief_digest("Where does Xiaoming look for the cabbage?")
    assert srv._wants_belief_digest("What does Xiao Ming most likely do?")
    assert not srv._wants_belief_digest("What kind of emotion does the friend feel?")
