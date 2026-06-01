"""Smoke test for examples/quickstart.py — imports + runs it fully offline.

Guards the README quickstart: it must run with no network / no API key and
render a working set that includes the pending-commitments section and the
⚠ due-commitment reminder.
"""
import importlib.util
import pathlib


def test_quickstart_runs_offline():
    # tests/python/<file> → parents[0]=python, [1]=tests, [2]=worktree root
    path = (pathlib.Path(__file__).resolve().parents[2]
            / "examples" / "quickstart.py")
    spec = importlib.util.spec_from_file_location("quickstart", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = mod.main()
    assert "Pending commitments" in out   # ## Pending commitments section
    assert "⚠" in out                     # due-commitment reminder
