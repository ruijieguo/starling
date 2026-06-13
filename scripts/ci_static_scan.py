"""Defense-line #1: ban testing-namespace imports from prod entrypoints.

Scans configured prod roots for forbidden tokens:
  - `starling::testing`            (C++)
  - `starling.testing`             (Python imports / attribute access)
  - `starling_testing_marker`      (CMake target name in non-CMake source)

Lines tagged with `NOLINT(starling-testing-isolation)` are skipped. The skip
also covers contiguous non-blank lines around the NOLINT line (i.e. the
"paragraph" containing the pragma), so a single NOLINT comment can suppress
a docstring + import block in a `.pyi` stub. Paragraph (rather than per-line)
semantics let one pragma cover a multi-line construct without the noise of
tagging every continuation line.

Paths in `--prod-roots` and `--allowed-roots` are resolved relative to the
process cwd. CI invokes this from the repo root; running from elsewhere will
silently scan zero files. Run from the repo root.

Exit code 0 = clean. Exit code 1 = violations printed to stdout.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

FORBIDDEN_PATTERNS = (
    re.compile(r"\bstarling::testing\b"),
    re.compile(r"\bstarling\.testing\b"),
    re.compile(r"\bstarling_testing_marker\b"),
    # M0.2: append_event_unsafe is the test-only OutboxWriter shortcut bound on
    # _core.SqliteAdapter — see bindings/python/module.cpp. Real producers must
    # share their own TransactionGuard with OutboxWriter; the unsafe shortcut
    # exists solely so TC-NEW-OUTBOX-IDEMP can seed events. Banning the bare
    # symbol catches both `adapter.append_event_unsafe(…)` and direct attribute
    # access on the C++ class binding.
    re.compile(r"\bappend_event_unsafe\b"),
)
NOLINT_TAG = "NOLINT(starling-testing-isolation)"
SOURCE_SUFFIXES = {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".h", ".py", ".pyi", ".js", ".ts"}

# Defense-line #2 (P3.b1 phase 2): statements 写收编。所有 statements 表的
# INSERT/UPDATE 只允许活在存储层(src/store/)、其唯一受控 INSERT 授权写者
# (src/bus/statement_writer.cpp),或测试(src/testing/)。其余子系统必须经
# StatementStore 语义方法,不得手搓 SQL —— 防止写不变式(六态机守卫)散落回潮。
STATEMENTS_WRITE_PATTERNS = (
    re.compile(r"\bINSERT INTO statements\b"),
    re.compile(r"\bUPDATE statements\b"),
)
STATEMENTS_WRITE_ALLOWED = (
    "src/store",
    "src/bus/statement_writer.cpp",
    "src/testing",
)


def _iter_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in SOURCE_SUFFIXES:
            yield path


def _is_under(child: Path, parent: Path) -> bool:
    """True iff `child` is `parent` itself or lives under `parent`. Both must
    be resolved (absolute) paths; we use string-prefix comparison with a
    trailing separator so that `/a/bar` is not treated as under `/a/ba`."""
    try:
        return child == parent or child.is_relative_to(parent)
    except AttributeError:
        # is_relative_to was added in Python 3.9; fall back to string compare.
        c = str(child)
        p = str(parent)
        return c == p or c.startswith(p + "/")


def _nolint_blocks(lines: list[str]) -> set[int]:
    """Return the set of 0-indexed line numbers that are part of a contiguous
    non-blank block containing at least one NOLINT(starling-testing-isolation).

    Contiguous non-blank means: a maximal run of lines whose stripped content
    is non-empty. A blank line breaks the run. A block-comment-style NOLINT
    therefore covers the lines immediately above/below it within the same
    paragraph (e.g. a docstring + NOLINT comment + import statement triple).
    """
    skipped: set[int] = set()
    block_start: int | None = None
    block_has_nolint = False
    for idx, line in enumerate(lines):
        is_blank = not line.strip()
        if is_blank:
            if block_start is not None and block_has_nolint:
                skipped.update(range(block_start, idx))
            block_start = None
            block_has_nolint = False
            continue
        if block_start is None:
            block_start = idx
        if NOLINT_TAG in line:
            block_has_nolint = True
    # Flush trailing block at EOF.
    if block_start is not None and block_has_nolint:
        skipped.update(range(block_start, len(lines)))
    return skipped


def scan(prod_roots: list[Path], allowed_roots: list[Path]) -> list[str]:
    violations: list[str] = []
    seen: set[Path] = set()
    for root in prod_roots:
        if not root.exists():
            continue
        for path in _iter_source_files(root):
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            if any(_is_under(resolved, allowed) for allowed in allowed_roots):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            skipped = _nolint_blocks(lines)
            for idx, line in enumerate(lines):
                if idx in skipped:
                    continue
                if NOLINT_TAG in line:
                    continue
                for pattern in FORBIDDEN_PATTERNS:
                    if pattern.search(line):
                        violations.append(
                            f"{path}:{idx + 1}: forbidden testing reference: {line.strip()}"
                        )
    return violations


def scan_statements_ownership(src_root: Path, allowed: list[Path]) -> list[str]:
    """statements 写收编红线:src/ 下非授权 .cpp 出现 INSERT/UPDATE statements 即违规。"""
    violations: list[str] = []
    if not src_root.exists():
        return violations
    for path in _iter_source_files(src_root):
        if path.suffix not in {".cpp", ".cc", ".cxx"}:
            continue
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if any(_is_under(resolved, a) for a in allowed):
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for idx, line in enumerate(lines):
            if NOLINT_TAG in line:
                continue
            for pattern in STATEMENTS_WRITE_PATTERNS:
                if pattern.search(line):
                    violations.append(
                        f"{path}:{idx + 1}: statements 写未收编进 StatementStore: "
                        f"{line.strip()}")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prod-roots",
        nargs="+",
        default=["src", "include", "bindings", "python/starling"],
        help="Roots that MUST NOT reference the testing namespace.",
    )
    parser.add_argument(
        "--allowed-roots",
        nargs="*",
        default=[
            "tests",
            "src/testing",
            "python/starling/testing",
            # Public header for the testing-only target — declares the
            # namespace, intentionally part of `include/` so test code can
            # consume it. Prod TUs include it only via `bindings/python/module.cpp`
            # which carries explicit NOLINT pragmas.
            "include/starling/testing_marker.hpp",
        ],
        help="Roots (or single files) intentionally allowed to import testing helpers (skipped).",
    )
    args = parser.parse_args()

    cwd = Path.cwd()
    prod_roots = [cwd / r for r in args.prod_roots]
    allowed_roots = [(cwd / r).resolve() for r in args.allowed_roots]

    violations = scan(prod_roots, allowed_roots)
    if violations:
        print("CI static scan FAILED — testing namespace leaked into prod roots:")
        for v in violations:
            print(f"  {v}")
        return 1
    print("CI static scan OK — no forbidden testing references in prod roots.")

    # Defense-line #2: statements 写收编。
    stmt_allowed = [(cwd / r).resolve() for r in STATEMENTS_WRITE_ALLOWED]
    stmt_violations = scan_statements_ownership(cwd / "src", stmt_allowed)
    if stmt_violations:
        print("CI static scan FAILED — statements 写未收编进 StatementStore:")
        for v in stmt_violations:
            print(f"  {v}")
        return 1
    print("CI static scan OK — statements 写均收编进 store/(+ statement_writer 授权 + testing)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
