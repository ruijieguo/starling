"""原生真实写入与评测巩固阶段的离线契约。"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[2] / "scripts/run_socialmem_baseline.py"
spec = importlib.util.spec_from_file_location("lifecycle_runner", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize("mode", ["immediate", "sleep"])
def test_lifecycle_uses_native_replay_after_actual_remember(tmp_path, mode):
    program = r'''
import importlib.util, json, sqlite3, sys
from starling import _core
from starling.memory import Memory
spec = importlib.util.spec_from_file_location("runner", sys.argv[1])
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
assert hasattr(runner, "apply_lifecycle"), "native lifecycle stage is missing"
llm = _core.FakeLLMAdapter()
llm.set_default_response(json.dumps([{"holder":"Ada","holder_perspective":"FIRST_PERSON",
    "subject":"Ada","predicate":"prefers","object":"quiet work",
    "modality":"BELIEVES","polarity":"POS","nesting_depth":0}]), True, "")
mem = Memory.open(sys.argv[2], llm=llm)
mem.remember("Ada prefers quiet work", holder="Ada", now="2026-06-27T12:00:00Z")
def rows():
    with sqlite3.connect(sys.argv[2]) as conn:
        return conn.execute("SELECT id,consolidation_state,review_status FROM statements ORDER BY id").fetchall()
before = rows()
assert before and any(row[1] == "volatile" for row in before), before
result = runner.apply_lifecycle(_core, mem._core.rt.adapter,
    {"lifecycle":sys.argv[3],"query_time":"2026-06-27T12:00:00Z"})
after = rows()
assert [row[0] for row in before] == [row[0] for row in after]
if sys.argv[3] == "immediate":
    assert before == after and result == {"mode":"immediate","stats":{}}
else:
    assert result["stats"]["compressed"] == len(before)
    assert all(row[1:] == ("consolidated", "approved") for row in after), after
'''
    result = subprocess.run([sys.executable, "-c", program, str(RUNNER), str(tmp_path / "memory.db"), mode],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_unknown_lifecycle_is_rejected_before_calling_core():
    assert hasattr(runner, "apply_lifecycle"), "native lifecycle stage is missing"
    with pytest.raises(ValueError, match="lifecycle"):
        runner.apply_lifecycle(None, None, {"lifecycle": "unsupported"})
