# Build Dependency + Configuration Robustness Design

**Date:** 2026-06-07
**Status:** Design approved; awaiting implementation plan

## Background

The project now builds successfully on the current Linux machine, but only after
using a long hand-written CMake configure command. The failed path exposed four
classes of fragility:

- `build/` can be polluted by stale cache entries, including conda
  `compiler_compat` linker wrappers.
- Linux dependency discovery is under-specified for SQLite >= 3.46, OpenSSL,
  libcurl, ICU, pybind11, nlohmann/json, and GoogleTest.
- Network-restricted environments fail when `FetchContent` is the first source
  for nlohmann/json or GoogleTest.
- Runtime linking can break if broad conda library directories are added to
  rpath, because they may pull an incompatible `libstdc++.so.6`; indirect
  libcurl dependencies also need explicit handling on Linux.

The README currently documents a Python editable path driven by
scikit-build-core, while CMake developers also need a direct CMake path. The
goal is one robust workflow that supports both paths.

## Goals

- Provide one recommended entrypoint that configures, builds, and optionally
  tests the project.
- Support both Linux and macOS.
- Prefer local dependencies first: virtualenv packages, active conda
  environments, conda package caches, Homebrew prefixes, system packages, and
  already-downloaded `build/_deps` sources.
- Allow automatic network fallback for missing source dependencies when the
  environment permits it, especially nlohmann/json and GoogleTest.
- Keep direct CMake usage simple through CMake presets.
- Keep Python editable builds supported and documented.
- Emit actionable diagnostics for missing or unsuitable dependencies.
- Avoid deleting or rewriting existing build directories automatically.

## Non-Goals

- Do not vendor third-party source code into the repository.
- Do not replace scikit-build-core as the Python build backend.
- Do not add package-manager-specific installers beyond Python build-tool
  installation into `.venv`.
- Do not make Linux depend on conda. Conda is only one discovery source.
- Do not alter product runtime behavior or database migrations.

## Recommended Approach

Use a small Python configuration entrypoint plus CMake presets and targeted CMake
hardening.

`scripts/configure_build.py` becomes the user-facing build assistant. It detects
local tools and dependencies, chooses a clean platform-specific build directory,
and invokes CMake with explicit cache variables when needed. `CMakePresets.json`
keeps the generated or recommended CMake invocation discoverable and lets users
run direct CMake commands without copying a long recipe. CMake itself remains
responsible for normal `find_package` calls, target wiring, and clear failure
messages, but it does not absorb all platform probing logic.

This keeps policy and filesystem heuristics in Python, while leaving build graph
ownership in CMake.

## User Workflows

Recommended one-command path:

```bash
python scripts/configure_build.py --build --test
```

Expected behavior:

1. Ensure `.venv` exists or report how to create it.
2. Ensure CMake, Ninja, scikit-build-core, and pybind11 are available from the
   virtualenv, installing from `requirements-build.txt` when the user requests
   automatic setup.
3. Detect local dependency locations and print the selected source for each.
4. Configure a platform build directory, defaulting to `build-linux` or
   `build-macos`.
5. Build with Ninja.
6. Run `ctest` when `--test` is supplied.

Direct CMake path:

```bash
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

Python editable path:

```bash
python scripts/configure_build.py --python-editable
```

The editable path should preserve the existing scikit-build-core behavior while
passing the same dependency hints where practical. It should also keep a
persistent build directory so C++ rebuilds and `ctest` remain available.

## Dependency Discovery

The configuration script uses a deterministic precedence order:

1. Explicit CLI flags and environment variables.
2. Active virtualenv packages, including `pybind11.get_cmake_dir()`.
3. Active conda environment, when `CONDA_PREFIX` is present.
4. Conda package caches under likely roots such as `~/miniconda3/pkgs` and
   `~/anaconda3/pkgs`.
5. Homebrew prefixes on macOS, including `/opt/homebrew` and `/usr/local`.
6. Existing local FetchContent sources under `build/_deps` and
   `build-linux/_deps`.
7. System `find_package` defaults.
8. Network fallback through CMake `FetchContent` for source dependencies.

For binary dependencies, the script only passes explicit paths when it can find a
coherent include/library pair. It should not add broad directories such as
`$CONDA_PREFIX/lib` to global rpath. Specific libraries are safer than prefix
wide linker state.

Required dependencies:

- SQLite >= 3.46
- OpenSSL crypto
- libcurl
- ICU `uc` on Linux
- Python >= 3.11 when Python bindings are enabled
- pybind11 for Python bindings
- nlohmann/json
- GoogleTest when tests are enabled

## CMake Changes

The top-level build should stay readable and target-oriented:

- Keep existing macOS Homebrew hints for OpenSSL and SQLite.
- Add Linux-safe hints only when they are narrow and reliable.
- Keep ICU required on non-Apple platforms because canonicalization uses ICU
  outside macOS.
- Prefer standard imported targets where available, with compatibility handling
  for existing `SQLite::SQLite3` usage if needed.
- Support local `FetchContent` overrides for nlohmann/json and GoogleTest via
  documented `FETCHCONTENT_SOURCE_DIR_*` variables.
- Ensure static libraries linked into Python modules are position-independent.
- Improve configure-time messages so missing dependencies point to the exact
  package or override variable to use.

`CMakePresets.json` should provide at least:

- `dev`: portable default, tests and Python enabled, Ninja generator.
- `release`: release build with tests and Python enabled.
- `linux-local`: Linux-oriented preset that the script can extend with detected
  local paths.
- `macos-local`: macOS-oriented preset that prefers Homebrew where present.

The presets should not hard-code user-specific absolute paths.

## Runtime Link Handling

Linux runtime linking must avoid the broad conda root library directory when it
would shadow the compiler runtime. If libcurl has indirect dependencies outside
standard loader paths, the configuration script should add the narrow dependency
directory or print a targeted diagnostic.

The current known case is `libssh2` for conda-provided libcurl. The script may
add a narrow build rpath for that directory and use linker flags that preserve
the intended lookup behavior, but it must not add all of `~/miniconda3/lib`.

## Error Handling

The script should fail before configure when it detects a known-bad state:

- The selected build directory contains a stale cache with a different generator
  or suspicious compiler linker wrapper.
- SQLite is found but older than 3.46.
- ICU is missing on Linux.
- Python bindings are requested but pybind11 cannot be imported from the chosen
  Python executable.
- A conda `compiler_compat` linker wrapper is present in CMake compiler
  arguments.

Failures should include:

- What was being detected.
- Which locations were checked.
- The exact override flag or package name to install.
- Whether network fallback is available for that dependency.

The script should recommend a new build directory instead of deleting an old one.

## Documentation

Update both README files:

- Make `python scripts/configure_build.py --build --test` the recommended path.
- Keep direct CMake and Python editable alternatives.
- Explain local-first dependency discovery and network fallback.
- Document Linux packages, macOS Homebrew packages, and conda cache reuse.
- Add troubleshooting entries for stale `build/`, FetchContent offline failures,
  SQLite version, ICU on Linux, conda `compiler_compat`, and rpath/libstdc++
  conflicts.

The existing `requirements-build.txt` and `requirements-dev.txt` remain the
source of Python build-tool installation guidance.

## Testing

Implementation should be verified with:

- Unit tests for dependency discovery helpers using temporary directories.
- Unit tests for stale cache detection and command generation.
- CMake configure smoke test using the script on the current Linux workspace.
- `cmake --build <configured-dir>`.
- `ctest --test-dir <configured-dir> --output-on-failure`.
- A Python editable smoke path when practical.

Manual macOS verification should be documented if no macOS runner is available
in the current environment.

## Acceptance Criteria

- A new developer can run one recommended command to configure and build without
  copying a long CMake command.
- Direct CMake and Python editable workflows both remain documented.
- Linux and macOS are both first-class documented targets.
- Local dependency sources are preferred over network access.
- Missing dependencies produce clear diagnostics.
- Existing source-level compile fixes remain compatible with the new workflow.
- The current Linux workspace builds and its C++ test suite passes through the
  new path.
