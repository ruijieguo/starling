#!/usr/bin/env python3
"""Gate C++ on NEW clang-tidy diagnostics (changed *lines*), not the backlog.

The tree has never been clang-tidy-clean (CI configure never passed until the
clang-tidy step was added in PR #2). `.clang-tidy` sets
``HeaderFilterRegex: 'include/starling/.*'`` + ``WarningsAsErrors: '*'``, so
linting a changed ``.cpp`` ALSO reports every advisory in the starling headers
it includes — which fails a PR on pre-existing debt that isn't its own
(``performance-enum-size`` on the ledger enums, ``cppcoreguidelines-avoid-const-
or-ref-data-members`` on reference members like ``PipelineLedger::conn_``, short
identifier names...). The earlier changed-*files* step tripped over exactly this
and blocked any C++ PR that touched a ``.cpp`` whose header carries debt.

Fix: build a clang-tidy ``-line-filter`` from the diff (changed C/C++ lines —
``.cpp`` AND ``.hpp``) and run clang-tidy on the changed ``.cpp`` translation
units. clang-tidy only emits a diagnostic whose file+line is in the filter, so:
  * a changed header line IS checked (the TU that includes it is linted, the
    line is in the filter, HeaderFilterRegex lets it through), and
  * an unchanged header line — the backlog — is dropped.
Only diagnostics on the lines this change touches can fail CI.

Usage:
  ci_clang_tidy_diff.py <base_sha> [build_dir]
    base_sha   git ref to diff against (three-dot: <base>...HEAD, i.e. the
               change's own commits since the merge-base — not main's drift).
    build_dir  CMake build dir with compile_commands.json (default: build).

Env:
  CLANG_TIDY  clang-tidy binary (default: clang-tidy-17). Set to ``echo`` to
              print the invocation instead of running it (local dry-run).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# `@@ -<old> +<new_start>[,<new_count>] @@` — we only need the new-side span.
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_CXX_ANY = (".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hxx", ".hh")
_CXX_TU = (".cpp", ".cc", ".cxx", ".c")
_TU_ROOTS = ("src/", "bindings/")
_ZERO_SHA = "0000000000000000000000000000000000000000"

# Whole-function / whole-signature shape checks: clang-tidy anchors these at the
# function DECLARATION and computes them over the entire body or parameter list, so
# they surface whenever a pre-existing function is *touched* (e.g. a void→bool
# return-type change) even though the specific changed line did not introduce the
# shape. They cannot be attributed to a single changed line and -line-filter does not
# reliably suppress them, so a changed-LINES gate must not enforce them:
#   - function-cognitive-complexity / function-size: whole-BODY metrics (the run()
#     orchestrator is cognitive-complexity 70 ≫ 25 and blocked an unrelated body edit).
#   - easily-swappable-parameters / convert-member-functions-to-static: whole-
#     SIGNATURE shape (N adjacent same-type params; whether the body uses `this`) —
#     these fire on every sibling in a class of conn-passing methods the instant one
#     is touched (commitment fulfill/withdraw: void→bool re-flagged the pre-existing
#     4-string_view signature + "could be static" across the whole engine).
# Appended to .clang-tidy via --checks (a leading '-' disables); .clang-tidy still
# enforces all of them for any full-tree / whole-function review.
_GATE_DISABLED_CHECKS = (
    "-readability-function-cognitive-complexity,"
    "-readability-function-size,"
    "-bugprone-easily-swappable-parameters,"
    "-readability-convert-member-functions-to-static"
)


def changed_lines(base: str) -> dict[str, list[list[int]]]:
    """path -> added-line ranges [[start, end], ...], from ``git diff -U0``."""
    out = subprocess.run(
        ["git", "diff", "-U0", "--diff-filter=ACMR", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    ranges: dict[str, list[list[int]]] = {}
    path: str | None = None
    for line in out.splitlines():
        if line.startswith("+++ "):
            p = line[4:].strip()
            if p == "/dev/null":
                path = None
            else:
                path = p[2:] if p.startswith("b/") else p
        elif line.startswith("@@") and path is not None:
            m = _HUNK.match(line)
            if not m:
                continue
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            if count == 0:  # pure deletion — no added lines on the new side
                continue
            ranges.setdefault(path, []).append([start, start + count - 1])
    return ranges


def tus_in_build(tus: list[str], build_dir: str) -> tuple[list[str], list[str]]:
    """Split changed TUs into (in-build, not-in-build) via compile_commands.json.

    A changed ``.cpp`` that the current CMake config doesn't compile (platform
    guard, test-only, etc.) has no compile command — passing it to clang-tidy
    would error and falsely fail CI. Keep only files clang-tidy can actually
    build; the caller logs the dropped ones (no silent skips).
    """
    cc_path = os.path.join(build_dir, "compile_commands.json")
    try:
        with open(cc_path, encoding="utf-8") as f:
            entries = json.load(f)
    except (OSError, ValueError):
        return tus, []  # no/unreadable compile db — let clang-tidy decide
    known = {os.path.realpath(e["file"]) for e in entries if e.get("file")}
    cwd = os.getcwd()
    in_build, missing = [], []
    for t in tus:
        (in_build if os.path.realpath(os.path.join(cwd, t)) in known else missing).append(t)
    return in_build, missing


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: ci_clang_tidy_diff.py <base_sha> [build_dir]", file=sys.stderr)
        return 2
    base = sys.argv[1]
    build_dir = sys.argv[2] if len(sys.argv) > 2 else "build"
    tidy = os.environ.get("CLANG_TIDY", "clang-tidy-17")

    if not base or base == _ZERO_SHA:
        print("No base ref to diff against — skipping (changed-lines gate).")
        return 0

    ranges = changed_lines(base)

    # line-filter: every changed C/C++ file (TU or header). This is what makes
    # the gate changed-*lines*: clang-tidy drops any diagnostic not named here.
    line_filter = [
        {"name": p, "lines": rs}
        for p, rs in sorted(ranges.items())
        if p.endswith(_CXX_ANY)
    ]
    if not line_filter:
        print("No changed C/C++ lines to lint.")
        return 0

    tus_changed = sorted(
        p for p in ranges if p.endswith(_CXX_TU) and p.startswith(_TU_ROOTS)
    )
    if not tus_changed:
        print(
            "Changed C/C++ lines are header-only (no .cpp TU under src/|bindings/). "
            "A header is linted via a TU that includes it; none changed, so there is "
            "nothing to compile-and-lint. Skipping."
        )
        return 0

    tus, missing = tus_in_build(tus_changed, build_dir)
    if missing:
        print("NOTE: changed .cpp not in this build config (not linted): " + ", ".join(missing))
    if not tus:
        print("No changed .cpp present in the build's compile_commands.json. Skipping.")
        return 0

    print(f"clang-tidy ({tidy}) on changed lines of:")
    for t in tus:
        print(f"  {t}")

    cmd = [tidy, "-p", build_dir, "--checks=" + _GATE_DISABLED_CHECKS,
           "-line-filter=" + json.dumps(line_filter), *tus]
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())
