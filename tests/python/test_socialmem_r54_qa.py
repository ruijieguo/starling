"""R5.4 QA orchestration: sealed inputs, fresh requests, and paired inference."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/run_socialmem_r54_qa.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def driver():
    assert SCRIPT.is_file(), 'R5.4 QA runner is not implemented'
    return load(SCRIPT, 'r54_qa_test')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))


@pytest.fixture
def sealed(tmp_path, monkeypatch):
    d = driver()
    root, contexts, parent = tmp_path / 'root', tmp_path / 'contexts', tmp_path / 'parent'
    contexts.mkdir()
    core = root / 'build/python/starling/_core.fixture.so'
    core.parent.mkdir(parents=True)
    core.write_bytes(b'new core')
    core_hash = digest(core)
    monkeypatch.setattr(d, 'EXPECTED_CORE_SHA256', core_hash)
    monkeypatch.setattr(d, 'ROOT', root)
    frozen_core = contexts / 'frozen/python/starling/_core.fixture.so'
    frozen_core.parent.mkdir(parents=True)
    frozen_core.write_bytes(core.read_bytes())
    frozen_runner = contexts / 'frozen/scripts/run_socialmem_baseline.py'
    frozen_runner.parent.mkdir(parents=True)
    frozen_runner.write_text('# frozen runner fixture\n')
    current_runner = root / 'scripts/run_socialmem_baseline.py'
    current_runner.parent.mkdir(parents=True)
    current_runner.write_bytes(frozen_runner.read_bytes())
    frozen = {str(p.relative_to(contexts / 'frozen')): digest(p)
              for p in (frozen_core, frozen_runner)}
    production = 'src/retrieval/source_retriever.cpp'
    for p in (root / production, contexts / 'implementation' / production):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('// retrieval fixture\n')
    config = {'answer_model': 'qwen3.8-27b', 'answer_max_tokens': 512, 'judge_max_tokens': 64,
              'answer_enable_thinking': False, 'max_retries': 0, 'timeout_ms': 120000,
              'answer_endpoint': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
              'answer_key_env': 'DASHSCOPE_API_KEY', 'core_sha256': core_hash,
              'scoring': 'existing_ladder_mc_and_single_yes_no_local_protocol',
              'max_context_bytes': 8000, 'recall_mode': 'hybrid'}
    records, groups = [], [{'group_id': f'g{i}', 'records': []} for i in range(7)]
    rows = {arm: [] for arm in d.ablation.ARMS}
    db_hashes = {}
    for group in groups:
        db = parent / 'runs' / group['group_id'] / 'frozen.db'
        db.parent.mkdir(parents=True)
        db.write_bytes(group['group_id'].encode())
        db_hashes[group['group_id']] = digest(db)
    for i in range(57):
        holders = [f'person{j}' for j in range(7 if i < 3 else 6)]
        gold = [f't{i}-0', f't{i}-1'] if i < 47 else [f't{i}-0']
        record = {'item_id': f'q{i:02d}', 'question': 'Question?', 'answer': 'expected',
                  'answer_format': 'free_response', 'history': [{'speaker': h} for h in holders],
                  'source': {'network_id': f'n{i % 6}', 'evidence_anchors': [{'turn_id': t} for t in gold]}}
        records.append(record)
        group = groups[i % 7]
        group['records'].append(record)
        for arm, (strategy, mode, k) in d.ablation.ARMS.items():
            turns = [f't{i}-0'] if i < 51 else [f'miss{i}']
            if arm in ('source10', 'sidecar') and i < 16:
                turns.append(f't{i}-1')
            refs = [{'turn_id': t, 'engram_ref': t, 'clause_id': 'c0'} for t in turns]
            block = '\n'.join('[SOURCE] ' + t for t in turns)
            receipt = {'block': block, 'source_refs': refs, 'source_count': len(refs),
                       'statement_ids': [], 'statement_count': 0, 'context_bytes': len(block.encode()),
                       'source_context_bytes': len(block.encode()), 'statement_context_bytes': 0,
                       'receipts': [{'holder': h, 'degraded_paths': []} for h in holders] if mode == 'hybrid' else []}
            row = {'item_id': record['item_id'], 'group_id': group['group_id'], 'arm': arm,
                   'strategy': strategy, 'mode': mode, 'k': k, 'holders': holders,
                   'database_sha256': db_hashes[group['group_id']], 'core_sha256': core_hash,
                   'status': 'ok', 'terminal': True, 'recall': receipt,
                   'embedding_requests': len(holders) if mode == 'hybrid' else 0}
            rows[arm].append(row)
            write(contexts / arm / 'recalls' / (record['item_id'] + '.json'), row)
    for name, value in [('sample.json', records), ('groups.json', groups), ('scope-manifest.json', {})]:
        write(contexts / name, value)
        write(parent / name, value)
    (parent / 'corpus.jsonl').write_text('{}\n')
    write(contexts / 'config.json', config)
    write(parent / 'config.json', {**config, 'core_sha256': 'old-core'})
    identity = {'core_sha256': core_hash, 'config_sha256': digest(contexts / 'config.json'),
                'scope_manifest_sha256': digest(contexts / 'scope-manifest.json'),
                'corpus_sha256': digest(parent / 'corpus.jsonl'), 'frozen_files': frozen}
    write(contexts / 'identity.json', identity)
    plan = {'parent': str(parent), 'qa_candidate': 'source10', 'arms': d.ablation.ARMS,
            'embedding_request_limit': 690, 'answer_requests': 0, 'judge_requests': 0,
            'loaded_core': str(frozen_core), 'loaded_core_sha256': core_hash,
            'parent_input_sha256': {n: digest(parent / n) for n in ('sample.json', 'groups.json', 'corpus.jsonl')},
            'parent_provenance': {'database_sha256': db_hashes, 'config': {**config, 'core_sha256': 'old-core'}}}
    write(contexts / 'execution-plan.json', plan)
    comparison = d.ablation.compare_rows(records, rows)
    comparison['embedding_requests'] = 690
    write(contexts / 'comparison.json', comparison)
    for arm in rows:
        write(contexts / arm / 'summary.json', {'rows': 57, 'statuses': {'ok': 57},
                                               'embedding_requests': sum(r['embedding_requests'] for r in rows[arm])})
    d.ablation.r53.seal_output(contexts)
    return d, contexts, root


def mutate_json(path, change):
    value = json.loads(path.read_text())
    change(value)
    write(path, value)


def test_accepts_complete_four_arm_input(sealed):
    d, contexts, _ = sealed
    validated = d.validate_inputs(contexts)
    assert len(validated['records']) == 57
    assert validated['comparison']['anchors']['baseline'] == {'hit': 51, 'total': 104}
    assert validated['comparison']['anchors']['source10'] == {'hit': 67, 'total': 104}


@pytest.mark.parametrize('mutation', ['incomplete', 'hash', 'extra', 'missing'])
def test_seal_fails_before_output_or_adapters(sealed, mutation, tmp_path, monkeypatch):
    d, contexts, _ = sealed
    if mutation == 'incomplete':
        mutate_json(contexts / 'seal.json', lambda x: x.update(state='incomplete'))
    elif mutation == 'hash':
        (contexts / 'comparison.json').write_text('{}')
    elif mutation == 'extra':
        (contexts / 'unexpected.txt').write_text('extra')
    else:
        (contexts / 'baseline/summary.json').unlink()
    monkeypatch.setattr(d, '_frozen_modules', lambda *_: pytest.fail('loaded modules before validation'))
    out = tmp_path / 'out'
    with pytest.raises(ValueError, match='seal'):
        d.run(contexts, out)
    assert not out.exists()


@pytest.mark.parametrize('field,value', [('answer_model', 'other'), ('answer_max_tokens', 513),
    ('judge_max_tokens', 65), ('answer_enable_thinking', True), ('max_retries', 1),
    ('timeout_ms', 119999), ('answer_endpoint', 'https://other.invalid')])
def test_fixed_model_protocol_rejects_resealed_drift(sealed, field, value):
    d, contexts, _ = sealed
    mutate_json(contexts / 'config.json', lambda x: x.update({field: value}))
    mutate_json(contexts / 'identity.json', lambda x: x.update(config_sha256=digest(contexts / 'config.json')))
    d.ablation.r53.seal_output(contexts)
    with pytest.raises(ValueError, match='config|protocol'):
        d.validate_inputs(contexts)


@pytest.mark.parametrize('target', ['current_core', 'frozen_core', 'code', 'identity'])
def test_core_and_code_identity_drift_rejected(sealed, target):
    d, contexts, root = sealed
    if target == 'current_core':
        next((root / 'build/python/starling').glob('*.so')).write_bytes(b'old')
    elif target == 'frozen_core':
        next((contexts / 'frozen/python/starling').glob('*.so')).write_bytes(b'old')
    elif target == 'code':
        (root / 'src/retrieval/source_retriever.cpp').write_text('// drift')
    else:
        mutate_json(contexts / 'identity.json', lambda x: x.update(core_sha256='old'))
    d.ablation.r53.seal_output(contexts)
    with pytest.raises(ValueError, match='core|frozen|code|identity'):
        d.validate_inputs(contexts)


@pytest.mark.parametrize('mutation', ['duplicate', 'missing', 'holders', 'receipts', 'requests',
                                     'terminal', 'strategy', 'statement', 'candidate'])
def test_manifest_health_and_candidate_fail_closed(sealed, mutation):
    d, contexts, _ = sealed
    path = contexts / 'baseline/recalls/q00.json'
    if mutation == 'duplicate':
        (path.parent / 'duplicate.json').write_bytes(path.read_bytes())
    elif mutation == 'missing':
        path.unlink()
    elif mutation == 'candidate':
        mutate_json(contexts / 'execution-plan.json', lambda x: x.update(qa_candidate='sidecar'))
    else:
        if mutation == 'statement':
            path = contexts / 'source10/recalls/q00.json'
        def change(row):
            if mutation == 'holders': row['holders'][0] = 'intruder'
            if mutation == 'receipts': row['recall']['receipts'].pop()
            if mutation == 'requests': row['embedding_requests'] = 0
            if mutation == 'terminal': row['terminal'] = False
            if mutation == 'strategy': row['strategy'] = 'evidence_profile_v7'
            if mutation == 'statement':
                row['recall']['statement_ids'] = ['forbidden']
                row['recall']['statement_count'] = 1
        mutate_json(path, change)
    d.ablation.r53.seal_output(contexts)
    with pytest.raises(ValueError):
        d.validate_inputs(contexts)


def test_refuses_existing_output_before_input_load(tmp_path):
    d = driver()
    with pytest.raises(ValueError, match='already exists'):
        d.run(tmp_path / 'missing', tmp_path)


class Response:
    ok, error, raw_completion = True, '', ''
    def __init__(self, text): self.raw_xml = text
    def to_json(self):
        return json.dumps({'attempt_count': 1, 'total_tokens': 3, 'http_attempts': [{'status': 200}]})


def offline_modules():
    runner = load(ROOT / 'scripts/run_socialmem_baseline.py', 'baseline_qa_fixture')
    ladder = SimpleNamespace(_ladder_prompt_free=lambda r, lines: r['question'] + '\n' + '\n'.join(lines))
    core = SimpleNamespace(grounded_memory_answer_prompt=lambda question, recall: question + '\n' + json.loads(recall)['block'])
    audit = SimpleNamespace(_judge_prompt=lambda q, gold, answer: f'{q}|{gold}|{answer}',
                            _parse_judge_verdict=lambda text: text.strip().lower() == 'yes')
    return runner, (core, None, audit, ladder, None, None)


def test_prompt_binding_rejects_changed_prompt_and_context_before_request(tmp_path):
    d = driver()
    runner, modules = offline_modules()
    record = {'item_id': 'q', 'question': 'Q?', 'answer': 'a', 'answer_format': 'free_response'}
    task = d.build_task('baseline', 'legacy', record, {'block': '[SOURCE] x'}, runner, {}, modules)
    assert task['prompt_sha256'] == hashlib.sha256(b'Q?\n[SOURCE] x').hexdigest()
    assert task['context_sha256'] == hashlib.sha256(b'[SOURCE] x').hexdigest()
    ledger = runner.BudgetLedger(tmp_path / 'ledger.sqlite', 500)
    for key in ('prompt', 'context_sha256'):
        altered = copy.deepcopy(task)
        altered[key] += 'tampered'
        with pytest.raises(ValueError, match='binding'):
            d.run_task(altered, tmp_path / 'answers', runner, modules, ledger, None)
    assert ledger.snapshot()['committed'] == 0


def test_exception_charges_full_bound_and_saves_terminal(tmp_path):
    d = driver()
    runner, modules = offline_modules()
    class Broken:
        def extract(self, *_): raise RuntimeError('unknown transport outcome')
    record = {'item_id': 'q', 'question': 'Q?', 'answer': 'a', 'answer_format': 'free_response'}
    task = d.build_task('source10', 'legacy', record, {'block': '[SOURCE] x'}, runner, {}, modules)
    ledger = runner.BudgetLedger(tmp_path / 'ledger.sqlite', 500)
    row = d.run_task(task, tmp_path / 'out', runner, modules, ledger, (None, None, Broken(), Broken()))
    assert row['terminal'] and row['status'] == 'technical_failure' and not row['correct']
    assert row['charged_requests'] == 2
    assert ledger.snapshot()['charged_upper'] == 2
    assert len(list((tmp_path / 'out').rglob('*.json'))) == 1


def test_pair_direction_four_cells_and_common_normal_gate():
    d = driver()
    records = [{'item_id': f'q{i}', 'source': {'network_id': f'n{i % 2}'}} for i in range(8)]
    left = [{'item_id': r['item_id'], 'status': 'ok', 'correct': False, 'terminal': True} for r in records]
    right = [{**r, 'correct': True} for r in left]
    right[-1].update(status='technical_failure', correct=False)
    result = d.compare_scores(records, left, right, repetitions=200)
    assert result['net_source10_minus_baseline'] == 7
    assert result['common_normal_questions'] == 7
    assert result['four_cells'] == {'both_correct': 0, 'baseline_only': 0, 'source10_only': 7, 'both_wrong': 1}
    assert result['common_normal_bootstrap']['ci95_percent'] == [100.0, 100.0]
    assert result['eligible_for_expanded_development'] is True
    reversed_result = d.compare_scores(records, right, left, repetitions=200)
    assert reversed_result['net_source10_minus_baseline'] == -7
    assert reversed_result['eligible_for_expanded_development'] is False
    assert 'v7' not in json.dumps(result)


def test_same_prompt_answer_judge_flip_audit():
    d = driver()
    rows = [{'item_id': 'q', 'arm': arm, 'policy': 'legacy', 'prompt_sha256': 'p',
             'judge_prompt': 'same', 'answer': {'raw_xml': 'same answer'},
             'judge': {'raw_xml': verdict}, 'status': 'ok', 'correct': correct}
            for arm, verdict, correct in [('baseline', 'yes', True), ('source10', 'no', False)]]
    audit = d.judge_flip_audit(rows)
    assert audit['identical_prompt_answer_groups'] == 1
    assert audit['judge_flip_groups'] == 1


def test_fresh_228_terminals_under_500_and_frozen_output(sealed, tmp_path, monkeypatch):
    d, contexts, _ = sealed
    runner, modules = offline_modules()
    class Offline:
        def __init__(self, text): self.text = text
        def extract(self, *_): return Response(self.text)
    monkeypatch.setattr(d, '_frozen_modules', lambda c, config, identity: (runner, modules))
    monkeypatch.setattr(runner, '_make_native_adapters', lambda *_: (None, None, Offline('answer'), Offline('yes')))
    monkeypatch.setattr(d, 'BOOTSTRAP_REPETITIONS', 200)
    out = tmp_path / 'out'
    result = d.run(contexts, out, workers=4)
    assert result['state'] == 'complete'
    assert result['terminal_count'] == 228
    assert result['ledger']['committed'] == 456
    assert result['ledger']['reserved'] == 0
    assert result['ledger']['remaining'] == 44
    rows = [json.loads(p.read_text()) for p in out.glob('answers/*/*/*.json')]
    assert len(rows) == 228 and all(r['terminal'] for r in rows)
    assert {r['arm'] for r in rows} == {'baseline', 'source10'}
    assert {r['policy'] for r in rows} == {'legacy', 'grounded_memory_v1'}
    assert all(r['prompt_sha256'] and r['context_sha256'] for r in rows)
    assert (out / 'implementation/scripts/run_socialmem_r54_qa.py').is_file()
    assert (out / 'implementation/scripts/run_socialmem_r52_v6_v7_qa.py').is_file()
    assert (out / 'frozen/scripts/run_socialmem_baseline.py').read_bytes() == (contexts / 'frozen/scripts/run_socialmem_baseline.py').read_bytes()
    archived_core = next((out / 'frozen/python/starling').glob('_core*.so'))
    assert digest(archived_core) == d.EXPECTED_CORE_SHA256
    assert json.loads((out / 'input-seal.json').read_text()) == json.loads((contexts / 'seal.json').read_text())
    d.ablation.r53.verify_seal(out)
    archived_core.write_bytes(b'changed archived dependency')
    with pytest.raises(ValueError, match='seal hash'):
        d.verify_seal(out)
