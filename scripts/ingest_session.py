#!/usr/bin/env python3
"""dogfood 子项 A(spool 架构第二步):Claude Code SessionEnd hook 入口 —— 只把一个
job 文件原子落到 spool 目录、立即退出;不做任何过滤/分块(那是 worker 的事,见 Task 3
的 `python/starling/dashboard/ingest_filter.py` + engine 后台 worker)。也支持
`--bootstrap <path...>` 批量喂历史 transcript。纯 stdlib,零依赖,近零工作。

SessionEnd hook payload(2026-07-12 核实官方 hooks 文档,取代 plan 里的占位结论):
stdin 是一个 JSON 对象,字段:
    session_id        — 当前会话 id
    transcript_path    — 会话 transcript 的绝对路径(**可能缺失!**不是保证字段)
    cwd                — hook 触发时的工作目录
    reason             — clear / resume / logout / prompt_input_exit /
                          bypass_permissions_disabled / other 之一;本脚本对所有取值
                          一视同仁地写 job,不按 reason 过滤/跳过
    hook_event_name    — 恒为 "SessionEnd"
    permission_mode    — 当前 permission mode
    effort             — 当前 reasoning effort 设置
(本脚本只读取 session_id / transcript_path / cwd 三个字段;reason 等其余字段与「是否
写 job」无关,不读取。)

`transcript_path` 缺失时的降级重建规则:按约定路径
`~/.claude/projects/<slug>/<session_id>.jsonl` 重建,其中 `slug` = `cwd` 把所有 "/"
替换成 "-"(前导 "/" 也变成前导 "-")。例:cwd `/Users/x/proj` → slug `-Users-x-proj`。
若重建出的文件在磁盘上确实不存在,则放弃、只记一行日志、不写 job —— 不产生指向不
存在文件的死 job(worker 没必要再处理一次必然失败)。

Hook 纪律:`main()` 里任何异常(含 stdin 不是合法 JSON)一律被吞掉 + 记日志,绝不非
零退出 —— SessionEnd hook 失败不能阻塞/污染用户的会话退出。
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

SPOOL = Path.home() / ".starling" / "ingest-spool"
LOG = Path.home() / ".starling" / "ingest.log"


def _log(msg: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass


def write_job(session_id: str, transcript_path: str, cwd: str, tenant: str) -> Path:
    """把一个摄入 job 原子落到 `SPOOL/<uuid>.json`:先写 `.tmp`,再 `rename`——worker
    扫 spool 时不会读到半写的文件。"""
    SPOOL.mkdir(parents=True, exist_ok=True)
    job = {"session_id": session_id, "transcript_path": transcript_path,
           "cwd": cwd, "tenant": tenant}
    path = SPOOL / f"{uuid.uuid4().hex}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(job))
    tmp.rename(path)                              # 原子出现(worker 不会读到半写)
    return path


def _resolve_transcript_path(transcript_path: str, cwd: str, session_id: str) -> str | None:
    """`transcript_path` 有值就原样信任返回(即便文件此刻不存在——这是 SessionEnd 自
    己给的字段,不是本脚本的猜测,worker 才是真正打开文件的一方)。缺失时按
    `~/.claude/projects/<slug>/<session_id>.jsonl` 重建(slug = cwd 所有 "/" 换成
    "-"),只有重建出的文件确实存在于磁盘才返回它,否则返回 None(调用方据此记日志
    并放弃,不写指向不存在文件的 job)。"""
    if transcript_path:
        return transcript_path
    if not cwd or not session_id:
        return None
    slug = cwd.replace("/", "-")
    candidate = Path.home() / ".claude" / "projects" / slug / f"{session_id}.jsonl"
    return str(candidate) if candidate.exists() else None


def main() -> None:
    try:
        argv = sys.argv[1:]
        tenant = os.environ.get("STARLING_DASH_TENANT", "default")
        if argv and argv[0] == "--bootstrap":
            for tp in argv[1:]:
                write_job(Path(tp).stem, tp, "", tenant)
            return
        payload = json.loads(sys.stdin.read() or "{}")
        sid = payload.get("session_id") or ""
        cwd = payload.get("cwd") or ""
        tp = payload.get("transcript_path") or ""
        resolved = _resolve_transcript_path(tp, cwd, sid)
        if not resolved:
            _log(f"no transcript_path for session={sid or 'unknown'} cwd={cwd!r}; skipped")
            return
        write_job(sid or "unknown", resolved, cwd, tenant)
    except Exception as exc:                      # 绝不非零退出阻塞会话
        _log(f"hook failed: {exc!r}")


if __name__ == "__main__":
    main()
    sys.exit(0)
