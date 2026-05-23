import subprocess
import sys
from pathlib import Path
import textwrap

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER = REPO_ROOT / "scripts" / "ci_static_scan.py"


def _run_scanner(extra_args, cwd):
    return subprocess.run(
        [sys.executable, str(SCANNER), *extra_args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_scanner_passes_on_clean_tree(tmp_path):
    # Mirror minimum repo shape: a prod source file, a test source file.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "preflight.cpp").write_text(
        '#include "starling/preflight.hpp"\nvoid f() {}\n'
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_smoke.cpp").write_text(
        '#include "starling/testing_marker.hpp"\n'
        "namespace t = starling::testing;\n"
    )
    result = _run_scanner(
        ["--prod-roots", "src", "--allowed-roots", "tests"], cwd=tmp_path
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_scanner_fails_when_prod_imports_testing_namespace(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "leaky.cpp").write_text(
        textwrap.dedent("""\
            #include "starling/testing_marker.hpp"
            namespace t = starling::testing;
            void leak() { (void)t::testing_marker_loaded(); }
        """)
    )
    result = _run_scanner(["--prod-roots", "src"], cwd=tmp_path)
    assert result.returncode != 0
    assert "starling::testing" in result.stdout + result.stderr


def test_scanner_fails_when_prod_imports_python_testing(tmp_path):
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "app.py").write_text(
        "from starling.testing import marker_loaded\n"
    )
    result = _run_scanner(["--prod-roots", "python"], cwd=tmp_path)
    assert result.returncode != 0
    assert "starling.testing" in result.stdout + result.stderr


def test_scanner_allows_pyi_stub_with_block_comment(tmp_path):
    # .pyi files often re-export everything; scanner must not flag them when
    # the line is inside a doc comment marked NOLINT(starling-testing-isolation).
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "_core.pyi").write_text(
        '"""starling.testing helpers."""\n'
        "# NOLINT(starling-testing-isolation): re-export for type checkers only\n"
        "from starling.testing import marker_loaded as marker_loaded\n"
    )
    result = _run_scanner(["--prod-roots", "python"], cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
