"""独立中英来源工程用例；Fake 准入决定不代表真实模型质量。"""
import importlib
import json
from pathlib import Path
import sys

import pytest
from starling import _core

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
CASES = json.loads((ROOT / 'tests/data/eval_socialmem_relation_boundary_v2.json').read_text())['cases']


@pytest.mark.parametrize('source_case', CASES, ids=[c['id'] for c in CASES])
def test_relation_fixture_survives_native_admission_storage_and_replay(source_case, tmp_path):
    evaluation = importlib.import_module('eval_socialmem_claim_contract')
    verifier = importlib.import_module('verify_socialmem_claim_contract')
    case = {**source_case, 'track': 'fixed_controls'}
    llm = _core.FakeLLMAdapter()
    llm.set_default_response(json.dumps({'schema_version': 1, 'decisions': [
        {'index': 0, 'retain': case['expected_keep'], 'reason': case['reason']}]}))
    (tmp_path / 'databases').mkdir()
    result = evaluation.evaluate_case(_core, case, None, {'baseline': '{convo}'}, tmp_path, llm,
                                      output_mode='json_schema_strict')
    assert result['native_ok'], result['claim_receipt']
    assert len(result['rows']) == int(case['expected_keep'])
    if case['expected_keep']:
        row = result['rows'][0]
        assert row['object_value'] == case['candidate']['object']
        assert row['subject_id'] == case['candidate']['subject']
        assert row['polarity'].upper() == case['candidate']['polarity']
        evidence = json.loads(row['semantic_claim_json'])
        assert evidence['actor'] == case['candidate']['evidence']['actor']
        assert evidence['event_time'] is None
    verifier.check_case(_core, tmp_path, case, None, {'baseline': '{convo}'}, result)
