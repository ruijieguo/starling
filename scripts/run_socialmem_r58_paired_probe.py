#!/usr/bin/env python3
"""R5.8 fixed six-task native paired probe; prepare/check are offline and run never resumes."""
from __future__ import annotations

import argparse
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
_spec=importlib.util.spec_from_file_location('r58_general_helpers',ROOT/'scripts/run_socialmem_r56_kwame_probe.py')
helpers=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(helpers)
read,write,sha,text_sha,inventory=helpers.read,helpers.write,helpers.sha,helpers.text_sha,helpers.inventory
copy_file,new_output=helpers.copy_file,helpers.new_output
BUDGET=54
ARMS=('A','B')
TENANT='default'
PROFILE='target_units_v1'
HISTORY={
    'Mum':dict(path='build/socialmem_20260925_r56_expanded/build',
        seal_sha256='6dcbd5a82172728cb2ae84f2b4811e94ced0c3552bd8598e4252130ab1fe762c',
        database='runs/ae45ef45d7ff23aade9a9a29/frozen.db',receipt='runs/ae45ef45d7ff23aade9a9a29/scope.json',
        schema='r56-expanded-seal-v1',stage='build',state='incomplete',units=15,batches=2,
        payload_bytes=3807,payload_sha256='91c41782d532083501e8361d2cfbb978480abe9138c41ec7aa7587cf6cc57535'),
    'Kwame':dict(path='build/socialmem_20260925_r56_kwame/run',
        seal_sha256='30f33e4437f09eaf7b080b7bd630c11afb4f2e10b0767e6e083d95f170f716a7',
        database='frozen.db',receipt='native-receipt.json',schema='r56-kwame-seal-v1',stage='run',state='complete',
        units=33,batches=5,payload_bytes=12133,
        payload_sha256='739a240bde63ee1286da19474305fb620be683fd48f4bf29defd3144cac7fab9')}
FIXED=dict(extract_endpoint='https://dashscope.aliyuncs.com/compatible-mode/v1',extract_model='qwen3.8-27b',
    extract_max_tokens=8192,extract_enable_thinking=False,timeout_ms=120000,max_retries=0,
    semantic_claim_contract=True,preserve_text_objects=True,claim_allow_code_fence=True,
    claim_protocol_retry_budget=1,claim_batch_size=8,claim_output_mode='json_object')
IMPLEMENTATION=('scripts/run_socialmem_r58_paired_probe.py','tests/python/test_socialmem_r58_paired_probe.py',
    'scripts/run_socialmem_r56_kwame_probe.py','scripts/run_socialmem_baseline.py')


def immutable(path):
    path=Path(path).resolve()
    if not path.is_file() or any(Path(str(path)+suffix).exists() for suffix in ('-wal','-shm')):
        raise ValueError('missing or live database')
    return closing(sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True))


def historical_seal(path,spec):
    if sha(path/'seal.json')!=spec['seal_sha256']:raise ValueError('fixed historical seal mismatch')
    seal=read(path/'seal.json');actual=inventory(path);actual.pop('seal.json',None)
    if (any(seal.get(k)!=spec[k] for k in ('schema','stage','state')) or not actual or seal.get('files')!=actual):
        raise ValueError('historical seal file set/hash mismatch')


def fixed_inputs():
    result={}
    for holder,spec in HISTORY.items():
        path=ROOT/spec['path'];historical_seal(path,spec);database=path/spec['database']
        if holder=='Mum':
            scope=read(path/spec['receipt']);rows=[r for r in scope['extraction'] if r.get('holder')==holder]
            if len(rows)!=1 or scope.get('group')!='ae45ef45d7ff23aade9a9a29':raise ValueError('Mum historical holder/scope mismatch')
            original=rows[0];receipt=original['receipt']['channels']['belief'];engram=original['engram_ref']
            with immutable(database) as db:
                sources=db.execute('SELECT d.engram_ref,e.payload_inline FROM source_documents d JOIN engrams e '
                    'ON e.id=d.engram_ref AND e.tenant_id=d.tenant_id WHERE d.tenant_id=? AND d.holder_id=?',
                    (TENANT,holder)).fetchall()
            source_link='source_documents'
        else:
            receipt=read(path/spec['receipt']);original=read(path/'commit.json');prepared=read(path/'remember-prepare.json')
            binding=read(path/'binding.json');engram=original.get('engram_ref')
            if (engram!=prepared.get('engram_ref') or binding.get('holder')!=holder or binding.get('tenant_id')!=TENANT
                or binding.get('payload_sha256')!=spec['payload_sha256'] or binding.get('payload_bytes')!=spec['payload_bytes']):
                raise ValueError('Kwame historical prepare/commit/binding mismatch')
            with immutable(database) as db:sources=db.execute('SELECT id,payload_inline FROM engrams WHERE tenant_id=?',(TENANT,)).fetchall()
            source_link='remember_prepare_and_commit'
        if len(sources)!=1 or sources[0][0]!=engram:raise ValueError('fixed historical holder engram mismatch')
        payload=sources[0][1]
        if (not isinstance(payload,bytes) or len(payload)!=spec['payload_bytes'] or text_sha(payload.decode())!=spec['payload_sha256']
            or receipt.get('holder')!=holder or receipt.get('source_payload_hash')!=spec['payload_sha256']):
            raise ValueError('fixed historical payload/receipt mismatch')
        original_plan=receipt['claim_batch_plan']
        if len(original_plan['source_units'])!=spec['units'] or len(original_plan['batches'])!=spec['batches']:
            raise ValueError('historical native source inventory mismatch')
        config=read(path/'config.json')
        if any(config.get(k)!=v or type(config.get(k)) is not type(v) for k,v in FIXED.items()):
            raise ValueError('historical extraction policy drift')
        result[holder]=dict(payload=payload.decode(),receipt=receipt,original_plan=original_plan,config=config,
            database=database,binding=dict(holder=holder,tenant_id=TENANT,path=str(path),seal_sha256=spec['seal_sha256'],
                database_sha256=sha(database),original_engram_ref=engram,source_link=source_link,
                payload_bytes=len(payload),payload_sha256=spec['payload_sha256'],receipt_sha256=sha(path/spec['receipt'])))
    return result


def fixed_tasks(plans):
    sequence=(('Mum',1,'A'),('Mum',1,'B'),('Mum',2,'B'),('Mum',2,'A'),('Kwame',1,'A'),('Kwame',1,'B'))
    tasks=[]
    for holder,repetition,arm in sequence:
        upper=6 if holder=='Mum' else 15
        if plans[holder][arm].get('belief_request_upper_bound')!=upper:raise ValueError('fixed native request bound mismatch')
        tasks.append(dict(task_id=f'{holder}{repetition}-{arm}',holder=holder,repetition=repetition,arm=arm,
            claim_batch_target_units=arm=='B',request_upper_bound=upper))
    return tasks


def allow_next(task,result):
    return result['status']=='passed' or task['arm']=='A' and result['status']=='protocol_failure'


def raw_cost(receipt,invoked,schema_hashes=None):
    if type(invoked) is not bool or not invoked and receipt is not None:raise ValueError('native invocation evidence mismatch')
    result=dict(observed_requests=0,known_tokens=0,known_prompt_tokens=0,known_completion_tokens=0,total_tokens=None,
        missing_token_usage=0,usage_complete=not invoked or receipt is not None,healthy_http=not invoked or receipt is not None,
        local_attempt_count_unknown=invoked and receipt is None,remote_execution_unknown=invoked and receipt is None,
        remote_execution_unknown_attempts=0,extraction_responses=0,admission_responses=0)
    attempts=receipt.get('attempts') if receipt else []
    if invoked and (not isinstance(attempts,list) or not attempts):
        result.update(local_attempt_count_unknown=True,usage_complete=False,healthy_http=False);attempts=[]
    for attempt in attempts:
        entries=[('extraction',attempt.get('extraction'))];admission=attempt.get('admission')
        if not isinstance(admission,dict) or type(admission.get('called')) is not bool:
            result.update(local_attempt_count_unknown=True,healthy_http=False)
            if isinstance(admission,dict) and (admission.get('http_attempts') or admission.get('attempt_count')):
                entries.append(('admission',admission))
        elif admission['called']:entries.append(('admission',admission))
        elif admission.get('attempt_count',0) or admission.get('http_attempts',[]):
            entries.append(('admission',admission));result.update(local_attempt_count_unknown=True,healthy_http=False)
        for kind,response in entries:
            result[kind+'_responses']+=1
            if not isinstance(response,dict):
                result.update(local_attempt_count_unknown=True,usage_complete=False,healthy_http=False);continue
            http=response.get('http_attempts');count=response.get('attempt_count')
            if not isinstance(http,list):http=[];result['local_attempt_count_unknown']=True
            if type(count) is not int or count!=len(http) or not http:result['local_attempt_count_unknown']=True
            result['observed_requests']+=len(http)
            healthy=(count==1 and len(http)==1 and response.get('ok') is True and response.get('error')==''
                and response.get('finish_reason')=='stop' and response.get('refusal') is False
                and response.get('output_mode')=='json_object'
                and response.get('raw_response')==response.get('raw_completion')
                and response.get('output_contract')==('claim_extraction_v2' if kind=='extraction' else 'claim_admission_v1'))
            if schema_hashes is not None:
                healthy &= response.get('schema_sha256')==schema_hashes.get(response.get('output_contract'))
                nested=response.get('structured_output')
                healthy &= isinstance(nested,dict) and all(response.get(k)==v for k,v in nested.items())
            if not http:result['missing_token_usage']+=1;result['usage_complete']=False
            for raw in http:
                unknown=raw.get('execution_certainty') not in ('not_connected','response_received')
                result['remote_execution_unknown_attempts']+=int(unknown)
                healthy &= raw.get('http_status')==200 and raw.get('curl_code')==0 and raw.get('execution_certainty')=='response_received'
                try:body=json.loads(raw['response_body'])
                except (ValueError,KeyError,TypeError):body={}
                if not isinstance(body,dict):body={}
                try:
                    choice=body['choices'][0];message=choice['message']
                    if not isinstance(choice,dict) or not isinstance(message,dict):raise ValueError('malformed HTTP choice')
                    healthy &= (choice.get('finish_reason')=='stop' and not message.get('refusal')
                        and message.get('content')==response.get('raw_completion')
                        and response.get('raw_http_response')==raw['response_body'])
                except (ValueError,KeyError,TypeError,IndexError):healthy=False
                try:
                    usage=body['usage'];values=[usage[k] for k in ('prompt_tokens','completion_tokens','total_tokens')]
                    if not all(type(v) is int and v>=0 for v in values) or values[0]+values[1]!=values[2] or values[2]<=0:
                        raise ValueError('invalid raw token usage')
                    result['known_prompt_tokens']+=values[0];result['known_completion_tokens']+=values[1];result['known_tokens']+=values[2]
                    if any(response.get(k)!=usage[k] for k in usage if k in ('prompt_tokens','completion_tokens','total_tokens')):
                        raise ValueError('raw/native usage mismatch')
                except (ValueError,KeyError,TypeError):result['missing_token_usage']+=1;result['usage_complete']=False;healthy=False
            result['healthy_http'] &= bool(healthy)
    result['remote_execution_unknown'] |= bool(result['remote_execution_unknown_attempts'] or result['local_attempt_count_unknown'])
    result['usage_complete'] &= not result['local_attempt_count_unknown'];result['healthy_http'] &= not result['local_attempt_count_unknown']
    if result['usage_complete']:result['total_tokens']=result['known_tokens']
    return result


def current_core(candidate_sha):
    cores=list((ROOT/'build/python/starling').glob('_core*.so'))
    if (not isinstance(candidate_sha,str) or len(candidate_sha)!=64 or len(cores)!=1 or sha(cores[0])!=candidate_sha):
        raise ValueError('explicit validated candidate core SHA must match the unique current core')
    return cores[0]


def source_paths():
    paths={ROOT/name for name in IMPLEMENTATION}
    for directory in ('src','include','python','bindings/python','cmake','migrations'):
        paths.update(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts
            and p.suffix in ('.cpp','.hpp','.h','.py','.in','.cmake','.sql'))
    paths.update(ROOT/name for name in ('CMakeLists.txt','build/CMakeCache.txt',
        'tests/cpp/test_claim_batch_target_units.cpp','tests/python/test_claim_batch_target_units.py') if (ROOT/name).is_file())
    return sorted(paths)


def seal(out,stage,state='complete'):
    if (out/'seal.json').exists():raise ValueError('output already sealed')
    write(out/'seal.json',dict(schema='r58-paired-seal-v1',stage=stage,state=state,files=inventory(out)))


def verify_seal(out):
    value=read(out/'seal.json');actual=inventory(out);actual.pop('seal.json',None)
    if value.get('schema')!='r58-paired-seal-v1' or value.get('state') not in ('complete','incomplete') or value.get('files')!=actual:
        raise ValueError('paired seal identity/file set mismatch')
    return value


def make_policy(core,config,arm):
    policy=helpers.make_policy(core,config)
    if not hasattr(policy,'claim_batch_target_units'):raise ValueError('candidate core lacks native target-unit policy')
    policy.claim_batch_target_units=arm=='B'
    return policy


def native_plans(core,inputs,config):
    plans={}
    for holder,source in inputs.items():
        plans[holder]={}
        for arm in ARMS:
            plan=json.loads(core.claim_extraction_batch_plan(source['payload'],make_policy(core,config,arm)))
            original=source['original_plan'];profile=plan.get('claim_batch_prompt_profile')
            if ((arm=='B' and profile!=PROFILE) or (arm=='A' and 'claim_batch_prompt_profile' in plan)
                or plan.get('claim_batch_size')!=8 or plan.get('claim_protocol_retry_budget')!=1
                or plan.get('source_payload_hash')!=source['binding']['payload_sha256']
                or plan.get('source_units')!=original['source_units'] or plan.get('batches')!=original['batches']):
                raise ValueError('native paired source/batch/profile drift')
            plans[holder][arm]=plan
    fixed_tasks(plans)
    return plans


def schema_identity(core):
    return {name:dict(schema=core.structured_output_schema(kind),sha256=core.structured_output_schema_sha256(kind))
        for name,kind in [('claim_extraction_v2',core.OutputContractKind.ClaimExtractionV2),
                          ('claim_admission_v1',core.OutputContractKind.ClaimAdmissionV1)]}


def prepare(out,core_sha256=None,evidence=()):
    out=new_output(out);core_path=current_core(core_sha256);inputs=fixed_inputs()
    sources={p.relative_to(ROOT).as_posix():sha(p) for p in source_paths()}
    evidence_sources={str(Path(p).resolve()):sha(p) for p in evidence}
    config={**FIXED, 'core_sha256':core_sha256,'created_at':inputs['Mum']['config']['created_at']}
    out.mkdir(parents=True)
    try:
        write(out/'stage.json',dict(stage='prepare'))
        for name in sources:copy_file(ROOT/name,out/'source'/name)
        for path in (ROOT/'python/starling').rglob('*.py'):
            if '__pycache__' not in path.parts:copy_file(path,out/'frozen/python/starling'/path.relative_to(ROOT/'python/starling'))
        copy_file(core_path,out/'frozen/python/starling'/core_path.name)
        for name in IMPLEMENTATION:
            if name.startswith('scripts/'):copy_file(ROOT/name,out/'frozen'/name)
        for index,path in enumerate(evidence_sources):copy_file(Path(path),out/'evidence'/f'{index}-{Path(path).name}')
        for holder,source in inputs.items():
            path=out/'inputs'/holder;path.mkdir(parents=True)
            (path/'payload.txt').write_bytes(source['payload'].encode())
            copy_file(source['database'],path/'source.db')
            copy_file(Path(source['binding']['path'])/'seal.json',path/'historical-seal.json')
            write(path/'binding.json',source['binding']);write(path/'receipt.json',source['receipt'])
            write(path/'original-plan.json',source['original_plan']);write(path/'original-config.json',source['config'])
        identity=dict(core_sha256=core_sha256,current_core=str(core_path.resolve()),source_files=sources,
            frozen_files=inventory(out/'frozen'),input_files=inventory(out/'inputs'),
            evidence_sources=evidence_sources,evidence_files=inventory(out/'evidence'))
        write(out/'identity.json',identity);write(out/'config.json',config)
        core,runtime=helpers.load_frozen(out,identity);plans=native_plans(core,inputs,config)
        write(out/'plans.json',plans);write(out/'tasks.json',fixed_tasks(plans));write(out/'schemas.json',schema_identity(core))
        summary=dict(stage='prepare',state='complete',external_requests=0,task_count=6,request_upper_bound=BUDGET,
            core_sha256=core_sha256,candidate_quality_claim='caller supplied candidate; prepare does not establish core quality')
        write(out/'summary.json',summary);validate_prepared(out,require_current=True);seal(out,'prepare')
        return summary
    except BaseException:
        (out/'exception.txt').write_text(traceback.format_exc());seal(out,'prepare','incomplete');raise


def validate_prepared(out,require_current=False):
    identity=read(out/'identity.json');config=read(out/'config.json');inputs=fixed_inputs()
    expected={**FIXED,'core_sha256':identity['core_sha256'],'created_at':inputs['Mum']['config']['created_at']}
    if config!=expected:raise ValueError('prepared fixed extraction policy mismatch')
    if (inventory(out/'source')!=identity['source_files'] or inventory(out/'frozen')!=identity['frozen_files']
        or inventory(out/'inputs')!=identity['input_files'] or inventory(out/'evidence')!=identity['evidence_files']):
        raise ValueError('frozen source/runtime/input/evidence mismatch')
    if require_current:
        if str(current_core(identity['core_sha256']).resolve())!=identity['current_core']:raise ValueError('candidate core path drift')
        if {p.relative_to(ROOT).as_posix():sha(p) for p in source_paths()}!=identity['source_files']:
            raise ValueError('current source identity drift')
        if any(sha(p)!=digest for p,digest in identity['evidence_sources'].items()):raise ValueError('validation evidence changed')
    for holder,source in inputs.items():
        path=out/'inputs'/holder
        for name,value in [('binding.json',source['binding']),('receipt.json',source['receipt']),
            ('original-plan.json',source['original_plan']),('original-config.json',source['config'])]:
            if read(path/name)!=value:raise ValueError('historical prepared input mismatch')
        if (sha(path/'source.db')!=source['binding']['database_sha256']
            or sha(path/'historical-seal.json')!=source['binding']['seal_sha256']
            or (path/'payload.txt').read_bytes()!=source['payload'].encode()):raise ValueError('historical prepared byte identity mismatch')
    core,runtime=helpers.load_frozen(out,identity);plans=native_plans(core,inputs,config);tasks=fixed_tasks(plans)
    if read(out/'plans.json')!=plans or read(out/'tasks.json')!=tasks or read(out/'schemas.json')!=schema_identity(core):
        raise ValueError('recomputed native plan/task/schema mismatch')
    return dict(prepared=out,core=core,runtime=runtime,identity=identity,config=config,inputs=inputs,plans=plans,tasks=tasks)


def make_adapter(core,config):
    return helpers.make_extract_adapter(core,config)


def remember_prepare(checked,rt,task):
    return checked['core'].memory_remember_prepare(rt.adapter,tenant_id=TENANT,holder_id=task['holder'],
        interlocutor='',adapter_name='r58_paired_probe',source_prefix='r58_paired_probe',
        created_at_iso8601=checked['config']['created_at'],payload=checked['inputs'][task['holder']]['payload'].encode())


def remember_commit(checked,rt,adapter,task,prepared,result):
    return checked['core'].memory_remember_commit(rt.adapter,adapter,tenant_id=TENANT,holder_id=task['holder'],
        interlocutor='',prepared=prepared,llm_result=result,policy=make_policy(checked['core'],checked['config'],task['arm']))


def database_proof(path,checked,task,prepared,commit):
    with immutable(path) as db:
        db.row_factory=sqlite3.Row
        engrams=db.execute('SELECT id,tenant_id,payload_inline FROM engrams').fetchall()
        rows=db.execute('SELECT id,tenant_id,holder_id,semantic_claim_json FROM statements ORDER BY id').fetchall()
        stored_sources=[dict(row) for row in db.execute('SELECT * FROM engrams')]
        stored_statements=[dict(row) for row in db.execute('SELECT * FROM statements ORDER BY id')]
        attempts=db.execute('SELECT count(*) FROM extraction_attempt').fetchone()[0]
    if prepared is None:
        if engrams or rows:raise ValueError('database contains records without native prepare evidence')
    elif [tuple(row) for row in engrams]!=[(prepared['engram_ref'],TENANT,checked['inputs'][task['holder']]['payload'].encode())]:
        raise ValueError('database payload differs from fixed holder source')
    if commit is None:
        if rows:raise ValueError('statements without commit receipt')
    elif (prepared is None or commit.get('engram_ref')!=prepared['engram_ref']
        or sorted(commit.get('statement_ids',[]))!=[row[0] for row in rows]
        or commit.get('source_preserved') is not True or attempts<1
        or commit.get('extraction_failed') is True and rows):raise ValueError('native commit/database proof mismatch')
    claims=[]
    for _,tenant,holder,raw in rows:
        if tenant!=TENANT or holder!=task['holder']:raise ValueError('database claim tenant/holder mismatch')
        claim=json.loads(raw)
        if claim.get('source_span',{}).get('engram_ref')!=prepared['engram_ref']:
            raise ValueError('database claim source engram mismatch')
        claim['source_span']['engram_ref']='<validated task source>'
        claims.append(claim)
    def normalize(value):
        if isinstance(value,dict):return {k:normalize(v) for k,v in value.items()}
        if isinstance(value,list):return [normalize(v) for v in value]
        if isinstance(value,bytes):return dict(payload_sha256=text_sha(value.decode()),payload_bytes=len(value))
        return '<validated task source>' if prepared and value==prepared['engram_ref'] else value
    def columns(row,excluded):
        return {key:normalize(json.loads(value) if key.endswith('_json') and value is not None else value)
                for key,value in row.items() if key not in excluded}
    # Fresh statement UUIDs and wall-clock maintenance timestamps differ on replay.
    # All semantic, evidence, source-time, governance and source-engram fields are compared.
    dynamic=('id','created_at','updated_at','last_accessed')
    statements=[columns(row,dynamic) for row in stored_statements]
    return dict(database_sha256=sha(path),statement_count=len(rows),extraction_attempt_count=attempts,
        claims=sorted(claims,key=lambda r:json.dumps(r,sort_keys=True)),
        statement_rows=sorted(statements,key=lambda r:json.dumps(r,sort_keys=True)),
        source_rows=[columns(row,('id',)) for row in stored_sources],excluded_statement_replay_fields=list(dynamic),
        source_payload_sha256=checked['inputs'][task['holder']]['binding']['payload_sha256'])


RESPONSE_VOLATILE={'attempt_count','http_attempts','prompt_tokens','completion_tokens','total_tokens','latency_ms','raw_http_response'}


def semantic_receipt(receipt):
    result=json.loads(json.dumps(receipt))
    for attempt in result.get('attempts',[]):
        for kind in ('extraction','admission'):
            if isinstance(attempt.get(kind),dict):
                for key in RESPONSE_VOLATILE:attempt[kind].pop(key,None)
                nested=attempt[kind].get('structured_output')
                if isinstance(nested,dict):
                    for key in RESPONSE_VOLATILE:nested.pop(key,None)
    return result


def native_replay(checked,task,receipt,commit,proof):
    if receipt is None or commit is None or proof is None:return dict(verified=False,reason='incomplete native receipt/commit/database')
    core=checked['core'];fake=core.FakeLLMAdapter();responses={}
    for attempt in receipt.get('attempts',[]):
        for kind in ('extraction','admission'):
            response=attempt.get(kind)
            if kind=='admission' and isinstance(response,dict) and response.get('called') is False:continue
            if not isinstance(response,dict) or not isinstance(response.get('raw_response'),str):
                return dict(verified=False,reason='incomplete response cannot be replayed')
            prompt=response.get('prompt');digest=response.get('prompt_input_hash')
            if not isinstance(prompt,str) or core.Extractor.compute_prompt_input_hash(prompt)!=digest:
                raise ValueError('native request prompt/hash mismatch')
            stable={k:v for k,v in response.items() if k not in RESPONSE_VOLATILE}
            if digest in responses and responses[digest]!=stable:raise ValueError('conflicting responses for one task prompt hash')
            responses[digest]=stable
            value=core.LLMResponse(response['raw_response'],response['ok'],response['error'])
            for key in ('finish_reason','refusal','raw_completion','capability_evidence_id'):setattr(value,key,response.get(key,'' if key!='refusal' else False))
            fake.set_response_object(digest,value)
    with tempfile.TemporaryDirectory(prefix='r58-native-replay-') as scratch:
        path=Path(scratch)/'replay.db';rt=checked['runtime']._build_local_store_sqlite_runtime(path);rt.start()
        try:
            prepared=remember_prepare(checked,rt,task)
            result=core.memory_extract_llm(rt.adapter,fake,'',task['holder'],checked['inputs'][task['holder']]['payload'].encode(),
                make_policy(core,checked['config'],task['arm']))
            actual=json.loads(core.claim_extraction_receipt(result));actual_commit=remember_commit(checked,rt,fake,task,prepared,result)
            if semantic_receipt(actual)!=semantic_receipt(receipt):raise ValueError('native semantic/prompt/batch replay mismatch')
            stable_commit=lambda value:{k:v for k,v in value.items() if k not in ('engram_ref','statement_ids')}
            if stable_commit(actual_commit)!=stable_commit(commit):raise ValueError('native commit replay mismatch')
            snapshot=Path(scratch)/'frozen.db'
            with closing(sqlite3.connect(path)) as source,closing(sqlite3.connect(snapshot)) as target:source.backup(target)
            actual_proof=database_proof(snapshot,checked,task,dict(engram_ref=prepared.engram_ref),actual_commit)
            if {k:v for k,v in proof.items() if k!='database_sha256'}!={k:v for k,v in actual_proof.items() if k!='database_sha256'}:
                raise ValueError('native persisted claim/source replay mismatch')
        finally:
            stop=getattr(rt,'stop',None)
            if callable(stop):stop()
    return dict(verified=True,reason='per-task native FakeLLM semantic replay; original HTTP accounting remains separate')


def analyze_task(out,checked,task):
    started=read(out/'started.json');reservation=started.get('reservation')
    if (started.get('task')!=task or type(started.get('native_entry_invoked')) is not bool
        or reservation!=dict(id=reservation.get('id'),state='reserved',upper_bound=task['request_upper_bound'])):
        raise ValueError('task start/reservation identity mismatch')
    receipt=read(out/'native-receipt.json') if (out/'native-receipt.json').exists() else None
    commit=read(out/'commit.json') if (out/'commit.json').exists() else None
    prepared=read(out/'remember-prepare.json') if (out/'remember-prepare.json').exists() else None
    cost=raw_cost(receipt,started['native_entry_invoked'],{k:v['sha256'] for k,v in schema_identity(checked['core']).items()});proof=None;errors=[]
    if (out/'frozen.db').exists():
        try:proof=database_proof(out/'frozen.db',checked,task,prepared,commit)
        except Exception as exc:errors.append(f'{type(exc).__name__}: {exc}')
    replay=dict(verified=False,reason='missing native evidence')
    if receipt is not None:
        expected=checked['plans'][task['holder']][task['arm']]
        if (receipt.get('claim_batch_plan')!=expected or receipt.get('source_payload_hash')!=expected['source_payload_hash']
            or receipt.get('holder')!=task['holder'] or receipt.get('claim_batch_size')!=8
            or (task['arm']=='B' and receipt.get('claim_batch_prompt_profile')!=PROFILE)
            or (task['arm']=='A' and 'claim_batch_prompt_profile' in receipt)):
            errors.append('native receipt fixed plan/profile/holder mismatch')
        try:replay=native_replay(checked,task,receipt,commit,proof)
        except Exception as exc:errors.append(f'{type(exc).__name__}: {exc}')
    healthy=(not errors and not (out/'failure.json').exists() and replay['verified'] and cost['healthy_http'] and cost['usage_complete']
        and not cost['local_attempt_count_unknown'] and not cost['remote_execution_unknown']
        and cost['observed_requests']<=task['request_upper_bound'] and commit is not None and proof is not None)
    status='technical_failure';count=proof['statement_count'] if proof else 0
    attempts=receipt.get('attempts',[]) if receipt else []
    failure_stage=('admission' if attempts and attempts[-1].get('admission',{}).get('called') is True else 'extraction')
    if healthy:
        if receipt.get('claim_batches_complete') is True and commit.get('extraction_failed') is False and not receipt.get('persistence_error'):
            status='passed' if task['arm']=='A' or count>0 else 'empty_candidate'
        elif (failure_stage=='extraction' and receipt.get('failure_category') in ('schema_failure','envelope_failure','batch_scope_failure')
              and commit.get('extraction_failed') is True
              and count==0 and not receipt.get('persistence_error')):status='protocol_failure'
    return dict(**task,status=status,native_entry_invoked=started['native_entry_invoked'],reservation=reservation,
        accounting=cost,native_replay=replay,database=proof,statement_count=count,evidence_errors=errors,
        failure_stage=failure_stage,failure_category=receipt.get('failure_category') if receipt else None,
        protocol_error_attempts=sum(bool(a.get('errors')) for a in attempts),
        protocol_correction_requests=len(attempts)-len({a.get('batch_index') for a in attempts}),
        candidate_count=sum(len((a.get('candidates') or {}).get('statements',[])) for a in attempts),retained_count=sum(len(a.get('retained') or []) for a in attempts),
        semantic_rejections=sum(len(a.get('semantic_rejections') or []) for a in attempts),
        admission_rejections=sum(a.get('admission',{}).get('semantic_rejected',0) for a in attempts),
        source_clause_ids=sorted({c.get('clause_id','') for c in proof['claims']}) if proof else [])


def execute_task(checked,task,out,ledger):
    out.mkdir(parents=True);reservation=None;started=None;rt=None
    with tempfile.TemporaryDirectory(prefix='r58-probe-task-') as scratch:
        live=Path(scratch)/'live.db'
        try:
            core=checked['core'];rt=checked['runtime']._build_local_store_sqlite_runtime(live);rt.start()
            prepared=remember_prepare(checked,rt,task)
            write(out/'remember-prepare.json',{k:getattr(prepared,k) for k in ('engram_ref','outcome','should_extract','created_at_iso8601')})
            if prepared.should_extract is not True:raise ValueError('native prepare did not authorize extraction')
            reservation=ledger.reserve(task['task_id'],'belief_batches',task['request_upper_bound'])
            if reservation.get('state')!='reserved':raise ValueError('fixed task reservation exhausted')
            started=dict(task=task,reservation=reservation,native_entry_invoked=False);write(out/'started.json',started)
            adapter=make_adapter(core,checked['config'])
            started['native_entry_invoked']=True;write(out/'started.json',started)
            result=core.memory_extract_llm(rt.adapter,adapter,'',task['holder'],checked['inputs'][task['holder']]['payload'].encode(),
                make_policy(core,checked['config'],task['arm']))
            write(out/'native-receipt.json',json.loads(core.claim_extraction_receipt(result)))
            write(out/'commit.json',remember_commit(checked,rt,adapter,task,prepared,result))
        except BaseException as exc:
            write(out/'failure.json',dict(error=f'{type(exc).__name__}: {exc}'))
        finally:
            if live.exists():
                backup(live,out/'frozen.db')
            if rt is not None:
                stop=getattr(rt,'stop',None)
                if callable(stop):stop()
    if started is None:raise ValueError('task failed before durable reservation/start; inspect failure evidence')
    try:result=analyze_task(out,checked,task)
    except Exception as exc:
        write(out/'analysis-failure.json',dict(error=f'{type(exc).__name__}: {exc}'));raise
    cost=result['accounting']
    if cost['local_attempt_count_unknown'] or cost['observed_requests']>task['request_upper_bound']:ledger.charge_upper(reservation['id'])
    else:ledger.settle(reservation['id'],cost['observed_requests'])
    write(out/'terminal.json',result)
    return result


def backup(live,target):
    with closing(sqlite3.connect(live)) as source,closing(sqlite3.connect(target)) as destination:source.backup(destination)


def partial_analysis_audit(path,checked,task):
    """An interrupted analyzer leaves raw costs inspectable, but no verified semantic terminal."""
    started=read(path/'started.json');reservation=started.get('reservation',{})
    if (started.get('task')!=task or type(started.get('native_entry_invoked')) is not bool
        or reservation!=dict(id=reservation.get('id'),state='reserved',upper_bound=task['request_upper_bound'])):
        raise ValueError('partial task start/reservation identity mismatch')
    receipt=read(path/'native-receipt.json') if (path/'native-receipt.json').exists() else None
    cost=raw_cost(receipt,started['native_entry_invoked'],{k:v['sha256'] for k,v in schema_identity(checked['core']).items()})
    failure=read(path/'analysis-failure.json')
    return dict(**task,status='technical_failure',artifact_state='partial',evidence_valid=False,
        native_entry_invoked=started['native_entry_invoked'],reservation=reservation,accounting=cost,
        native_replay=dict(verified=False,reason='task analysis aborted; saved semantic evidence remains unverified'),
        statement_count=None,database_sha256=sha(path/'frozen.db') if (path/'frozen.db').exists() else None,
        evidence_errors=['analysis failure: '+failure['error']])


def read_ledger(out):
    with immutable(out/'request-ledger.sqlite') as db:
        rows=[dict(zip(('id','scope','stage','upper_bound','actual','state'),row)) for row in db.execute(
            'SELECT id,scope,stage,upper_bound,actual,state FROM reservations ORDER BY id')]
    committed=reserved=charged=0
    for row in rows:
        upper,actual,state=row['upper_bound'],row['actual'],row['state']
        if type(upper) is not int or upper<0 or state not in ('reserved','settled','charged_upper'):raise ValueError('invalid ledger row')
        if state=='settled':
            if type(actual) is not int or not 0<=actual<=upper:raise ValueError('invalid ledger settlement')
            committed+=actual
        elif state=='charged_upper':committed+=upper;charged+=upper
        else:reserved+=upper
    return rows,dict(budget=BUDGET,committed=committed,reserved=reserved,charged_upper=charged,remaining=BUDGET-committed-reserved)


def summarize(out,checked):
    reservations,ledger=read_ledger(out);results=[];tasks=checked['tasks'];failures=[]
    if len(reservations)>6 or ledger['remaining']<0:raise ValueError('over-budget/task ledger')
    for index,reservation in enumerate(reservations):
        task=tasks[index];path=out/'tasks'/task['task_id']
        if (reservation['id']!=index+1 or reservation['scope']!=task['task_id'] or reservation['stage']!='belief_batches'
            or reservation['upper_bound']!=task['request_upper_bound']):raise ValueError('fixed task reservation order/bound mismatch')
        if index and not allow_next(tasks[index-1],results[-1]):raise ValueError('task invoked after mandatory stop')
        if (path/'started.json').exists():
            journal=read(path/'started.json').get('reservation')
            if (not isinstance(journal,dict) or type(journal.get('id')) is not int or type(journal.get('upper_bound')) is not int
                or journal!=dict(id=reservation['id'],state='reserved',upper_bound=reservation['upper_bound'])):
                raise ValueError('started reservation does not match exact SQLite ledger identity')
        if not (path/'started.json').exists():
            cost=raw_cost(None,True)
            result=dict(**task,status='technical_failure',accounting=cost,native_replay=dict(verified=False,reason='missing durable start'),
                statement_count=0,evidence_errors=['reservation exists without start evidence'])
        elif (path/'analysis-failure.json').exists():result=partial_analysis_audit(path,checked,task);cost=result['accounting']
        else:result=analyze_task(path,checked,task);cost=result['accounting']
        expected=('charged_upper',None) if cost['local_attempt_count_unknown'] or cost['observed_requests']>task['request_upper_bound'] else ('settled',cost['observed_requests'])
        if (reservation['state'],reservation['actual'])!=expected:
            interrupted=(out/'failure.json').exists() and not (path/'terminal.json').exists()
            if reservation['state']=='reserved':failures.append(task['task_id']+': unresolved reservation')
            elif interrupted and reservation['state']=='charged_upper' and reservation['actual'] is None:
                failures.append(task['task_id']+': conservative upper charge after settlement interruption')
            else:raise ValueError('raw HTTP/task ledger settlement mismatch')
        if (path/'terminal.json').exists() and read(path/'terminal.json')!=result:raise ValueError('recomputed native task terminal mismatch')
        results.append(result)
    attempted={p.name for p in (out/'tasks').iterdir()} if (out/'tasks').exists() else set()
    unreserved=attempted-{t['task_id'] for t in tasks[:len(reservations)]}
    if unreserved:
        expected_next=tasks[len(reservations)]['task_id'] if len(reservations)<6 else None
        if unreserved!={expected_next}:raise ValueError('unexpected task artifacts outside fixed execution prefix')
        failures.append(expected_next+': setup failed before reservation')
    if (out/'failure.json').exists():failures.append('stage exception: '+read(out/'failure.json')['error'])
    if len(results)<6 and results and allow_next(tasks[len(results)-1],results[-1]) and not failures:
        raise ValueError('execution stopped without a failure or fixed stop condition')
    missing_terminals=[r['task_id'] for r in results if not (out/'tasks'/r['task_id']/'terminal.json').exists()]
    candidate=[r for r in results if r['arm']=='B'];passed=len(candidate)==3 and all(r['status']=='passed' for r in candidate) and not failures and not missing_terminals
    accounting=[r['accounting'] for r in results];complete=all(a['usage_complete'] for a in accounting)
    known=sum(a['known_tokens'] for a in accounting)
    return dict(stage='run',state='complete' if passed else 'incomplete',status='paired_probe_passed' if passed else 'paired_probe_stopped',
        candidate_passed=passed,tasks=results,unexecuted_tasks=[t['task_id'] for t in tasks[len(results):]],stage_failures=failures,
        missing_terminal_tasks=missing_terminals,
        observed_requests=sum(a['observed_requests'] for a in accounting),known_tokens=known,total_tokens=known if complete else None,
        usage_complete=complete,local_attempt_count_unknown=any(a['local_attempt_count_unknown'] for a in accounting),
        remote_execution_unknown=any(a['remote_execution_unknown'] for a in accounting),ledger=ledger,
        limitation='Six historical development-source technical probes; no reliability, baseline, semantic recall or QA gain claim')


def run(prepared,out):
    out=new_output(out);prepared=Path(prepared).resolve();checked=check(prepared,'prepare');validate_prepared(prepared,require_current=True)
    out.mkdir(parents=True);write(out/'stage.json',dict(stage='run',input=str(prepared),input_seal_sha256=sha(prepared/'seal.json')))
    copy_file(prepared/'seal.json',out/'prepare-seal.json')
    for name in ('config.json','identity.json','plans.json','tasks.json','schemas.json'):copy_file(prepared/name,out/name)
    ledger=helpers.baseline.BudgetLedger(out/'request-ledger.sqlite',BUDGET)
    try:
        for task in checked['tasks']:
            result=execute_task(checked,task,out/'tasks'/task['task_id'],ledger)
            print(f"{task['task_id']}: {result['status']}",flush=True)
            if not allow_next(task,result):break
        validate_prepared(prepared,require_current=True)
    except BaseException as exc:write(out/'failure.json',dict(error=f'{type(exc).__name__}: {exc}'))
    for reservation in read_ledger(out)[0]:
        if reservation['state']=='reserved':
            path=out/'tasks'/reservation['scope'];receipt_path=path/'native-receipt.json';started_path=path/'started.json'
            receipt=read(receipt_path) if receipt_path.exists() else None
            invoked=read(started_path)['native_entry_invoked'] if started_path.exists() else True
            cost=raw_cost(receipt,invoked)
            try:
                if cost['local_attempt_count_unknown'] or cost['observed_requests']>reservation['upper_bound']:ledger.charge_upper(reservation['id'])
                else:ledger.settle(reservation['id'],cost['observed_requests'])
            except Exception:
                try:ledger.charge_upper(reservation['id'])
                except Exception:pass  # The read-only audit reports the durable reservation as unresolved.
    summary=summarize(out,checked);write(out/'summary.json',summary);seal(out,'run',summary['state']);return summary


def check(out,expected_stage=None):
    out=Path(out).resolve();sealed=verify_seal(out);stage=read(out/'stage.json')
    if stage.get('stage')!=sealed.get('stage'):raise ValueError('stage/seal mismatch')
    if expected_stage and (stage['stage']!=expected_stage or sealed['state']!='complete'):raise ValueError('incomplete or wrong input stage')
    if stage['stage']=='prepare':
        if sealed['state']!='complete':raise ValueError('incomplete prepare cannot supply a runtime')
        checked=validate_prepared(out);summary=dict(stage='prepare',state='complete',external_requests=0,task_count=6,
            request_upper_bound=BUDGET,core_sha256=checked['identity']['core_sha256'],
            candidate_quality_claim='caller supplied candidate; prepare does not establish core quality')
    elif stage['stage']=='run':
        prepared=Path(stage['input']).resolve()
        if prepared==out:raise ValueError('cyclic stage input')
        checked=check(prepared,'prepare')
        if stage.get('input_seal_sha256')!=sha(prepared/'seal.json') or sha(out/'prepare-seal.json')!=sha(prepared/'seal.json'):
            raise ValueError('prepare identity drift')
        for name in ('config.json','identity.json','plans.json','tasks.json','schemas.json'):
            if sha(out/name)!=sha(prepared/name):raise ValueError('run fixed input copy drift')
        summary=summarize(out,checked)
    else:raise ValueError('unknown paired probe stage')
    if read(out/'summary.json')!=summary or sealed['state']!=summary['state']:raise ValueError('recomputed paired summary mismatch')
    verify_seal(out)
    return dict(**checked,summary=summary) if 'summary' not in checked else {**checked,'summary':summary}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);stages=parser.add_subparsers(dest='stage',required=True)
    p=stages.add_parser('prepare');p.add_argument('--out',type=Path,required=True);p.add_argument('--core-sha256',required=True)
    p.add_argument('--evidence',type=Path,action='append',default=[])
    p=stages.add_parser('run');p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p=stages.add_parser('check');p.add_argument('--input',type=Path,required=True)
    args=parser.parse_args(argv)
    summary=(prepare(args.out,args.core_sha256,args.evidence) if args.stage=='prepare' else
             run(args.input,args.out) if args.stage=='run' else check(args.input)['summary'])
    print(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2));return int(summary['state']!='complete')


if __name__=='__main__':raise SystemExit(main())
