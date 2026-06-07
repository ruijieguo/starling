#!/usr/bin/env python3
"""Configure Starling builds with local-first dependency discovery."""

from __future__ import annotations

import argparse
import os
import platform
import re
import subprocess
import sys
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
        prefix = Path(conda_prefix).expanduser()
        if prefix.parent.name == "envs":
            roots.append(prefix.parent.parent / "pkgs")
        else:
            roots.append(prefix / "pkgs")
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


def shared_library_names(base: str, system: str) -> tuple[str, ...]:
    if system == "Darwin":
        return (f"lib{base}.dylib", f"{base}.dylib")
    return (f"lib{base}.so", f"{base}.so")


def append_pair_args(args: list[str], *, include_key: str, library_key: str, pair: LibraryPair) -> None:
    args.append(f"-D{include_key}={pair.include_dir}")
    args.append(f"-D{library_key}={pair.library}")


def ordered_dependency_roots(system: str, pkg_roots: Iterable[Path]) -> list[Path]:
    roots: list[Path] = []
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        roots.append(Path(conda_prefix).expanduser())
    if system == "Darwin":
        roots.extend(
            Path(p)
            for p in (
                "/opt/homebrew/opt/sqlite",
                "/opt/homebrew/opt/openssl@3",
                "/opt/homebrew/opt/curl",
                "/usr/local/opt/sqlite",
                "/usr/local/opt/openssl@3",
                "/usr/local/opt/curl",
            )
        )
    roots.extend(conda_pkg_candidates(pkg_roots, "sqlite"))
    roots.extend(conda_pkg_candidates(pkg_roots, "openssl"))
    roots.extend(conda_pkg_candidates(pkg_roots, "libcurl"))
    roots.extend(conda_pkg_candidates(pkg_roots, "curl"))
    roots.extend(conda_pkg_candidates(pkg_roots, "icu"))

    unique: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        key = root.resolve() if root.exists() else root
        if key in seen:
            continue
        unique.append(root)
        seen.add(key)
    return unique


def absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def conda_pkg_root_for_curl_library(curl_library: Path, pkg_roots: Iterable[Path]) -> Path | None:
    if curl_library.name != "libcurl.so":
        return None
    library = absolute_path(curl_library)
    for pkg_root in pkg_roots:
        root = absolute_path(pkg_root)
        try:
            rel = library.relative_to(root)
        except ValueError:
            continue
        if len(rel.parts) != 3:
            continue
        package, libdir, libname = rel.parts
        if libdir == "lib" and libname == "libcurl.so" and (
            package.startswith("libcurl-") or package.startswith("curl-")
        ):
            return pkg_root
    return None


def unique_cmake_list(values: Iterable[str | Path]) -> list[str]:
    result: list[str] = []
    for value in values:
        for item in str(value).split(";"):
            if item and item not in result:
                result.append(item)
    return result


def append_linker_flag(existing_flags: str, flag: str) -> str:
    flags = existing_flags.strip()
    if flag in flags.split():
        return flags
    return f"{flags} {flag}".strip()


def runtime_link_args_for_linux(
    curl_library: Path,
    pkg_roots: Iterable[Path],
    *,
    existing_build_rpath: Iterable[str | Path] = (),
    existing_exe_linker_flags: str = "",
    existing_shared_linker_flags: str = "",
) -> list[str]:
    if curl_library.suffix != ".so":
        return []
    pkg_root = conda_pkg_root_for_curl_library(curl_library, pkg_roots)
    if pkg_root is None:
        return []
    args: list[str] = []
    for candidate in conda_pkg_candidates([pkg_root], "libssh2"):
        libdir = candidate / "lib"
        if (libdir / "libssh2.so").exists():
            rpath = unique_cmake_list(existing_build_rpath)
            libdir_text = str(libdir)
            if libdir_text not in rpath:
                rpath.append(libdir_text)
            exe_flags = append_linker_flag(existing_exe_linker_flags, "-Wl,--disable-new-dtags")
            shared_flags = append_linker_flag(existing_shared_linker_flags, "-Wl,--disable-new-dtags")
            args.extend(
                [
                    f"-DCMAKE_BUILD_RPATH={';'.join(rpath)}",
                    f"-DCMAKE_EXE_LINKER_FLAGS={exe_flags}",
                    f"-DCMAKE_SHARED_LINKER_FLAGS={shared_flags}",
                ]
            )
            return args
    return args


def find_openssl_root(roots: Iterable[Path], system: str) -> tuple[Path, LibraryPair, Path] | None:
    ssl_names = shared_library_names("ssl", system)
    crypto_names = shared_library_names("crypto", system)
    for root in roots:
        ssl_pair = find_library_pair([root], "include/openssl/ssl.h", ssl_names)
        if ssl_pair is None:
            continue
        crypto = next(
            (
                libdir / libname
                for libdir in (root / "lib", root / "lib64")
                for libname in crypto_names
                if (libdir / libname).exists()
            ),
            None,
        )
        if crypto is not None:
            return root, ssl_pair, crypto
    return None


def discover_dependency_hints(
    *,
    system: str,
    pkg_roots: Iterable[Path],
    build_dirs: Iterable[Path],
    python: Path,
    existing_build_rpath: Iterable[str | Path] = (),
    existing_exe_linker_flags: str = "",
    existing_shared_linker_flags: str = "",
) -> DependencyHints:
    pkg_root_list = list(pkg_roots)
    roots = ordered_dependency_roots(system, pkg_root_list)

    args: list[str] = []
    notes: list[str] = []
    warnings: list[str] = []

    sqlite_pair: LibraryPair | None = None
    sqlite_error: BuildConfigError | None = None
    for root in roots:
        candidate = find_library_pair([root], "include/sqlite3.h", shared_library_names("sqlite3", system))
        if candidate is None:
            continue
        version = sqlite_header_version(candidate.include_dir / "sqlite3.h")
        if version is not None and version < MIN_SQLITE:
            sqlite_error = BuildConfigError(
                f"SQLite {version[0]}.{version[1]}.{version[2]} found at {candidate.include_dir}; "
                "Starling requires SQLite >= 3.46. Install a newer sqlite package or pass -DSQLite3_* overrides."
            )
            continue
        sqlite_pair = candidate
        break
    if sqlite_pair is None and sqlite_error is not None:
        raise sqlite_error
    if sqlite_pair is not None:
        append_pair_args(args, include_key="SQLite3_INCLUDE_DIR", library_key="SQLite3_LIBRARY", pair=sqlite_pair)
        notes.append(f"SQLite: {sqlite_pair.library}")

    openssl = find_openssl_root(roots, system)
    if openssl is not None:
        root, ssl_pair, crypto = openssl
        args.extend(
            [
                f"-DOPENSSL_ROOT_DIR={root}",
                f"-DOPENSSL_INCLUDE_DIR={ssl_pair.include_dir}",
                f"-DOPENSSL_SSL_LIBRARY={ssl_pair.library}",
                f"-DOPENSSL_CRYPTO_LIBRARY={crypto}",
            ]
        )
        notes.append(f"OpenSSL: {root}")

    curl_pair = find_library_pair(roots, "include/curl/curl.h", shared_library_names("curl", system))
    if curl_pair is not None:
        append_pair_args(args, include_key="CURL_INCLUDE_DIR", library_key="CURL_LIBRARY", pair=curl_pair)
        notes.append(f"libcurl: {curl_pair.library}")
        if system == "Linux":
            runtime_args = runtime_link_args_for_linux(
                curl_pair.library,
                pkg_root_list,
                existing_build_rpath=existing_build_rpath,
                existing_exe_linker_flags=existing_exe_linker_flags,
                existing_shared_linker_flags=existing_shared_linker_flags,
            )
            if runtime_args:
                args.extend(runtime_args)
                notes.append("Linux runtime link: added narrow libssh2 rpath for conda libcurl")

    if system != "Darwin":
        icu_pair = find_library_pair(roots, "include/unicode/utypes.h", shared_library_names("icuuc", system))
        if icu_pair is not None:
            root = icu_pair.include_dir.parent
            args.extend(
                [
                    f"-DICU_ROOT={root}",
                    f"-DICU_INCLUDE_DIR={icu_pair.include_dir}",
                    f"-DICU_UC_LIBRARY={icu_pair.library}",
                    f"-DICU_UC_LIBRARY_RELEASE={icu_pair.library}",
                ]
            )
            notes.append(f"ICU uc: {icu_pair.library}")
        else:
            warnings.append(
                "ICU uc was not found locally; CMake will try system paths. On Debian/Ubuntu install libicu-dev."
            )

    pybind_dir = pybind11_cmake_dir(python)
    if pybind_dir is not None:
        args.append(f"-Dpybind11_DIR={pybind_dir}")
        notes.append(f"pybind11: {pybind_dir}")
    else:
        warnings.append(f"pybind11 is not importable from {python}; install requirements-build.txt in .venv.")

    args.extend(fetchcontent_source_args(build_dirs))
    return DependencyHints(cmake_args=tuple(args), notes=tuple(notes), warnings=tuple(warnings))


def python_executable() -> Path:
    venv_python = REPO_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return venv_python if venv_python.exists() else Path(sys.executable)


def pybind11_cmake_dir(python: Path) -> Path | None:
    code = "import pybind11, sys; sys.stdout.write(pybind11.get_cmake_dir())"
    try:
        result = subprocess.run([str(python), "-c", code], text=True, capture_output=True, check=False)
    except OSError:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    path = Path(result.stdout.strip())
    return path if path.exists() else None


def cache_value(cache_text: str, key: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(key)}(?::[^=]*)?=(.*)$", re.MULTILINE)
    match = pattern.search(cache_text)
    return match.group(1).strip() if match else None


def runtime_link_cache_values(build_dir: Path) -> tuple[tuple[str, ...], str, str]:
    cache = build_dir / "CMakeCache.txt"
    if not cache.exists():
        return (), "", ""
    text = cache.read_text(encoding="utf-8", errors="ignore")
    build_rpath = tuple(unique_cmake_list((cache_value(text, "CMAKE_BUILD_RPATH") or "",)))
    exe_flags = cache_value(text, "CMAKE_EXE_LINKER_FLAGS") or ""
    shared_flags = cache_value(text, "CMAKE_SHARED_LINKER_FLAGS") or ""
    return build_rpath, exe_flags, shared_flags


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
    compiler_args = (
        cache_value(text, "CMAKE_CXX_COMPILER_ARG1"),
        cache_value(text, "CMAKE_C_COMPILER_ARG1"),
    )
    if any(arg and "compiler_compat" in arg for arg in compiler_args):
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
    python = python_executable()
    if args.install_build_tools:
        install_build_tools(python)
    try:
        check_stale_cache(args.build_dir, expected_generator="Ninja")
        build_rpath, exe_linker_flags, shared_linker_flags = runtime_link_cache_values(args.build_dir)
        hints = discover_dependency_hints(
            system=platform.system(),
            pkg_roots=candidate_conda_pkg_roots(),
            build_dirs=[REPO_ROOT / "build", REPO_ROOT / "build-linux", REPO_ROOT / "build-macos", args.build_dir],
            python=python,
            existing_build_rpath=build_rpath,
            existing_exe_linker_flags=exe_linker_flags,
            existing_shared_linker_flags=shared_linker_flags,
        )
    except BuildConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    ninja = REPO_ROOT / ".venv" / ("Scripts/ninja.exe" if os.name == "nt" else "bin/ninja")
    configure_cmd = cmake_configure_command(
        build_dir=args.build_dir,
        build_type=args.build_type,
        python=python,
        ninja=ninja if ninja.exists() else None,
        build_python=args.build_python,
        build_tests=args.build_tests,
        allow_network=args.allow_network,
        extra_args=hints.cmake_args,
    )
    for note in hints.notes:
        print(f"found: {note}")
    for warning in hints.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if args.python_editable:
        run(python_editable_command(build_dir=args.build_dir, cmake_args=hints.cmake_args))
        return 0
    for cmd in planned_commands(configure_cmd=configure_cmd, build_dir=args.build_dir, build=args.build, test=args.test):
        run(cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
