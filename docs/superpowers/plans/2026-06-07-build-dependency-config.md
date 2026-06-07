# Build Dependency + Configuration Robustness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Starling build easier and more robust through a local-first build configuration script, CMake presets, CMake dependency hardening, and updated build docs for Linux and macOS.

**Architecture:** Add `scripts/configure_build.py` as the recommended entrypoint: it detects local tools/dependencies, rejects known-bad build cache states, and invokes CMake/build/test/editable commands with explicit cache hints. Keep build graph ownership in CMake via `CMakePresets.json`, targeted `CMakeLists.txt` improvements, and a small unit-tested Python helper surface. Preserve scikit-build-core for Python editable builds and let CMake `FetchContent` handle network fallback for source dependencies when local sources are absent.

**Tech Stack:** Python 3.11+ stdlib (`argparse`, `dataclasses`, `pathlib`, `subprocess`, `sysconfig`), CMake 3.27+, Ninja, scikit-build-core, pybind11, OpenSSL, SQLite, libcurl, ICU, nlohmann/json, GoogleTest, pytest, ctest.

**Spec:** `docs/superpowers/specs/2026-06-07-build-dependency-config-design.md` (commit `20c6e82`).

**Execution notes:** Current working tree contains pre-existing Linux compile fixes in C++/CMake files and an untracked `build-linux/` directory. Do not revert them. When a task needs to touch one of those modified files, inspect the current file and work with the existing changes. Commit only the files listed in that task.

---

## File Structure

- Create `scripts/configure_build.py` — CLI and pure helper functions for dependency discovery, stale-cache checks, CMake command construction, build/test/editable execution, and human-readable diagnostics.
- Create `tests/python/test_configure_build.py` — unit tests for the helper functions without invoking network or a real compiler.
- Create `CMakePresets.json` — portable direct-CMake presets with no user-specific absolute paths.
- Modify `CMakeLists.txt` — keep existing Linux compile fixes, add clearer dependency messages/local override support, and preserve target-oriented dependency wiring.
- Modify `tests/cpp/CMakeLists.txt` — keep GoogleTest local override support and make network fallback behavior explicit.
- Modify `README.md` and `README.zh-CN.md` — make the new script the recommended path and document direct CMake/editable alternatives plus troubleshooting.
- Modify `.gitignore` — ignore `build-dev/`, `build-release/`, `build-linux/`, and `build-macos/`.

---

## Task 0: Baseline And Dirty-Tree Inventory

**Files:**
- No edits

- [ ] **Step 1: Record current worktree state**

Run:

```bash
git status --short
```

Expected: shows existing modified C++/CMake files from the prior compile work, an untracked `build-linux/`, and this plan file once it is created. Do not clean the tree.

- [ ] **Step 2: Verify current Linux build still works before changing build tooling**

Run:

```bash
.venv/bin/cmake --build build-linux
.venv/bin/ctest --test-dir build-linux --output-on-failure
```

Expected: CMake build succeeds and ctest reports all C++ tests passing. If this fails, stop and debug the compile failure before changing build tooling.

- [ ] **Step 3: Commit the plan if not already committed**

Run:

```bash
git add docs/superpowers/plans/2026-06-07-build-dependency-config.md
git commit -m "docs: plan robust build configuration"
```

Expected: local commit containing only this plan file.

---

## Task 1: Pure Python Detection Helpers

**Files:**
- Create: `scripts/configure_build.py`
- Create: `tests/python/test_configure_build.py`

- [ ] **Step 1: Write failing tests for package candidate ordering and library pairs**

Create `tests/python/test_configure_build.py` with:

```python
from pathlib import Path

import pytest

from scripts import configure_build as cb


def test_conda_pkg_candidates_prefer_highest_version(tmp_path):
    pkgs = tmp_path / "pkgs"
    old = pkgs / "sqlite-3.45.2-hold_0"
    new = pkgs / "sqlite-3.51.0-hnew_0"
    for root in (old, new):
        (root / "include").mkdir(parents=True)
        (root / "lib").mkdir()
        (root / "include" / "sqlite3.h").write_text("#define SQLITE_VERSION \"3.0\"\n")
        (root / "lib" / "libsqlite3.so").write_text("")

    candidates = cb.conda_pkg_candidates([pkgs], "sqlite")

    assert candidates[0] == new
    assert candidates[1] == old


def test_find_library_pair_requires_include_and_library(tmp_path):
    root = tmp_path / "openssl"
    (root / "include" / "openssl").mkdir(parents=True)
    (root / "lib").mkdir()
    (root / "include" / "openssl" / "ssl.h").write_text("")
    (root / "lib" / "libssl.so").write_text("")

    pair = cb.find_library_pair(
        roots=[root],
        include_rel="include/openssl/ssl.h",
        library_names=("libssl.so", "libssl.dylib"),
    )

    assert pair == cb.LibraryPair(include_dir=root / "include", library=root / "lib" / "libssl.so")


def test_find_library_pair_returns_none_for_partial_match(tmp_path):
    root = tmp_path / "openssl"
    (root / "include" / "openssl").mkdir(parents=True)
    (root / "include" / "openssl" / "ssl.h").write_text("")

    assert cb.find_library_pair([root], "include/openssl/ssl.h", ("libssl.so",)) is None


def test_sqlite_header_version_parsing(tmp_path):
    header = tmp_path / "sqlite3.h"
    header.write_text('#define SQLITE_VERSION "3.51.0"\n', encoding="utf-8")

    assert cb.sqlite_header_version(header) == (3, 51, 0)


def test_sqlite_header_version_missing_returns_none(tmp_path):
    header = tmp_path / "sqlite3.h"
    header.write_text("/* no version */\n", encoding="utf-8")

    assert cb.sqlite_header_version(header) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/python/test_configure_build.py -q
```

Expected: FAIL because `scripts.configure_build` or the helper functions do not exist yet.

- [ ] **Step 3: Add helper implementation**

Create `scripts/configure_build.py` with:

```python
#!/usr/bin/env python3
"""Configure Starling builds with local-first dependency discovery."""

from __future__ import annotations

import argparse
import os
import platform
import re
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
MIN_SQLITE = (3, 46, 0)


@dataclass(frozen=True)
class LibraryPair:
    include_dir: Path
    library: Path


@dataclass(frozen=True)
class DependencyHints:
    cmake_args: tuple[str, ...]
    notes: tuple[str, ...]
    warnings: tuple[str, ...] = ()


class BuildConfigError(RuntimeError):
    """Raised for actionable pre-configure failures."""


def version_key(path: Path) -> tuple[int, ...]:
    match = re.search(r"-(\d+(?:\.\d+)+)", path.name)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def conda_pkg_candidates(pkg_roots: Iterable[Path], prefix: str) -> list[Path]:
    candidates: list[Path] = []
    for pkg_root in pkg_roots:
        if not pkg_root.exists():
            continue
        candidates.extend(p for p in pkg_root.iterdir() if p.is_dir() and p.name.startswith(f"{prefix}-"))
    return sorted(candidates, key=version_key, reverse=True)


def find_library_pair(
    roots: Iterable[Path],
    include_rel: str,
    library_names: Sequence[str],
) -> LibraryPair | None:
    for root in roots:
        include = root / include_rel
        if not include.exists():
            continue
        for libdir in (root / "lib", root / "lib64"):
            for libname in library_names:
                lib = libdir / libname
                if lib.exists():
                    return LibraryPair(include_dir=root / "include", library=lib)
    return None


def sqlite_header_version(header: Path) -> tuple[int, int, int] | None:
    text = header.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'#\s*define\s+SQLITE_VERSION\s+"(\d+)\.(\d+)\.(\d+)"', text)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def default_build_dir(system: str | None = None) -> Path:
    name = (system or platform.system()).lower()
    if name == "darwin":
        return REPO_ROOT / "build-macos"
    if name == "linux":
        return REPO_ROOT / "build-linux"
    return REPO_ROOT / "build"


def candidate_conda_pkg_roots() -> list[Path]:
    roots: list[Path] = []
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        roots.append(Path(conda_prefix).expanduser().parent / "pkgs")
    for base in ("~/miniconda3/pkgs", "~/anaconda3/pkgs", "~/mambaforge/pkgs", "~/micromamba/pkgs"):
        roots.append(Path(base).expanduser())
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        resolved = root.resolve() if root.exists() else root
        if resolved not in seen:
            unique.append(root)
            seen.add(resolved)
    return unique


def fetchcontent_source_args(build_dirs: Iterable[Path]) -> list[str]:
    args: list[str] = []
    mapping = {
        "JSON": "json-src",
        "GOOGLETEST": "googletest-src",
    }
    for cmake_name, dirname in mapping.items():
        for build_dir in build_dirs:
            src = build_dir / "_deps" / dirname
            if src.exists():
                args.append(f"-DFETCHCONTENT_SOURCE_DIR_{cmake_name}={src}")
                break
    return args


def python_executable() -> Path:
    venv_python = REPO_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return venv_python if venv_python.exists() else Path(sys.executable)


def pybind11_cmake_dir(python: Path) -> Path | None:
    code = "import pybind11, sys; sys.stdout.write(pybind11.get_cmake_dir())"
    result = subprocess.run([str(python), "-c", code], text=True, capture_output=True, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    path = Path(result.stdout.strip())
    return path if path.exists() else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=default_build_dir())
    parser.add_argument("--build-type", default="Release", choices=("Debug", "Release", "RelWithDebInfo", "MinSizeRel"))
    parser.add_argument("--build", action="store_true", help="Run cmake --build after configure.")
    parser.add_argument("--test", action="store_true", help="Run ctest after build/configure.")
    parser.add_argument("--python-editable", action="store_true", help="Run pip editable build with the same CMake hints.")
    parser.add_argument("--install-build-tools", action="store_true", help="Install requirements-build.txt into the selected Python environment.")
    parser.add_argument("--allow-network", action="store_true", default=True, help="Allow CMake FetchContent network fallback.")
    parser.add_argument("--no-network", dest="allow_network", action="store_false", help="Disable FetchContent network fallback.")
    parser.add_argument("--no-python", dest="build_python", action="store_false", help="Disable Python bindings.")
    parser.add_argument("--no-tests", dest="build_tests", action="store_false", help="Disable C++ tests.")
    parser.set_defaults(build_python=True, build_tests=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    print(f"Repository: {REPO_ROOT}")
    print(f"Build dir: {args.build_dir}")
    print("Dependency detection is added in later tasks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run helper tests**

Run:

```bash
.venv/bin/python -m pytest tests/python/test_configure_build.py -q
```

Expected: PASS for the five helper tests.

- [ ] **Step 5: Commit helper scaffold**

Run:

```bash
git add scripts/configure_build.py tests/python/test_configure_build.py
git commit -m "build: add local dependency detection helpers"
```

Expected: commit contains only the new script and tests.

---

## Task 2: CMake Command Generation And Stale Cache Guards

**Files:**
- Modify: `scripts/configure_build.py`
- Modify: `tests/python/test_configure_build.py`

- [ ] **Step 1: Add failing tests for stale cache and command construction**

Append to `tests/python/test_configure_build.py`:

```python
def test_check_stale_cache_rejects_compiler_compat(tmp_path):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "CMakeCache.txt").write_text(
        "CMAKE_CXX_COMPILER_ARG1:STRING=-pthread -B /x/miniconda3/compiler_compat\n",
        encoding="utf-8",
    )

    with pytest.raises(cb.BuildConfigError, match="compiler_compat"):
        cb.check_stale_cache(build_dir, expected_generator="Ninja")


def test_check_stale_cache_rejects_generator_mismatch(tmp_path):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "CMakeCache.txt").write_text(
        "CMAKE_GENERATOR:INTERNAL=Unix Makefiles\n",
        encoding="utf-8",
    )

    with pytest.raises(cb.BuildConfigError, match="different generator"):
        cb.check_stale_cache(build_dir, expected_generator="Ninja")


def test_cmake_configure_command_contains_core_flags(tmp_path):
    python = tmp_path / "python"
    ninja = tmp_path / "ninja"
    cmd = cb.cmake_configure_command(
        build_dir=tmp_path / "build-linux",
        build_type="Release",
        python=python,
        ninja=ninja,
        build_python=True,
        build_tests=True,
        allow_network=True,
        extra_args=["-DSQLite3_INCLUDE_DIR=/sqlite/include"],
    )

    assert cmd[:5] == ["cmake", "-S", str(cb.REPO_ROOT), "-B", str(tmp_path / "build-linux")]
    assert "-G" in cmd and "Ninja" in cmd
    assert "-DSTARLING_BUILD_PYTHON=ON" in cmd
    assert "-DSTARLING_BUILD_TESTS=ON" in cmd
    assert f"-DPython_EXECUTABLE={python}" in cmd
    assert f"-DCMAKE_MAKE_PROGRAM={ninja}" in cmd
    assert "-DSQLite3_INCLUDE_DIR=/sqlite/include" in cmd
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/python/test_configure_build.py -q
```

Expected: FAIL because `check_stale_cache` and `cmake_configure_command` do not exist.

- [ ] **Step 3: Implement cache guard and command generation**

Add these functions to `scripts/configure_build.py` above `build_parser()`:

```python
def cache_value(cache_text: str, key: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(key)}(?::[^=]*)?=(.*)$", re.MULTILINE)
    match = pattern.search(cache_text)
    return match.group(1).strip() if match else None


def check_stale_cache(build_dir: Path, expected_generator: str) -> None:
    cache = build_dir / "CMakeCache.txt"
    if not cache.exists():
        return
    text = cache.read_text(encoding="utf-8", errors="ignore")
    generator = cache_value(text, "CMAKE_GENERATOR")
    if generator and generator != expected_generator:
        raise BuildConfigError(
            f"{build_dir} was configured with a different generator ({generator}). "
            f"Use a new build directory or reconfigure manually with {expected_generator}."
        )
    suspicious = (
        cache_value(text, "CMAKE_CXX_COMPILER_ARG1")
        or cache_value(text, "CMAKE_C_COMPILER_ARG1")
        or ""
    )
    if "compiler_compat" in suspicious:
        raise BuildConfigError(
            f"{build_dir} contains conda compiler_compat linker wrapper state. "
            "Use a fresh build directory such as build-linux or build-macos."
        )


def cmake_configure_command(
    *,
    build_dir: Path,
    build_type: str,
    python: Path,
    ninja: Path | None,
    build_python: bool,
    build_tests: bool,
    allow_network: bool,
    extra_args: Sequence[str],
) -> list[str]:
    cmd = [
        "cmake",
        "-S",
        str(REPO_ROOT),
        "-B",
        str(build_dir),
        "-G",
        "Ninja",
        f"-DCMAKE_BUILD_TYPE={build_type}",
        f"-DSTARLING_BUILD_PYTHON={'ON' if build_python else 'OFF'}",
        f"-DSTARLING_BUILD_TESTS={'ON' if build_tests else 'OFF'}",
        f"-DPython_EXECUTABLE={python}",
    ]
    if not allow_network:
        cmd.append("-DFETCHCONTENT_FULLY_DISCONNECTED=ON")
    if ninja is not None:
        cmd.append(f"-DCMAKE_MAKE_PROGRAM={ninja}")
    cmd.extend(extra_args)
    return cmd


def run(cmd: Sequence[str], *, cwd: Path = REPO_ROOT) -> None:
    print("+ " + " ".join(str(part) for part in cmd))
    subprocess.run(list(map(str, cmd)), cwd=cwd, check=True)
```

Update `main()` to call `check_stale_cache()` and print the configure command:

```python
def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        check_stale_cache(args.build_dir, expected_generator="Ninja")
    except BuildConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    python = python_executable()
    ninja = REPO_ROOT / ".venv" / ("Scripts/ninja.exe" if os.name == "nt" else "bin/ninja")
    cmd = cmake_configure_command(
        build_dir=args.build_dir,
        build_type=args.build_type,
        python=python,
        ninja=ninja if ninja.exists() else None,
        build_python=args.build_python,
        build_tests=args.build_tests,
        allow_network=args.allow_network,
        extra_args=[],
    )
    print("Configure command:")
    print(" ".join(cmd))
    return 0
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/python/test_configure_build.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit cache guard and command generation**

Run:

```bash
git add scripts/configure_build.py tests/python/test_configure_build.py
git commit -m "build: guard stale cmake caches"
```

Expected: commit contains script and test updates only.

---

## Task 3: Local Dependency Hint Discovery

**Files:**
- Modify: `scripts/configure_build.py`
- Modify: `tests/python/test_configure_build.py`

- [ ] **Step 1: Add failing tests for discovered CMake arguments**

Append to `tests/python/test_configure_build.py`:

```python
def test_discover_dependency_hints_from_conda_cache(tmp_path):
    pkgs = tmp_path / "pkgs"
    sqlite = pkgs / "sqlite-3.51.0-h_0"
    openssl = pkgs / "openssl-3.0.18-h_0"
    curl = pkgs / "libcurl-8.9.1-h_0"
    icu = pkgs / "icu-73.1-h_0"
    for root in (sqlite, openssl, curl, icu):
        (root / "include").mkdir(parents=True)
        (root / "lib").mkdir()
    (sqlite / "include" / "sqlite3.h").write_text('#define SQLITE_VERSION "3.51.0"\n')
    (sqlite / "lib" / "libsqlite3.so").write_text("")
    (openssl / "include" / "openssl").mkdir()
    (openssl / "include" / "openssl" / "ssl.h").write_text("")
    (openssl / "lib" / "libssl.so").write_text("")
    (openssl / "lib" / "libcrypto.so").write_text("")
    (curl / "include" / "curl").mkdir()
    (curl / "include" / "curl" / "curl.h").write_text("")
    (curl / "lib" / "libcurl.so").write_text("")
    (icu / "include" / "unicode").mkdir()
    (icu / "include" / "unicode" / "utypes.h").write_text("")
    (icu / "lib" / "libicuuc.so").write_text("")

    hints = cb.discover_dependency_hints(
        system="Linux",
        pkg_roots=[pkgs],
        build_dirs=[],
        python=Path("/venv/bin/python"),
    )

    args = set(hints.cmake_args)
    assert f"-DSQLite3_INCLUDE_DIR={sqlite / 'include'}" in args
    assert f"-DSQLite3_LIBRARY={sqlite / 'lib' / 'libsqlite3.so'}" in args
    assert f"-DOPENSSL_ROOT_DIR={openssl}" in args
    assert f"-DCURL_LIBRARY={curl / 'lib' / 'libcurl.so'}" in args
    assert f"-DICU_ROOT={icu}" in args
    assert any("SQLite" in note for note in hints.notes)


def test_discover_dependency_hints_rejects_old_sqlite(tmp_path):
    pkgs = tmp_path / "pkgs"
    sqlite = pkgs / "sqlite-3.45.0-h_0"
    (sqlite / "include").mkdir(parents=True)
    (sqlite / "lib").mkdir()
    (sqlite / "include" / "sqlite3.h").write_text('#define SQLITE_VERSION "3.45.0"\n')
    (sqlite / "lib" / "libsqlite3.so").write_text("")

    with pytest.raises(cb.BuildConfigError, match="SQLite"):
        cb.discover_dependency_hints(
            system="Linux",
            pkg_roots=[pkgs],
            build_dirs=[],
            python=Path("/venv/bin/python"),
        )


def test_fetchcontent_args_include_existing_sources(tmp_path):
    build = tmp_path / "build"
    (build / "_deps" / "json-src").mkdir(parents=True)
    (build / "_deps" / "googletest-src").mkdir(parents=True)

    args = cb.fetchcontent_source_args([build])

    assert f"-DFETCHCONTENT_SOURCE_DIR_JSON={build / '_deps' / 'json-src'}" in args
    assert f"-DFETCHCONTENT_SOURCE_DIR_GOOGLETEST={build / '_deps' / 'googletest-src'}" in args
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/python/test_configure_build.py -q
```

Expected: FAIL because `discover_dependency_hints` is not implemented.

- [ ] **Step 3: Implement dependency hint discovery**

Add these helpers to `scripts/configure_build.py`:

```python
def shared_library_names(base: str, system: str) -> tuple[str, ...]:
    if system == "Darwin":
        return (f"lib{base}.dylib", f"{base}.dylib")
    return (f"lib{base}.so", f"{base}.so")


def append_pair_args(args: list[str], *, include_key: str, library_key: str, pair: LibraryPair) -> None:
    args.append(f"-D{include_key}={pair.include_dir}")
    args.append(f"-D{library_key}={pair.library}")


def discover_dependency_hints(
    *,
    system: str,
    pkg_roots: Iterable[Path],
    build_dirs: Iterable[Path],
    python: Path,
) -> DependencyHints:
    roots: list[Path] = []
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        roots.append(Path(conda_prefix).expanduser())
    if system == "Darwin":
        roots.extend(Path(p) for p in ("/opt/homebrew/opt/sqlite", "/opt/homebrew/opt/openssl@3", "/opt/homebrew/opt/curl", "/usr/local/opt/sqlite", "/usr/local/opt/openssl@3", "/usr/local/opt/curl"))
    roots.extend(conda_pkg_candidates(pkg_roots, "sqlite"))
    roots.extend(conda_pkg_candidates(pkg_roots, "openssl"))
    roots.extend(conda_pkg_candidates(pkg_roots, "libcurl"))
    roots.extend(conda_pkg_candidates(pkg_roots, "curl"))
    roots.extend(conda_pkg_candidates(pkg_roots, "icu"))

    args: list[str] = []
    notes: list[str] = []
    warnings: list[str] = []

    sqlite_pair = find_library_pair(roots, "include/sqlite3.h", shared_library_names("sqlite3", system))
    if sqlite_pair is not None:
        version = sqlite_header_version(sqlite_pair.include_dir / "sqlite3.h")
        if version is not None and version < MIN_SQLITE:
            raise BuildConfigError(
                f"SQLite {version[0]}.{version[1]}.{version[2]} found at {sqlite_pair.include_dir}; "
                "Starling requires SQLite >= 3.46. Install a newer sqlite package or pass -DSQLite3_* overrides."
            )
        append_pair_args(args, include_key="SQLite3_INCLUDE_DIR", library_key="SQLite3_LIBRARY", pair=sqlite_pair)
        notes.append(f"SQLite: {sqlite_pair.library}")

    ssl_pair = find_library_pair(roots, "include/openssl/ssl.h", shared_library_names("ssl", system))
    crypto_pair = find_library_pair(roots, "include/openssl/ssl.h", shared_library_names("crypto", system))
    if ssl_pair is not None and crypto_pair is not None:
        root = ssl_pair.include_dir.parent
        args.extend([
            f"-DOPENSSL_ROOT_DIR={root}",
            f"-DOPENSSL_INCLUDE_DIR={ssl_pair.include_dir}",
            f"-DOPENSSL_SSL_LIBRARY={ssl_pair.library}",
            f"-DOPENSSL_CRYPTO_LIBRARY={crypto_pair.library}",
        ])
        notes.append(f"OpenSSL: {root}")

    curl_pair = find_library_pair(roots, "include/curl/curl.h", shared_library_names("curl", system))
    if curl_pair is not None:
        append_pair_args(args, include_key="CURL_INCLUDE_DIR", library_key="CURL_LIBRARY", pair=curl_pair)
        notes.append(f"libcurl: {curl_pair.library}")

    if system != "Darwin":
        icu_pair = find_library_pair(roots, "include/unicode/utypes.h", shared_library_names("icuuc", system))
        if icu_pair is not None:
            root = icu_pair.include_dir.parent
            args.extend([
                f"-DICU_ROOT={root}",
                f"-DICU_INCLUDE_DIR={icu_pair.include_dir}",
                f"-DICU_UC_LIBRARY={icu_pair.library}",
                f"-DICU_UC_LIBRARY_RELEASE={icu_pair.library}",
            ])
            notes.append(f"ICU uc: {icu_pair.library}")
        else:
            warnings.append("ICU uc was not found locally; CMake will try system paths. On Debian/Ubuntu install libicu-dev.")

    pybind_dir = pybind11_cmake_dir(python)
    if pybind_dir is not None:
        args.append(f"-Dpybind11_DIR={pybind_dir}")
        notes.append(f"pybind11: {pybind_dir}")
    else:
        warnings.append(f"pybind11 is not importable from {python}; install requirements-build.txt in .venv.")

    args.extend(fetchcontent_source_args(build_dirs))
    return DependencyHints(cmake_args=tuple(args), notes=tuple(notes), warnings=tuple(warnings))
```

Update `main()` so `extra_args` comes from `discover_dependency_hints()`:

```python
    try:
        check_stale_cache(args.build_dir, expected_generator="Ninja")
        hints = discover_dependency_hints(
            system=platform.system(),
            pkg_roots=candidate_conda_pkg_roots(),
            build_dirs=[REPO_ROOT / "build", REPO_ROOT / "build-linux", REPO_ROOT / "build-macos", args.build_dir],
            python=python_executable(),
        )
    except BuildConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
```

Use `hints.cmake_args` in `cmake_configure_command()`, and print notes/warnings:

```python
    for note in hints.notes:
        print(f"found: {note}")
    for warning in hints.warnings:
        print(f"warning: {warning}", file=sys.stderr)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/python/test_configure_build.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit dependency discovery**

Run:

```bash
git add scripts/configure_build.py tests/python/test_configure_build.py
git commit -m "build: discover local dependency hints"
```

Expected: commit contains script and tests only.

---

## Task 4: CLI Execution Paths

**Files:**
- Modify: `scripts/configure_build.py`
- Modify: `tests/python/test_configure_build.py`

- [ ] **Step 1: Add failing tests for build/test/editable command planning**

Append to `tests/python/test_configure_build.py`:

```python
def test_planned_commands_include_configure_build_and_ctest(tmp_path):
    commands = cb.planned_commands(
        configure_cmd=["cmake", "-S", ".", "-B", str(tmp_path / "build")],
        build_dir=tmp_path / "build",
        build=True,
        test=True,
    )

    assert commands == [
        ["cmake", "-S", ".", "-B", str(tmp_path / "build")],
        ["cmake", "--build", str(tmp_path / "build")],
        ["ctest", "--test-dir", str(tmp_path / "build"), "--output-on-failure"],
    ]


def test_python_editable_command_passes_cmake_defines(tmp_path):
    cmd = cb.python_editable_command(
        build_dir=tmp_path / "build-linux",
        cmake_args=("-DSQLite3_LIBRARY=/sqlite/libsqlite3.so", "-DSTARLING_BUILD_TESTS=ON"),
    )

    assert cmd[:4] == [str(cb.python_executable()), "-m", "pip", "install"]
    assert "-e" in cmd
    assert "--no-build-isolation" in cmd
    assert f"--config-settings=build-dir={tmp_path / 'build-linux'}" in cmd
    assert "--config-settings=cmake.define.SQLite3_LIBRARY=/sqlite/libsqlite3.so" in cmd


def test_network_disabled_adds_fetchcontent_disconnected_define(tmp_path):
    cmd = cb.cmake_configure_command(
        build_dir=tmp_path / "build-linux",
        build_type="Release",
        python=tmp_path / "python",
        ninja=None,
        build_python=True,
        build_tests=True,
        extra_args=[],
        allow_network=False,
    )

    assert "-DFETCHCONTENT_FULLY_DISCONNECTED=ON" in cmd
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/python/test_configure_build.py -q
```

Expected: FAIL because the planning functions do not exist.

- [ ] **Step 3: Implement command planning and execution**

Add to `scripts/configure_build.py`:

```python
def planned_commands(
    *,
    configure_cmd: Sequence[str],
    build_dir: Path,
    build: bool,
    test: bool,
) -> list[list[str]]:
    commands = [list(configure_cmd)]
    if build:
        commands.append(["cmake", "--build", str(build_dir)])
    if test:
        commands.append(["ctest", "--test-dir", str(build_dir), "--output-on-failure"])
    return commands


def python_editable_command(*, build_dir: Path, cmake_args: Sequence[str]) -> list[str]:
    cmd = [
        str(python_executable()),
        "-m",
        "pip",
        "install",
        "-e",
        ".[dev]",
        "--no-build-isolation",
        f"--config-settings=build-dir={build_dir}",
    ]
    for arg in cmake_args:
        if not arg.startswith("-D"):
            continue
        key_value = arg[2:]
        cmd.append(f"--config-settings=cmake.define.{key_value}")
    return cmd


def install_build_tools(python: Path) -> None:
    run([str(python), "-m", "pip", "install", "-r", str(REPO_ROOT / "requirements-build.txt")])
```

Update `main()`:

```python
    python = python_executable()
    if args.install_build_tools:
        install_build_tools(python)
    ninja = REPO_ROOT / ".venv" / ("Scripts/ninja.exe" if os.name == "nt" else "bin/ninja")
    configure_cmd = cmake_configure_command(
        build_dir=args.build_dir,
        build_type=args.build_type,
        python=python,
        ninja=ninja if ninja.exists() else None,
        build_python=args.build_python,
        build_tests=args.build_tests,
        allow_network=args.allow_network,
        extra_args=list(hints.cmake_args),
    )
    if args.python_editable:
        run(python_editable_command(build_dir=args.build_dir, cmake_args=hints.cmake_args))
        return 0
    for cmd in planned_commands(configure_cmd=configure_cmd, build_dir=args.build_dir, build=args.build, test=args.test):
        run(cmd)
    return 0
```

Remove the old "Configure command" print-only block.

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/python/test_configure_build.py -q
```

Expected: PASS.

- [ ] **Step 5: Smoke-run CLI help**

Run:

```bash
.venv/bin/python scripts/configure_build.py --help
```

Expected: help text shows `--build`, `--test`, `--python-editable`, `--install-build-tools`, `--no-network`, `--no-python`, and `--no-tests`.

- [ ] **Step 6: Commit CLI paths**

Run:

```bash
git add scripts/configure_build.py tests/python/test_configure_build.py
git commit -m "build: wire configure build and editable commands"
```

Expected: commit contains script and tests only.

---

## Task 5: CMake Presets

**Files:**
- Create: `CMakePresets.json`
- Modify: `.gitignore`

- [ ] **Step 1: Create CMake presets**

Create `CMakePresets.json`:

```json
{
  "version": 6,
  "cmakeMinimumRequired": {
    "major": 3,
    "minor": 27,
    "patch": 0
  },
  "configurePresets": [
    {
      "name": "dev",
      "displayName": "Development",
      "generator": "Ninja",
      "binaryDir": "${sourceDir}/build-dev",
      "cacheVariables": {
        "CMAKE_BUILD_TYPE": "Debug",
        "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
        "STARLING_BUILD_PYTHON": "ON",
        "STARLING_BUILD_TESTS": "ON"
      }
    },
    {
      "name": "release",
      "displayName": "Release",
      "generator": "Ninja",
      "binaryDir": "${sourceDir}/build-release",
      "cacheVariables": {
        "CMAKE_BUILD_TYPE": "Release",
        "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
        "STARLING_BUILD_PYTHON": "ON",
        "STARLING_BUILD_TESTS": "ON"
      }
    },
    {
      "name": "linux-local",
      "displayName": "Linux local dependency build",
      "inherits": "release",
      "condition": {
        "type": "equals",
        "lhs": "${hostSystemName}",
        "rhs": "Linux"
      },
      "binaryDir": "${sourceDir}/build-linux"
    },
    {
      "name": "macos-local",
      "displayName": "macOS local dependency build",
      "inherits": "release",
      "condition": {
        "type": "equals",
        "lhs": "${hostSystemName}",
        "rhs": "Darwin"
      },
      "binaryDir": "${sourceDir}/build-macos"
    }
  ],
  "buildPresets": [
    {
      "name": "dev",
      "configurePreset": "dev"
    },
    {
      "name": "release",
      "configurePreset": "release"
    },
    {
      "name": "linux-local",
      "configurePreset": "linux-local"
    },
    {
      "name": "macos-local",
      "configurePreset": "macos-local"
    }
  ],
  "testPresets": [
    {
      "name": "dev",
      "configurePreset": "dev",
      "output": {
        "outputOnFailure": true
      }
    },
    {
      "name": "release",
      "configurePreset": "release",
      "output": {
        "outputOnFailure": true
      }
    },
    {
      "name": "linux-local",
      "configurePreset": "linux-local",
      "output": {
        "outputOnFailure": true
      }
    },
    {
      "name": "macos-local",
      "configurePreset": "macos-local",
      "output": {
        "outputOnFailure": true
      }
    }
  ]
}
```

- [ ] **Step 2: Ignore platform build directories**

If `.gitignore` does not already ignore these names, add:

```gitignore
build-dev/
build-release/
build-linux/
build-macos/
```

- [ ] **Step 3: Validate presets list**

Run:

```bash
.venv/bin/cmake --list-presets
```

Expected: output lists `dev`, `release`, and the platform-appropriate local preset.

- [ ] **Step 4: Commit presets**

Run:

```bash
git add CMakePresets.json .gitignore
git commit -m "build: add cmake presets"
```

Expected: commit contains only preset and ignore updates.

---

## Task 6: CMake Dependency Hardening

**Files:**
- Modify: `CMakeLists.txt`
- Modify: `tests/cpp/CMakeLists.txt`

- [ ] **Step 1: Inspect current CMake files before editing**

Run:

```bash
sed -n '1,220p' CMakeLists.txt
sed -n '1,80p' tests/cpp/CMakeLists.txt
```

Expected: `CMakeLists.txt` already includes the prior Linux ICU and PIC fixes. Preserve them.

- [ ] **Step 2: Add top-level diagnostic helper and dependency status messages**

In `CMakeLists.txt`, after `include(cmake/StarlingOptions.cmake)`, add:

```cmake
function(starling_dependency_hint name hint)
    message(STATUS "Starling dependency ${name}: ${hint}")
endfunction()
```

After `find_package(OpenSSL REQUIRED)`, add:

```cmake
starling_dependency_hint("OpenSSL" "${OPENSSL_VERSION} include=${OPENSSL_INCLUDE_DIR}")
```

After `find_package(SQLite3 3.46 REQUIRED)`, add:

```cmake
starling_dependency_hint("SQLite3" "${SQLite3_VERSION} include=${SQLite3_INCLUDE_DIRS}")
```

After `find_package(CURL REQUIRED)`, add:

```cmake
starling_dependency_hint("CURL" "${CURL_VERSION_STRING} include=${CURL_INCLUDE_DIRS}")
```

Inside the non-Apple ICU branch, after `find_package(ICU REQUIRED COMPONENTS uc)`, add:

```cmake
    starling_dependency_hint("ICU uc" "${ICU_VERSION} include=${ICU_INCLUDE_DIRS}")
```

- [ ] **Step 3: Add SQLite imported-target compatibility**

Before `target_link_libraries(starling_core PUBLIC ...)`, add:

```cmake
if(TARGET SQLite3::SQLite3)
    set(STARLING_SQLITE_TARGET SQLite3::SQLite3)
elseif(TARGET SQLite::SQLite3)
    set(STARLING_SQLITE_TARGET SQLite::SQLite3)
else()
    message(FATAL_ERROR "SQLite3 target not found after find_package(SQLite3). Pass -DSQLite3_INCLUDE_DIR and -DSQLite3_LIBRARY if CMake cannot locate SQLite >= 3.46.")
endif()
```

Change the link line from:

```cmake
target_link_libraries(starling_core PUBLIC OpenSSL::Crypto SQLite::SQLite3
```

to:

```cmake
target_link_libraries(starling_core PUBLIC OpenSSL::Crypto ${STARLING_SQLITE_TARGET}
```

- [ ] **Step 4: Make nlohmann/json local override message explicit**

Replace the existing nlohmann/json `if(NOT nlohmann_json_FOUND)` block with:

```cmake
find_package(nlohmann_json 3.11 QUIET)
if(nlohmann_json_FOUND)
    starling_dependency_hint("nlohmann_json" "package config")
else()
    include(FetchContent)
    if(DEFINED FETCHCONTENT_SOURCE_DIR_JSON)
        starling_dependency_hint("nlohmann_json" "local source ${FETCHCONTENT_SOURCE_DIR_JSON}")
    else()
        starling_dependency_hint("nlohmann_json" "FetchContent network fallback")
    endif()
    FetchContent_Declare(json
        GIT_REPOSITORY https://github.com/nlohmann/json.git
        GIT_TAG v3.11.3)
    FetchContent_MakeAvailable(json)
endif()
```

- [ ] **Step 5: Make GoogleTest local override message explicit**

In `tests/cpp/CMakeLists.txt`, before `FetchContent_Declare(googletest ...)`, add:

```cmake
if(DEFINED FETCHCONTENT_SOURCE_DIR_GOOGLETEST)
    message(STATUS "Starling dependency GoogleTest: local source ${FETCHCONTENT_SOURCE_DIR_GOOGLETEST}")
else()
    message(STATUS "Starling dependency GoogleTest: FetchContent network fallback")
endif()
```

- [ ] **Step 6: Configure with the existing local build command**

Run the command printed by the new script without building first:

```bash
.venv/bin/python scripts/configure_build.py --build-dir build-linux
```

Expected: configure succeeds or prints a clear actionable error. If it only prints commands because previous tasks left dry-run behavior by mistake, fix `main()` so configure actually runs.

- [ ] **Step 7: Commit CMake hardening**

Run:

```bash
git add CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "build: harden cmake dependency discovery"
```

Expected: commit includes only CMake files.

---

## Task 7: Runtime Link Narrowing For Conda libcurl

**Files:**
- Modify: `scripts/configure_build.py`
- Modify: `tests/python/test_configure_build.py`

- [ ] **Step 1: Add failing tests for narrow libssh2 rpath**

Append to `tests/python/test_configure_build.py`:

```python
def test_runtime_link_args_add_narrow_libssh2_dir(tmp_path):
    curl_root = tmp_path / "libcurl-8.9.1-h_0"
    ssh_root = tmp_path / "libssh2-1.11.1-h_0"
    (curl_root / "lib").mkdir(parents=True)
    (curl_root / "lib" / "libcurl.so").write_text("")
    (ssh_root / "lib").mkdir(parents=True)
    (ssh_root / "lib" / "libssh2.so").write_text("")

    args = cb.runtime_link_args_for_linux(curl_root / "lib" / "libcurl.so", [tmp_path])

    assert f"-DCMAKE_BUILD_RPATH={ssh_root / 'lib'}" in args
    assert "-DCMAKE_EXE_LINKER_FLAGS=-Wl,--disable-new-dtags" in args
    assert "-DCMAKE_SHARED_LINKER_FLAGS=-Wl,--disable-new-dtags" in args


def test_runtime_link_args_do_not_add_conda_root_lib(tmp_path):
    curl = tmp_path / "miniconda3" / "pkgs" / "libcurl-8.9.1-h_0" / "lib" / "libcurl.so"
    curl.parent.mkdir(parents=True)
    curl.write_text("")
    args = cb.runtime_link_args_for_linux(curl, [tmp_path / "miniconda3" / "pkgs"])

    assert all(str(tmp_path / "miniconda3" / "lib") not in arg for arg in args)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/python/test_configure_build.py -q
```

Expected: FAIL because `runtime_link_args_for_linux` is not implemented.

- [ ] **Step 3: Implement narrow runtime link hints**

Add to `scripts/configure_build.py`:

```python
def runtime_link_args_for_linux(curl_library: Path, pkg_roots: Iterable[Path]) -> list[str]:
    if curl_library.suffix != ".so":
        return []
    args: list[str] = []
    for root in pkg_roots:
        for candidate in conda_pkg_candidates([root], "libssh2"):
            libdir = candidate / "lib"
            if (libdir / "libssh2.so").exists():
                args.extend([
                    f"-DCMAKE_BUILD_RPATH={libdir}",
                    "-DCMAKE_EXE_LINKER_FLAGS=-Wl,--disable-new-dtags",
                    "-DCMAKE_SHARED_LINKER_FLAGS=-Wl,--disable-new-dtags",
                ])
                return args
    return args
```

Update `discover_dependency_hints()` after libcurl is found:

```python
        if system == "Linux":
            runtime_args = runtime_link_args_for_linux(curl_pair.library, pkg_roots)
            if runtime_args:
                args.extend(runtime_args)
                notes.append("Linux runtime link: added narrow libssh2 rpath for conda libcurl")
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/python/test_configure_build.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit runtime link narrowing**

Run:

```bash
git add scripts/configure_build.py tests/python/test_configure_build.py
git commit -m "build: add narrow linux runtime link hints"
```

Expected: commit contains script and tests only.

---

## Task 8: README Build Documentation

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`

- [ ] **Step 1: Update English README build section**

In `README.md`, replace the current "Build & test" step-by-step section with content that keeps the same structure but uses this recommended path:

```markdown
## Build & test

Recommended path from the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements-build.txt
python scripts/configure_build.py --build --test
```

The script is local-first. It reuses tools and dependency sources from `.venv`,
an active conda environment, conda package caches, Homebrew, system packages,
and existing `build/_deps` sources before letting CMake `FetchContent` use the
network for nlohmann/json or GoogleTest.

Direct CMake users can run:

```bash
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

Python editable install:

```bash
python scripts/configure_build.py --python-editable
```

After changing C++ sources, rebuild:

```bash
cmake --build build-linux   # Linux default from the script
cmake --build build-macos   # macOS default from the script
```

Troubleshooting:

- Stale `build/`: use `build-linux`, `build-macos`, or another fresh build dir.
- SQLite: Starling requires SQLite >= 3.46.
- Linux ICU: install `libicu-dev` or provide ICU CMake variables.
- Offline FetchContent: rerun after a prior successful download or pass
  `-DFETCHCONTENT_SOURCE_DIR_JSON=...` and
  `-DFETCHCONTENT_SOURCE_DIR_GOOGLETEST=...`.
- Conda linker wrappers: avoid CMake caches containing `compiler_compat`.
- Conda libstdc++ conflicts: do not add all of `~/miniconda3/lib` to rpath.
```

Preserve the Dashboard section and all non-build README content.

- [ ] **Step 2: Update Chinese README build section**

In `README.zh-CN.md`, make the equivalent Chinese update:

```markdown
## 构建与测试

推荐从仓库根目录运行:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements-build.txt
python scripts/configure_build.py --build --test
```

这个脚本优先复用本机依赖: `.venv`、当前 conda 环境、conda package cache、Homebrew、系统包、以及已有的 `build/_deps` 源码。只有本机找不到 nlohmann/json 或 GoogleTest 时，才交给 CMake `FetchContent` 尝试联网兜底。

直接使用 CMake:

```bash
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

Python editable 安装:

```bash
python scripts/configure_build.py --python-editable
```

改了 C++ 源码后重建:

```bash
cmake --build build-linux   # Linux 默认目录
cmake --build build-macos   # macOS 默认目录
```

排障:

- 旧 `build/` 污染: 换用 `build-linux`、`build-macos` 或另一个新目录。
- SQLite: 需要 SQLite >= 3.46。
- Linux ICU: 安装 `libicu-dev`，或手动传 ICU CMake 变量。
- 离线 FetchContent: 复用已有下载，或传
  `-DFETCHCONTENT_SOURCE_DIR_JSON=...` 和
  `-DFETCHCONTENT_SOURCE_DIR_GOOGLETEST=...`。
- conda linker wrapper: 避免复用带 `compiler_compat` 的 CMake cache。
- conda libstdc++ 冲突: 不要把整个 `~/miniconda3/lib` 加进 rpath。
```

Preserve the Dashboard section and all non-build README content.

- [ ] **Step 3: Check README command snippets**

Run:

```bash
rg -n "configure_build|cmake --preset|build-linux|compiler_compat|SQLite" README.md README.zh-CN.md
```

Expected: both README files mention the new script, direct CMake presets, platform build dirs, and troubleshooting.

- [ ] **Step 4: Commit docs**

Run:

```bash
git add README.md README.zh-CN.md
git commit -m "docs: simplify build instructions"
```

Expected: commit contains only README updates.

---

## Task 9: End-To-End Verification

**Files:**
- No source edits unless verification exposes a bug in prior tasks

- [ ] **Step 1: Run Python unit tests for build script**

Run:

```bash
.venv/bin/python -m pytest tests/python/test_configure_build.py -q
```

Expected: all build script tests pass.

- [ ] **Step 2: Configure through the new script**

Run:

```bash
.venv/bin/python scripts/configure_build.py --build-dir build-linux
```

Expected: CMake configure succeeds using local dependency hints, or exits with a clear diagnostic that names the missing dependency and override path.

- [ ] **Step 3: Build through the new script**

Run:

```bash
.venv/bin/python scripts/configure_build.py --build-dir build-linux --build
```

Expected: configure then build succeeds.

- [ ] **Step 4: Test through the new script**

Run:

```bash
.venv/bin/python scripts/configure_build.py --build-dir build-linux --build --test
```

Expected: build succeeds and `ctest` reports all C++ tests passing.

- [ ] **Step 5: Verify direct preset path**

Run:

```bash
.venv/bin/cmake --preset linux-local
.venv/bin/cmake --build --preset linux-local
.venv/bin/ctest --preset linux-local
```

Expected: direct preset path succeeds on Linux. On macOS, use `macos-local`.

- [ ] **Step 6: Verify Python editable path if dependency state permits**

Run:

```bash
.venv/bin/python scripts/configure_build.py --build-dir build-linux --python-editable
```

Expected: editable install succeeds without losing the persistent build directory. If network is unavailable and a source dependency is missing, document the exact failure and local override used.

- [ ] **Step 7: Run broad regression tests**

Run:

```bash
.venv/bin/ctest --test-dir build-linux --output-on-failure
.venv/bin/python -m pytest tests/python/test_configure_build.py -q
```

Expected: ctest and build-script unit tests pass.

- [ ] **Step 8: Handle any verification fixes**

If verification exposes a bug, return to the task that introduced the bug,
update that task's listed files, rerun that task's focused tests, and commit
with that task's commit message pattern. Do not make a catch-all verification
commit.

Expected: no additional commit from this step when verification passes.

---

## Self-Review Checklist

- Spec coverage: tasks cover local-first dependency discovery, network fallback through FetchContent, Linux/macOS support, direct CMake presets, Python editable path, stale cache diagnostics, rpath narrowing, docs, and verification.
- Placeholder scan: no task uses unresolved placeholders for implementation.
- Type consistency: helper names used in tests match the planned implementation names: `LibraryPair`, `DependencyHints`, `BuildConfigError`, `conda_pkg_candidates`, `find_library_pair`, `sqlite_header_version`, `check_stale_cache`, `cmake_configure_command`, `discover_dependency_hints`, `runtime_link_args_for_linux`, `planned_commands`, and `python_editable_command`.
