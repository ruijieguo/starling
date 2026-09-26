#!/usr/bin/env python3
"""完整1031题来源模式入口；准备快照、冻结核验先于模型请求。"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ENDPOINT='https://dashscope.aliyuncs.com/compatible-mode/v1'
CORE_SHA='89f08596f37a1511b499a591b9612a204d4fef5b39e1e743d0548625f24db923'
CORPUS_SHA='ba9d11578f6ebdad5bf3a0e443cf44a0d002fd400e11b243890f3fcc06ec607c'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def validate_protocol(plan,config,groups):
    expected={'recall_mode':'sources','answer_enable_thinking':False,'retain_sources':True,
              'http_budget':1848,'k':10,'max_context_bytes':8000,'max_retries':0,'timeout_ms':120000,
              'query_time':'2026-12-08T00:00:00Z','answer_max_tokens':512,'judge_max_tokens':64,
              'answer_model':'qwen3.8-27b','extract_model':'qwen3.8-27b',
              'answer_endpoint':ENDPOINT,'extract_endpoint':ENDPOINT}
    for key,value in expected.items():
        if type(config.get(key)) is not type(value) or config[key]!=value:
            raise ValueError(f'full source configuration drift: {key}')
    if config.get('judge_enable_thinking') is not None:
        raise ValueError('judge settings changed')
    if (plan.get('questions'),plan.get('groups'),plan.get('http_budget'))!=(1031,49,1848):
        raise ValueError('full source plan drift')
    records=[r for g in groups for r in g['records']]
    if len(groups)!=49 or len(records)!=1031 or len({r['item_id'] for r in records})!=1031:
        raise ValueError('full source question set changed')
    if [g['group_id'] for g in groups]!=plan['scope_ids']:
        raise ValueError('full source scope set changed')
    if sum(1+int(r['answer_format']!='multiple_choice') for r in records)!=1848:
        raise ValueError('full source request bound changed')


def verify_manifest(work,plan):
    work=Path(work);files=plan.get('files',{})
    scopes=plan.get('scope_ids',[])
    if len(scopes)!=49 or len(set(scopes))!=49:
        raise ValueError('full source scope manifest incomplete')
    required={'identity.json','config.json','corpus.jsonl','scope-manifest.json','network-split.json'}
    failed=set(plan.get('failed_scopes',[]))
    if not failed.issubset(scopes):raise ValueError('unknown failed scope')
    required.update(f'runs/{g}/{name}' for g in scopes for name in (
        ['scope.failure.json'] if g in failed else ['scope.json','frozen.db']))
    if not required.issubset(files):raise ValueError('full source archive manifest incomplete')
    def verify(names):
        for name in names:
            if Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('invalid full source archive path')
            if not (work/name).is_file() or sha(work/name)!=files[name]:
                raise ValueError(f'full source artifact hash mismatch: {name}')
    verify(required)
    identity=json.loads((work/'identity.json').read_text())
    frozen=identity['frozen_files']
    if 'scripts/run_socialmem_baseline.py' not in frozen:
        raise ValueError('full source frozen runner not registered')
    for name,expected in frozen.items():
        if files.get('frozen/'+name)!=expected:raise ValueError('full source frozen identity incomplete')
    verify(files)


def verify_scope_states(work,groups,runner,fingerprint,plan):
    for group in groups:
        folder=Path(work)/'runs'/group['group_id']
        if group['group_id'] in plan.get('failed_scopes',[]):
            failure=json.loads((folder/'scope.failure.json').read_text())
            if failure.get('fingerprint')!=fingerprint or not failure.get('error'):
                raise ValueError('invalid source failure receipt')
            states=runner.question_states(folder/'questions',[r['item_id'] for r in group['records']],fingerprint)
            if any(state!='terminal' for state in states.values()):
                raise ValueError('source failure questions must be terminal before execution')
            for record in group['records']:
                relative=f"runs/{group['group_id']}/questions/{runner._stable_id(str(record['item_id']))}.json"
                if relative not in plan.get('files',{}):
                    raise ValueError('source failure question missing from archive manifest')
                result=json.loads((Path(work)/relative).read_text())
                if result.get('status')!='ingestion_failure' or result.get('correct') is not False or result.get('terminal') is not True:
                    raise ValueError('source failure question has invalid terminal result')
        elif runner.scope_state(folder,fingerprint)!='terminal':
            raise ValueError('full source snapshot missing; extraction fallback prohibited')


def load_frozen_runner(work):
    scripts=(Path(work)/'frozen/scripts').resolve()
    sys.path.insert(0,str(scripts))
    runner=importlib.import_module('run_socialmem_baseline')
    if Path(runner.__file__).resolve()!=scripts/'run_socialmem_baseline.py':
        raise ValueError('full source runner loaded outside frozen directory')
    return runner


def check(work):
    work=Path(work).resolve()
    plan=json.loads((work/'execution-plan.json').read_text())
    if sha(Path(__file__))!=plan['driver_sha256']:raise ValueError('full source driver drift')
    verify_manifest(work,plan)
    cfg=json.loads((work/'config.json').read_text())
    if cfg['core_sha256']!=CORE_SHA or sha(work/'corpus.jsonl')!=CORPUS_SHA:
        raise ValueError('full source core or corpus changed')
    runner=load_frozen_runner(work)
    fingerprint=runner._verify_identity(work,cfg)
    groups=runner.prepare_groups(runner._read_jsonl(work/'corpus.jsonl'))
    validate_protocol(plan,cfg,groups)
    verify_scope_states(work,groups,runner,fingerprint,plan)
    return runner,groups


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['check','run']);p.add_argument('--work',type=Path,required=True)
    args=p.parse_args();runner,groups=check(args.work)
    if args.mode=='check':print(json.dumps({'verified':True,'questions':1031,'groups':49,'http_limit':1848,'requests':0}))
    else:
        report=runner.run(args.work,groups=groups,workers=4)
        print(json.dumps({'summary':report['summary'],'ledger':report['ledger']},ensure_ascii=False))
if __name__=='__main__':main()
