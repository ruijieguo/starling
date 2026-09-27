"""日常回归必须显式报告历史跳过，显式回放不能吞掉失败。"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def isolated_suite(tmp_path):
    shutil.copyfile(ROOT / 'tests/python/conftest.py', tmp_path / 'conftest.py')
    options = tomllib.loads((ROOT / 'pyproject.toml').read_text())['tool']['pytest']['ini_options']
    (tmp_path / 'pytest.ini').write_text(f"[pytest]\naddopts = {options['addopts']}\n")
    (tmp_path / 'test_boundary.py').write_text('''
from pathlib import Path
import pytest

@pytest.fixture
def archive():
    Path('archive-setup-ran').touch()
    return Path('missing-archive.json').read_text()

@pytest.mark.historical_eval(reason='fixed archived native build')
def original_history(archive):
    assert archive

test_reused_history = original_history

def test_current():
    Path('current-ran').touch()
''')
    return tmp_path


def run_suite(path, *args):
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONDONTWRITEBYTECODE='1')
    env.pop('PYTEST_ADDOPTS', None)
    return subprocess.run([sys.executable, '-m', 'pytest', '-q', '-ra', *args],
                          cwd=path, env=env, capture_output=True, text=True, timeout=30)


def test_default_reports_history_skip_before_fixture_and_runs_current(isolated_suite):
    result = run_suite(isolated_suite)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 passed, 1 skipped' in result.stdout
    assert '--run-historical' in result.stdout
    assert 'fixed archived native build' in result.stdout
    assert (isolated_suite / 'current-ran').exists()
    assert not (isolated_suite / 'archive-setup-ran').exists()


def test_explicit_history_preserves_missing_artifact_error(isolated_suite):
    result = run_suite(isolated_suite, '--run-historical', '-m', 'historical_eval')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'FileNotFoundError' in result.stdout
    assert (isolated_suite / 'archive-setup-ran').exists()
    assert not (isolated_suite / 'current-ran').exists()


def test_current_failure_is_not_suppressed(isolated_suite):
    (isolated_suite / 'test_failure.py').write_text('def test_current_failure():\n    assert 2 == 3\n')
    result = run_suite(isolated_suite)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'test_current_failure' in result.stdout and '1 failed, 1 passed, 1 skipped' in result.stdout


def test_unknown_marker_is_rejected(isolated_suite):
    (isolated_suite / 'test_typo.py').write_text('import pytest\n@pytest.mark.historic_eval\ndef test_typo(): pass\n')
    result = run_suite(isolated_suite)
    assert result.returncode != 0
    assert 'historic_eval' in result.stdout


def test_fixture_cycles_are_released_before_next_test(isolated_suite):
    (isolated_suite / 'test_resources.py').write_text('''
import gc
from pathlib import Path
import sqlite3
import weakref
import pytest

gc.disable()

class Resource:
    pass

@pytest.fixture
def cyclic_connection():
    yield
    resource = Resource()
    resource.connection = sqlite3.connect(':memory:')
    resource.cycle = resource
    weakref.finalize(resource, Path('resource-released').touch)

def test_a(cyclic_connection):
    assert not Path('resource-released').exists()

def test_b():
    assert Path('resource-released').exists()
''')
    result = run_suite(isolated_suite, 'test_resources.py')
    assert result.returncode == 0, result.stdout + result.stderr
    assert '2 passed' in result.stdout


def test_fixture_teardown_error_is_not_suppressed(isolated_suite):
    (isolated_suite / 'test_teardown.py').write_text('''
import pytest

@pytest.fixture
def broken_teardown():
    yield
    raise RuntimeError('teardown must remain visible')

def test_current(broken_teardown):
    pass
''')
    result = run_suite(isolated_suite, 'test_teardown.py')
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'teardown must remain visible' in result.stdout
    assert '1 passed, 1 error' in result.stdout
