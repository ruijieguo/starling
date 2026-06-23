def test_mental_state_bound_and_callable():
    from starling import _core
    assert hasattr(_core, "mental_state_of")
    ms_cls = _core.MentalState
    for f in ("beliefs", "knowledge", "desires", "intentions", "commitments", "preferences"):
        assert hasattr(ms_cls, f)
    from starling.tom.primitives import mental_state_of  # wrapper exists
