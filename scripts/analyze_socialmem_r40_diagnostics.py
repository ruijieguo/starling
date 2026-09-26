#!/usr/bin/env python3
"""R4 封存后的只读统计：精确来源回指、网络分层与技术失败。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def coverage(record, recall, claims):
    anchors=[(a.get('speaker_display_name'),a.get('turn_id'))
             for a in record['source'].get('evidence_anchors',[])]
    sources={(r.get('speaker'),r.get('turn_id')) for r in recall.get('source_refs',[]) if r.get('turn_id')}
    statements=set()
    for sid in recall.get('statement_ids',[]):
        turn=claims.get(sid,{}).get('source_turn') or {}
        if turn.get('turn_id'):
            statements.add((turn.get('speaker'),turn['turn_id']))
    return {'anchors':len(anchors),'source_hits':sum(a in sources for a in anchors),
            'statement_only_hits':sum(a in statements-sources for a in anchors),
            'union_hits':sum(a in sources|statements for a in anchors)}


def diagnose(work):
    work=Path(work).resolve()
    seal=read(work/'completion-seal.json')
    for name,digest in seal['files'].items():
        if sha(work/name)!=digest:
            raise ValueError('封存发生漂移: '+name)
    records=read(work/'sample.json');old=read(work/'parent-results.json')
    rows={(r['item_id'],r['arm']):r for p in (work/'receipts').glob('*.json') for r in [read(p)]}
    claims={}
    for g in read(work/'groups.json'):
        db=work/'source-databases'/g['group_id']/'frozen.db'
        # 不创建 WAL/SHM，不修改已冻结数据库或评测清单。
        with sqlite3.connect(f'{db.as_uri()}?mode=ro&immutable=1',uri=True) as conn:
            claims[g['group_id']]={sid:json.loads(raw) for sid,raw in
                conn.execute('SELECT id,semantic_claim_json FROM statements') if raw}
    details=[];networks=defaultdict(Counter);by_type=defaultdict(Counter)
    failures=[];usage=defaultdict(Counter);changed=[]
    for record in records:
        key=record['item_id'];ctx=read(work/'recalls'/(hashlib.sha256(key.encode()).hexdigest()+'.json'))
        rec=ctx.get('recall',{});network=record['source']['network_id'];qtype=record['query_type']
        item={'item_id':key,'question':record['question'],'query_type':qtype,'network_id':network,
              'r35':coverage(record,old[key]['recall'],claims[ctx['group_id']]),
              'r40':coverage(record,rec,claims[ctx['group_id']]),
              'profile':rec.get('source_diagnostics',{}).get('evidence_profile',{})}
        for tag in ('r35','r40'):
            for k,v in item[tag].items():by_type[qtype][tag+'_'+k]+=v
        states={'r35':{'correct':old[key]['correct'],'status':old[key]['status']}}
        networks[network]['n']+=1;networks[network]['r35_correct']+=old[key]['correct']
        for arm in ('retrieval','native_answer'):
            row=rows[key,arm];states[arm]={'correct':row['correct'],'status':row['status']}
            networks[network][arm+'_correct']+=row['correct']
            networks[network][arm+'_failures']+=row['status']!='ok'
            if row['status']!='ok':
                failures.append({'item_id':key,'arm':arm,'query_type':qtype,'status':row['status'],
                    'error':row.get('error'),'finish_reason':row.get('answer',{}).get('response',{}).get('finish_reason')})
            for stage in ('answer','judge'):
                response=row.get(stage,{}).get('response',{})
                for field in ('prompt_tokens','completion_tokens','total_tokens','latency_ms'):
                    usage[arm][stage+'_'+field]+=response.get(field,0)
                usage[arm][stage+'_responses']+=bool(response)
                if response.get('finish_reason')=='length':usage[arm][stage+'_length']+=1
        item['outcomes']=states;details.append(item)
        if len({v['correct'] for v in states.values()})>1:changed.append(item)
    return {'method':'精确 (speaker, turn_id)；声明回指只验证出处，不证明其包含完整答案要点',
        'work':str(work),'completion_seal_sha256':sha(work/'completion-seal.json'),
        'diagnostic_script_sha256':sha(__file__),'by_network':dict(networks),
        'coverage_by_query_type':dict(by_type),'coverage_total':dict(sum(by_type.values(),Counter())),
        'usage':dict(usage),'failures':failures,'changed_questions':changed,'details':details}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.resolve().is_relative_to(args.work.resolve()):
        raise ValueError('补充统计必须写入封存目录之外')
    result=diagnose(args.work)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('details','changed_questions')},ensure_ascii=False,indent=2))
