"""第 5 期验收（spec §16 第 4 条）：客户端写一个世界的同时，看板 API 按世界读到新语句、能召回、收到 world_changed；
世界关掉之后按标签找到，看板只读打开它，不迁移（库文件 sha256 不变、没有新的 -wal/-shm）。

真的 `starling-serve` 子进程（同一个进程提供客户端 API 与看板 API），数据目录与 HOME 在 tmp 下，环境里没有 OPENAI_*；
抽取与嵌入走本机假端点。配置与假端点夹具复用 test_acceptance_service。所有等待都有上限，子进程在夹具的 finally 里杀掉。
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import secrets
import sqlite3
import time
import uuid

import pytest
import websockets

import starling_client

from fakes.openai_fake_server import FakeOpenAI
from fakes.service_proc import ServiceFactory
from test_acceptance_service import DIM, HOLDER, NOW, _remember_ok, _text, _write_config

_LIVE_S = 5.0
_POLL_S = 0.1
_WS_S = 10.0
_UTTERANCES = ["Alice deploys the auth service", "Bruno tunes the billing cache",
               "Chen rotates the infra key"]


@pytest.fixture(scope="module")
def fake_openai(tmp_path_factory):
    fake = FakeOpenAI(api_key="sk-fake-" + secrets.token_hex(16), dim=DIM,
                      log_path=tmp_path_factory.mktemp("fake-openai") / "fake-stderr.log")
    fake.start()
    try:
        yield fake
    finally:
        fake.stop()


@pytest.fixture
def service(tmp_path, fake_openai):
    factory = ServiceFactory(tmp_path, token=secrets.token_urlsafe(24))
    try:
        data_dir = tmp_path / "D"
        _write_config(data_dir, fake_openai)
        proc = factory(data_dir).start_and_wait()
        proc.data_dir = data_dir
        yield proc
    finally:
        factory.kill_all()


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _dir_files(db_path: str) -> set[str]:
    return set(os.listdir(os.path.dirname(db_path)))


def _registry_db_path(data_dir, world: str) -> str:
    """库路径取自注册表（只读打开），不自己拼。"""
    conn = sqlite3.connect(f"file:{data_dir / 'registry.db'}?mode=ro", uri=True)
    try:
        row = conn.execute("SELECT db_path FROM worlds WHERE name = ?", (world,)).fetchone()
    finally:
        conn.close()
    assert row is not None, world
    return row[0]


def _poll(fn, what: str, timeout_s: float = _LIVE_S):
    """每 0.1 s 调一次 fn，真值就返回；超过 timeout_s 判失败。"""
    deadline = time.monotonic() + timeout_s
    last = None
    while True:
        last = fn()
        if last:
            return last
        if time.monotonic() >= deadline:
            raise AssertionError(f"{what}: not seen within {timeout_s}s; last={last!r}")
        time.sleep(_POLL_S)


def _objects(http, world: str) -> set[str]:
    resp = http.get(f"/api/w/{world}/statements", params={"limit": 500})
    assert resp.status_code == 200, resp.text
    rows = resp.json()["rows"]
    return {row["object_value"] for row in rows}


def _recall_texts(http, world: str, query: str) -> str:
    resp = http.post(f"/api/w/{world}/recall", json={"query": query, "k": 10, "holder": HOLDER})
    assert resp.status_code == 200, resp.text
    results = resp.json()["results"]
    return json.dumps(results, ensure_ascii=False)


async def _ws_collect(url: str, token: str, world: str, ready: asyncio.Event,
                      stop: asyncio.Event) -> dict | None:
    """连 /ws，第一帧发 token；订阅好之后置 ready，直到收到这个世界的 world_changed 或 stop 为止。"""
    async with websockets.connect(url.replace("http://", "ws://") + "/ws", proxy=None) as ws:
        await ws.send(token)
        ready.set()
        while not stop.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            msg = json.loads(raw)
            if msg.get("type") == "world_changed" and msg.get("world") == world:
                return msg
    return None


def test_4_dashboard_sees_client_writes_and_reopens_closed_world_read_only(service, fake_openai):
    run_id = "run-" + uuid.uuid4().hex[:12]
    world = "acc4-" + uuid.uuid4().hex[:8]
    http = service.client()
    client = starling_client.connect(service.url, token=service.token, timeout_s=30.0)
    try:
        # 1. 可回收世界：从一个源世界分叉出来，带唯一标签与 retention_group。
        client.create_world("acc4-src")
        forked = client.fork("acc4-src", world, reclaimable=True, labels={"run_id": run_id},
                             retention_group="acc4-group")
        assert forked["world"]["name"] == world

        # 3 的实时推送：先订阅，再写。
        async def live_and_write():
            ready, stop = asyncio.Event(), asyncio.Event()
            task = asyncio.create_task(_ws_collect(service.url, service.token, world, ready, stop))
            await asyncio.wait_for(ready.wait(), _WS_S)
            await asyncio.sleep(0.3)                      # token 帧到达并登记
            # 2. 客户端可写打开，写入若干条事件（同步调用放进线程，事件循环继续收帧）。
            mem = client.open(world, holder=HOLDER)

            def write():
                for index, utterance in enumerate(_UTTERANCES):
                    _remember_ok(mem.remember_event(f"{world}#{index}", _text("bob", utterance),
                                                    interlocutor="bob"))
                assert mem.embed_pending(NOW).embedded >= len(_UTTERANCES)

            await asyncio.to_thread(write)
            await asyncio.wait({task}, timeout=_WS_S)
            stop.set()                                    # 超时则让收帧循环退出，不取消 task
            return mem, await task

        mem, ws_msg = asyncio.run(live_and_write())
        try:
            assert ws_msg is not None, "没收到这个世界的 world_changed"
            assert ws_msg["type"] == "world_changed" and ws_msg["world"] == world

            # 3. 句柄还开着：看板在 5 秒内按内容读到新语句、能召回、held_by_client 为真。
            expected = {text.lower() for text in _UTTERANCES}   # 抽取把 object 规范化成小写
            live_objects = _poll(lambda: (o := _objects(http, world)) >= expected and o,
                                 "dashboard statements")
            assert expected <= live_objects
            for utterance in _UTTERANCES:
                assert utterance.lower() in _recall_texts(http, world, utterance), utterance
            detail = http.get(f"/api/worlds/{world}")
            assert detail.status_code == 200, detail.text
            assert detail.json()["held_by_client"] is True
        finally:
            # 4. 关句柄，再关世界。
            mem.close()
        client.close_world(world)

        # 5. 关掉之后：按标签正好找到这一个世界。
        found = client.list_worlds(labels={"run_id": run_id})
        assert [w["name"] for w in found["worlds"]] == [world], found
        assert found["total"] == 1

        db_path = _registry_db_path(service.data_dir, world)
        sha, files = _sha256(db_path), _dir_files(db_path)
        assert not any(name.endswith(("-wal", "-shm")) for name in files), files   # 关掉后目录里没有 WAL 残留

        # 看板只读打开：语句与句柄开着时读到的一致，能召回，open_mode 为 ro。
        closed_objects = _objects(http, world)
        assert closed_objects == live_objects
        assert _UTTERANCES[0].lower() in _recall_texts(http, world, _UTTERANCES[0])
        detail = http.get(f"/api/worlds/{world}").json()
        assert detail["open_mode"] == "ro"
        assert detail["held_by_client"] is False

        # 不迁移：库字节不变，目录里没有新增文件（尤其是 -wal/-shm）。
        assert _sha256(db_path) == sha
        after = _dir_files(db_path)
        assert after == files, after ^ files
        assert not any(name.endswith(("-wal", "-shm")) for name in after), after
    finally:
        with contextlib.suppress(Exception):
            client.close()
        http.close()
