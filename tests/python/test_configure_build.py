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


def test_candidate_conda_pkg_roots_include_base_prefix_cache(tmp_path, monkeypatch):
    base = tmp_path / "miniforge3"
    expected = base / "pkgs"
    monkeypatch.setenv("CONDA_PREFIX", str(base))

    roots = cb.candidate_conda_pkg_roots()

    assert expected in roots


def test_candidate_conda_pkg_roots_include_named_env_base_cache(tmp_path, monkeypatch):
    base = tmp_path / "miniforge3"
    prefix = base / "envs" / "dev"
    expected = base / "pkgs"
    monkeypatch.setenv("CONDA_PREFIX", str(prefix))

    roots = cb.candidate_conda_pkg_roots()

    assert expected in roots


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
