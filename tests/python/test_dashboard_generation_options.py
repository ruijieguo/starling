"""provider 配置里的生成参数(max_tokens/timeout_ms/max_retries/enable_thinking)
经 `_build_chat_adapter` 转发给 C++ OpenAIAdapter;未设置时保持 C++ 默认值。
通过本地 HTTP 边界观察,不联网。"""
import json
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

import starling.dashboard.engine as engmod
from starling import _core
from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine, _build_chat_adapter


class _Server(ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer.server_bind 会调 socket.getfqdn 做反向解析,本机实测约 35 秒。
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "127.0.0.1", self.server_address[1]


@pytest.fixture
def llm_server():
    seen: list[dict] = []
    delay = {"s": 0.0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            time.sleep(delay["s"])
            body = b'{"choices":[{"message":{"content":"[]"},"finish_reason":"stop"}]}'
            try:
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = _Server(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, seen, delay
    server.shutdown()
    server.server_close()
    thread.join()


def _provider(server, **extra):
    return {"provider": "openai", "api_key": "k", "model": "m",
            "base_url": f"http://127.0.0.1:{server.server_port}/v1", **extra}


def test_max_tokens_and_thinking_switch_are_forwarded(llm_server):
    server, seen, _ = llm_server
    adapter = _build_chat_adapter(_provider(server, max_tokens=16384, enable_thinking=False))
    assert adapter.extract("p", "h").ok
    assert seen[0]["max_tokens"] == 16384
    assert seen[0]["enable_thinking"] is False


def test_unset_options_keep_cpp_defaults(llm_server):
    server, seen, _ = llm_server
    adapter = _build_chat_adapter(_provider(server))
    assert adapter.extract("p", "h").ok
    assert seen[0]["max_tokens"] == 4096
    assert "enable_thinking" not in seen[0]
    assert "thinking" not in seen[0]


def test_thinking_type_is_forwarded_as_the_thinking_field(llm_server):
    """有的 OpenAI 兼容网关不认 enable_thinking=false、只认 thinking.type(实测 2026-11-13:前者 44 秒全是推理、
    content 为空,后者 1.4 秒正常结束)。provider 设了 thinking_type 就要写进请求体;空串与未设置一样不发。"""
    server, seen, _ = llm_server
    assert _build_chat_adapter(_provider(server, thinking_type="disabled", enable_thinking=False)).extract("p", "h").ok
    assert seen[0]["thinking"] == {"type": "disabled"}
    assert seen[0]["enable_thinking"] is False
    assert _build_chat_adapter(_provider(server, thinking_type="")).extract("p", "h").ok
    assert "thinking" not in seen[1]


def test_timeout_and_retries_are_forwarded(llm_server):
    server, _, delay = llm_server
    delay["s"] = 1.5
    adapter = _build_chat_adapter(_provider(server, timeout_ms=300, max_retries=0))
    started = time.monotonic()
    result = adapter.extract("p", "h")
    assert not result.ok and "Timeout" in result.error
    assert time.monotonic() - started < 1.2


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfgfile = tmp_path / "starling.json"
    cfg = DashboardConfig(db_path=str(tmp_path / "c.db"), token="", config_path=str(cfgfile))
    engine = DashboardEngine(cfg)
    return TestClient(create_app(cfg, engine=engine)), cfgfile


def test_generation_options_roundtrip_through_config_route(ctx, monkeypatch):
    client, cfgfile = ctx
    monkeypatch.setattr(engmod, "_build_chat_adapter", lambda c: _core.FakeLLMAdapter())
    opts = {"max_tokens": 16384, "timeout_ms": 240000, "max_retries": 1, "enable_thinking": False}
    reply = client.post("/api/config", json={
        "providers": {"default": {"provider": "openai", "model": "m", "api_key": "sk-x", **opts}},
        "roles": {"extraction": "default"}})
    assert reply.status_code == 200
    public = client.get("/api/config").json()["providers"]["default"]
    assert {k: public.get(k) for k in opts} == opts
    stored = json.loads(cfgfile.read_text())["providers"]["default"]
    assert {k: stored.get(k) for k in opts} == opts

    # 只改 model:已存的生成参数保留;非正数被忽略。
    client.post("/api/config", json={"providers": {"default": {
        "model": "m2", "max_tokens": 0, "timeout_ms": -5}}})
    stored = json.loads(cfgfile.read_text())["providers"]["default"]
    assert stored["model"] == "m2"
    assert stored["max_tokens"] == 16384 and stored["timeout_ms"] == 240000

    # max_retries=0 是合法值(不重试)。
    client.post("/api/config", json={"providers": {"default": {"max_retries": 0}}})
    assert json.loads(cfgfile.read_text())["providers"]["default"]["max_retries"] == 0
    assert "sk-x" not in json.dumps(client.get("/api/config").json())


def test_thinking_type_roundtrips_through_config_route_and_clears_on_empty(ctx, monkeypatch):
    client, cfgfile = ctx
    monkeypatch.setattr(engmod, "_build_chat_adapter", lambda c: _core.FakeLLMAdapter())
    reply = client.post("/api/config", json={
        "providers": {"default": {"provider": "openai", "model": "m", "api_key": "sk-x", "thinking_type": "disabled"}},
        "roles": {"extraction": "default"}})
    assert reply.status_code == 200
    assert client.get("/api/config").json()["providers"]["default"]["thinking_type"] == "disabled"
    assert json.loads(cfgfile.read_text())["providers"]["default"]["thinking_type"] == "disabled"

    # 不带 thinking_type 的编辑保留它;空串清除。
    client.post("/api/config", json={"providers": {"default": {"model": "m2"}}})
    assert json.loads(cfgfile.read_text())["providers"]["default"]["thinking_type"] == "disabled"
    client.post("/api/config", json={"providers": {"default": {"thinking_type": ""}}})
    assert "thinking_type" not in json.loads(cfgfile.read_text())["providers"]["default"]
    assert "thinking_type" not in client.get("/api/config").json()["providers"]["default"]
