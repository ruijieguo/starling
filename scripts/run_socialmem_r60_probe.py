#!/usr/bin/env python3
"""R6.0 candidate profile probe for complete early scopes; real provider calls are explicit."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
R60 = ROOT / 'scripts/run_socialmem_r60_expanded.py'
spec = importlib.util.spec_from_file_location('r60_expanded_probe_runtime', R60)
r60 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r60)

CORE_SHA256 = r60.CORE_SHA256
PROFILE = r60.PROFILE
DEFAULT_SCOPE_LIMIT = 2


def _write(path: Path, value):
    r60.write(path, value)


def run(prepared, out, scope_limit=DEFAULT_SCOPE_LIMIT):
    out = r60.new_output(out)
    checked = r60.check(Path(prepared), 'prepare', require_current=True)
    if type(scope_limit) is not int or scope_limit < 1 or scope_limit > len(checked['groups']):
        raise ValueError('invalid R6.0 probe scope limit')
    out.mkdir(parents=True)
    selected = checked['groups'][:scope_limit]
    stage = dict(stage='probe', input=str(Path(prepared).resolve()),
                 input_seal_sha256=checked['seal_sha256'], scope_limit=scope_limit)
    _write(out / 'stage.json', stage)
    _write(out / 'prepare-seal.json', r60.read(Path(prepared) / 'seal.json'))
    _write(out / 'config.json', r60.read(Path(prepared) / 'config.json'))
    _write(out / 'identity.json', r60.read(Path(prepared) / 'identity.json'))
    _write(out / 'execution-plan.json', dict(stage='probe', workers=1,
        groups=[g['group_id'] for g in selected], core_sha256=CORE_SHA256,
        claim_batch_prompt_profile=PROFILE, scope_limit=scope_limit,
        build_budget=r60.BUILD_BUDGET))
    ledger = r60.make_ledger(out / 'request-ledger.sqlite')
    results = {}
    for index, group in enumerate(selected):
        result = r60.run_scope(checked, group, out / 'runs' / group['group_id'], ledger)
        results[group['group_id']] = result
        print(f'probe scopes: {index + 1}/{scope_limit}; {group["group_id"]}; {result["status"]}', flush=True)
        if result['status'] != 'passed':
            break
    complete = len(results) == scope_limit and all(v['status'] == 'passed' for v in results.values())
    ledger_rows = r60.old.ledger_rows(ledger.path)
    summary = dict(stage='probe', state='complete' if complete else 'incomplete',
        core_sha256=CORE_SHA256, claim_batch_prompt_profile=PROFILE,
        scope_limit=scope_limit, selected_scopes=[g['group_id'] for g in selected],
        completed_scopes=[gid for gid, value in results.items() if value['status'] == 'passed'],
        unexecuted_scopes=[g['group_id'] for g in selected[len(results):]],
        scopes=results, ledger=r60.previous.read_ledger(ledger.path, r60.BUILD_BUDGET),
        reservations=ledger_rows, external_requests=sum(
            value['accounting']['observed_native_requests'] for value in results.values()),
        provider='dashscope', model=checked['config'].get('extract_model'),
        limitation='R6.0 early-scope protocol/semantic probe; no retrieval or QA score.')
    _write(out / 'summary.json', summary)
    r60.seal_output(out, 'probe', summary['state'])
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--scope-limit', type=int, default=DEFAULT_SCOPE_LIMIT)
    args = parser.parse_args(argv)
    result = run(args.input, args.out, args.scope_limit)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return int(result['state'] != 'complete')


if __name__ == '__main__':
    raise SystemExit(main())
