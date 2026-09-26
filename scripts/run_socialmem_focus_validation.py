#!/usr/bin/env python3
"""开发门槛通过后，以相同冻结候选做298题保留集验收。"""
import argparse,json,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_socialmem_k30_controlled as base
ROOT=Path(__file__).resolve().parents[1]
read,write,sha=base.read,base.write,base.sha


def validate_gate(overall):
    if overall['n']!=733 or overall['delta']<.05 or overall['network_bootstrap_delta_95ci'][0]<=0:
        raise ValueError('development improvement gate not met')


def validate_config(parent,candidate):
    if parent.get('http_budget')!=1314 or json.dumps(candidate,sort_keys=True)!=json.dumps({**parent,'http_budget':534},sort_keys=True):
        raise ValueError('validation only changes selected-set request budget')


def select_reserved(records,split):
    base.select_records(records,split)
    selected=[r for r in records if r['source']['network_id'] in split['reserved_networks']]
    if len(selected)!=298 or len({r['source']['network_id'] for r in selected})!=10 or sum(1+(r['answer_format']!='multiple_choice') for r in selected)!=534:
        raise ValueError('reserved question set changed')
    return selected


def verify_development(dev,expected_seal=None):
    if expected_seal is not None and sha(dev/'completion-seal.json')!=expected_seal:raise ValueError('development seal changed')
    seal=read(dev/'completion-seal.json');base.verify_files(dev,seal['files'])
    if seal['questions']!=733:raise ValueError('development incomplete')
    analysis=read(dev/'paired-analysis.json');validate_gate(analysis['comparisons']['k30']['overall'])
    baseline=Path(read(dev/'execution-plan.json')['baseline_work']);base.verify_parent(baseline)
    return baseline


def prepare(work,dev):
    work,dev=Path(work).resolve(),Path(dev).resolve();baseline=verify_development(dev)
    if work.exists():raise ValueError('validation requires a new directory')
    work.mkdir(parents=True)
    old=read(dev/'identity.json')
    for name in old['frozen_files']:
        dst=work/'frozen'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(dev/'frozen'/name,dst)
    for name in ['corpus.jsonl','scope-manifest.json','network-split.json']:shutil.copyfile(dev/name,work/name)
    config={**read(dev/'config.json'),'http_budget':534};validate_config(read(dev/'config.json'),config);write(work/'config.json',config)
    identity={**old,'config_sha256':sha(work/'config.json'),
              'core_path':str(work/'frozen/python/starling/_core.cpython-314-darwin.so'),
              'candidate_change':'相同冻结人物检索候选的298题保留集验收'}
    write(work/'identity.json',identity);runner=base.load_runner(work);fp=runner._verify_identity(work,config)
    selected=select_reserved(runner._read_jsonl(work/'corpus.jsonl'),read(work/'network-split.json'));groups=runner.prepare_groups(selected)
    for g in groups:
        folder=work/'runs'/g['group_id'];folder.mkdir(parents=True);source=baseline/'runs'/g['group_id']
        shutil.copyfile(source/'frozen.db',folder/'frozen.db');scope=read(source/'scope.json');scope['fingerprint']=fp;write(folder/'scope.json',scope)
    shutil.copyfile(Path(__file__),work/'run.py');shutil.copyfile(base.__file__,work/'run_socialmem_k30_controlled.py')
    for name in ['tests/python/test_focus_validation_guard.py','docs/superpowers/specs/2026-09-17-socialmem-focus-validation-design.md','docs/superpowers/plans/2026-09-17-socialmem-focus-validation.md']:
        target=work/'execution-sources'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    plan={'development_work':str(dev),'development_seal_sha256':sha(dev/'completion-seal.json'),
          'baseline_work':str(baseline),'driver_sha256':sha(work/'run.py'),'questions':298,'groups':10,'http_budget':534,
          'scope_ids':[g['group_id'] for g in groups],'question_ids':[r['item_id'] for r in selected]}
    plan['files']={str(p.relative_to(work)):sha(p) for p in sorted(work.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    write(work/'execution-plan.json',plan)


def check(work):
    work=Path(work).resolve();plan=read(work/'execution-plan.json')
    if sha(Path(__file__))!=plan['driver_sha256']:raise ValueError('validation driver changed')
    base.verify_files(work,plan['files']);dev=Path(plan['development_work']);baseline=verify_development(dev,plan['development_seal_sha256'])
    config,identity=read(work/'config.json'),read(work/'identity.json');validate_config(read(dev/'config.json'),config)
    if identity['frozen_files']!=read(dev/'identity.json')['frozen_files']:raise ValueError('validation candidate differs')
    required={'run.py','run_socialmem_k30_controlled.py','config.json','identity.json','corpus.jsonl','scope-manifest.json','network-split.json'}
    required.update('frozen/'+n for n in identity['frozen_files'])
    required.update(f'runs/{g}/{n}' for g in plan['scope_ids'] for n in ['scope.json','frozen.db'])
    if not required<=plan['files'].keys():raise ValueError('incomplete validation manifest')
    for name in ['corpus.jsonl','scope-manifest.json','network-split.json']:
        if sha(work/name)!=sha(dev/name):raise ValueError('validation input/split differs')
    runner=base.load_runner(work);fp=runner._verify_identity(work,config)
    selected=select_reserved(runner._read_jsonl(work/'corpus.jsonl'),read(work/'network-split.json'));groups=runner.prepare_groups(selected)
    if ([r['item_id'] for r in selected]!=plan['question_ids'] or [g['group_id'] for g in groups]!=plan['scope_ids']
        or (plan['questions'],plan['groups'],plan['http_budget'])!=(298,10,534)):
        raise ValueError('validation plan changed')
    for g in groups:
        folder=work/'runs'/g['group_id']
        if runner.scope_state(folder,fp)!='terminal' or (folder/'scope.failure.json').exists():raise ValueError('source unavailable')
        if sha(folder/'frozen.db')!=sha(baseline/'runs'/g['group_id']/'frozen.db'):raise ValueError('source database changed')
    if sum(runner.question_request_bound(r,config,work/'runs'/g['group_id']/'frozen.db') for g in groups for r in g['records'])!=534:raise ValueError('native budget changed')
    return runner,groups


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','check','run']);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--development',type=Path,default=ROOT/'build/socialmem_20260917_source_focus');args=p.parse_args()
    if args.mode=='prepare':prepare(args.work,args.development)
    runner,groups=check(args.work)
    if args.mode!='run':print(json.dumps({'verified':True,'questions':298,'http_limit':534,'requests':0}));return
    report=runner.run(args.work,groups=groups,workers=4);records=[r for g in groups for r in g['records']];rows=[r for g in report['groups'] for r in g['results']]
    summary=runner.summarize(records,rows);result={'state':'complete' if summary['executed']==298 else 'partial','summary':summary,'ledger':report['ledger']}
    write(args.work/'selected-summary.json',result);print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
