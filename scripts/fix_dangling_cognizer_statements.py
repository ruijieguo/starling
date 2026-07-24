#!/usr/bin/env python3
"""订正历史污染语句:subject_kind='cognizer' 但 subject 指向已归档(=entity)认知体
(PR3 / 认知体过度注册修复的收尾)。

背景:PR1 之前 name_resolver 把每条抽取语句的 subject 无条件当 cognizer 注册,
同时把 statements.subject_kind 焊死成 'cognizer'。PR2 归档了污染的 cognizer 节点
(1292 个技术实体),但**引用它们的语句仍标着 subject_kind='cognizer'**——这批
1686 条语句的 subject 是 `.181 GPU` / `/hdd free space` / `._* files` 这类技术
实体,却被 ToM 读路径(mentalizing_believe / second_order,按 subject_kind='cognizer'
筛)当成认知体信念读进来,GPU/硬盘被当认知主体推理。本脚本把它们的 subject_kind
订正为 'entity',与 subject 真实性质一致。

判据(与 PR2 归档同源):subject 指向【已归档】认知体 = 该 subject 已被 LLM 判为
非认知体,故其语句的 subject_kind 也应是 entity。

安全性(已在 PR3 调查中核实):
- 精确范围:仅 subject_kind='cognizer' 且 subject_id(存 canonical_name)命中已归档
  认知体名的行。
- 零同名歧义:没有「指向已归档、但同名还有活跃 cognizer」的行(核实=0),按 name
  批改不会误伤活跃认知体。
- 全部 nesting_depth=0:不碰二阶信念,改 subject_kind 不影响 ToM 嵌套链。
- object 侧无污染:object_kind='cognizer' 指向已归档=0。

可逆:--apply 把改动的 stmt id 写进审计文件(默认 <db>.pr3-fixed.json);
--restore <file> 读回,把这些 id 的 subject_kind 改回 'cognizer'。不 DELETE、不
加列(无需 migration)。

单写者要求:跑之前必须停 dashboard(launchd io.starling.dashboard + wedgewatch),
否则并发 upsert 会与本脚本写竞争(PR2 踩过 WAL 并发覆盖的坑)。

用法:
    # dry-run(只统计+打印样本,不写库):
    python scripts/fix_dangling_cognizer_statements.py --db ~/.starling/dashboard.db --tenant default --dry-run
    # 真执行(写审计文件):
    python scripts/fix_dangling_cognizer_statements.py --db ~/.starling/dashboard.db --tenant default --apply
    # 回滚:
    python scripts/fix_dangling_cognizer_statements.py --db ~/.starling/dashboard.db --tenant default --restore <db>.pr3-fixed.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys


# ---------------------------------------------------------------------------
# 纯逻辑(单测覆盖):给定 statements 行 + 已归档认知体名集,算出要订正的 stmt id。
# 不碰 DB、不碰网络。
# ---------------------------------------------------------------------------
def plan_fix(
    rows: list[dict],
    archived_names: set[str],
) -> list[str]:
    """rows: [{id, subject_kind, subject_id}]。subject_id 存 canonical_name(表面串)。
    archived_names: 已归档(=判为 entity)认知体的 canonical_name 集。

    返回 fix_ids:subject_kind=='cognizer' 且 subject_id 命中 archived_names 的 stmt id。

    幂等:已订正的行(subject_kind=='entity')不再命中(条件要求 =='cognizer')。
    """
    fix_ids: list[str] = []
    for r in rows:
        if r.get("subject_kind") != "cognizer":
            continue  # 只订正仍标 cognizer 的;已订正/本就是 entity 的跳过(幂等)
        if r.get("subject_id") in archived_names:
            fix_ids.append(r["id"])
    return fix_ids


# ---------------------------------------------------------------------------
# DB 读写(薄封装,便于 plan_fix 单测隔离)。
# ---------------------------------------------------------------------------
def load_archived_names(db: str, tenant: str) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        cur = conn.execute(
            "SELECT canonical_name FROM cognizers "
            "WHERE tenant_id=? AND archived_at IS NOT NULL",
            (tenant,))
        return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def load_cognizer_statements(db: str, tenant: str) -> list[dict]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT id, subject_kind, subject_id FROM statements "
            "WHERE tenant_id=? AND subject_kind='cognizer'",
            (tenant,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def apply_fix(db: str, tenant: str, fix_ids: list[str]) -> None:
    conn = sqlite3.connect(db)
    try:
        with conn:  # 单事务:全成或全不成
            conn.executemany(
                "UPDATE statements SET subject_kind='entity' "
                "WHERE id=? AND tenant_id=? AND subject_kind='cognizer'",
                [(sid, tenant) for sid in fix_ids])
    finally:
        conn.close()


def restore_fix(db: str, tenant: str, fix_ids: list[str]) -> int:
    conn = sqlite3.connect(db)
    try:
        with conn:
            cur = conn.executemany(
                "UPDATE statements SET subject_kind='cognizer' "
                "WHERE id=? AND tenant_id=? AND subject_kind='entity'",
                [(sid, tenant) for sid in fix_ids])
            return cur.rowcount
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="订正指向已归档认知体的悬挂 cognizer 语句(subject_kind→entity)")
    p.add_argument("--db", required=True)
    p.add_argument("--tenant", default="default")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只统计+打印样本,不写库")
    mode.add_argument("--apply", action="store_true", help="真执行订正 + 写审计文件")
    mode.add_argument("--restore", metavar="AUDIT_JSON", help="从审计文件回滚")
    p.add_argument("--audit", default=None,
                   help="审计文件路径(默认 <db>.pr3-fixed.json)")
    args = p.parse_args(argv)

    audit_path = args.audit or (args.db + ".pr3-fixed.json")

    if args.restore:
        with open(args.restore, encoding="utf-8") as fh:
            fix_ids = json.load(fh)["fix_ids"]
        n = restore_fix(args.db, args.tenant, fix_ids)
        print(f"restored {n} statements (subject_kind entity→cognizer)", file=sys.stderr)
        return 0

    archived = load_archived_names(args.db, args.tenant)
    rows = load_cognizer_statements(args.db, args.tenant)
    fix_ids = plan_fix(rows, archived)

    print(f"tenant={args.tenant}: {len(rows)} cognizer-subject statements, "
          f"{len(archived)} archived cognizer names → {len(fix_ids)} to fix", file=sys.stderr)

    # 抽样打印前 20 个被订正语句的 subject(确认都是技术实体)
    id_to_subj = {r["id"]: r["subject_id"] for r in rows}
    print("\n--- 订正样本(前 20 subject)---")
    for sid in fix_ids[:20]:
        print(f"  {id_to_subj.get(sid)}")

    if args.dry_run:
        print("\n[dry-run] 未写库。加 --apply 真执行。", file=sys.stderr)
        return 0

    apply_fix(args.db, args.tenant, fix_ids)
    with open(audit_path, "w", encoding="utf-8") as fh:
        json.dump({"tenant": args.tenant, "fix_ids": fix_ids}, fh)
    print(f"\n[applied] 订正 {len(fix_ids)} 条 subject_kind cognizer→entity。"
          f"审计文件:{audit_path}  回滚:--restore {audit_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
