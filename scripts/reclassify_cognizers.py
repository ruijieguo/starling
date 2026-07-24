#!/usr/bin/env python3
"""存量认知体一次性 LLM 重分类归档(PR2 / Task 10)。

背景:PR1 之前,name_resolver 把每条抽取语句的 subject 无条件注册成 kind=human
认知体,污染 cognizers 表(dogfood 实测 1283 行几乎全是 eval 指标垃圾如
"iter1 Q1 improvement" / "c20 composite score")。PR1 已从源头止血(抽取时判
subject_kind);本脚本清理存量。

设计(plan-eng-review 锁定):
- **纯 LLM 分类为准,不做「有边保护」** —— 生产库里唯一有边的 6 个认知体
  (Alice/Bob/Carol/Dana/Frank/Sam)是 seed_demo 的演示假人,不是真实主体;
  「有边=真主体」的假设不成立,故删除该保护。真实性完全由 LLM 判据保证。
- **可逆**:归档 = UPDATE archived_at=<ts>(不 DELETE);恢复 = archived_at=NULL。
- **幂等重入**:已归档的行(archived_at IS NOT NULL)默认跳过。
- **纯逻辑 / 真 LLM 分离**:plan_archive() 是纯函数(单测覆盖);classify_names()
  真调 LLM(不测,Clash 黑洞换时刻重跑)。

真 LLM,不进 CI。key 从环境读不打印。

用法:
    # dry-run(只打印计划,不写库):
    OPENAI_API_KEY=... OPENAI_BASE_URL=... \\
        python scripts/reclassify_cognizers.py --db ~/.starling/dashboard.db --tenant default --dry-run
    # 真执行:
    OPENAI_API_KEY=... OPENAI_BASE_URL=... \\
        python scripts/reclassify_cognizers.py --db ~/.starling/dashboard.db --tenant default --apply
    # 回滚(恢复本次归档):
    python scripts/reclassify_cognizers.py --db ~/.starling/dashboard.db --tenant default --restore-all
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timezone

# 认知体判据(与 PR1 belief prompt 的 SUBJECT_KIND 段一致):能持有信念的主体。
CLASSIFY_PROMPT = """You classify whether each NAME denotes a COGNIZER (an entity that can hold beliefs) or a non-cognizer ENTITY.

- cognizer: a person (human), an AI agent (e.g. Claude, the assistant), an organization/team (group), a role, or the narrator's self. Something that can hold beliefs / mental states.
- entity: a technical thing, product, library, device, metric, score, number, version string, or abstract thing — anything that CANNOT hold beliefs.

For each input name output one JSON object: {"name": <verbatim input>, "is_cognizer": true|false, "cognizer_kind": "human"|"agent"|"group"|"role"|"self"|null}
cognizer_kind is null when is_cognizer is false.

Examples:
- "Alice" -> {"name":"Alice","is_cognizer":true,"cognizer_kind":"human"}
- "the eng team" -> {"name":"the eng team","is_cognizer":true,"cognizer_kind":"group"}
- "Claude" -> {"name":"Claude","is_cognizer":true,"cognizer_kind":"agent"}
- "H800 memory" -> {"name":"H800 memory","is_cognizer":false,"cognizer_kind":null}
- "macro4 score" -> {"name":"macro4 score","is_cognizer":false,"cognizer_kind":null}
- "iter3 total time" -> {"name":"iter3 total time","is_cognizer":false,"cognizer_kind":null}
- "TE 2.14.1" -> {"name":"TE 2.14.1","is_cognizer":false,"cognizer_kind":null}

Output ONLY a JSON array, one object per input name, same order.

NAMES:
{names}"""

VALID_KINDS = {"human", "agent", "group", "role", "self", "external"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# 纯逻辑(单测覆盖):给定 DB 行 + LLM 分类结果,算出归档 id 集 + kind 更新集。
# 不碰 DB、不碰网络。
# ---------------------------------------------------------------------------
def plan_archive(
    rows: list[dict],
    classification: dict[str, dict],
) -> tuple[list[str], list[tuple[str, str]]]:
    """rows: [{id, canonical_name, kind, archived_at}]。
    classification: {name: {is_cognizer: bool, cognizer_kind: str|None}}。

    返回 (archive_ids, kind_updates):
      archive_ids   —— 判为 entity(非认知体)→ 归档的 cognizer id 列表。
      kind_updates  —— 判为 cognizer 但 kind 与库中不同 → (id, new_kind) 列表。

    规则(无「有边保护」——纯 LLM 分类为准):
      - 已归档(archived_at 非空)→ 跳过(幂等重入)。
      - 分类缺失(LLM 没返回该 name)→ 保守跳过(不归档,留待重跑),不误杀。
      - is_cognizer=False → 归档。
      - is_cognizer=True 且 cognizer_kind 合法且 != 库中 kind → kind 更新。
    """
    archive_ids: list[str] = []
    kind_updates: list[tuple[str, str]] = []
    for r in rows:
        if r.get("archived_at"):
            continue  # 幂等:已归档跳过
        verdict = classification.get(r["canonical_name"])
        if verdict is None:
            continue  # 分类缺失:保守不动(留待重跑),不误杀
        if not verdict.get("is_cognizer", False):
            archive_ids.append(r["id"])
            continue
        # 是认知体:看 kind 要不要更准
        new_kind = verdict.get("cognizer_kind")
        if new_kind in VALID_KINDS and new_kind != r.get("kind"):
            kind_updates.append((r["id"], new_kind))
    return archive_ids, kind_updates


# ---------------------------------------------------------------------------
# 真 LLM(不测):批量把 name 分类成 cognizer/entity。
# ---------------------------------------------------------------------------
def _classify_batch_once(names: list[str], base_url: str, api_key: str, model: str) -> list[dict]:
    names_block = "\n".join(names)
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": CLASSIFY_PROMPT.replace("{names}", names_block)}],
        "temperature": 0,
        "max_tokens": 8192,
    }).encode("utf-8")
    req = urllib.request.Request(
        url=f"{base_url}/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json\n"):
            content = content[len("json\n"):]
    return json.loads(content)


def classify_names(names: list[str], base_url: str, api_key: str, model: str,
                   batch_size: int = 40) -> dict[str, dict]:
    """分批分类,返回 {name: {is_cognizer, cognizer_kind}}。失败的批跳过(留待重跑)。"""
    out: dict[str, dict] = {}
    for i in range(0, len(names), batch_size):
        batch = names[i:i + batch_size]
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                for obj in _classify_batch_once(batch, base_url, api_key, model):
                    nm = obj.get("name")
                    if isinstance(nm, str):
                        out[nm] = {"is_cognizer": bool(obj.get("is_cognizer", False)),
                                   "cognizer_kind": obj.get("cognizer_kind")}
                last_exc = None
                break
            except Exception as e:  # noqa: BLE001
                last_exc = e
                if attempt < 2:
                    time.sleep(2 ** attempt)
        if last_exc is not None:
            print(f"WARN: batch [{i}:{i+len(batch)}] classify failed: {last_exc}", file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# DB 读写(薄封装,便于 plan_archive 单测隔离)。
# ---------------------------------------------------------------------------
def load_rows(db: str, tenant: str) -> list[dict]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT id, canonical_name, kind, archived_at FROM cognizers WHERE tenant_id=?",
            (tenant,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def apply_plan(db: str, tenant: str, archive_ids: list[str],
               kind_updates: list[tuple[str, str]], ts: str) -> None:
    conn = sqlite3.connect(db)
    try:
        with conn:  # 单事务:全成或全不成
            conn.executemany(
                "UPDATE cognizers SET archived_at=? WHERE id=? AND tenant_id=?",
                [(ts, cid, tenant) for cid in archive_ids])
            conn.executemany(
                "UPDATE cognizers SET kind=? WHERE id=? AND tenant_id=?",
                [(k, cid, tenant) for cid, k in kind_updates])
    finally:
        conn.close()


def restore_all(db: str, tenant: str) -> int:
    conn = sqlite3.connect(db)
    try:
        with conn:
            cur = conn.execute(
                "UPDATE cognizers SET archived_at=NULL WHERE tenant_id=? AND archived_at IS NOT NULL",
                (tenant,))
            return cur.rowcount
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="存量认知体一次性 LLM 重分类归档(真 LLM,非 CI)")
    p.add_argument("--db", required=True)
    p.add_argument("--tenant", default="default")
    p.add_argument("--model", default=os.environ.get("STARLING_EVAL_MODEL", "gpt-5.5"))
    p.add_argument("--batch-size", type=int, default=40)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只分类+打印计划,不写库")
    mode.add_argument("--apply", action="store_true", help="真执行归档+kind 更新")
    mode.add_argument("--restore-all", action="store_true", help="恢复所有归档(archived_at=NULL)")
    args = p.parse_args(argv)

    if args.restore_all:
        n = restore_all(args.db, args.tenant)
        print(f"restored {n} archived cognizers (archived_at=NULL)", file=sys.stderr)
        return 0

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set(不打印 key)", file=sys.stderr)
        return 2

    rows = load_rows(args.db, args.tenant)
    active = [r for r in rows if not r.get("archived_at")]
    names = sorted({r["canonical_name"] for r in active})
    print(f"tenant={args.tenant}: {len(rows)} cognizers ({len(active)} active), "
          f"{len(names)} distinct names → classifying...", file=sys.stderr)

    classification = classify_names(names, base_url, api_key, args.model, args.batch_size)
    archive_ids, kind_updates = plan_archive(rows, classification)

    print(f"\n计划:归档 {len(archive_ids)} 个(entity),更新 kind {len(kind_updates)} 个,"
          f"分类覆盖 {len(classification)}/{len(names)} names", file=sys.stderr)
    # 抽样打印前 20 个归档名 + 所有 kind 更新
    arch_names = {r["id"]: r["canonical_name"] for r in rows}
    print("\n--- 归档样本(前 20)---")
    for cid in archive_ids[:20]:
        print(f"  archive: {arch_names.get(cid)}")
    if kind_updates:
        print("\n--- kind 更新(全部)---")
        for cid, k in kind_updates:
            print(f"  {arch_names.get(cid)}: → {k}")

    if args.dry_run:
        print("\n[dry-run] 未写库。加 --apply 真执行。", file=sys.stderr)
        return 0

    ts = utc_now()
    apply_plan(args.db, args.tenant, archive_ids, kind_updates, ts)
    print(f"\n[applied ts={ts}] 归档 {len(archive_ids)} + kind 更新 {len(kind_updates)}。"
          f"回滚:--restore-all", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
