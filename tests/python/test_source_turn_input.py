"""原生来源话轮格式、存储和评测边界。"""
import copy
import importlib
import json
import sys
from pathlib import Path

import pytest
from starling import _core

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))


def render(turns):
    assert hasattr(_core, 'claim_source_turn_payload'), 'native SourceTurn renderer missing'
    return _core.claim_source_turn_payload(json.dumps(turns, ensure_ascii=False))


def test_renderer_preserves_time_utf8_and_escaped_turn_boundaries():
    text = '我担心发布。\nMina: said yes | "quoted"'
    turns = [{'speaker': 'Mina', 'text': text, 'observed_at': '2025-05-05T11:04:00', 'turn_id': 't1'}]
    payload = render(turns)
    assert len(payload.splitlines()) == 1
    units = json.loads(_core.claim_source_units(payload))
    assert len(units) == 1
    assert units[0]['utterance'] == text
    assert units[0]['observed_at'] == '2025-05-05T11:04:00'
    assert units[0]['byte_end'] == len(payload.encode())
    assert units[0]['turn_id'] == 't1'


@pytest.mark.parametrize('bad', [{'speaker': 'Mina', 'text': 'x', 'answer': 'SECRET'},
                               {'speaker': 'Mina', 'text': 'x', 'observed_at': '2025-02-30T10:00:00'},
                               {'speaker': 'Mina', 'text': 'x', 'turn_index': -1}])
def test_renderer_rejects_unknown_label_fields_and_invalid_metadata(bad):
    assert hasattr(_core, 'claim_source_turn_payload'), 'native SourceTurn renderer missing'
    with pytest.raises(RuntimeError):
        _core.claim_source_turn_payload(json.dumps([bad]))


def test_evaluation_maps_reviewed_history_without_touching_baseline_or_gold():
    evaluation = importlib.import_module('eval_socialmem_claim_contract')
    assert hasattr(evaluation, 'with_source_turns'), 'source-turn evaluation input mapping missing'
    history = [{'speaker': 'Mina', 'text': '我很担心发布。', 'observed_at': '2025-05-05T11:04:00',
                'turn_id': 't1', 'session_index': 1, 'message_index': 3},
               {'speaker': 'Other', 'text': 'other holder', 'observed_at': None,
                'turn_id': 't2', 'session_index': 1, 'message_index': 4}]
    inputs = {'records': [{'item_id': 'Q', 'history': history, 'answer': 'SECRET'}],
              'scoped': [{'id': 'M', 'item_id': 'Q', 'holder': 'Mina', 'passage': 'old'}],
              'p1': [{'id':'p1'}], 'base_calls': {'raw':'frozen'}}
    before = copy.deepcopy(inputs)
    result = evaluation.with_source_turns(_core, inputs)
    assert inputs == before
    assert result['base_calls'] == before['base_calls'] and result['p1'] == before['p1']
    units = json.loads(_core.claim_source_units(result['scoped'][0]['passage']))
    assert len(units) == 1 and units[0]['turn_id'] == 't1'
    assert units[0]['turn_index'] == 3
    assert units[0]['session_id'] is None
    assert 'SECRET' not in result['scoped'][0]['passage']
