#!/usr/bin/env python3
"""R6.3：修复枚举边界后离线重新核验R6.2上下文，再执行fresh QA。"""
from pathlib import Path
import argparse
import importlib.util
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]
ORIGIN_SEAL='13bb9e5976ddc4afe42bec784a02fea3284b8556973757605fd00c48c2c6b4fd'


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts/run_socialmem_r62_evaluate.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module.engine


historical=load('r63_historical_evaluation')
engine=load('r63_revalidated_evaluation')
engine.SEAL_SCHEMA='r63-evaluation-seal-v1'
engine.IDENTITY_SCHEMA='r63-evaluation-identity-v1'
engine.FAILURE_SCHEMA='r63-evaluation-failure-v1'
engine.OWN_FILES=(*engine.OWN_FILES,'scripts/run_socialmem_r63_evaluate.py',
    'tests/python/test_socialmem_r63_evaluate.py','tests/python/test_socialmem_context_audit.py')
_base_check=engine.check
_base_retrieval_summary=engine.retrieval_summary
COPIED=('baseline','source10','started','request-ledger.sqlite')


def verify_origin(origin):
    origin=Path(origin).resolve()
    if engine.sha(origin/'seal.json')!=ORIGIN_SEAL:raise ValueError('recovery origin seal mismatch')
    seal=historical.verify_seal(origin)
    if seal['stage']!='retrieve' or seal['state']!='incomplete':raise ValueError('recovery requires incomplete retrieval')
    checked=historical.validate_identity(origin)
    stage=engine.read(origin/'stage.json');failure=engine.read(origin/'failure.json')
    expected=dict(stage='retrieve',input=str(checked['built']),input_seal_sha256=checked['seal_sha256'],workers=4)
    if stage!=expected or failure.get('stage_info')!=expected:raise ValueError('recovery origin stage mismatch')
    if (failure.get('schema')!=historical.FAILURE_SCHEMA or failure.get('provenance')!=historical.provenance(checked)
        or failure.get('source_files')!=engine.read(origin/'identity.json')['source_files']
        or not failure.get('exception','').startswith('TypeError: render_context_line(): incompatible function arguments.')
        or 'ContextPackLabel' not in failure['exception']):raise ValueError('recovery origin failure mismatch')
    if (engine.sha(origin/'input-seal.json')!=checked['seal_sha256']
        or engine.read(origin/'execution-plan.json')!=historical.execution_plan('retrieve',4,checked)):
        raise ValueError('recovery origin execution binding mismatch')
    if any((origin/('request-ledger.sqlite'+suffix)).exists() for suffix in ('-wal','-shm')):
        raise ValueError('recovery origin ledger is live')
    if any(p.is_symlink() for name in COPIED for p in ([origin/name] if (origin/name).is_file() else (origin/name).rglob('*'))):
        raise ValueError('recovery origin copied evidence symlink')
    return checked


def copied_inventory(directory):
    result={}
    for name in COPIED:
        path=directory/name
        if path.is_file():result[name]=engine.sha(path)
        else:result.update({name+'/'+k:v for k,v in engine.inventory(path).items()})
    return result


def recovery_proof(origin,checked):
    return dict(schema='r63-context-recovery-v1',mode='revalidated_recovery',origin=str(origin),
        origin_state='incomplete',origin_seal_sha256=ORIGIN_SEAL,
        origin_failure_sha256=engine.sha(origin/'failure.json'),build_seal_sha256=checked['seal_sha256'],
        core_sha256=engine.CORE_SHA256,copied_files=copied_inventory(origin),
        original_audit_source_sha256=engine.read(origin/'identity.json')['source_files']['scripts/run_socialmem_r56_evaluate.py'],
        validation_audit_source_sha256=engine.sha(ROOT/'scripts/run_socialmem_r56_evaluate.py'),
        inherited_embedding_requests=1336,new_external_requests=0,
        historical_checker_reexecuted=False,
        reason='原checker以字符串调用原生枚举接口；新checker逐条核验原生渲染、原始调用日志及费用。')


def validate_recovery(out):
    proof=engine.read(out/'recovery.json');origin=Path(proof['origin']).resolve()
    if origin==out:raise ValueError('cyclic recovery origin')
    checked=verify_origin(origin)
    expected=recovery_proof(origin,checked)
    # 历史恢复产物绑定自身封存的核验代码，而不是未来工作区版本。
    expected['validation_audit_source_sha256']=engine.read(out/'identity.json')['source_files']['scripts/run_socialmem_r56_evaluate.py']
    if proof!=expected:raise ValueError('recovery proof mismatch')
    if copied_inventory(out)!=expected['copied_files']:raise ValueError('recovery copied evidence mismatch')
    for name in ('seal.json','failure.json'):
        if engine.sha(out/('origin-'+name))!=engine.sha(origin/name):raise ValueError('recovery origin copy mismatch')
    return checked


def retrieval_summary(out,checked,rows):
    summary=_base_retrieval_summary(out,checked,rows)
    summary.update(mode='revalidated_recovery',inherited_embedding_requests=summary['embedding_requests'],new_embedding_requests=0)
    return summary


def recover(origin,out,evidence=()):
    out=engine.builder.new_output(out);origin=Path(origin).resolve();checked=verify_origin(origin)
    # 本阶段没有provider构造或检索调用。全部外部消费由原始回执继承。
    engine.freeze_stage(checked,out,'retrieve',checked['built'],checked['seal_sha256'],4,evidence)
    for name in COPIED:
        source=origin/name
        if source.is_dir():shutil.copytree(source,out/name)
        else:shutil.copyfile(source,out/name)
    for name in ('seal.json','failure.json'):shutil.copyfile(origin/name,out/('origin-'+name))
    engine.write(out/'recovery.json',recovery_proof(origin,checked))
    runner,modules=engine.runtime_modules(checked);rows=engine.read_retrieval_rows(out)
    engine.retrieval_inventory(checked,rows,require_healthy=True)
    engine.verify_contexts(checked,rows,modules)
    summary=retrieval_summary(out,checked,rows)
    if summary['state']!='complete' or summary['embedding_requests']!=1336:raise ValueError('recovery terminals incomplete')
    engine.write(out/'execution-plan.json',engine.execution_plan('retrieve',4,checked))
    engine.write(out/'comparison.json',engine.previous.retrieval_comparison(checked['records'],rows))
    engine.write(out/'summary.json',summary)
    engine.validate_identity(out,require_current=True);validate_recovery(out)
    engine.builder.old.validate_loaded(checked['prepared'],checked['identity'])
    engine.seal_output(out,'retrieve')
    return summary


def check(out,expected_stage=None):
    out=Path(out).resolve();seal=engine.verify_seal(out)
    if seal['stage']=='retrieve':validate_recovery(out)
    return _base_check(out,expected_stage)


engine.retrieval_summary=retrieval_summary
engine.check=check


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='stage',required=True)
    for name in ('recover','qa'):
        p=sub.add_parser(name);p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
        p.add_argument('--workers',type=int,default=4);p.add_argument('--evidence',type=Path,action='append',default=[])
    p=sub.add_parser('check');p.add_argument('--input',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.stage=='recover':
        if args.workers!=4:raise ValueError('recovery retains original four-worker plan')
        result=recover(args.input,args.out,args.evidence)
    elif args.stage=='qa':result=engine.qa(args.input,args.out,args.workers,args.evidence)
    else:
        audited=check(args.input);result=dict(audited['summary'],audit_program_files=audited['audit_program_files'])
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True));return int(result['state']!='complete')


if __name__=='__main__':raise SystemExit(main())
