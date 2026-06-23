"""Unit tests for the in-loop server's HiToM chain-question parser."""
import importlib.util

_spec = importlib.util.spec_from_file_location("tomeval_server", "scripts/starling_tomeval_server.py")
srv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(srv)


def test_order3_chain_parsed():
    q = "Where does Aiden think Avery thinks Carter thinks the cabbage is?"
    assert srv._parse_chain_question(q) == (["Aiden", "Avery", "Carter"], "cabbage")


def test_order4_chain_parsed():
    q = "Where does Amelia think Nathan thinks Jackson thinks Sophia thinks the tomato is?"
    assert srv._parse_chain_question(q) == (["Amelia", "Nathan", "Jackson", "Sophia"], "tomato")


def test_order1_really_think_not_a_chain():
    assert srv._parse_chain_question("Where does Isla really think the cabbage is?") is None


def test_first_order_simple_think_not_a_chain():
    assert srv._parse_chain_question("Where does Isla think the cabbage is?") is None


def test_non_hitom_question_ignored():
    assert srv._parse_chain_question("[Question] Which of the following best describes X? [Candidate Answers]") is None
