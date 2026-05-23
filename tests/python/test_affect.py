import pytest
from starling.schema.affect import AffectVector


def test_affect_zero_yields_minimum_salience():
    v = AffectVector(valence=0.0, arousal=0.0, dominance=0.0, novelty=0.0, stakes=0.0)
    # salience = 0.4 * 0.4 * 0.3 * 0.3 * 1.0 = 0.0144
    assert abs(v.salience() - 0.0144) < 1e-9


def test_affect_max_yields_unit_salience():
    v = AffectVector(valence=1.0, arousal=1.0, dominance=1.0, novelty=1.0, stakes=1.0)
    # salience = 1.0 * 1.0 * 1.0 * 1.0 * 1.0 = 1.0
    assert abs(v.salience() - 1.0) < 1e-9


def test_affect_negative_valence_uses_abs():
    pos = AffectVector(valence=0.5, arousal=0.5, dominance=0.0, novelty=0.5, stakes=0.5)
    neg = AffectVector(valence=-0.5, arousal=0.5, dominance=0.0, novelty=0.5, stakes=0.5)
    assert abs(pos.salience() - neg.salience()) < 1e-9


def test_affect_frozen():
    v = AffectVector(valence=0.0, arousal=0.0, dominance=0.0, novelty=0.0, stakes=0.0)
    with pytest.raises(Exception):
        v.valence = 0.5  # type: ignore[misc]
