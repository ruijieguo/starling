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


def test_runtime_link_cache_values_read_existing_flags(tmp_path):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "CMakeCache.txt").write_text(
        "\n".join(
            [
                "CMAKE_BUILD_RPATH:STRING=/existing/a;/existing/b",
                "CMAKE_EXE_LINKER_FLAGS:STRING=-Wl,-z,relro",
                "CMAKE_SHARED_LINKER_FLAGS:STRING=-Wl,-O1",
                "CMAKE_MODULE_LINKER_FLAGS:STRING=-Wl,-z,now",
            ]
        ),
        encoding="utf-8",
    )

    build_rpath, exe_flags, shared_flags, module_flags = cb.runtime_link_cache_values(build_dir)

    assert build_rpath == ("/existing/a", "/existing/b")
    assert exe_flags == "-Wl,-z,relro"
    assert shared_flags == "-Wl,-O1"
    assert module_flags == "-Wl,-z,now"


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


def test_ordered_dependency_roots_prefers_package_cache_before_conda_prefix(tmp_path, monkeypatch):
    prefix = tmp_path / "env"
    pkgs = tmp_path / "pkgs"
    sqlite_cache = pkgs / "sqlite-3.51.0-h_0"
    openssl_cache = pkgs / "openssl-3.0.18-h_0"
    prefix.mkdir()
    sqlite_cache.mkdir(parents=True)
    openssl_cache.mkdir()
    monkeypatch.setenv("CONDA_PREFIX", str(prefix))

    roots = cb.ordered_dependency_roots("Linux", [pkgs])

    assert roots[:3] == [sqlite_cache, openssl_cache, prefix]


def test_discover_dependency_hints_from_conda_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    monkeypatch.setattr(cb, "pybind11_cmake_dir", lambda python: None)
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


def test_discover_dependency_hints_rejects_old_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    monkeypatch.setattr(cb, "pybind11_cmake_dir", lambda python: None)
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


def test_discover_dependency_hints_skips_old_conda_prefix_sqlite_for_cache(tmp_path, monkeypatch):
    prefix = tmp_path / "env"
    cache = tmp_path / "pkgs"
    old_sqlite = prefix
    new_sqlite = cache / "sqlite-3.51.0-h_0"
    for root in (old_sqlite, new_sqlite):
        (root / "include").mkdir(parents=True)
        (root / "lib").mkdir()
        (root / "lib" / "libsqlite3.so").write_text("")
    (old_sqlite / "include" / "sqlite3.h").write_text('#define SQLITE_VERSION "3.45.0"\n')
    (new_sqlite / "include" / "sqlite3.h").write_text('#define SQLITE_VERSION "3.51.0"\n')
    monkeypatch.setenv("CONDA_PREFIX", str(prefix))
    monkeypatch.setattr(cb, "pybind11_cmake_dir", lambda python: None)

    hints = cb.discover_dependency_hints(
        system="Linux",
        pkg_roots=[cache],
        build_dirs=[],
        python=Path("/venv/bin/python"),
    )

    args = set(hints.cmake_args)
    assert f"-DSQLite3_INCLUDE_DIR={new_sqlite / 'include'}" in args
    assert f"-DSQLite3_LIBRARY={new_sqlite / 'lib' / 'libsqlite3.so'}" in args


def test_discover_dependency_hints_prefers_package_cache_over_broad_conda_root_libs(tmp_path, monkeypatch):
    conda = tmp_path / "miniconda3"
    pkgs = conda / "pkgs"
    (conda / "include" / "openssl").mkdir(parents=True)
    (conda / "include" / "curl").mkdir(parents=True)
    (conda / "include" / "unicode").mkdir(parents=True)
    (conda / "lib").mkdir()
    (conda / "include" / "openssl" / "ssl.h").write_text("")
    (conda / "include" / "curl" / "curl.h").write_text("")
    (conda / "include" / "unicode" / "utypes.h").write_text("")
    (conda / "lib" / "libssl.so").write_text("")
    (conda / "lib" / "libcrypto.so").write_text("")
    (conda / "lib" / "libcurl.so").write_text("")
    (conda / "lib" / "libicuuc.so").write_text("")

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
    monkeypatch.setenv("CONDA_PREFIX", str(conda))
    monkeypatch.setattr(cb, "pybind11_cmake_dir", lambda python: None)

    hints = cb.discover_dependency_hints(
        system="Linux",
        pkg_roots=[pkgs],
        build_dirs=[],
        python=Path("/venv/bin/python"),
    )

    args = set(hints.cmake_args)
    assert f"-DOPENSSL_ROOT_DIR={openssl}" in args
    assert f"-DCURL_LIBRARY={curl / 'lib' / 'libcurl.so'}" in args
    assert f"-DICU_UC_LIBRARY={icu / 'lib' / 'libicuuc.so'}" in args
    assert all(str(conda / "lib") not in arg for arg in args)


def test_discover_dependency_hints_requires_coherent_openssl_root(tmp_path, monkeypatch):
    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    monkeypatch.setattr(cb, "pybind11_cmake_dir", lambda python: None)
    pkgs = tmp_path / "pkgs"
    ssl_only = pkgs / "openssl-3.0.18-hssl_0"
    crypto_only = pkgs / "openssl-3.0.17-hcrypto_0"
    for root in (ssl_only, crypto_only):
        (root / "include" / "openssl").mkdir(parents=True)
        (root / "lib").mkdir()
        (root / "include" / "openssl" / "ssl.h").write_text("")
    (ssl_only / "lib" / "libssl.so").write_text("")
    (crypto_only / "lib" / "libcrypto.so").write_text("")

    hints = cb.discover_dependency_hints(
        system="Linux",
        pkg_roots=[pkgs],
        build_dirs=[],
        python=Path("/venv/bin/python"),
    )

    assert not any(arg.startswith("-DOPENSSL_") for arg in hints.cmake_args)


def test_fetchcontent_args_include_existing_sources(tmp_path):
    build = tmp_path / "build"
    (build / "_deps" / "json-src").mkdir(parents=True)
    (build / "_deps" / "googletest-src").mkdir(parents=True)

    args = cb.fetchcontent_source_args([build])

    assert f"-DFETCHCONTENT_SOURCE_DIR_JSON={build / '_deps' / 'json-src'}" in args
    assert f"-DFETCHCONTENT_SOURCE_DIR_GOOGLETEST={build / '_deps' / 'googletest-src'}" in args


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
    assert "-DCMAKE_MODULE_LINKER_FLAGS=-Wl,--disable-new-dtags" in args


def test_runtime_link_args_do_not_add_conda_root_lib(tmp_path):
    curl = tmp_path / "miniconda3" / "pkgs" / "libcurl-8.9.1-h_0" / "lib" / "libcurl.so"
    curl.parent.mkdir(parents=True)
    curl.write_text("")
    args = cb.runtime_link_args_for_linux(curl, [tmp_path / "miniconda3" / "pkgs"])

    assert all(str(tmp_path / "miniconda3" / "lib") not in arg for arg in args)


def test_runtime_link_args_filter_existing_broad_conda_root_rpath(tmp_path, monkeypatch):
    conda = tmp_path / "miniconda3"
    pkgs = conda / "pkgs"
    curl = pkgs / "libcurl-8.9.1-h_0" / "lib" / "libcurl.so"
    ssh = pkgs / "libssh2-1.11.1-h_0" / "lib" / "libssh2.so"
    keep = tmp_path / "custom" / "lib"
    curl.parent.mkdir(parents=True)
    ssh.parent.mkdir(parents=True)
    keep.mkdir(parents=True)
    curl.write_text("")
    ssh.write_text("")
    monkeypatch.setenv("CONDA_PREFIX", str(conda))

    args = cb.runtime_link_args_for_linux(
        curl,
        [pkgs],
        existing_build_rpath=[conda / "lib", keep],
    )

    assert f"-DCMAKE_BUILD_RPATH={keep};{ssh.parent}" in args
    assert all(str(conda / "lib") not in arg for arg in args)


def test_runtime_link_args_filter_dependency_broad_conda_root_rpath(tmp_path, monkeypatch):
    conda = tmp_path / "miniconda3"
    pkgs = conda / "pkgs"
    curl = pkgs / "libcurl-8.9.1-h_0" / "lib" / "libcurl.so"
    stdcxx = pkgs / "libstdcxx-15.2.0-h_0" / "lib" / "libstdc++.so.6"
    for path in (curl, stdcxx):
        path.parent.mkdir(parents=True)
        path.write_text("")
    monkeypatch.setenv("CONDA_PREFIX", str(conda))

    args = cb.runtime_link_args_for_linux(
        curl,
        [pkgs],
        dependency_library_dirs=[conda / "lib", curl.parent],
    )

    expected_rpath = f"{curl.parent};{stdcxx.parent}"
    assert f"-DCMAKE_BUILD_RPATH={expected_rpath}" in args
    assert f"-DCMAKE_INSTALL_RPATH={expected_rpath}" in args
    assert all(str(conda / "lib") not in arg for arg in args)


def test_runtime_link_args_add_install_rpath_with_dependency_and_stdlib_dirs(tmp_path):
    pkgs = tmp_path / "pkgs"
    curl = pkgs / "libcurl-8.9.1-h_0" / "lib" / "libcurl.so"
    ssh = pkgs / "libssh2-1.11.1-h_0" / "lib" / "libssh2.so"
    stdcxx = pkgs / "libstdcxx-15.2.0-h_0" / "lib" / "libstdc++.so.6"
    openssl_lib = pkgs / "openssl-3.0.18-h_0" / "lib"
    sqlite_lib = pkgs / "sqlite-3.51.0-h_0" / "lib"
    for path in (curl, ssh, stdcxx):
        path.parent.mkdir(parents=True)
        path.write_text("")
    openssl_lib.mkdir(parents=True)
    sqlite_lib.mkdir(parents=True)

    args = cb.runtime_link_args_for_linux(
        curl,
        [pkgs],
        dependency_library_dirs=[openssl_lib, sqlite_lib, curl.parent],
    )

    expected_rpath = f"{openssl_lib};{sqlite_lib};{curl.parent};{ssh.parent};{stdcxx.parent}"
    assert f"-DCMAKE_BUILD_RPATH={expected_rpath}" in args
    assert f"-DCMAKE_INSTALL_RPATH={expected_rpath}" in args


def test_runtime_link_args_add_stdlib_rpath_without_libssh2(tmp_path):
    pkgs = tmp_path / "pkgs"
    curl = pkgs / "libcurl-8.9.1-h_0" / "lib" / "libcurl.so"
    stdcxx = pkgs / "libstdcxx-15.2.0-h_0" / "lib" / "libstdc++.so.6"
    for path in (curl, stdcxx):
        path.parent.mkdir(parents=True)
        path.write_text("")

    args = cb.runtime_link_args_for_linux(
        curl,
        [pkgs],
        dependency_library_dirs=[curl.parent],
    )

    expected_rpath = f"{curl.parent};{stdcxx.parent}"
    assert f"-DCMAKE_BUILD_RPATH={expected_rpath}" in args
    assert f"-DCMAKE_INSTALL_RPATH={expected_rpath}" in args


def test_runtime_link_args_ignore_system_custom_libcurl(tmp_path):
    curl = tmp_path / "usr" / "local" / "lib" / "libcurl.so"
    ssh_root = tmp_path / "pkgs" / "libssh2-1.11.1-h_0"
    curl.parent.mkdir(parents=True)
    curl.write_text("")
    (ssh_root / "lib").mkdir(parents=True)
    (ssh_root / "lib" / "libssh2.so").write_text("")

    args = cb.runtime_link_args_for_linux(curl, [tmp_path / "pkgs"])

    assert args == []


def test_runtime_link_args_require_libssh2_from_same_pkg_root(tmp_path):
    curl = tmp_path / "pkgs-a" / "libcurl-8.9.1-h_0" / "lib" / "libcurl.so"
    ssh_root = tmp_path / "pkgs-b" / "libssh2-1.11.1-h_0"
    curl.parent.mkdir(parents=True)
    curl.write_text("")
    (ssh_root / "lib").mkdir(parents=True)
    (ssh_root / "lib" / "libssh2.so").write_text("")

    args = cb.runtime_link_args_for_linux(curl, [tmp_path / "pkgs-a", tmp_path / "pkgs-b"])

    assert args == []


def test_runtime_link_args_preserve_existing_values_and_deduplicate(tmp_path):
    curl = tmp_path / "pkgs" / "libcurl-8.9.1-h_0" / "lib" / "libcurl.so"
    ssh_root = tmp_path / "pkgs" / "libssh2-1.11.1-h_0"
    existing_rpath = tmp_path / "existing" / "lib"
    curl.parent.mkdir(parents=True)
    curl.write_text("")
    (ssh_root / "lib").mkdir(parents=True)
    (ssh_root / "lib" / "libssh2.so").write_text("")

    args = cb.runtime_link_args_for_linux(
        curl,
        [tmp_path / "pkgs"],
        existing_build_rpath=[existing_rpath],
        existing_exe_linker_flags="-Wl,-z,relro -Wl,--disable-new-dtags",
        existing_shared_linker_flags="-Wl,-O1",
        existing_module_linker_flags="-Wl,-z,now",
    )

    assert f"-DCMAKE_BUILD_RPATH={existing_rpath};{ssh_root / 'lib'}" in args
    assert "-DCMAKE_EXE_LINKER_FLAGS=-Wl,-z,relro -Wl,--disable-new-dtags" in args
    assert "-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-O1 -Wl,--disable-new-dtags" in args
    assert "-DCMAKE_MODULE_LINKER_FLAGS=-Wl,-z,now -Wl,--disable-new-dtags" in args
    assert sum("--disable-new-dtags" in arg for arg in args) == 3
