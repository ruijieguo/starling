#!/usr/bin/env python3
"""固定57题的来源候选对照；校验明确实验配置与冻结差分后调用既有runner。"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))

NETWORKS=('grp_0d1e2f3a','grp_2b3c4d5e','grp_3c4d5e6f','grp_4d5e6f7a','grp_9c0d1e2f','grp_a3b4c5d6')
BASE_CORE='89f08596f37a1511b499a591b9612a204d4fef5b39e1e743d0548625f24db923'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def select_groups(groups):
    selected=[g for g in groups if g['network_id'] in NETWORKS]
    records=[r for g in selected for r in g['records']]
    if (len(selected)!=7 or {g['network_id'] for g in selected}!=set(NETWORKS)
            or len(records)!=57 or len({r['item_id'] for r in records})!=57
            or sum(1+int(r['answer_format']!='multiple_choice') for r in records)!=101):
        raise ValueError('speaker development question set changed')
    return selected

def validate_config(parent,candidate,core,variant='speaker'):
    if parent.get('core_sha256')!=BASE_CORE or parent.get('recall_mode')!='sources':
        raise ValueError('speaker comparison parent changed')
    expected={**parent,'core_sha256':core,'http_budget':101}
    if variant=='context_density':expected['k']=30
    elif variant!='speaker':raise ValueError('unknown source candidate profile')
    if candidate!=expected or core==BASE_CORE:
        raise ValueError('speaker comparison must only change native core and budget')

def validate_code_delta(parent,candidate,variant='speaker'):
    old,new=parent['frozen_files'],candidate['frozen_files']
    changed={name for name in old if old[name]!=new.get(name)}
    allowed={'python/starling/_core.cpython-314-darwin.so','src/retrieval/source_retriever.cpp','tests/cpp/test_source_retriever.cpp'}
    if variant=='context_density':allowed.update({'include/starling/extractor/claim_contract.hpp','src/extractor/claim_contract.cpp'})
    elif variant!='speaker':raise ValueError('unknown source candidate profile')
    if changed!=allowed:
        raise ValueError('speaker comparison changed unrelated frozen code')
    if set(new)-set(old)!={'scripts/run_socialmem_source_speaker.py','tests/python/test_source_speaker_guard.py'}:
        raise ValueError('speaker comparison added unrelated frozen code')

def summarize_selected(runner,groups,report):
    records=[r for g in groups for r in g['records']]
    results=[r for g in report['groups'] for r in g['results']]
    summary=runner.summarize(records,results)
    return {'state':'complete' if summary['executed']==len(records) else 'partial',
            'summary':summary,'ledger':report['ledger'],'scope_ids':[g['group_id'] for g in groups]}

def verify_files(work,files):
    for name,expected in files.items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('invalid speaker archive path')
        if not (work/name).is_file() or sha(work/name)!=expected:
            raise ValueError(f'speaker artifact mismatch: {name}')

def verify_manifest(work,plan):
    work=Path(work);files=plan.get('files',{})
    required={'config.json','identity.json','corpus.jsonl','scope-manifest.json','network-split.json','run.py'}
    required.update(f'runs/{g}/{name}' for g in plan['scope_ids'] for name in ('scope.json','frozen.db'))
    if not required.issubset(files):raise ValueError('incomplete speaker source manifest')
    verify_files(work,{k:files[k] for k in required})
    identity=json.loads((work/'identity.json').read_text())
    if 'scripts/run_socialmem_baseline.py' not in identity['frozen_files']:
        raise ValueError('speaker frozen runner missing')
    for name,expected in identity['frozen_files'].items():
        if files.get('frozen/'+name)!=expected:raise ValueError('speaker frozen file omitted')
    verify_files(work,files)

def check(work):
    work=Path(work).resolve();plan=json.loads((work/'execution-plan.json').read_text())
    if sha(Path(__file__))!=plan['driver_sha256']:raise ValueError('speaker driver drift')
    verify_manifest(work,plan)
    parent=Path(plan['parent_work'])
    if sha(parent/'completion-seal.json')!=plan['parent_seal_sha256']:
        raise ValueError('speaker parent seal drift')
    verify_files(parent,json.loads((parent/'completion-seal.json').read_text())['files'])
    summary=json.loads((parent/'summary.json').read_text())
    if summary['state']!='complete' or summary['summary']['executed']!=1031:
        raise ValueError('speaker parent must be complete')
    cfg=json.loads((work/'config.json').read_text())
    variant=plan.get('variant','speaker')
    validate_config(json.loads((parent/'config.json').read_text()),cfg,plan['core_sha256'],variant)
    validate_code_delta(json.loads((parent/'identity.json').read_text()),json.loads((work/'identity.json').read_text()),variant)
    for name in ('corpus.jsonl','scope-manifest.json','network-split.json'):
        if sha(work/name)!=sha(parent/name):raise ValueError('speaker corpus or split changed')
    sys.path.insert(0,str(work/'frozen/scripts'))
    from run_socialmem_source_full import load_frozen_runner
    runner=load_frozen_runner(work)
    fingerprint=runner._verify_identity(work,cfg)
    groups=select_groups(runner.prepare_groups(runner._read_jsonl(work/'corpus.jsonl')))
    if [g['group_id'] for g in groups]!=plan['scope_ids']:raise ValueError('speaker scope drift')
    for group in groups:
        folder=work/'runs'/group['group_id']
        if runner.scope_state(folder,fingerprint)!='terminal':raise ValueError('speaker source snapshot not ready')
        if sha(folder/'frozen.db')!=sha(parent/'runs'/group['group_id']/'frozen.db'):
            raise ValueError('speaker source snapshot differs from baseline')
    if sum(runner.question_request_bound(r,cfg,work/'runs'/g['group_id']/'frozen.db') for g in groups for r in g['records'])!=101:
        raise ValueError('speaker native request bound changed')
    return runner,groups

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('check','run'));parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args();runner,groups=check(args.work)
    if args.mode=='check':print(json.dumps({'verified':True,'questions':57,'groups':7,'http_limit':101,'requests':0}))
    else:
        result=runner.run(args.work,groups=groups,workers=4)
        selected=summarize_selected(runner,groups,result)
        runner._json_write(args.work/'selected-summary.json',selected)
        print(json.dumps(selected))
if __name__=='__main__':main()
