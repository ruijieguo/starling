from starling import _core


def test_strict_perception_reconstruction_is_bound():
    assert hasattr(_core.PerceptionReconstructor, "reconstruct_strict")
