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
