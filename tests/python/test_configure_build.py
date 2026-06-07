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
