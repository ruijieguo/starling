"""保留集只能在开发门槛通过后评测同一个冻结候选。"""
import importlib.util,json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]

def module():
 p=ROOT/'scripts/run_socialmem_focus_validation.py';assert p.is_file(),'validation driver missing'
 spec=importlib.util.spec_from_file_location('focus_validation',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_development_gate():
 m=module();passed={'n':733,'delta':.1,'network_bootstrap_delta_95ci':[.06,.14]}
 m.validate_gate(passed)
 for field,value in [('n',732),('delta',.049),('network_bootstrap_delta_95ci',[-.01,.11])]:
  with pytest.raises(ValueError):m.validate_gate({**passed,field:value})

def test_only_request_budget_changes():
 m=module();old={'core_sha256':'a'*64,'source_strategy':'focused_window','http_budget':1314,'k':30}
 m.validate_config(old,{**old,'http_budget':534})
 for field,value in [('core_sha256','b'*64),('source_strategy','focused'),('http_budget',535),('k',60)]:
  with pytest.raises(ValueError):m.validate_config(old,{**old,'http_budget':534,field:value})

@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_all_reserved_questions_and_no_development_leakage():
 m=module();p=ROOT/'build/socialmem_20260917_baseline_recovered'
 records=[json.loads(l) for l in (p/'corpus.jsonl').read_text().splitlines()];split=json.loads((p/'network-split.json').read_text())
 selected=m.select_reserved(records,split);assert len(selected)==298
 assert len({r['source']['network_id'] for r in selected})==10
 assert not {r['source']['network_id'] for r in selected}&set(split['development_networks'])
 with pytest.raises(ValueError):m.select_reserved(records[:-1],split)
 with pytest.raises(ValueError):m.select_reserved(records+[records[0]],split)
 split['reserved_networks'][0]=split['development_networks'][0]
 with pytest.raises(ValueError):m.select_reserved(records,split)
