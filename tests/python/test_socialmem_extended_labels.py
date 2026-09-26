"""独立标签统计：显式片段覆盖，非生产语义判断。"""
import importlib
import importlib.util
import hashlib
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))


def module():
    assert importlib.util.find_spec('eval_socialmem_extended'), 'extended-label evaluator missing'
    return importlib.import_module('eval_socialmem_extended')


def target():
    return {'actor':'Mina','predicate':'feels','polarity':'POS','modality':'BELIEVES',
            'object_all':[['sad'],['team']], 'topic_any':['team'], 'time_text':'',
            'event_time':None,'scope_options':[['ASSERTED']], 'speech_act':'state'}


def candidate():
    return {'subject_id':'Mina','predicate':'feels','polarity':'pos','modality':'BELIEVES',
            'object_value':'sad about leaving the team','semantic_claim_json':json.dumps({
                'topic':'team','scope_markers':['ASSERTED'],'time_text':'','event_time':None})}


def test_one_prediction_cannot_cover_two_targets():
    score = module().score_case([target(), target()], [candidate()], native_ok=True)
    assert score['targets'] == 2
    assert score['object_covered'] == score['joint_covered'] == 1
    assert score['valid_targets'] == 2


def test_technical_failure_stays_in_strict_denominator():
    score = module().score_case([target()], [candidate()], native_ok=False)
    assert score['targets'] == 1 and score['joint_covered'] == 0
    assert score['valid_targets'] == 0 and score['technical_failed_targets'] == 1


def test_topic_and_scope_are_independent_from_object_coverage():
    row = candidate(); row['semantic_claim_json'] = json.dumps({
        'topic':None,'scope_markers':['REPORTED'],'event_time':None,'time_text':''})
    score = module().score_case([target()], [row], native_ok=True)
    assert score['object_covered'] == 1 and score['joint_covered'] == 0
    assert score['topic_covered'] == score['scope_covered'] == 0
    assert score['time_covered'] == 1


def test_source_hash_mismatch_blocks_extended_label_evaluation():
    labels = {'schema_version':1,'cases':[{'id':'x','source_sha256':'incorrect','targets':[target()]}]}
    with pytest.raises(ValueError, match='source'):
        module().summarize(labels, [{'id':'x','passage':'Mina: sad about team'}], [])


def test_maximum_matching_recovers_flexible_prediction_for_second_target():
    team = target()
    work = {**target(), 'object_all': [['sad'], ['work']], 'topic_any': ['team']}
    flexible = {**candidate(), 'object_value': 'sad about team and work'}
    team_only = candidate()
    score = module().score_case([team, work], [flexible, team_only], native_ok=True)
    assert score['object_covered'] == score['joint_covered'] == 2
    assert score['unmatched_predictions'] == 0


def test_identity_fields_and_declared_alternatives_are_required():
    synonym = {**target(), 'object_all': [['sad', 'unhappy'], ['team']]}
    rows = [{**candidate(), 'subject_id': 'Other'},
            {**candidate(), 'polarity': 'neg'},
            {**candidate(), 'modality': 'INTENDS'},
            {**candidate(), 'object_value': 'unhappy about team'}]
    score = module().score_case([synonym], rows, native_ok=True)
    assert score['joint_covered'] == 1
    assert score['unmatched_predictions'] == 3


def test_missing_evidence_does_not_receive_empty_time_credit():
    row = {**candidate(), 'semantic_claim_json': ''}
    score = module().score_case([target()], [row], native_ok=True)
    assert score['object_covered'] == 1
    assert score['topic_covered'] == score['scope_covered'] == score['time_covered'] == 0


def test_exact_topic_and_time_fields_do_not_accept_partial_or_inferred_values():
    row = candidate()
    row['semantic_claim_json'] = json.dumps({
        'topic': 'team outing', 'scope_markers': ['ASSERTED'],
        'time_text': '', 'event_time': '2025-05-05T11:04:00'})
    score = module().score_case([target()], [row], native_ok=True)
    assert score['object_covered'] == score['scope_covered'] == 1
    assert score['topic_covered'] == score['time_covered'] == score['joint_covered'] == 0


def fixtures():
    cases = [{'id': 'good', 'passage': 'Mina: sad about team'},
             {'id': 'failed', 'passage': 'Mina: sad about team again'},
             {'id': 'missing', 'passage': 'Mina: sad about team once more'},
             {'id': 'legacy', 'passage': 'Mina: I prefer tea'}]
    labels = {'schema_version': 1, 'metric': 'declared_text_and_evidence_coverage',
              'label_origin': 'source_only_authored_before_new_run', 'cases': [
                  {'id': c['id'], 'source_sha256': hashlib.sha256(c['passage'].encode()).hexdigest(),
                   'targets': [] if c['id'] == 'legacy' else [target()],
                   'coverage': 'legacy_channel_only' if c['id'] == 'legacy' else 'partial_supplemental_targets'}
                  for c in cases]}
    results = [{'id': c['id'], 'track': 'synthetic', 'rows': [candidate()],
                'after': [candidate(), candidate()], 'native_ok': True,
                'base_receipt': {'extraction_failed': c['id'] == 'failed'}}
               for c in cases if c['id'] != 'missing']
    return labels, cases, results


def test_summary_keeps_strict_denominator_and_filters_native_result_track():
    labels, cases, results = fixtures()
    results.append({'id': 'good', 'track': 'p1', 'rows': [candidate()]})
    score = module().summarize(labels, cases, results)
    assert score['targets'] == 3 and score['valid_targets'] == 1
    assert score['technical_failed_targets'] == 2
    assert score['joint_covered'] == score['predictions'] - score['unmatched_predictions'] == 1
    assert score['strict_rates']['joint'] == pytest.approx(1 / 3)
    assert score['valid_rates']['joint'] == 1
    assert score['cases'] == 4 and score['evaluated_cases'] == 3
    assert score['excluded_cases'] == 1 and score['missing_result_cases'] == 1
    assert score['excluded_case_predictions'] == 1
    assert score['speech_act']['state']['joint_covered'] == 1
    assert score['speech_act']['state']['targets'] == 3
    assert len(score['case_scores']) == 4


def test_legacy_prediction_does_not_count_as_unmatched_supplement():
    row = {**candidate(), 'predicate': 'prefers'}
    score = module().score_case([target()], [candidate(), row], native_ok=True)
    assert score['predictions'] == 1 and score['excluded_predictions'] == 1
    assert score['unmatched_predictions'] == 0


def test_speech_act_groups_share_global_matching_without_double_counting():
    targets = [target(), {**target(), 'speech_act': 'reported_state'}]
    score = module().score_case(targets, [candidate()], native_ok=True)
    assert sum(group['joint_covered'] for group in score['speech_act'].values()) == 1
    assert sum(group['targets'] for group in score['speech_act'].values()) == 2


@pytest.mark.parametrize('mutation', ['duplicate_label', 'duplicate_source', 'duplicate_result',
                                    'missing_source', 'missing_label', 'unknown_result'])
def test_summary_rejects_ambiguous_or_incomplete_source_identity(mutation):
    labels, cases, results = fixtures()
    if mutation == 'duplicate_label':
        labels['cases'].append(labels['cases'][0])
    elif mutation == 'duplicate_source':
        cases.append(cases[0])
    elif mutation == 'duplicate_result':
        results.append(results[0])
    elif mutation == 'missing_source':
        cases.pop()
    elif mutation == 'missing_label':
        labels['cases'].pop()
    else:
        results.append({**results[0], 'id': 'unknown'})
    with pytest.raises(ValueError):
        module().summarize(labels, cases, results)


def test_frozen_corpus_has_fourteen_targets_and_four_explicit_exclusions():
    root = Path(__file__).resolve().parents[2]
    labels = json.loads((root / 'tests/data/eval_socialmem_extended_labels.json').read_text())
    cases = json.loads((root / 'tests/data/eval_socialmem_predicate_cases.json').read_text())
    score = module().summarize(labels, cases, [])
    assert score['targets'] == score['technical_failed_targets'] == 14
    assert score['excluded_cases'] == 4 and score['evaluated_cases'] == 12
    assert score['valid_rates']['joint'] is None
