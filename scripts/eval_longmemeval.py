#!/usr/bin/env python3
"""LongMemEval (time-reasoning + knowledge-update) harness.

fixture-mode: deterministic mock answerer (offline, CI). real-mode: build a real
retrieval pipeline (SqliteAdapter + OpenAIEmbeddingAdapter + EmbeddingWorker +
SemanticRetriever) + OpenAIAdapter answering — needs OPENAI_API_KEY (gated).

The fixture path NEVER imports ``starling._core``; all `_core`/network access is
lazy-imported inside ``_real_answer`` so CI stays fully offline. real-mode is
GATED behind OPENAI_API_KEY and is NOT exercised this milestone, but is kept as
sound, importable Python.
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

ACCURACY_THRESHOLD = 0.55
SUBSETS = ("time-reasoning", "knowledge-update")


def _fixture_answer(record: dict, idx: int) -> int:
    # 90% correct deterministically (well above 0.55).
    return int(record["answer"]) if idx % 10 < 9 else (int(record["answer"]) + 1) % len(record["options"])


def _build_history_lines(record: dict) -> str:
    """Render the conversation history as observed-at-prefixed lines for the prompt."""
    lines = []
    for turn in record.get("history", []):
        lines.append(
            f"[{turn.get('observed_at', '')}] {turn.get('speaker', '?')}: {turn.get('text', '')}"
        )
    return "\n".join(lines) if lines else "(no history)"


def _build_answer_prompt(record: dict, recalled: list[str]) -> str:
    """Build the multiple-choice prompt fed to the answering LLM.

    `recalled` are the most-relevant memory rows surfaced by SemanticRetriever
    (predicate + object_value snippets), oldest-to-newest in the recall order.
    """
    options_block = "\n".join(f"{i}. {opt}" for i, opt in enumerate(record["options"]))
    recall_block = "\n".join(f"- {r}" for r in recalled) if recalled else "(no memories recalled)"
    return (
        "You are answering a multiple-choice question using a memory system's recall.\n\n"
        "Full conversation history (each line is timestamped):\n"
        f"{_build_history_lines(record)}\n\n"
        "Most-relevant recalled memories:\n"
        f"{recall_block}\n\n"
        f"Question: {record['question']}\n\n"
        "Options (0-based index):\n"
        f"{options_block}\n\n"
        "Respond with ONLY the integer index of the correct option. No explanation."
    )


def _parse_option_index(text: str, n_options: int) -> int:
    """Extract the first valid 0-based option index from an LLM response."""
    valid = set(str(i) for i in range(n_options))
    for ch in text:
        if ch in valid:
            return int(ch)
    raise ValueError(f"could not parse option index from response: {text!r}")


def _real_answer(record: dict) -> int:
    """GATED real-mode: build pipeline, write history, recall, ask LLM. Needs OPENAI_API_KEY.

    Lazy-imports `starling._core` so fixture-mode never touches the native ext.
    Gated behind OPENAI_API_KEY; NOT exercised this milestone, but kept sound.
    """
    import sqlite3
    import tempfile
    import urllib.request

    from starling import _core
    from starling.testing import relax_preflight_for_m0_3

    # relax_preflight is a no-op here (we drive _core directly, not a Runtime),
    # but kept for parity with the in-repo pipeline tests / future Runtime wiring.
    relax_preflight_for_m0_3()

    # NOTE: SqliteAdapter.open(":memory:") returns db_path ":memory:", but a raw
    # sqlite3.connect(":memory:") opens a *separate* empty DB (no migrated tables).
    # The seed + C++ pipeline must share ONE db, so we back it with a real file —
    # matching every in-repo pipeline test (test_pattern_completion.py et al.).
    tmpdir = tempfile.mkdtemp(prefix="lme_real_")
    db_path = os.path.join(tmpdir, "lme.db")
    adapter = _core.SqliteAdapter.open(db_path)  # runs migrations → tables exist

    # --- seed each history turn as a 'believes' statement (24-col INSERT, the
    #     same column list as tests/python/test_p2c_commitment_lifecycle.py's
    #     _seed_commits). Raw writes are committed + closed BEFORE the C++ worker
    #     writes, to keep WAL writers strictly sequential (no `database is locked`).
    _INSERT = (
        "INSERT INTO statements("
        "id,tenant_id,holder_id,holder_perspective,subject_kind,subject_id,"
        "predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,"
        "salience,affect_json,activation,last_accessed,provenance,"
        "consolidation_state,review_status,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
    )
    conn = sqlite3.connect(str(adapter.db_path), timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        for i, turn in enumerate(record.get("history", [])):
            observed_at = turn.get("observed_at", "1970-01-01T00:00:00Z")
            text = turn.get("text", "")
            stmt_id = f"{record['item_id']}-h{i}"
            conn.execute(
                _INSERT,
                (
                    stmt_id, "default", "alice", "first_person", "cognizer",
                    "subject", "said", "str", text, "a" * 64, "v1", "believes",
                    "pos", 0.9, observed_at, 0.5, "{}", 0.0, observed_at,
                    "user_input", "consolidated", "approved", observed_at, observed_at,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    # --- embed the seeded statements (production embedder, gated on key) ---
    now_iso = "2026-06-01T00:00:00Z"
    # Embeddings and chat may be different providers (a reasoning chat model like
    # DeepSeek has no embeddings endpoint). OpenAIEmbeddingConfig.from_env() reads
    # OPENAI_* (api_key is env-only), so if DASHSCOPE_API_KEY is set, temporarily
    # point OPENAI_* at DashScope's OpenAI-compatible embeddings endpoint to build
    # the embedder, then restore OPENAI_* for the chat call below.
    if os.environ.get("DASHSCOPE_API_KEY"):
        _sv_k, _sv_b = os.environ.get("OPENAI_API_KEY"), os.environ.get("OPENAI_BASE_URL")
        os.environ["OPENAI_API_KEY"] = os.environ["DASHSCOPE_API_KEY"]
        os.environ["OPENAI_BASE_URL"] = os.environ.get("DASHSCOPE_BASE_URL", "")
        _emb_cfg = _core.OpenAIEmbeddingConfig.from_env()
        _emb_cfg.model = os.environ.get("EMBEDDING_MODEL", "text-embedding-v3")
        _emb_cfg.dim = int(os.environ.get("EMBEDDING_DIM", "1024"))
        emb = _core.OpenAIEmbeddingAdapter(_emb_cfg)
        if _sv_k is not None:
            os.environ["OPENAI_API_KEY"] = _sv_k
        if _sv_b is not None:
            os.environ["OPENAI_BASE_URL"] = _sv_b
    else:
        emb = _core.OpenAIEmbeddingAdapter(_core.OpenAIEmbeddingConfig.from_env())
    idx = _core.SqliteBlobVectorIndex()
    _core.EmbeddingWorker(adapter, emb, idx).tick_one_batch(now_iso)

    # --- vector recall for the question (reuse the SAME emb + idx) ---
    sr = _core.SemanticRetriever(adapter, emb, idx)
    res = sr.vector_recall(
        _core.SemanticRetrieverParams(
            tenant_id="default",
            holder_id="alice",
            query_text=record["question"],
            k=5,
        )
    )
    recalled: list[str] = []
    for scored in res.rows:
        row = scored.row
        # row.predicate / row.object_value are the rendered fact fields (see
        # test_basic_retrieve_receipt.py). Surface them as recall snippets.
        recalled.append(f"{getattr(row, 'predicate', '')}: {getattr(row, 'object_value', '')}".strip(": "))

    # --- ask the LLM for an option index ---
    # NOTE: _core.OpenAIAdapter is a C++ LLMAdapter consumed by the Extractor; it
    # exposes NO Python-callable chat/extract method (only FakeLLMAdapter.extract
    # is bound). We still construct it from env to validate the same config
    # plumbing the C++ path uses, then perform the actual chat-completion over the
    # proven HTTP path (mirrors scripts/eval_fantom.py). Both read OPENAI_API_KEY
    # from the env on the C++ side / Authorization header — never as a param/log.
    cfg = _core.OpenAIAdapterConfig.from_env()  # raises if OPENAI_API_KEY unset
    # from_env() does NOT read a model env var (defaults to gpt-5.5); allow an
    # override so the gated run can point chat at e.g. DeepSeek's deepseek-v4-flash.
    cfg.model = os.environ.get("CHAT_MODEL", cfg.model)
    _adapter_constructed = _core.OpenAIAdapter(cfg)  # offline; no network yet
    base_url = cfg.base_url
    model = cfg.model
    api_key = os.environ.get("OPENAI_API_KEY", "")

    prompt = _build_answer_prompt(record, recalled)
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            # 512 so reasoning models (deepseek-v4-*) can emit a visible answer;
            # _parse_option_index grabs the first valid index, so extra text is fine.
            "max_tokens": 512,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url=f"{base_url}/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"].strip()
    return _parse_option_index(content, len(record["options"]))


def run_one_round(corpus, subsets, fixture_mode):
    counts = {s: [0, 0] for s in subsets}
    for idx, rec in enumerate(corpus):
        s = rec.get("subset", "")
        if s not in subsets:
            continue
        counts[s][1] += 1
        pred = _fixture_answer(rec, idx) if fixture_mode else _real_answer(rec)
        if pred == int(rec["answer"]):
            counts[s][0] += 1
    return {s: (counts[s][0], counts[s][1]) for s in subsets}


def write_report(path: Path, rounds, subsets, threshold, overall_pass):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# LongMemEval Report", "", "| subset | last-acc | threshold | verdict |", "|---|---|---|---|"]
    last = rounds[-1]
    for s in subsets:
        c, t = last.get(s, (0, 0))
        acc = c / t if t else 0.0
        lines.append(f"| {s} | {acc:.4f} | {threshold:.2f} | {'PASS' if acc >= threshold else '**FAIL**'} |")
    lines.append(f"\noverall: {'PASS' if overall_pass else 'FAIL'}")
    path.write_text("\n".join(lines) + "\n")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="LongMemEval harness.")
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--report", type=Path, default=Path("build/eval_longmemeval.md"))
    p.add_argument("--subsets", default=",".join(SUBSETS))
    p.add_argument("--fixture-mode", action="store_true")
    args = p.parse_args(argv)
    subsets = tuple(x.strip() for x in args.subsets.split(",") if x.strip())
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not args.fixture_mode and not api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr); return 1
    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr); return 1
    corpus = [json.loads(l) for l in args.corpus.read_text().splitlines() if l.strip()]
    rounds = [run_one_round(corpus, subsets, args.fixture_mode) for _ in range(args.rounds)]
    last = rounds[-1]
    failures = [s for s in subsets
                if (last.get(s, (0, 0))[1] == 0) or (last[s][0] / last[s][1] < ACCURACY_THRESHOLD)]
    overall = len(failures) == 0
    write_report(args.report, rounds, subsets, ACCURACY_THRESHOLD, overall)
    print(f"Report written to {args.report}", file=sys.stderr)
    if overall:
        print("PASS — all subsets within accuracy threshold"); return 0
    for s in failures:
        print(f"BLOCKED — subset {s} below threshold or empty")
    return 1


if __name__ == "__main__":
    sys.exit(main())
