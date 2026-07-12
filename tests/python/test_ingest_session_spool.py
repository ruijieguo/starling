import importlib.util
import io
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "ingest_session",
    str(Path(__file__).resolve().parents[2] / "scripts" / "ingest_session.py"))
ingest_session = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ingest_session)


def test_write_job_creates_spool_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_session, "SPOOL", tmp_path / "spool")
    p = ingest_session.write_job("s1", "/t/x.jsonl", "/proj/foo", "default")
    assert p.exists()
    job = json.loads(p.read_text())
    assert job["session_id"] == "s1" and job["transcript_path"] == "/t/x.jsonl"
    assert job["cwd"] == "/proj/foo" and job["tenant"] == "default"


def test_hook_main_reads_stdin_and_exits_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_session, "SPOOL", tmp_path / "spool")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        {"session_id": "s2", "transcript_path": "/t/y.jsonl", "cwd": "/proj/bar"})))
    monkeypatch.setattr("sys.argv", ["ingest_session.py"])
    ingest_session.main()                       # 不抛
    jobs = list((tmp_path / "spool").glob("*.json"))
    assert len(jobs) == 1 and json.loads(jobs[0].read_text())["session_id"] == "s2"


def test_malformed_stdin_exits_zero_no_throw(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_session, "SPOOL", tmp_path / "spool")
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    monkeypatch.setattr("sys.argv", ["ingest_session.py"])
    ingest_session.main()                       # 绝不抛(hook 不能非零退出)


def test_bootstrap_writes_job_per_path(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_session, "SPOOL", tmp_path / "spool")
    monkeypatch.setattr("sys.argv",
                        ["ingest_session.py", "--bootstrap", "/t/a.jsonl", "/t/b.jsonl"])
    ingest_session.main()
    assert len(list((tmp_path / "spool").glob("*.json"))) == 2


# --- Controller resolution: transcript_path 可能缺失于 SessionEnd payload,须按
# ~/.claude/projects/<slug>/<session_id>.jsonl (slug = cwd 所有 "/" 换成 "-") 重建,
# 且只在重建路径确实存在时才用它写 job。---

def test_missing_transcript_path_reconstructs_from_cwd(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_session, "SPOOL", tmp_path / "spool")
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    cwd = "/proj/foo"
    slug = cwd.replace("/", "-")
    transcript_dir = fake_home / ".claude" / "projects" / slug
    transcript_dir.mkdir(parents=True)
    transcript_file = transcript_dir / "s3.jsonl"
    transcript_file.write_text("{}")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        {"session_id": "s3", "cwd": cwd})))
    monkeypatch.setattr("sys.argv", ["ingest_session.py"])
    ingest_session.main()
    jobs = list((tmp_path / "spool").glob("*.json"))
    assert len(jobs) == 1
    job = json.loads(jobs[0].read_text())
    assert job["session_id"] == "s3"
    assert job["transcript_path"] == str(transcript_file)
    assert job["cwd"] == cwd


def test_missing_transcript_and_no_file_skips(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_session, "SPOOL", tmp_path / "spool")
    fake_home = tmp_path / "home2"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.setattr(ingest_session, "LOG", fake_home / ".starling" / "ingest.log")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        {"session_id": "s4", "cwd": "/proj/bar"})))
    monkeypatch.setattr("sys.argv", ["ingest_session.py"])
    ingest_session.main()                        # 不抛
    assert not list((tmp_path / "spool").glob("*.json"))
    assert (fake_home / ".starling" / "ingest.log").exists()   # skip 记了日志
