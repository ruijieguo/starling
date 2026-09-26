#!/usr/bin/env python3
"""人物来源检索固定开发评测；仅编排冻结C++实现，不复制检索算法。"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_socialmem_k30_controlled as base

ROOT=Path(__file__).resolve().parents[1]
PARENT_SEAL='43576437925d64f2401c063885107e451058c58031258c7fbc12f2ca71c3a890'
CORE_NAME='python/starling/_core.cpython-314-darwin.so'
CHANGED={CORE_NAME,'include/starling/retrieval/source_retriever.hpp','src/retrieval/source_retriever.cpp',
         'bindings/python/bind_05_retrieval.cpp','scripts/eval_ladder_pipeline.py',
         'scripts/run_socialmem_baseline.py','tests/cpp/test_source_retriever.cpp',
         'tests/python/test_source_retriever_binding.py'}
read,write,sha=base.read,base.write,base.sha


def validate_config(parent,candidate):
    core=candidate.get('core_sha256','');strategy=candidate.get('source_strategy')
    expected={**parent,'core_sha256':core,'source_strategy':strategy}
    if (parent.get('core_sha256')!=base.CORE or parent.get('k')!=30 or parent.get('http_budget')!=1314
        or parent.get('recall_mode')!='sources' or strategy not in ('focused','focused_window')
        or not isinstance(core,str) or not re.fullmatch('[0-9a-f]{64}',core) or core==base.CORE
        or json.dumps(candidate,sort_keys=True)!=json.dumps(expected,sort_keys=True)):
        raise ValueError('focus only permits reviewed native core and source strategy changes')


def validate_code_delta(parent,candidate):
    old,new=parent['frozen_files'],candidate['frozen_files']
    if old.keys()!=new.keys() or any(old[k]!=new[k] for k in old if k not in CHANGED):
        raise ValueError('unreviewed code or prompt change')


def validate_ablation(result,strategy,digest):
    profiles=result['profiles']
    chosen=max(('focused','focused_window'),key=lambda s:profiles[s]['hits'])
    if (result.get('verified') is not True or result['questions']!=733 or result['core_sha256']!=digest
        or result['selected']!=chosen or strategy!=chosen or profiles['bm25']['hits']!=560
        or profiles['bm25']['zero']!=293 or profiles[chosen]['hits']<=560 or profiles[chosen]['zero']>293):
        raise ValueError('ablation core, baseline or preregistered selection changed')


def verify_parent(parent):
    if sha(parent/'completion-seal.json')!=PARENT_SEAL:raise ValueError('k30 parent seal changed')
    seal=read(parent/'completion-seal.json');base.verify_files(parent,seal['files'])
    if (seal['questions'],seal['correct'])!=(733,197):raise ValueError('k30 parent incomplete')
    baseline=parent.parent/'socialmem_20260917_baseline_recovered'
    base.verify_parent(baseline)
    return baseline


def selected_groups(runner,work):
    selected=base.select_records(runner._read_jsonl(work/'corpus.jsonl'),read(work/'network-split.json'))
    return selected,runner.prepare_groups(selected)


def prepare(work,parent,ablation):
    work,parent=Path(work).resolve(),Path(parent).resolve();baseline=verify_parent(parent)
    if work.exists():raise ValueError('prepare requires a new directory')
    result=read(ablation);digest=sha(ROOT/'build'/CORE_NAME);strategy=result['selected']
    validate_ablation(result,strategy,digest)
    original=read(parent/'identity.json');work.mkdir(parents=True)
    for name,expected in original['frozen_files'].items():
        source=ROOT/'build'/name if name==CORE_NAME else ROOT/name
        # Verify the compiled source tree contains no unreviewed native changes.
        if name!=CORE_NAME and source.is_file() and sha(source)!=expected and name not in CHANGED:
            raise ValueError(f'unreviewed workspace drift: {name}')
        if name not in CHANGED:source=parent/'frozen'/name
        target=work/'frozen'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    for name in ['corpus.jsonl','scope-manifest.json','network-split.json']:shutil.copyfile(parent/name,work/name)
    config={**read(parent/'config.json'),'source_strategy':strategy,'core_sha256':digest}
    validate_config(read(parent/'config.json'),config);write(work/'config.json',config)
    identity={**original,'core_path':str(work/'frozen'/CORE_NAME),'core_sha256':digest,
        'config_sha256':sha(work/'config.json'),'parent_k30_seal_sha256':PARENT_SEAL,
        'candidate_change':'C++显式人物与相邻话轮；k30/8000字节与评分保持',
        'frozen_files':{n:sha(work/'frozen'/n) for n in original['frozen_files']}}
    validate_code_delta(original,identity);write(work/'identity.json',identity)
    runner=base.load_runner(work);fingerprint=runner._verify_identity(work,config)
    selected,groups=selected_groups(runner,work)
    for group in groups:
        folder=work/'runs'/group['group_id'];folder.mkdir(parents=True)
        old=parent/'runs'/group['group_id'];shutil.copyfile(old/'frozen.db',folder/'frozen.db')
        metadata=read(old/'scope.json');metadata['fingerprint']=fingerprint;write(folder/'scope.json',metadata)
    shutil.copyfile(Path(__file__),work/'run.py')
    shutil.copyfile(Path(base.__file__),work/'run_socialmem_k30_controlled.py')
    shutil.copyfile(ablation,work/'native-ablation.json')
    snapshot=ROOT/'build/socialmem_focus_checks/parent-documentation'
    docs=read(baseline/'completion-seal.json')['workspace_documentation']
    base.verify_files(snapshot,docs);shutil.copytree(snapshot,work/'parent-documentation')
    sources=['scripts/run_socialmem_source_focus.py','tests/python/test_source_focus_guard.py',
             'build/socialmem_focus_checks/native_ablation.py']
    sources+= [str(p.relative_to(ROOT)) for p in (ROOT/'docs').rglob('*.md')]
    for name in sources:
        target=work/'execution-sources'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    plan={'parent_work':str(parent),'baseline_work':str(baseline),'parent_seal_sha256':PARENT_SEAL,
        'driver_sha256':sha(work/'run.py'),'core_sha256':digest,'strategy':strategy,
        'questions':733,'groups':39,'http_budget':1314,
        'scope_ids':[g['group_id'] for g in groups],'question_ids':[r['item_id'] for r in selected]}
    plan['files']={str(p.relative_to(work)):sha(p) for p in sorted(work.rglob('*'))
                   if p.is_file() and '__pycache__' not in p.parts}
    write(work/'execution-plan.json',plan)


def check(work):
    work=Path(work).resolve();plan=read(work/'execution-plan.json')
    if sha(Path(__file__))!=plan['driver_sha256'] or plan['parent_seal_sha256']!=PARENT_SEAL:
        raise ValueError('focus driver/parent changed')
    base.verify_manifest(work,plan)
    # base manifest additionally requires all scope snapshots and frozen imports.
    parent=Path(plan['parent_work']);baseline=verify_parent(parent)
    base.verify_files(work/'parent-documentation',read(baseline/'completion-seal.json')['workspace_documentation'])
    config,identity=read(work/'config.json'),read(work/'identity.json')
    validate_config(read(parent/'config.json'),config);validate_code_delta(read(parent/'identity.json'),identity)
    validate_ablation(read(work/'native-ablation.json'),config['source_strategy'],config['core_sha256'])
    for name in ['corpus.jsonl','scope-manifest.json','network-split.json']:
        if sha(work/name)!=sha(parent/name):raise ValueError('input or split changed')
    runner=base.load_runner(work);fingerprint=runner._verify_identity(work,config)
    selected,groups=selected_groups(runner,work)
    if ([g['group_id'] for g in groups]!=plan['scope_ids'] or [r['item_id'] for r in selected]!=plan['question_ids']
        or (plan['questions'],plan['groups'],plan['http_budget'])!=(733,39,1314)
        or plan['core_sha256']!=config['core_sha256'] or plan['strategy']!=config['source_strategy']):
        raise ValueError('selected set or execution plan changed')
    for group in groups:
        folder=work/'runs'/group['group_id']
        if runner.scope_state(folder,fingerprint)!='terminal' or (folder/'scope.failure.json').exists():
            raise ValueError('source snapshot unavailable; extraction prohibited')
        if sha(folder/'frozen.db')!=sha(parent/'runs'/group['group_id']/'frozen.db'):
            raise ValueError('source database changed')
    bound=sum(runner.question_request_bound(r,config,work/'runs'/g['group_id']/'frozen.db')
              for g in groups for r in g['records'])
    if bound!=1314:raise ValueError('native request budget changed')
    return runner,groups


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','check','run']);parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--parent',type=Path,default=ROOT/'build/socialmem_20260917_k30_controlled')
    parser.add_argument('--ablation',type=Path,default=ROOT/'build/socialmem_focus_checks/native-ablation.json')
    args=parser.parse_args()
    if args.mode=='prepare':
        prepare(args.work,args.parent,args.ablation)
    runner,groups=check(args.work)
    if args.mode!='run':
        print(json.dumps({'verified':True,'questions':733,'groups':39,'http_limit':1314,'requests':0}));return
    report=runner.run(args.work,groups=groups,workers=4)
    records=[r for g in groups for r in g['records']];results=[r for g in report['groups'] for r in g['results']]
    summary=runner.summarize(records,results)
    selected={'state':'complete' if summary['executed']==733 else 'partial','summary':summary,
              'ledger':report['ledger'],'scope_ids':[g['group_id'] for g in groups]}
    write(args.work/'selected-summary.json',selected)
    print(json.dumps(selected,ensure_ascii=False))

if __name__=='__main__':main()
