#!/usr/bin/env python3
"""R5.7 fixed native strict-capability probe: at most four HTTP requests, no resume."""
from __future__ import annotations
import argparse
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT/'build/socialmem_20260925_r56_expanded/prepare'
PREPARE_SEAL_SHA256 = '4aca92fe8eca1615fd7fe65a66d7cf28048f4ac789aa676367acc5ac4bda1577'
CORE_SHA256 = '4c5a7c39ae708a13d10065a0816a5c97a994929479cb0898f504c21e12b422f9'
CONTRACTS = ('claim_admission_v1', 'claim_extraction_v2')
SOURCES = ('scripts/run_socialmem_r57_strict_probe.py', 'tests/python/test_socialmem_r57_strict_probe.py')
BUDGET = 4
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location('r57_builder', ROOT/'scripts/run_socialmem_r56_expanded.py')
builder = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(builder)
read, write, sha, inventory = builder.read, builder.write, builder.sha, builder.inventory


def probe_config(config):
    expected = dict(core_sha256=CORE_SHA256, extract_endpoint='https://dashscope.aliyuncs.com/compatible-mode/v1',
        extract_model='qwen3.8-27b', extract_max_tokens=8192, timeout_ms=120000, extract_enable_thinking=False, max_retries=0)
    if any(config.get(key) != value for key, value in expected.items()):
        raise ValueError('fixed prepare config mismatch')
    return dict(endpoint=config['extract_endpoint'], model=config['extract_model'], max_tokens=8192,
        timeout_ms=120000, enable_thinking=False, max_retries=0, json_object_output=False,
        output_mode='json_schema_strict', key_env='DASHSCOPE_API_KEY')


def load_fixed():
    """Historical prepare is the only native import root; no live-source equality gate."""
    builder.verify_historical(PREPARE, PREPARE_SEAL_SHA256, 'r56-expanded-seal-v1', 'prepare')
    config, identity = read(PREPARE/'config.json'), read(PREPARE/'identity.json')
    if identity['core_sha256'] != CORE_SHA256 or identity['config_sha256'] != sha(PREPARE/'config.json'):
        raise ValueError('fixed prepare identity mismatch')
    effective = probe_config(config)
    runner, modules = builder.frozen_modules(PREPARE, config, identity)
    core = modules[0]
    if sha(Path(core.__file__)) != CORE_SHA256:
        raise ValueError('loaded core mismatch')
    return runner, core, effective


def native_contract(core, name):
    return (core.OutputContractKind.ClaimAdmissionV1 if name == CONTRACTS[0]
            else core.OutputContractKind.ClaimExtractionV2)


def native_schemas(core):
    return {name:dict(schema=core.structured_output_schema(native_contract(core,name)),
        sha256=core.structured_output_schema_sha256(native_contract(core,name))) for name in CONTRACTS}



def fixture_prompts(core, contract):
    # Compare with the fixed native fixture; Python never sends these prompts.
    source=(PREPARE/'source/src/extractor/openai_adapter.cpp').read_text()
    admission=json.loads(re.search(r'std::string\(("Return JSON .*?")\);',source).group(1))
    contrary=json.loads(re.search(r'observation\.prompt\+=(".*?");',source).group(1))
    first=(admission if contract==CONTRACTS[0] else
           core.claim_extraction_prompt('Nora: I feel cheerful about the community picnic.','Nora'))
    return [first,first+contrary]


def make_adapter(core, config):
    with builder.baseline._provider_environment(config['key_env'], config['endpoint']):
        native = core.OpenAIAdapterConfig.from_env()
        native.base_url, native.model = config['endpoint'], config['model']
        for key in ('max_tokens', 'timeout_ms', 'max_retries', 'enable_thinking', 'json_object_output'):
            setattr(native, key, config[key])
        return core.OpenAIAdapter(native)


def analyze(core, evidence, contract, config):
    """Native classification plus independent raw-HTTP accounting and acceptance."""
    error = core.validate_capability_evidence_json(json.dumps(evidence,ensure_ascii=False))
    if (evidence.get('output_contract') != contract or evidence.get('output_mode') != 'json_schema_strict'
        or evidence.get('endpoint') != config['endpoint'] or evidence.get('model') != config['model']):
        raise ValueError('capability fixed contract/model/endpoint mismatch')
    result = dict(contract=contract,native_state=evidence.get('state'),native_validation_error=error,
        native_error=evidence.get('error'),observed_requests=0,known_tokens=0,observed_tokens=None,missing_token_usage=0,usage_complete=True,
        local_attempt_count_unknown=bool(error),remote_execution_unknown=False,healthy_http=True,
        raw_native_usage_matches=True,raw_finish_matches=True,server_errors=[],passed=False)
    probes = evidence.get('probes', [])
    if not isinstance(probes,list) or len(probes)!=2:
        result['local_attempt_count_unknown']=True
        probes=probes if isinstance(probes,list) else []
    result['missing_token_usage']+=max(0,2-len(probes))
    expected_prompts=fixture_prompts(core,contract)
    for index,probe in enumerate(probes):
        if index>=2 or probe.get('prompt')!=expected_prompts[index]:
            raise ValueError('native capability fixture prompt mismatch')
        response=probe.get('response',{}); attempts=response.get('http_attempts',[])
        if not isinstance(attempts,list):attempts=[]
        if len(attempts)!=1 or response.get('attempt_count')!=len(attempts):
            result['local_attempt_count_unknown']=True
        if not attempts:
            result['missing_token_usage']+=1;result['usage_complete']=False;result['healthy_http']=False
        result['observed_requests']+=len(attempts)
        for attempt in attempts:
            certainty=attempt.get('execution_certainty')
            result['remote_execution_unknown'] |= certainty not in ('not_connected','response_received')
            healthy=(attempt.get('http_status')==200 and attempt.get('curl_code')==0
                and certainty=='response_received' and response.get('ok') is True
                and response.get('finish_reason')=='stop' and response.get('refusal') is False)
            try: envelope=json.loads(attempt['response_body'])
            except (ValueError,KeyError,TypeError):envelope={}
            if not isinstance(envelope,dict):envelope={}
            choices=envelope.get('choices')
            first=choices[0] if isinstance(choices,list) and choices else {}
            raw_finish=first.get('finish_reason') if isinstance(first,dict) else None
            if healthy and raw_finish!=response.get('finish_reason'):
                result['raw_finish_matches']=False
            result['healthy_http'] &= healthy and raw_finish=='stop'
            if 'error' in envelope:result['server_errors'].append(envelope['error'])
            try:
                usage=envelope['usage']; values=[usage[k] for k in ('prompt_tokens','completion_tokens','total_tokens')]
                if not all(type(v) is int and v>=0 for v in values) or values[0]+values[1]!=values[2] or values[2]<=0:
                    raise ValueError('invalid usage')
                result['known_tokens']+=values[2]
                if any(response.get(k)!=usage[k] for k in ('prompt_tokens','completion_tokens','total_tokens')):
                    result['raw_native_usage_matches']=False
            except (ValueError,KeyError,TypeError):
                result['missing_token_usage']+=1;result['usage_complete']=False
    if evidence.get('request_count')!=result['observed_requests'] or result['observed_requests']>2:
        result['local_attempt_count_unknown']=True
    result['remote_execution_unknown'] |= result['local_attempt_count_unknown']
    result['usage_complete'] &= not result['local_attempt_count_unknown']
    if result['usage_complete']:result['observed_tokens']=result['known_tokens']
    result['passed']=(not error and result['native_state']=='observed_conformant'
        and result['observed_requests']==2 and result['healthy_http'] and result['usage_complete']
        and result['raw_finish_matches'] and result['raw_native_usage_matches'] and not result['remote_execution_unknown'])
    return result


def ledger_rows(out):
    path=out/'request-ledger.sqlite'
    totals=builder.previous.read_ledger(path,BUDGET)
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        if db.execute('pragma integrity_check').fetchall()!=[('ok',)]:raise ValueError('ledger integrity failure')
        rows=[dict(zip(('id','scope','stage','upper_bound','actual','state'),r)) for r in db.execute(
            'select id,scope,stage,upper_bound,actual,state from reservations order by id')]
    return rows,totals


def summarize(out, core, config):
    reservations,ledger=ledger_rows(out); results=[]
    if ledger['reserved'] or ledger['remaining']<0 or len(reservations)>2:
        raise ValueError('unfinished or excessive ledger')
    setup_path=out/'setup.failure.json'
    setup_failure=read(setup_path) if setup_path.exists() else None
    if bool(setup_failure)==bool(reservations):raise ValueError('setup/contract invocation mismatch')
    for index,reservation in enumerate(reservations):
        name=CONTRACTS[index]
        if (reservation['id']!=index+1 or reservation['scope']!='strict_probe'
            or reservation['stage']!=name or reservation['upper_bound']!=2):
            raise ValueError('contract reservation order/bound mismatch')
        if index and not results[-1]['passed']:raise ValueError('extraction invoked after failed admission')
        started=read(out/(name+'.started.json'))
        if started!=dict(contract=name,reservation=dict(id=index+1,state='reserved',upper_bound=2)):
            raise ValueError('contract reservation journal mismatch')
        failure_path=out/(name+'.failure.json'); evidence_path=out/(name+'.evidence.json')
        if failure_path.exists():
            if evidence_path.exists():raise ValueError('ambiguous exception/receipt')
            failure=read(failure_path)
            if failure.get('kind')!='native_call_exception' or not failure.get('detail'):
                raise ValueError('invalid native exception evidence')
            result=dict(contract=name,native_state='unknown',failure=failure,observed_requests=0,
                known_tokens=0,observed_tokens=None,missing_token_usage=2,usage_complete=False,
                local_attempt_count_unknown=True,remote_execution_unknown=True,passed=False)
        else:result=analyze(core,read(evidence_path),name,config)
        expected=('charged_upper',None) if result['local_attempt_count_unknown'] else ('settled',result['observed_requests'])
        if (reservation['state'],reservation['actual'])!=expected:
            raise ValueError('raw HTTP/reservation settlement mismatch')
        results.append(result)
    expected_files={name+suffix for name in CONTRACTS[:len(results)] for suffix in ('.started.json',)}
    for name in CONTRACTS[:len(results)]:
        expected_files.add(name+('.failure.json' if (out/(name+'.failure.json')).exists() else '.evidence.json'))
    actual_files={p.name for p in out.glob('claim_*')}
    if actual_files!=expected_files:raise ValueError('extra or missing contract artifacts')
    source_end=read(out/'execution-end.json')
    if set(source_end)!=set(SOURCES) or any(not isinstance(v,str) or len(v)!=64 for v in source_end.values()):
        raise ValueError('invalid execution-end source inventory')
    sources_unchanged=source_end==read(out/'identity.json')['sources']
    passed=len(results)==2 and all(r['passed'] for r in results) and sources_unchanged
    usage_complete=all(r['usage_complete'] for r in results)
    known_tokens=sum(r['known_tokens'] for r in results)
    return dict(stage='strict_probe',state='complete' if passed else 'incomplete',
        status='strict_fixture_passed' if passed else 'strict_fixture_stopped',
        execution_sources_unchanged=sources_unchanged,contracts=results,setup_failure=setup_failure,observed_requests=sum(r['observed_requests'] for r in results),
        known_tokens=known_tokens,observed_tokens=known_tokens if usage_complete else None,
        missing_token_usage=sum(r['missing_token_usage'] for r in results),usage_complete=usage_complete,
        local_attempt_count_unknown=any(r['local_attempt_count_unknown'] for r in results),
        remote_execution_unknown=any(r['remote_execution_unknown'] for r in results),ledger=ledger,
        conclusion_scope='Fixed endpoint/model/schema protocol fixtures only; no semantic, build or QA acceptance.')


def seal(out):
    if (out/'seal.json').exists():raise ValueError('output already sealed')
    write(out/'seal.json',dict(schema='r57-strict-probe-seal-v1',files=inventory(out)))


def run(out):
    out=Path(out).resolve()
    if out.exists():raise ValueError('output already exists')
    runner,core,config=load_fixed()
    out.mkdir(parents=True)
    sources={name:sha(ROOT/name) for name in SOURCES}
    for name in SOURCES:
        target=out/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    write(out/'config.json',config);write(out/'schemas.json',native_schemas(core))
    write(out/'identity.json',dict(prepare=str(PREPARE.resolve()),prepare_seal_sha256=PREPARE_SEAL_SHA256,
        core_sha256=CORE_SHA256,loaded_core=str(Path(core.__file__).resolve()),sources=sources,
        config_sha256=sha(out/'config.json'),schemas_sha256=sha(out/'schemas.json')))
    shutil.copyfile(PREPARE/'seal.json',out/'prepare-seal.json')
    ledger=runner.BudgetLedger(out/'request-ledger.sqlite',BUDGET)
    try:adapter=make_adapter(core,config)
    except Exception as exc:
        write(out/'setup.failure.json',dict(kind='adapter_setup_exception',detail=type(exc).__name__+': '+str(exc)))
    else:
        for name in CONTRACTS:
            reservation=ledger.reserve('strict_probe',name,2)
            if reservation['state']!='reserved':raise RuntimeError('fixed probe budget unexpectedly blocked')
            write(out/(name+'.started.json'),dict(contract=name,reservation=reservation))
            try:
                request=core.StructuredOutputRequest(native_contract(core,name),core.OutputMode.JsonSchemaStrict)
                raw=adapter.probe_structured_output(request).to_json()
                evidence=json.loads(raw)
            except Exception as exc:
                write(out/(name+'.failure.json'),dict(kind='native_call_exception',detail=type(exc).__name__+': '+str(exc)))
                ledger.charge_upper(reservation['id']);break
            write(out/(name+'.evidence.json'),evidence)
            result=analyze(core,evidence,name,config)
            if result['local_attempt_count_unknown']:ledger.charge_upper(reservation['id'])
            else:ledger.settle(reservation['id'],result['observed_requests'])
            if not result['passed']:break
    write(out/'execution-end.json',{name:sha(ROOT/name) for name in SOURCES})
    summary=summarize(out,core,config);write(out/'summary.json',summary);seal(out)
    return summary


def check(out):
    out=Path(out).resolve();stored=read(out/'seal.json');actual=inventory(out);actual.pop('seal.json',None)
    if stored!=dict(schema='r57-strict-probe-seal-v1',files=actual):raise ValueError('probe seal mismatch')
    _,core,config=load_fixed();identity=read(out/'identity.json')
    if (identity.get('prepare')!=str(PREPARE.resolve()) or identity.get('prepare_seal_sha256')!=PREPARE_SEAL_SHA256
        or identity.get('core_sha256')!=CORE_SHA256 or identity.get('loaded_core')!=str(Path(core.__file__).resolve())
        or sha(out/'prepare-seal.json')!=PREPARE_SEAL_SHA256):raise ValueError('fixed input identity mismatch')
    if (read(out/'config.json')!=config or identity.get('config_sha256')!=sha(out/'config.json')
        or read(out/'schemas.json')!=native_schemas(core) or identity.get('schemas_sha256')!=sha(out/'schemas.json')):
        raise ValueError('native schema/config identity mismatch')
    if (set(identity.get('sources',{}))!=set(SOURCES)
        or inventory(out/'source')!=identity['sources']):raise ValueError('executed source copy/manifest mismatch')
    result=summarize(out,core,config)
    if result!=read(out/'summary.json'):raise ValueError('recomputed capability/accounting summary mismatch')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);stages=parser.add_subparsers(dest='stage',required=True)
    stages.add_parser('run').add_argument('--out',type=Path,required=True)
    stages.add_parser('check').add_argument('--input',type=Path,required=True)
    args=parser.parse_args(argv);result=run(args.out) if args.stage=='run' else check(args.input)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2));return int(result['state']!='complete')


if __name__=='__main__':raise SystemExit(main())
