#!/usr/bin/env python3
"""进攻层基准适配器(PR-4):把异构外部语料归一成 runner 吃的规范 record。

规范 record(eval_ladder / eval_ladder_pipeline 消费,以 longmemeval 为准):
  {item_id, subset, history:[{speaker,text,observed_at}], question,
   options:[...], answer:int, gold_statements?:[...], is_abstain?:bool}

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

from typing import Any


class AdapterError(ValueError):
    """语料缺必需字段时 fail-loud(不静默补默认值,避免错位跑通)。"""


def _require(row: dict, keys: tuple[str, ...], where: str) -> None:
    missing = [k for k in keys if k not in row]
    if missing:
        raise AdapterError(f"{where}: 缺必需字段 {missing};实际字段={sorted(row)}")


def _canonical(item_id: str, subset: str, history: list[dict], question: str,
               options: list[str], answer: int, *,
               gold_statements: list[dict] | None = None,
               is_abstain: bool = False) -> dict:
    """构造一条规范 record,统一校验答案索引与选项一致性。"""
    if not options:
        raise AdapterError(f"{item_id}: options 为空")
    if not is_abstain and not (0 <= answer < len(options)):
        raise AdapterError(f"{item_id}: answer={answer} 越界(options={len(options)})")
    rec = {
        "item_id": item_id, "subset": subset, "history": history,
        "question": question, "options": options, "answer": answer,
    }
    if gold_statements is not None:
        rec["gold_statements"] = gold_statements
    if is_abstain:
        rec["is_abstain"] = True
    return rec


# ---------------------------------------------------------------------------
# passthrough 类:已是规范形状,只做轻校验(catch 上游语料损坏)。
# ---------------------------------------------------------------------------
def adapt_passthrough(rows: list[dict], *, benchmark: str) -> list[dict]:
    out = []
    for i, r in enumerate(rows):
        _require(r, ("item_id", "question", "options", "answer"), f"{benchmark}[{i}]")
        out.append(_canonical(
            r["item_id"], r.get("subset", "default"), r.get("history", []),
            r["question"], r["options"], int(r["answer"]),
            gold_statements=r.get("gold_statements"),
            is_abstain=bool(r.get("is_abstain", False)),
        ))
    return out


# ---------------------------------------------------------------------------
# SocialMemBench:多方社会群组记忆(Starling 主场:归属/视角/知识边界)。
# 文档 schema(dataset card):
#   qa 行:           {qa_id, network_id, question, choices:[...], answer_idx, category}
#   conversations 行:{network_id, turn_idx, speaker, text, timestamp}
# 归一:按 network_id 把 conversations 聚成 history,附到该网络的每道 qa。
# ---------------------------------------------------------------------------
def adapt_socialmembench(qa_rows: list[dict], conversation_rows: list[dict]) -> list[dict]:
    # 先按 network_id 聚合会话轮 → history(按 turn_idx 排序)。
    by_net: dict[str, list[dict]] = {}
    for i, c in enumerate(conversation_rows):
        _require(c, ("network_id", "turn_idx", "speaker", "text"), f"socialmem.conv[{i}]")
        by_net.setdefault(c["network_id"], []).append(c)
    for net in by_net.values():
        net.sort(key=lambda t: t["turn_idx"])
    history_of = {
        net: [{"speaker": t["speaker"], "text": t["text"],
               "observed_at": t.get("timestamp", "1970-01-01T00:00:00Z")}
              for t in turns]
        for net, turns in by_net.items()
    }

    out = []
    for i, q in enumerate(qa_rows):
        _require(q, ("qa_id", "network_id", "question", "choices", "answer_idx"),
                 f"socialmem.qa[{i}]")
        net = q["network_id"]
        if net not in history_of:
            raise AdapterError(f"socialmem.qa[{i}]: network_id={net} 无对应会话")
        out.append(_canonical(
            str(q["qa_id"]), q.get("category", "social"), history_of[net],
            q["question"], list(q["choices"]), int(q["answer_idx"]),
        ))
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
    # socialmembench 需两张表,签名不同,调用方直接调 adapt_socialmembench。
}
