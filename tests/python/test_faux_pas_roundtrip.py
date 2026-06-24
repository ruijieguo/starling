"""Binding smoke test for detect_faux_pas / FauxPasCandidate (SP-B)."""


def test_faux_pas_bound():
    from starling import _core
    assert hasattr(_core, "detect_faux_pas")
    c = _core.FauxPasCandidate
    for f in ("ignorant", "unknown_fact", "who_knows"):
        assert hasattr(c, f)
    from starling.tom.primitives import detect_faux_pas  # noqa: F401
