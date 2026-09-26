#!/usr/bin/env python3
"""冻结及执行独立范围 schema 对照；语义、能力与 HTTP 均调用原生核心。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from eval_socialmem_scope_latency import (
    build_native_adapter, capture_preview, load_stage, require, write_json_new,
    canonical_sha256, file_sha256,
)
import probe_socialmem_output_capability as capability

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {"endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
          "model": "qwen3.7-plus", "timeout_ms": 120000, "max_tokens": 4096,
          "max_retries": 0, "temperature": 0, "output_mode": "json_schema_strict"}
SOURCE_IDS = ("Q9_a0b1c2d3_Marcus", "Q1_a5s1c1_Femi", "eval-029", "Q1_a5s1c1_Claudette")
EXPECTED_CORE_SHA256 = {
    'C0': '94749a715ae19ea57bdce350b00cf382f45fef2a520fe7bcb88d57c6df201cfe',
    'C1': '0b1b0aac125c67a2101e53cdf9a72deac23c37b956d631d2c74b1e11bbeff5d1',
}
EXPECTED_SOURCES_SHA256 = '2198e0a42ac11956d469c9fe6a80a4ccfc7d43f217ab82d62c15db07b7c3f556'
LIMITS = {'probe': 16, 'extract': 16, 'admission': 16, 'total': 48}


def read(path):
    return json.loads(Path(path).read_text())


def model_case(case):
    return {key: case[key] for key in ("id", "track", "holder", "passage")}


def schema_delta(before, after, path=""):
    if isinstance(before, dict) and isinstance(after, dict):
        return [change for key in sorted(before.keys() | after.keys())
                for change in schema_delta(before.get(key), after.get(key), path + "/" + key)]
    return [] if before == after else [(path, before, after)]


def classify_extraction(receipt):
    if not receipt["ok"]:
        return "transport_failure"
    if receipt.get("wire_error"):
        return "wire_failure"
    if (receipt.get("parse_result") or {}).get("errors"):
        return "parse_failure"
    return "parsed"


def invoke(action, plan_path, arm, out, *extra):
    command = [sys.executable, "-S", str(Path(__file__).resolve()), action,
               "--plan", str(plan_path), "--arm", arm, "--out", str(out), *map(str, extra)]
    result = subprocess.run(command, text=True, capture_output=True, timeout=1100)
    require(result.returncode == 0, "isolated worker failed: " + result.stderr[-3000:])
    return read(out)


def code_paths():
    scripts = [ROOT / "scripts" / name for name in (
        "run_socialmem_schema.py", "socialmem_run_guard.py", "eval_socialmem_r1b.py",
        "eval_socialmem_scope_latency.py", "probe_socialmem_output_capability.py")]
    native = [path for directory in ('src/extractor', 'include/starling/extractor',
                                     'src/net', 'include/starling/net')
              for path in sorted((ROOT / directory).glob('*'))
              if path.suffix in ('.cpp', '.hpp')]
    return scripts + native + [ROOT / 'bindings/python/bind_06_extractor.cpp']


def verify_plan(plan_path):
    from eval_socialmem_r1b import schedule_samples
    plan = read(plan_path)
    require(plan["schema_version"] == 1 and plan["config"] == CONFIG, "plan config drift")
    require(tuple(plan["arms"]) == ("C0", "C1"), "plan arm drift")
    require(tuple(case["id"] for case in plan["cases"]) == SOURCE_IDS, "plan source cohort drift")
    require(canonical_sha256(plan['cases']) == EXPECTED_SOURCES_SHA256, 'authorized source content drift')
    require(plan['schedule'] == schedule_samples(plan['cases'], arms=('C0', 'C1')), 'schedule drift')
    require(plan['limits'] == LIMITS, 'limits drift')
    body = {k: v for k, v in plan.items() if k != "plan_sha256"}
    require(canonical_sha256(body) == plan["plan_sha256"], "plan digest drift")
    for name, expected in plan["file_sha256"].items():
        require(file_sha256(name) == expected, f"plan file drift: {name}")
    for arm, frozen in plan["arms"].items():
        require(frozen['core_sha256'] == EXPECTED_CORE_SHA256[arm], 'authorized core identity drift')
        require(file_sha256(frozen["core_path"]) == frozen["core_sha256"], "core file drift")
        require(frozen["config"] == CONFIG, "arm config drift")
        require(frozen["sources"] == {c["id"]: canonical_sha256(model_case(c)) for c in plan["cases"]},
                "source identity drift")
    return plan


def freeze(stages, cases_path, out):
    from eval_socialmem_r1b import schedule_samples
    out = Path(out).resolve()
    require(not out.exists(), "freeze output already exists")
    cases = [model_case(c) for c in read(cases_path)]
    require(tuple(c["id"] for c in cases) == SOURCE_IDS, "fixed four sources required")
    require(canonical_sha256(cases) == EXPECTED_SOURCES_SHA256, 'authorized source content drift')
    require(len(stages) == 2, 'exactly two native stages required')
    for arm, stage in zip(('C0', 'C1'), stages):
        modules = list((Path(stage) / 'python/starling').glob('_core*.so'))
        require(len(modules) == 1 and file_sha256(modules[0]) == EXPECTED_CORE_SHA256[arm],
                'authorized core identity drift')
    out.mkdir(parents=True)
    write_json_new(out / "cases.json", cases)
    previews = {}
    for arm, stage in zip(("C0", "C1"), stages):
        args = [sys.executable, "-S", str(Path(__file__).resolve()), "preview",
                "--stage", str(Path(stage).resolve()), "--cases", str(out / "cases.json"),
                "--out", str(out / f"{arm}-preview.json")]
        subprocess.run(args, check=True, timeout=120)
        previews[arm] = read(out / f"{arm}-preview.json")
        require(previews[arm]['identity']['core_sha256'] == EXPECTED_CORE_SHA256[arm],
                'authorized loaded core identity drift')
    left, right = previews.values()
    delta = schema_delta(left["identity"]["schema"], right["identity"]["schema"])
    prefix = "/properties/statements/items/properties/evidence/properties/scope_markers/"
    require(delta == [(prefix + "minItems", None, 1), (prefix + "uniqueItems", None, True)],
            "unexpected native schema delta")
    require(left["admission_schema_sha256"] == right["admission_schema_sha256"], "admission schema drift")
    require(left["identity"]["core_sha256"] != right["identity"]["core_sha256"], "identical cores")
    for a, b in zip(left["requests"], right["requests"]):
        aa, bb = json.loads(json.dumps(a["body"])), json.loads(json.dumps(b["body"]))
        aa.pop("response_format", None); bb.pop("response_format", None)
        require(aa == bb, "non-schema request/prompt drift")
        require(a["path"] == b["path"], "request path drift")
    plan = {"schema_version": 1, "experiment": "scope_schema_alignment", "config": CONFIG,
            "created_at": datetime.now(timezone.utc).isoformat(), "cases": cases,
            "schedule": schedule_samples(cases, arms=("C0", "C1")), "arms": {},
            "schema_delta": delta, "limits": dict(LIMITS),
            "file_sha256": {str(p.resolve()): file_sha256(p) for p in code_paths()}}
    for p in [Path(cases_path), ROOT / "docs/superpowers/specs/2026-09-16-scope-schema-alignment-design.md"]:
        # 冻结副本脱离后续报告更新。
        target = out / p.name
        if target.name != 'cases.json':
            target.write_bytes(p.read_bytes())
        plan["file_sha256"][str(target)] = file_sha256(target)
    for arm, preview in previews.items():
        require(preview["probe_request_count"] == 8 and preview["extraction_request_count"] == 4,
                "preview request shape drift")
        frozen = {"identity_version":1, "arm":arm, "stage":str(Path(stages[("C0","C1").index(arm)]).resolve()),
                  "core_path":preview["identity"]["core_path"],
                  "core_sha256":preview["identity"]["core_sha256"], "config":CONFIG,
                  "schemas":{"claim_extraction_v2":preview["identity"]["schema_sha256"],
                             "claim_admission_v1":preview["admission_schema_sha256"]},
                  "sources":{c["id"]:canonical_sha256(c) for c in cases},
                  "prompt_sha256":{c["id"]:r["prompt_sha256"] for c,r in zip(cases,preview["receipts"])},
                  "code_sha256":{str(p.resolve()):file_sha256(p) for p in code_paths()},
                  "preview": str(out / f"{arm}-preview.json"),
                  "preview_sha256":file_sha256(out / f"{arm}-preview.json")}
        plan["arms"][arm] = frozen
        plan["file_sha256"][frozen["core_path"]] = frozen["core_sha256"]
        plan["file_sha256"][frozen["preview"]] = frozen["preview_sha256"]
    plan["plan_sha256"] = canonical_sha256(plan)
    write_json_new(out / "plan.json", plan)
    return plan


def validate_frozen(core, config, frozen, *, case=None, report_path=None, report_sha256=None, at=None):
    from socialmem_run_guard import verify_identity, verify_capability
    verify_identity(core, config, frozen, case)
    if report_path is None:
        return True
    readiness = verify_capability(core, config, frozen, report_path, report_sha256, at=at)
    require(readiness["ready"], "capability gate failed: " + str(readiness["reasons"]))
    return readiness


def worker(action, plan_path, arm, out, *, run_dir, sequence=None):
    from socialmem_run_guard import RequestLedger, GuardedRequestGate
    from eval_socialmem_r1b import worker_sample
    plan = verify_plan(plan_path)
    frozen = plan["arms"][arm]
    core = load_stage(frozen["stage"])
    run_dir, out = Path(run_dir), Path(out)
    ledger = RequestLedger(run_dir / "requests.jsonl", plan["plan_sha256"])
    # adapter 唯一构造入口，配置快照来自同一原生 Config，不接受外部伪造。
    llm, config = build_native_adapter(core, model=CONFIG["model"], timeout_ms=CONFIG["timeout_ms"],
                                      endpoint=CONFIG["endpoint"], credential_env="DASHSCOPE_API_KEY")
    validate_frozen(core, config, frozen)
    if action == "probe":
        caps=[]
        for mode in ("json_object", "json_schema_strict"):
            for name, kind in capability.contract_values(core).items():
                validate_frozen(core, config, frozen)
                reservation = mode + ":" + name
                ledger.reserve(arm, "probe", reservation, 2)
                evidence = llm.probe_structured_output(core.StructuredOutputRequest(kind, capability.mode_value(core, mode)))
                value=json.loads(core.capability_evidence_json(evidence))
                write_json_new(run_dir / f"{arm}-{mode}-{name}.json", value)
                caps.append(value)
        report={"schema_version":1,"created_at":datetime.now(timezone.utc).isoformat(),
                "core_sha256":file_sha256(core.__file__),
                "transport":{k:config[k] for k in ('endpoint','model')},
                "schemas":{n:{"schema":json.loads(core.structured_output_schema(k)),
                              "sha256":core.structured_output_schema_sha256(k)}
                           for n,k in capability.contract_values(core).items()},
                "capabilities":caps,"request_count":sum(c['request_count'] for c in caps),
                "probe_max_retries":0,"quality":None}
        write_json_new(run_dir / f"{arm}-capability.json", report)
        readiness = capability.check_report(core, report, config, "json_schema_strict")
        result={"report":report,"readiness":readiness,"core_sha256":frozen['core_sha256']}
    elif action == "check":
        report_path=run_dir / f"{arm}-capability.json"
        gate=read(run_dir / "gate.json")[arm]
        require(file_sha256(report_path)==gate['report_sha256'], 'capability report file drift')
        result=validate_frozen(core,config,frozen,report_path=report_path,report_sha256=gate['report_sha256'])
    else:
        entry=plan['schedule'][sequence]
        require(entry['arm']==arm, 'schedule arm mismatch')
        case=entry['case']; report_path=run_dir / f"{arm}-capability.json"
        gate=read(run_dir / 'gate.json')[arm]
        at=datetime.fromisoformat(read(run_dir / 'batch-start.json')['at'])
        validate_frozen(core,config,frozen,case=case,report_path=report_path,
                        report_sha256=gate['report_sha256'],at=at)
        reserve = GuardedRequestGate(core, config, frozen, case=case, ledger=ledger,
            arm=arm, request_id=str(sequence), report_path=report_path,
            report_sha256=gate['report_sha256'], at=at)
        result=worker_sample(core,llm,config,case,artifact_dir=out.parent,
                             before_request=reserve)
        result['extraction_stage']=classify_extraction(result['extraction'])
        result['arm']=arm; result['sequence']=sequence
        result['core_sha256']=frozen['core_sha256']
        result['not_executed']=['persistence','embedding','retrieval','qa','judge']
    write_json_new(out, result)
    return result


def run(plan_path, out):
    from socialmem_run_guard import RequestLedger
    plan_path=Path(plan_path).resolve();out=Path(out).resolve()
    plan=verify_plan(plan_path)
    require(not out.exists(), 'run output already exists; no automatic resume')
    out.mkdir(parents=True)
    ledger=RequestLedger(out/'requests.jsonl',plan['plan_sha256'],create=True)
    results=[];gate={};status='stopped_capability_gate';error=None
    try:
        for arm in plan['arms']:
            package=invoke('probe',plan_path,arm,out/f'{arm}-probe.json','--run-dir',out)
            gate[arm]={'ready':package['readiness']['ready'],
                       'report_sha256':file_sha256(out/f'{arm}-capability.json')}
            print(json.dumps({'arm':arm,'readiness':package['readiness']},ensure_ascii=False),flush=True)
            if not gate[arm]['ready']:break
        write_json_new(out/'gate.json',gate)
        if len(gate)==2 and all(v['ready'] for v in gate.values()):
            for arm in plan['arms']:
                ready=invoke('check',plan_path,arm,out/f'{arm}-check.json','--run-dir',out)
                require(ready['ready'], 'capability gate expired before sample batch')
            write_json_new(out/'batch-start.json',{'at':datetime.now(timezone.utc).isoformat()})
            status='complete_with_observations'
            for i,entry in enumerate(plan['schedule']):
                path=out/f'sample-{i:02d}'/'result.json'
                result=invoke('sample',plan_path,entry['arm'],path,'--run-dir',out,'--sequence',i)
                results.append(result)
                print(json.dumps({'sequence':i,'arm':entry['arm'],'id':entry['case_id'],
                                  'status':result['status'],'retained':len(result['retained'])}),flush=True)
    except Exception as exc:
        status='stopped_error';error=f'{type(exc).__name__}: {exc}'
    summary={'status':status,'error':error,'plan_sha256':plan['plan_sha256'],
             'finished_at':datetime.now(timezone.utc).isoformat(),'budget':ledger.snapshot(),
             'samples_completed':len(results),'quality':None,'promotion_ready':False}
    write_json_new(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('preview','freeze','run','probe','check','sample'))
    p.add_argument('--out',type=Path,required=True);p.add_argument('--plan',type=Path)
    p.add_argument('--stage',type=Path);p.add_argument('--stages',nargs=2,type=Path)
    p.add_argument('--cases',type=Path);p.add_argument('--arm',choices=('C0','C1'))
    p.add_argument('--run-dir',type=Path);p.add_argument('--sequence',type=int)
    args=p.parse_args()
    if args.action=='preview':
        core=load_stage(args.stage)
        value=capture_preview(core,read(args.cases),model=CONFIG['model'],timeout_ms=CONFIG['timeout_ms'],intended_endpoint=CONFIG['endpoint'])
        value['admission_schema_sha256']=core.structured_output_schema_sha256(core.OutputContractKind.ClaimAdmissionV1)
        write_json_new(args.out,value)
    elif args.action=='freeze':freeze(args.stages,args.cases,args.out)
    elif args.action=='run':run(args.plan,args.out)
    else:worker(args.action,args.plan,args.arm,args.out,run_dir=args.run_dir,sequence=args.sequence)


if __name__=='__main__':
    main()
