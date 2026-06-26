"""Unit tests for the in-loop server's CK (common-knowledge) question parser."""


def test_parse_ck_question():
    from scripts.starling_tomeval_server import _parse_ck_question
    g, t = _parse_ck_question("Is it common knowledge among Alice, Bob and Carol that the ball is in the box?")
    assert g == ["Alice", "Bob", "Carol"]
    assert t == "ball"
    assert _parse_ck_question("Where is the ball?") is None
