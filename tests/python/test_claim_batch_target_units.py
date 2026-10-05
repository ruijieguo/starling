"""Python carries the target-unit policy; all prompt, parsing and commit logic is native."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest
from starling import _core, runtime
from starling.extractor.config import ExtractionConfig

SOURCE='Mina: I feel sad about leaving.\nMina: I feel happy about arriving.\nMina: I feel calm about staying.'


def target_policy():
    assert hasattr(_core.ValidationPolicy(),'claim_batch_target_units'),'native target-unit policy missing'
    p=_core.ValidationPolicy();p.semantic_claim_contract=p.preserve_text_objects=True
    p.claim_batch_size=1;p.claim_batch_target_units=True;return p


def data(prompt):
    return json.JSONDecoder().raw_decode(prompt.split('\nSOURCE_DATA_JSON:\n',1)[1])[0]


def test_native_default_false_and_old_prompt_plan_byte_identity():
    assert hasattr(_core.ValidationPolicy(),'claim_batch_target_units'),'native target-unit policy missing'
    p=_core.ValidationPolicy();assert p.claim_batch_target_units is False
    p.semantic_claim_contract=p.preserve_text_objects=True;p.claim_batch_size=1;p.claim_protocol_retry_budget=1
    # Re-recorded on purpose on 2026-10-05: the final format check gained the NEG/NEGATED reminder line.
    # The batch-plan pin on the next line is unchanged.
    assert hashlib.sha256(_core.claim_extraction_prompt(SOURCE,'Mina').encode()).hexdigest()=='f0736f29fd8c5eebce36b9fedfd150255c936e145d4eca47162806f1fbd9852f'
    assert hashlib.sha256(_core.claim_extraction_batch_plan(SOURCE,p).encode()).hexdigest()=='38691044ca106deee345d1dad67cd0680caf7fb52e91df6de5e2c987d4c9e092'


def test_dataclass_maps_flag_and_native_validation_rejects_invalid_combinations():
    assert 'claim_batch_target_units' in ExtractionConfig.__dataclass_fields__
    assert ExtractionConfig().to_native_policy().claim_batch_target_units is False
    c=ExtractionConfig(semantic_claim_contract=True,preserve_text_objects=True,claim_batch_size=8,claim_batch_target_units=True)
    assert c.to_native_policy().claim_batch_target_units is True
    for semantic,size in [(False,0),(False,1),(True,0)]:
        with pytest.raises(ValueError):
            ExtractionConfig(semantic_claim_contract=semantic,preserve_text_objects=True,claim_batch_size=size,claim_batch_target_units=True)
    p=target_policy();p.claim_batch_size=0
    with pytest.raises(ValueError):p.validate()


def test_baseline_helper_only_maps_new_flag():
    path=Path(__file__).resolve().parents[2]/'scripts/run_socialmem_baseline.py'
    spec=importlib.util.spec_from_file_location('target_baseline_mapping',path)
    baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
    assert hasattr(baseline._build_extraction_config({}).to_native_policy(),'claim_batch_target_units')
    assert baseline._build_extraction_config({}).to_native_policy().claim_batch_target_units is False
    p=baseline._build_extraction_config(dict(semantic_claim_contract=True,preserve_text_objects=True,
        claim_batch_size=8,claim_batch_target_units=True)).to_native_policy()
    assert p.claim_batch_target_units is True
    with pytest.raises(ValueError):baseline._build_extraction_config(dict(claim_batch_target_units=True))


def test_native_fake_batches_expose_only_target_index_and_keep_source(tmp_path):
    p=target_policy();p.claim_output_mode=_core.OutputMode.JsonObject
    rt=runtime._build_local_store_sqlite_runtime(tmp_path/'targets.db');rt.start()
    fake=_core.FakeLLMAdapter();fake.set_default_response('{"schema_version":2,"statements":[]}')
    extracted=_core.memory_extract_llm(rt.adapter,fake,'','Mina',SOURCE.encode(),p)
    receipt=json.loads(_core.claim_extraction_receipt(extracted))
    assert receipt['claim_batches_complete'] and receipt['claim_batch_prompt_profile']=='target_units_statement_first_v1'
    assert receipt['claim_batch_plan']['claim_batch_prompt_profile']=='target_units_statement_first_v1'
    assert len(receipt['attempts'])==len(fake.structured_requests)==3
    for i,attempt in enumerate(receipt['attempts']):
        payload=data(attempt['extraction']['prompt'])
        assert payload['source']==SOURCE and payload['source_role']=='context_only'
        assert payload['target_clause_ids']==[f'c{i}']
        assert [u['clause_id'] for u in payload['source_units']]==[f'c{i}']
        assert not attempt['admission']['called']


def test_general_fact_channel_clears_target_flag_for_extraction_and_commit(tmp_path):
    source=SOURCE+' Water boils at 100 C.'
    p=target_policy();path=tmp_path/'channels.db';rt=runtime._build_local_store_sqlite_runtime(path);rt.start()
    fake=_core.FakeLLMAdapter();fake.set_default_response('{"schema_version":2,"statements":[]}')
    raw=json.dumps([dict(holder='Mina',holder_perspective='FIRST_PERSON',subject='water',subject_kind='entity',
        predicate='has_value',object='boiling point 100 C',modality='BELIEVES',polarity='POS',nesting_depth=0)])
    fake.set_response(_core.Extractor.compute_prompt_input_hash('GENERAL::Mina::'+source),raw)
    fake.set_response(_core.Extractor.compute_prompt_input_hash('EPISODIC::'+source),'[]')
    prepared=_core.memory_remember_prepare(rt.adapter,tenant_id='default',holder_id='Mina',interlocutor='',
        adapter_name='test',source_prefix='target-channel',created_at_iso8601='2099-01-01T00:00:00Z',payload=source.encode())
    bundle=_core.memory_remember_extract_all(rt.adapter,fake,'unused {convo}','EPISODIC::{passage}',
        'GENERAL::{self}::{convo}',holder_id='Mina',payload=source.encode(),policy=p)
    result=_core.memory_remember_commit_all(rt.adapter,fake,tenant_id='default',holder_id='Mina',interlocutor='',
        prepared=prepared,extracted=bundle,policy=p)
    assert not result['extraction_failed']
    with sqlite3.connect(path) as db:
        assert db.execute('select predicate,object_value,semantic_claim_json from statements').fetchall()==[
            ('has_value','boiling point 100 C',None)]
