import pytest


@pytest.fixture(autouse=True)
def isolate_dashboard_ingest_spool(tmp_path, monkeypatch):
    """Dashboard tests must never inspect or mutate the user's live spool."""
    monkeypatch.setenv("STARLING_DASH_INGEST_SPOOL", str(tmp_path / "ingest-spool"))


@pytest.fixture
def core():
    from starling import _core
    return _core
