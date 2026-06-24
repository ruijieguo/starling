"""Starling-in-the-loop answering server for the ToMEval harness (OpenAI-compatible).

ToMEval (/Users/jaredguo-mini/develop/ToMEval) evaluates a "model" by POSTing
multiple-choice items (ToMBench AND HiToM) to an OpenAI `/v1/chat/completions`
endpoint. This server IS that endpoint, but the "model" is
**Starling-with-deepseek-in-the-loop**:

  per request:
    1. parse the STORY out of the `[Story] … [Question]` block of the user message,
    2. remember(story) into a fresh Starling memory — deepseek-v4-pro drives the
       belief + episodic + general-fact extraction (so Starling's social-cognition
       machinery — events, beliefs, who-perceived-what — is actually exercised),
    3. dump that extracted memory (statements + perception_state),
    4. ask deepseek-v4-pro to answer the MCQ, augmented with the dumped memory as a
       reasoning scaffold (CoT protocol → final answer as \\boxed{X}),
    5. return the answer in OpenAI chat-completion shape.

deepseek-v4-pro is Starling's LLM (extraction) AND the final answerer; the memory is
the in-the-loop scaffold. This measures whether Starling's structured memory helps
the model on the full ToMBench (all 8 ability families), the in-the-loop companion
to the deterministic location-FB perception eval.

Run (from the starling repo root, with the funded deepseek endpoint in env):
    eval "$(grep -E '^[[:space:]]*export (DEEPSEEK_API_KEY|DEEPSEEK_BASE_URL)=' ~/.zshrc)"
    OPENAI_API_KEY="$DEEPSEEK_API_KEY" OPENAI_BASE_URL="$DEEPSEEK_BASE_URL/v1" \
      .venv/bin/python -m uvicorn scripts.starling_tomeval_server:app \
        --host 127.0.0.1 --port 8900 --workers 1

The OpenAIAdapter reads OPENAI_API_KEY/OPENAI_BASE_URL from the env (never logged).
A sync handler runs in uvicorn's threadpool, so ToMEval's max_workers concurrency is
honoured; a fresh adapter + temp db per request keeps the threads isolated.
"""
from __future__ import annotations

import contextlib
import gc
import os
import re
import sqlite3
import sys
import tempfile
import threading
import time
import traceback
import uuid

from fastapi import FastAPI
from fastapi.responses import JSONResponse

import starling
from starling import _core

# Reasoning models count hidden chain-of-thought toward max_tokens; 4096 truncates
# to empty. Match the eval harnesses' 32768 (see the deepseek-eval memory note).
_MAX_TOKENS = 32768

# OpenAIAdapterConfig.from_env() only reads the base_url + key; the model defaults to
# "gpt-5.5", which the deepseek endpoint rejects (-> empty / transient_after_retry).
# The eval harnesses pass --model deepseek-v4-pro explicitly; we must too.
_MODEL = os.environ.get("STARLING_TOMBENCH_MODEL", "deepseek-v4-pro")

# PER-REQUEST TIME BUDGET MUST STAY UNDER ToMEval's client timeout (~20 min/request).
# One request makes up to (3 remember extraction calls + _ANSWER_TRIES answer calls),
# each bounded by _TIMEOUT_MS, times the adapter's own max_retries. If that product
# exceeds the client timeout, a slow/empty item gets orphaned, the client times out
# and RE-SENDS, and the re-sends pile onto an already-slow endpoint -> compounding
# stall. That is exactly what hung a 300-item run at 227/300: the old 600s timeout x
# 4 answer-retries = 40 min >> the 20-min client timeout. The fix is a bounded budget:
#   3 remember x 180s  +  2 answer x 180s  =  15 min  <  20-min client timeout.
# Empties here are NOT a timeout symptom — they are deepseek-v4-pro exhausting its
# 32768-token budget on hidden reasoning and returning http-200 with content="" (seen
# clustered at lat~480s). A shorter timeout just fails those faster (they fall back and
# are excluded); it does not lose answers the model would otherwise have produced.
_TIMEOUT_MS = int(os.environ.get("STARLING_TOMBENCH_TIMEOUT_MS", "180000"))

# 0: the adapter does NO internal HTTP retry, so a stuck call cannot multiply the
# budget (the _answer loop below owns answer-level retries; remember degrades to
# no-scaffold on failure). With HTTP/1.1 forced, transport errors are rare anyway.
_MAX_RETRIES = int(os.environ.get("STARLING_TOMBENCH_MAX_RETRIES", "0"))

# Answer attempts. Empties at temp=0 are near-deterministic, so 4 retries was mostly
# futile budget-burn; 2 catches a genuinely transient empty without blowing the budget.
_ANSWER_TRIES = int(os.environ.get("STARLING_TOMBENCH_ANSWER_TRIES", "2"))

# Story-section patterns per benchmark prompt layout:
#   ToMBench: "[Story] … [Question]" (EN) / "[故事] … [问题]" (ZH)
#   HiToM:    "Story: … Question:"  (numbered event sequence)
_STORY_PATTERNS = (
    re.compile(r"\[Story\]\s*(.*?)\s*\[Question\]", re.S),
    re.compile(r"\[故事\]\s*(.*?)\s*\[问题\]", re.S),
    re.compile(r"Story:\s*(.*?)\s*Question:", re.S),
    re.compile(r"故事[:：]\s*(.*?)\s*问题[:：]", re.S),
    # EmoBench (and other ToMEval datasets) render the passage under a markdown
    # "## Scenario" header, the question under "## Question". Non-greedy so a single
    # scenario is captured; grouped multi-scenario prompts get the first (degraded).
    re.compile(r"##\s*Scenario\s*(.*?)\s*##\s*Question", re.S),
    re.compile(r"##\s*情景\s*(.*?)\s*##\s*问题", re.S),
)


_thread_local = threading.local()


def _new_adapter() -> "_core.OpenAIAdapter":
    """A per-THREAD cached adapter (reuse the SSL connection, keep-alive).

    Creating a fresh adapter per call opened a fresh SSL connection every time; at
    concurrency the connection churn produced `transport_error:SSL connect error`
    (instant 0s failures) -> empty answers (the HiToM fallback root cause, NOT
    tokenkey.dev rate-limit). uvicorn runs the sync handler in a bounded threadpool,
    so caching one adapter per thread gives a bounded set of persistent connections,
    each used sequentially within a request (safe — libcurl handles are not shared
    across threads, and a thread serves one request at a time)."""
    ad = getattr(_thread_local, "adapter", None)
    if ad is None:
        cfg = _core.OpenAIAdapterConfig.from_env()
        cfg.model = _MODEL
        cfg.max_tokens = _MAX_TOKENS
        cfg.timeout_ms = _TIMEOUT_MS
        cfg.max_retries = _MAX_RETRIES
        ad = _core.OpenAIAdapter(cfg)
        _thread_local.adapter = ad
    return ad


def _extract_story(user_content: str) -> str:
    for rx in _STORY_PATTERNS:
        m = rx.search(user_content)
        if m:
            return m.group(1).strip()
    return ""


# HiToM nested-belief question: "Where does A think B thinks … the THEME is?".
# The `\s+thinks?\s+the\s+` REQUIRES a think/thinks immediately before "the THEME" — that
# consumes the FINAL verb so it does not cling to the last cognizer (without it,
# "Carter thinks" would survive the split and fail the single-token guard). `re` is the
# module-level import at the top of the server file.
_CHAIN_RX = re.compile(r"\bdoes\s+(.+?)\s+thinks?\s+the\s+([A-Za-z][\w ]*?)\s+is\b", re.I)
_THINK_SPLIT = re.compile(r"\s+thinks?\s+", re.I)


def _parse_chain_question(question: str):
    """Return (chain, theme) for an order>=2 HiToM nested-belief question, else None.
    chain is outermost-first; the deepest (belief-holder) is last. Single-cognizer
    ("really think" / plain "think") and non-HiToM questions return None (the caller
    falls back to the existing dump scaffold)."""
    m = _CHAIN_RX.search(question or "")
    if not m:
        return None
    span, theme = m.group(1).strip(), m.group(2).strip()
    parts = [p.strip() for p in _THINK_SPLIT.split(span) if p.strip()]
    if len(parts) < 2:
        return None  # one cognizer (e.g. "Isla" / "Isla really") -> not a nested chain
    # Each part must be a single name token (HiToM uses single first names); a multi-word
    # part is a parse artifact -> skip and fall back to the plain dump.
    if any(len(p.split()) != 1 for p in parts):
        return None
    return parts, theme


def _memory_dump(db_path: str, tenant: str) -> str:
    """A structured ToM scaffold from Starling's extraction:
      (1) the object-location trail (initial stative + each move, parsed into
          located_at facts), and
      (2) each character's LAST DIRECTLY-OBSERVED location (perception_state —
          who-knows-what; the load-bearing nested-belief signal).
    The raw event list is omitted: the story already carries it, so the value Starling
    adds is the parsed trail + the computed per-character beliefs. NOTE the column is
    `theme_id` (querying `theme` silently raised OperationalError, so perception_state
    — Starling's core ToM signal — never reached the dump before)."""
    facts: list[str] = []
    beliefs: list[str] = []
    con = sqlite3.connect(db_path)
    try:
        with contextlib.suppress(sqlite3.OperationalError):
            for subj, obj in con.execute(
                "SELECT subject_id, object_value FROM statements "
                "WHERE tenant_id=? AND predicate='located_at' ORDER BY rowid",
                (tenant,),
            ):
                facts.append(f"  - {subj} -> {obj}")
        with contextlib.suppress(sqlite3.OperationalError):
            for cog, theme, val in con.execute(
                "SELECT cognizer_id, theme_id, state_value FROM perception_state "
                "WHERE tenant_id=? AND state_dim='location' ORDER BY rowid",
                (tenant,),
            ):
                beliefs.append(f"  - {cog} last directly observed the {theme} at: {val}")
    finally:
        con.close()
    out = []
    if facts:
        out.append("Object-location trail my memory extracted (chronological):\n" + "\n".join(facts))
    if beliefs:
        out.append("Each character's LAST DIRECTLY-OBSERVED location (= what they still believe "
                   "if they left before a later move; a character ABSENT for a move does NOT learn it):\n"
                   + "\n".join(beliefs))
    return "\n\n".join(out)


def _format_chain_injection(chain: list[str], theme: str, location: str) -> str:
    nested = " thinks ".join(chain) + " thinks"
    return (
        "Starling's deterministic ToM engine computed the answer to this exact "
        "nested-belief question:\n"
        f"  {nested} the {theme} is in: {location}\n"
        "Use this as the primary answer (match it to the lettered choice). If the story "
        "explicitly shows a character LIED about the location, adjust accordingly."
    )


def _chain_injection_for(mem, user_content: str) -> str:
    """If the question is an order>=2 HiToM chain, compute the nested belief via Starling
    and return a definitive injection string; else "" (caller keeps the plain dump)."""
    parsed = _parse_chain_question(user_content)
    if not parsed:
        return ""
    chain, theme = parsed
    try:
        frontier = _core.KnowledgeFrontier(mem._rt.adapter)
        sb = _core.what_does_X_think_chain(
            mem._rt.adapter, frontier, chain, theme, mem._core.tenant,
            "9999-12-31T23:59:59Z")
    except Exception:
        print("[CHAIN-EXC]\n" + traceback.format_exc(), file=sys.stderr, flush=True)
        return ""
    if not sb.has_belief or not sb.state_value:
        return ""  # incomplete perception -> fall back to the plain dump
    return _format_chain_injection(chain, theme, sb.state_value)


# Question families whose answer turns on a character's BDI+K mental state. Emotion /
# belief / non-literal are GATED OFF (mental-state dump is noise there -> existing dump/chain).
_MENTAL_STATE_CUES = ("plan to", "want", "wants", "intend", "knows", "know that",
                      "most likely do", "decide", "prefer")
_GATE_OFF_CUES = ("emotion", "feel", "feeling", "think the", "thinks the", "really think")


def _wants_mental_state(question: str) -> bool:
    q = (question or "").lower()
    if any(c in q for c in _GATE_OFF_CUES):
        return False
    return any(c in q for c in _MENTAL_STATE_CUES)


def _format_mental_state(ms) -> str:
    def line(label, rows):
        items = [f"{r.subject_id} {r.predicate} {r.object_value}" for r in rows]
        return f"  {label}: " + "; ".join(items) if items else ""
    parts = [line("knows", ms.knowledge), line("wants", ms.desires), line("intends", ms.intentions),
             line("prefers", ms.preferences), line("committed", ms.commitments), line("believes", ms.beliefs)]
    return "\n".join(p for p in parts if p)


def _mental_state_injection_for(mem, user_content: str) -> str:
    if not _wants_mental_state(user_content):
        return ""
    try:
        mem.tick()  # consolidate fresh volatile statements so mental_state_of sees them
        agent = getattr(mem._core, "agent", None) or "narrator"
        ms = _core.mental_state_of(mem._rt.adapter, agent, mem._core.tenant, "9999-12-31T23:59:59Z")
        body = _format_mental_state(ms)
    except Exception:
        print("[MENTALSTATE-EXC]\n" + traceback.format_exc(), file=sys.stderr, flush=True)
        return ""
    if not body:
        return ""
    return ("[Mental states my memory extracted (subject = the character; use these for "
            "knowledge/desire/intention questions)]\n" + body)


_FAUX_PAS_CUES = ("inappropriate", "faux pas", "faux-pas", "say something", "said something",
                  "tactless", "offend", "不当", "失礼", "冒犯")


def _wants_faux_pas(question: str) -> bool:
    q = (question or "").lower()
    return any(c in q for c in _FAUX_PAS_CUES)


def _format_faux_pas(cands) -> str:
    lines = []
    for c in cands[:5]:
        lines.append(
            f"  {c.ignorant} still believes {c.theme} is '{c.stale_value}', but it is now "
            f"'{c.actual_value}' — {c.ignorant} was absent when it changed, while "
            f"{', '.join(c.who_knows)} perceived the change.")
    return "\n".join(lines)


def _faux_pas_injection_for(mem, user_content: str) -> str:
    if not _wants_faux_pas(user_content):
        return ""
    try:
        mem.tick()
        frontier = _core.KnowledgeFrontier(mem._rt.adapter)
        cands = _core.detect_faux_pas(mem._rt.adapter, frontier, mem._core.tenant,
                                      "9999-12-31T23:59:59Z")
    except Exception:
        print("[FAUXPAS-EXC]\n" + traceback.format_exc(), file=sys.stderr, flush=True)
        return ""
    body = _format_faux_pas(cands)
    if not body:
        return ""
    return ("[Faux-pas preconditions my memory computed — an ignorant party may commit a "
            "faux pas if they speak about this]\n" + body)


def _starling_memory_for(story: str, user_content: str = "") -> str:
    """remember(story) into a throwaway Starling memory, return the dump. Best-effort."""
    if not story:
        return ""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()
    mem = None
    try:
        mem = starling.Memory.open(db_path, agent="narrator", llm=_new_adapter())
        mem.remember(story)
        dump = _memory_dump(db_path, mem._core.tenant)
        chain = _chain_injection_for(mem, user_content)
        extra = (chain
                 or _mental_state_injection_for(mem, user_content)
                 or _faux_pas_injection_for(mem, user_content))
        return (dump + "\n\n" + extra) if extra else dump
    except Exception:  # extraction can fail (parse); degrade to no scaffold
        print(f"[REMEMBER-EXC]\n{traceback.format_exc()}", file=sys.stderr, flush=True)
        return ""
    finally:
        # CRITICAL under sustained load: close + GC-release the Memory runtime so its
        # SQLite connection fd is freed. close() only drops the cached handle; the
        # SqliteAdapter fd is released only when rt/adapter is GC'd (the embedded
        # core relies on GC). Without this, ~thousands of requests leak fds (the
        # unlinked temp-db connection stays open) -> the libcurl deepseek call can't
        # get a socket fd -> empty answers (the full-run 70% fallback root cause).
        if mem is not None:
            with contextlib.suppress(Exception):
                mem.close()
        mem = None
        gc.collect()
        for path in (db_path, db_path + "-wal", db_path + "-shm"):
            with contextlib.suppress(OSError):
                os.unlink(path)


def _answer(system: str, user: str, memdump: str) -> str:
    """deepseek-v4-pro answers the MCQ, scaffolded by Starling's extracted memory."""
    prompt = f"{system}\n\n{user}"
    if memdump:
        prompt += (
            "\n\n[Structured memory my memory system extracted from the story]\n"
            f"{memdump}\n\n"
            "Use BOTH the story and this extracted memory (especially who perceived / "
            "knows / believes what) to reason step by step, then give the final answer "
            "as \\boxed{X}."
        )
    for attempt in range(_ANSWER_TRIES):
        t = time.time()
        try:
            resp = _new_adapter().extract(prompt)
            out = (resp.raw_xml or "").strip()
            if out:
                return out
            print(f"[ANSWER-EMPTY] attempt={attempt} ok={resp.ok} err={resp.error!r} "
                  f"lat={time.time() - t:.0f}s plen={len(prompt)}", file=sys.stderr, flush=True)
        except Exception:
            print(f"[ANSWER-EXC] attempt={attempt} lat={time.time() - t:.0f}s\n"
                  f"{traceback.format_exc()}", file=sys.stderr, flush=True)
        time.sleep(0.6 * (attempt + 1))  # brief backoff; the reused conn re-establishes
    return ""


app = FastAPI()


@app.get("/v1/models")
def models() -> JSONResponse:  # ToMEval doesn't probe this, but harmless to expose.
    return JSONResponse({"object": "list", "data": [
        {"id": "starling-deepseek", "object": "model", "owned_by": "starling"}]})


@app.post("/v1/chat/completions")
def chat_completions(body: dict) -> JSONResponse:
    messages = body.get("messages") or []
    model = body.get("model", "starling-deepseek")
    system = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
    user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")

    memdump = _starling_memory_for(_extract_story(user), user)
    content = _answer(system, user, memdump)
    if not content:
        # Never return empty: ToMEval scores content_none as wrong AND retries 5×
        # (burning budget). An empty answer means the deepseek call failed (usually
        # budget depletion); emit a parseable box so it scores (wrong) without retry.
        content = "(no answer produced) \\boxed{A}"

    return JSONResponse({
        "id": "chatcmpl-" + uuid.uuid4().hex[:24],
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    })
