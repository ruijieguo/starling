#!/usr/bin/env python3
"""进攻层基准适配器(PR-4):把异构外部语料归一成 runner 吃的规范 record。

规范 record(eval_ladder / eval_ladder_pipeline 消费):
  {item_id, subset, history:[{speaker,text,observed_at}], question,
   answer_format:"multiple_choice"|"long_form"|"short_answer",
   options:[...],           # MC 非空;自由文本为空
   answer:int|str,          # MC=0-based 下标;自由文本=参考答案(judge 比对)
   gold_statements?:[...], is_abstain?:bool}

每个适配器只做 **I/O 归一**,不做评分/检索(那是 runner 的事)。真实数据集
的列名以各自 dataset card 为准;**下载真实数据后必须按实际列名校验**——本文件
按文档化 schema 映射,遇缺字段 fail-loud(不静默塞默认值,以免"跑通但错位")。

覆盖(数据可得性见 impl-spec §4.2):
  - longmemeval / locomo / beam:已是规范形状(或近似),passthrough + 轻校验。
  - socialmembench(HF anon4data,4 parquet:networks/personas/conversations/qa):
    多方社会群组记忆——Starling 主场。qa 行 join conversations 成 history。
  - memsyco(GitHub XMUDepLIT,JSONL,5 任务):记忆-证据冲突/弃答;标注了
    "有效记忆 / 冲突证据",可机械转 gold_statements(喂 S_star_oracle 台阶)。

设计:适配器吃**已加载的行**(list[dict]),不碰 parquet/JSONL 读取本身
(读取用 pandas/datasets,属 real-mode gated I/O)。这样归一逻辑可用合成
fixture 离线测(无需下载真实数据、无网络)。
"""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any


class AdapterError(ValueError):
    """语料缺必需字段时 fail-loud(不静默补默认值,避免错位跑通)。"""


def _require(row: dict, keys: tuple[str, ...], where: str) -> None:
    missing = [k for k in keys if k not in row]
    if missing:
        raise AdapterError(f"{where}: 缺必需字段 {missing};实际字段={sorted(row)}")


def _canonical(item_id: str, subset: str, history: list[dict], question: str,
               options: list[str], answer: int | str, *,
               answer_format: str = "multiple_choice",
               gold_statements: list[dict] | None = None,
               is_abstain: bool = False,
               query_type: str | None = None) -> dict:
    """构造一条规范 record。

    MC 题(answer_format=multiple_choice):options 非空,answer 为 0-based 下标(校验越界)。
    自由文本题(long_form/short_answer):options 空,answer 为参考文本(交给 judge 比对)。

    subset 是**打分/归因轴**(band 随之不同:确定性 MC=0.05、judge 自由文本=α_judge);
    query_type(可空)保留基准原生的认知任务分类,供报告二次细分——不参与打分,零信息损失。
    """
    if answer_format == "multiple_choice":
        if not options:
            raise AdapterError(f"{item_id}: MC options 为空")
        if not is_abstain and not (isinstance(answer, int) and 0 <= answer < len(options)):
            raise AdapterError(f"{item_id}: answer={answer!r} 越界(options={len(options)})")
    else:
        if options:
            raise AdapterError(f"{item_id}: 自由文本题 options 应为空,实得 {len(options)}")
        if not is_abstain and not isinstance(answer, str):
            raise AdapterError(
                f"{item_id}: 自由文本 answer 应为字符串,实得 {type(answer).__name__}")
    rec = {
        "item_id": item_id, "subset": subset, "history": history,
        "question": question, "options": options, "answer": answer,
        "answer_format": answer_format,
    }
    if gold_statements is not None:
        rec["gold_statements"] = gold_statements
    if is_abstain:
        rec["is_abstain"] = True
    if query_type is not None:
        rec["query_type"] = query_type
    return rec


# ---------------------------------------------------------------------------
# passthrough 类:已是规范形状,只做轻校验(catch 上游语料损坏)。
# ---------------------------------------------------------------------------
def adapt_passthrough(rows: list[dict], *, benchmark: str) -> list[dict]:
    """已是规范形状的语料:只过 _canonical 轻校验,不重写语义。

    **按 answer_format 分流**:MC 题 answer 是 0-based 下标(int() 归一容错字符串
    数字);自由文本题 answer 是参考文本,**不得** int()——那会把 817 道 long_form/
    short_answer 直接炸掉。query_type(基准原生认知分类)原样透传,零信息损失。"""
    out = []
    for i, r in enumerate(rows):
        _require(r, ("item_id", "question", "options", "answer"), f"{benchmark}[{i}]")
        fmt = r.get("answer_format", "multiple_choice")
        answer = int(r["answer"]) if fmt == "multiple_choice" else r["answer"]
        out.append(_canonical(
            r["item_id"], r.get("subset", "default"), r.get("history", []),
            r["question"], r["options"], answer,
            answer_format=fmt,
            gold_statements=r.get("gold_statements"),
            is_abstain=bool(r.get("is_abstain", False)),
            query_type=r.get("query_type"),
        ))
        for key in ("source", "evaluation_protocol"):
            if key in r:
                out[-1][key] = r[key]
    return out


def _parse_json(value: Any, where: str) -> Any:
    """真实 parquet 里 JSON 列以字符串落地;宽容已解析对象(合成 fixture 直接传 list/dict)。"""
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise AdapterError(f"{where}: JSON 解析失败 {exc}") from exc


# MC options_json 真实有三种编码(214 条 profile:184 dict / 12 list-of-str / 18 list-of-dict):
#   dict:        {"A": "Josh", "B": "Leon", ...}                ——键即字母,值即纯文本
#   list-of-str: ["A) Donna", "B) Lena", ...]                   ——每项前缀 "X) " 编码字母
#   list-of-dict:[{"option": "A", "name": "Derek"}, ...]        ——option=字母,name=纯文本
# 三者都归一成 (letters, options):letters=字母,options=对应纯文本。
_MC_PREFIX = re.compile(r"^\s*([A-Za-z])\s*[).:\-]\s*(.*)$", re.S)


def _mc_options(opts_raw: Any, where: str) -> tuple[list[str], list[str]]:
    """把 MC options_json(dict / 带 'X) ' 前缀的 list / list-of-dict)归一成 (letters, options)。"""
    if isinstance(opts_raw, dict):
        if not opts_raw:
            raise AdapterError(f"{where}: MC options dict 为空")
        letters = sorted(opts_raw)
        return letters, [str(opts_raw[k]) for k in letters]
    if isinstance(opts_raw, list):
        if not opts_raw:
            raise AdapterError(f"{where}: MC options list 为空")
        letters, options = [], []
        for item in opts_raw:
            if isinstance(item, dict):
                # list-of-dict:{"option": 字母, "name": 文本}
                if "option" not in item or "name" not in item:
                    raise AdapterError(
                        f"{where}: MC option dict 缺 option/name 键 {item!r}")
                letters.append(str(item["option"]).strip().upper())
                options.append(str(item["name"]).strip())
            else:
                m = _MC_PREFIX.match(str(item))
                if not m:
                    raise AdapterError(f"{where}: MC option 项无 'X)' 字母前缀 {item!r}")
                letters.append(m.group(1).upper())
                options.append(m.group(2).strip())
        if len(set(letters)) != len(letters):
            raise AdapterError(f"{where}: MC option 字母重复 {letters}")
        return letters, options
    raise AdapterError(f"{where}: MC options_json 非法类型 {type(opts_raw).__name__}")


# ---------------------------------------------------------------------------
# SocialMemBench:多方社会群组记忆(Starling 主场:归属/视角/知识边界)。
# 真实 schema(下载 4 parquet 后 profile 得,2026-07 校验):
#   qa 行(1031):{qa_id, network_id, query_type, question, answer(参考文本/解释),
#     answer_format:"multiple_choice"|"long_form"|"short_answer",
#     options_json(MC=dict '{"A":..}';自由文本='[]'),
#     correct_option(MC=字母 'C';自由文本=''或截断前缀,不可信),
#     evidence_anchors_json:[{session_index,turn_id,speaker_display_name,
#                             message_excerpt,relevance}]}
#   conv 行(7355):{network_id, session_index, turn_id, speaker_display_name,
#     message, message_index, timestamp}
# 归一:
#   - history:按 network_id 聚合,排序键 (session_index, message_index)。
#   - MC:options_json dict 按字母排序成 list;correct_option 字母 → 0-based 下标。
#   - 自由文本:options 空,answer=参考文本(交 judge);correct_option 弃用(截断)。
#   - gold_statements:**检索级(retrieval-level)**——从 evidence_anchors 派生,
#     holder=alice(统一记忆主,避免 planner 视角遮蔽误杀 oracle),subject=说话人,
#     predicate=said,object=原文摘录,observed_at 按 turn_id 查真实 timestamp。
#     每条带 _gold_level="retrieval" 如实标注:这不是抽取级蒸馏事实,而是"该看
#     哪些轮"的检索级 gold。因此 S_star_oracle 度量的是"检索到正确证据轮"的上界,
#     而非"抽取出正确事实"的上界——报告须照此口径解释(impl-spec / eval-plan)。
# ---------------------------------------------------------------------------
def adapt_socialmembench(qa_rows: list[dict], conversation_rows: list[dict]) -> list[dict]:
    # 先按 network_id 聚合会话轮 → history;同时建 turn_id → 真实 timestamp 映射。
    turn_source: dict[tuple[str, str], dict] = {}
    by_net: dict[str, list[dict]] = {}
    for i, c in enumerate(conversation_rows):
        _require(c, ("network_id", "turn_id", "session_index", "message_index",
                     "speaker_display_name", "message", "timestamp"),
                 f"socialmem.conv[{i}]")
        key = (c["network_id"], c["turn_id"])
        if key in turn_source:
            raise AdapterError(f"duplicate SocialMemBench turn: {key}")
        turn_source[key] = c
        by_net.setdefault(c["network_id"], []).append(c)
    for turns in by_net.values():
        turns.sort(key=lambda t: (int(t["session_index"]), int(t["message_index"])))
    history_of = {
        net: [{"speaker": t["speaker_display_name"], "text": t["message"],
               "observed_at": t["timestamp"], "turn_id": t["turn_id"],
               "session_index": int(t["session_index"]), "message_index": int(t["message_index"])}
              for t in turns]
        for net, turns in by_net.items()
    }

    id_counts = Counter(str(q.get("qa_id")) for q in qa_rows)
    seen_items = set()
    out = []
    for i, q in enumerate(qa_rows):
        _require(q, ("qa_id", "network_id", "query_type", "question", "answer",
                     "answer_format", "options_json", "correct_option",
                     "evidence_anchors_json"), f"socialmem.qa[{i}]")
        net = q["network_id"]
        source_id = str(q["qa_id"])
        item_id = f"{net}/{source_id}" if id_counts[source_id] > 1 else source_id
        if item_id in seen_items:
            raise AdapterError(f"duplicate SocialMemBench QA identity: {item_id}")
        seen_items.add(item_id)
        if net not in history_of:
            raise AdapterError(f"socialmem.qa[{i}]: network_id={net} 无对应会话")

        # gold:检索级,从 evidence_anchors 派生(observed_at 按 turn_id 查真时戳)。
        anchors = _parse_json(q["evidence_anchors_json"], f"socialmem.qa[{i}].anchors")
        gold = [{
            "holder": "alice",
            "subject": a.get("speaker_display_name", "unknown"),
            "predicate": "said",
            "object": a.get("message_excerpt", ""),
            "observed_at": turn_source.get((net, a.get("turn_id")), {}).get(
                "timestamp", "1970-01-01T00:00:00Z"),
            "turn_id": a.get("turn_id"),
            "session_index": turn_source.get((net, a.get("turn_id")), {}).get(
                "session_index", a.get("session_index")),
            "_gold_level": "retrieval",  # 如实标注:检索级,非抽取级蒸馏
        } for a in anchors]

        fmt = q["answer_format"]
        if fmt == "multiple_choice":
            opts_raw = _parse_json(q["options_json"], f"socialmem.qa[{i}].options")
            letters, options = _mc_options(opts_raw, f"socialmem.qa[{i}]")
            correct = q["correct_option"]
            if correct not in letters:
                raise AdapterError(
                    f"socialmem.qa[{i}]: correct_option={correct!r} 不在 {letters}")
            out.append(_canonical(
                item_id, "socialmem_mc", history_of[net],
                q["question"], options, letters.index(correct),
                answer_format="multiple_choice", gold_statements=gold or None,
                query_type=q["query_type"],
            ))
        elif fmt in ("long_form", "short_answer"):
            # 自由文本:answer=参考文本(judge 比对);correct_option 截断不可用。
            out.append(_canonical(
                item_id, "socialmem_free", history_of[net],
                q["question"], [], q["answer"],
                answer_format=fmt, gold_statements=gold or None,
                query_type=q["query_type"],
            ))
        else:
            raise AdapterError(f"socialmem.qa[{i}]: 未知 answer_format={fmt!r}")
        out[-1]["source"] = {
            "benchmark": "socialmembench", "network_id": net, "qa_id": q["qa_id"],
            "reference_answer": q["answer"], "correct_option": q["correct_option"],
            "evidence_anchors": anchors,
            "temporal_anchors": _parse_json(q.get("temporal_anchors_json", "[]"),
                                             f"socialmem.qa[{i}].temporal_anchors"),
        }
    return out


# ---------------------------------------------------------------------------
# MemSyco-Bench:记忆-证据冲突/弃答。文档 schema(JSONL,每行一任务):
#   {task_id, task_type, dialogue:[{speaker,text,ts}], question, options,
#    answer_idx, valid_memory:[{holder,subject,predicate,object,observed_at}]?,
#    is_unanswerable?}
# valid_memory → gold_statements(喂 S_star_oracle,隔离抽取税)。
# is_unanswerable → is_abstain(认识论诚实主张)。
# ---------------------------------------------------------------------------
def adapt_memsyco(rows: list[dict]) -> list[dict]:
    out = []
    for i, r in enumerate(rows):
        _require(r, ("task_id", "task_type", "question", "options"), f"memsyco[{i}]")
        is_abstain = bool(r.get("is_unanswerable", False))
        history = [{"speaker": t.get("speaker", "user"), "text": t.get("text", ""),
                    "observed_at": t.get("ts", "1970-01-01T00:00:00Z")}
                   for t in r.get("dialogue", [])]
        gold = r.get("valid_memory")  # 可空;None → 该题不参与 oracle 台阶
        out.append(_canonical(
            str(r["task_id"]), r["task_type"], history,
            r["question"], list(r["options"]),
            int(r.get("answer_idx", 0)),
            gold_statements=gold, is_abstain=is_abstain,
        ))
    return out


# 注册表:runner 侧按 --benchmark 选适配器。真实 I/O(parquet/jsonl 读取)
# 由 real-mode gated 调用方在装配时提供已加载的行。
ADAPTERS = {
    "longmemeval": lambda rows: adapt_passthrough(rows, benchmark="longmemeval"),
    "locomo": lambda rows: adapt_passthrough(rows, benchmark="locomo"),
    "beam": lambda rows: adapt_passthrough(rows, benchmark="beam"),
    "memsyco": adapt_memsyco,
    # socialmembench 需两张表(qa+conversations),签名不同,调用方直接调
    # adapt_socialmembench 归一成 jsonl;runner 再用 prenormalized 通道读那份 jsonl。
    "prenormalized": lambda rows: adapt_passthrough(rows, benchmark="prenormalized"),
}
