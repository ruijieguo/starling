"""R6.2 评测门禁及共享原生检索/QA合同。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'scripts/run_socialmem_r62_evaluate.py'


def driver():
    assert SCRIPT.is_file(), 'R6.2 evaluator required'
    spec=importlib.util.spec_from_file_location('r62_evaluation_test', SCRIPT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.engine


def test_evaluator_binds_candidate_recovery_builder():
    m=driver()
    assert m.CORE_SHA256==m.builder.CORE_SHA256
    assert m.builder.ARM=='r62_embedding_health_revalidated_development'
    assert m.SEAL_SCHEMA=='r62-evaluation-seal-v1'


_spec=importlib.util.spec_from_file_location('r62_gate_tests',ROOT/'tests/python/test_socialmem_r61_evaluate.py')
_gates=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_gates)
_gates.driver=driver
test_build_gate_uses_actual_new_profile_before_reaching_provider=_gates.test_build_gate_uses_actual_new_profile_before_reaching_provider

_spec=importlib.util.spec_from_file_location('r62_shared_eval',ROOT/'tests/python/test_socialmem_r59_evaluate.py')
_shared=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_shared)
_shared.driver=driver;_shared.SCRIPT=SCRIPT
_shared.FIXTURE_BUILD=ROOT/'build/socialmem_20260926_r62_work/evaluator-native-fixture/build'
native=_shared.native
synthetic_contexts=_shared.synthetic_contexts
localhost_stages=_shared.localhost_stages
for _name,_test in vars(_shared).items():
    if _name.startswith('test_') and _name!='test_invalid_build_identity_is_rejected_before_provider':
        globals()['test_shared_'+_name[5:]]=_test
