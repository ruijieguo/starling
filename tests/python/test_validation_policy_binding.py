import starling


def test_validation_policy_fields():
    pol = starling._core.ValidationPolicy()
    assert pol.confidence_drop_floor == 0.30
    assert pol.weak_inference_floor == 0.50
    assert list(pol.extra_core_predicates) == []
    pol.extra_core_predicates = ["annotates", "cites"]
    pol.confidence_drop_floor = 0.15
    pol.weak_inference_floor = 0.70
    assert list(pol.extra_core_predicates) == ["annotates", "cites"]
    assert pol.confidence_drop_floor == 0.15
    assert pol.weak_inference_floor == 0.70
