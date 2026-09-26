#!/usr/bin/env python3
"""固定6题的来源消融入口；全部身份验证先于任何模型adapter构造。"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

ARMS = ('statements', 'sources', 'hybrid', 'full')
BUDGETS = {'statements':35, 'sources':11, 'hybrid':35, 'full':11}
GROUP = '135c86f3d282d1560e6fe9e7'
QUESTIONS = ['Q3_ph9s1c1','Q4_ph9s1c2','Q5_ph9s2c1','Q8_ph9s3c1','Q8_ph9s4c1','Q7_ph9s5c1']
HOLDERS = ['Anika','Diane','Luca','Raj']
ENDPOINT = 'https://dashscope.aliyuncs.com/compatible-mode/v1'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_plan(plan):
    expected = {'arms':list(ARMS), 'budgets':BUDGETS, 'group_id':GROUP,
                'question_ids':QUESTIONS, 'holders':HOLDERS, 'http_budget':92}
    for key, value in expected.items():
        if plan.get(key) != value:
            raise ValueError(f'comparison plan drift: {key}')


def verify_files(root, files):
    for name, expected in files.items():
        path = Path(root) / name
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f'comparison artifact hash mismatch: {name}')


def validate_answer_setting(plan, config):
    planned = plan.get('answer_enable_thinking')
    if (planned is not None and planned is not False) or config.get('answer_enable_thinking') is not planned:
        raise ValueError('comparison answer_enable_thinking differs from frozen experiment')


def verify_file_manifest(root, files):
    if not isinstance(files, dict):
        raise ValueError('comparison file manifest must be a mapping')
    required = {f'{arm}/{name}' for arm in ARMS for name in (
        'config.json', 'identity.json', 'corpus.jsonl', 'scope-manifest.json',
        f'runs/{GROUP}/scope.json', f'runs/{GROUP}/frozen.db')}
    missing = required - files.keys()
    if missing:
        raise ValueError(f'comparison file manifest missing: {sorted(missing)}')
    verify_files(root, {name: files[name] for name in required})
    for arm in ARMS:
        identity = json.loads((Path(root)/arm/'identity.json').read_text())
        frozen_files = identity['frozen_files']
        if not isinstance(frozen_files, dict) or 'scripts/run_socialmem_baseline.py' not in frozen_files:
            raise ValueError(f'comparison file manifest missing frozen runner: {arm}')
        for relative, expected in frozen_files.items():
            if not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
                raise ValueError(f'comparison file manifest invalid frozen path: {arm}/{relative}')
            name = f'{arm}/frozen/{relative}'
            if files.get(name) != expected:
                raise ValueError(f'comparison file manifest frozen identity mismatch: {name}')
    verify_files(root, files)


def check(work):
    work = Path(work).resolve()
    plan = json.loads((work/'execution-plan.json').read_text())
    validate_plan(plan)
    if sha256(Path(__file__)) != plan['driver_sha256']:
        raise ValueError('comparison driver hash mismatch')
    verify_file_manifest(work, plan['files'])
    prepared = {}
    for arm in ARMS:
        folder = work / arm
        cfg = json.loads((folder/'config.json').read_text())
        validate_answer_setting(plan, cfg)
        for role in ('extract','answer'):
            if cfg[role+'_endpoint'] != ENDPOINT or cfg[role+'_model'] != 'qwen3.8-27b':
                raise ValueError('provider or model differs from authorized comparison')
        for key, expected in {'embedding_endpoint':ENDPOINT,'embedding_model':'qwen3.7-text-embedding',
                'recall_mode':arm,'http_budget':BUDGETS[arm],'max_retries':0,'timeout_ms':120000,
                'k':10,'max_context_bytes':8000,'lifecycle':'sleep','retain_sources':True,
                'extract_enable_thinking':False,'core_sha256':plan['core_sha256']}.items():
            if cfg.get(key) != expected:
                raise ValueError(f'comparison config drift: {arm}/{key}')
        spec = importlib.util.spec_from_file_location('comparison_runner_'+arm,
            folder/'frozen/scripts/run_socialmem_baseline.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        fingerprint = runner._verify_identity(folder, cfg)
        groups = runner.prepare_groups(runner._read_jsonl(folder/'corpus.jsonl'))
        selected = [g for g in groups if g['group_id']==GROUP]
        if len(selected)!=1 or len(groups)!=49:
            raise ValueError('comparison group drift')
        group = selected[0]
        if ([r['item_id'] for r in group['records']]!=QUESTIONS or len(group['history'])!=50
                or runner.history_holders(group['history'])!=HOLDERS):
            raise ValueError('comparison source or question drift')
        scope = folder/'runs'/GROUP
        if runner.scope_state(scope,fingerprint)!='terminal':
            raise ValueError('frozen source ingestion is incomplete; no extraction permitted')
        if sha256(scope/'frozen.db')!=plan['snapshot_sha256']:
            raise ValueError('comparison snapshot hash mismatch')
        with sqlite3.connect('file:'+str(scope/'frozen.db')+'?mode=ro',uri=True) as conn:
            if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise ValueError('snapshot integrity failure')
            if conn.execute('SELECT COUNT(*) FROM statements').fetchone()[0]!=11:
                raise ValueError('frozen statement identity count changed')
            if conn.execute('SELECT COUNT(*) FROM statement_vectors').fetchone()[0]!=11:
                raise ValueError('frozen embedding count changed')
        if sum(runner.question_request_bound(r,cfg,scope/'frozen.db') for r in group['records'])!=BUDGETS[arm]:
            raise ValueError('request reservation drift')
        prepared[arm] = (runner, group)
    return prepared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('check','run'))
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--arm', choices=ARMS)
    args = parser.parse_args()
    prepared = check(args.work)
    if args.mode=='check':
        print(json.dumps({'verified':True,'arms':list(ARMS),'questions_per_arm':6,'http_limit':92,'requests':0}))
    else:
        if args.arm is None:
            parser.error('run requires one --arm in its own process')
        runner, group = prepared[args.arm]
        result = runner.run(args.work/args.arm,groups=[group],workers=1)
        print(json.dumps({'arm':args.arm, 'summary':result['groups'][0]['summary'], 'ledger':result['ledger']}))


if __name__=='__main__':
    main()
