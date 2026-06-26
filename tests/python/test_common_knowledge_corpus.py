"""Gold self-consistency test for the CK synthetic eval corpus generator.

TDD step 1: this test must FAIL (ModuleNotFoundError) before the generator
is implemented, then pass once it is.
"""


def test_ck_gold_matches_construction():
    from scripts.build_common_knowledge_corpus import generate_item  # noqa: PLC0415

    # public construction -> gold "yes"
    pub = generate_item(seed=1, public=True)
    assert pub["answer"].lower().startswith("yes"), (
        f"Expected answer starting with 'yes' for public=True, got {pub['answer']!r}"
    )
    assert "common knowledge among" in pub["question"].lower(), (
        f"Expected 'common knowledge among' in question, got {pub['question']!r}"
    )

    # private construction -> gold "no"
    priv = generate_item(seed=1, public=False)
    assert priv["answer"].lower().startswith("no"), (
        f"Expected answer starting with 'no' for public=False, got {priv['answer']!r}"
    )
    assert "common knowledge among" in priv["question"].lower(), (
        f"Expected 'common knowledge among' in question for private case, got {priv['question']!r}"
    )
