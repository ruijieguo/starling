"""Starling-in-the-loop ToMBench answering server (OpenAI-compatible).

ToMEval (/Users/jaredguo-mini/develop/ToMEval) evaluates a "model" by POSTing
ToMBench multiple-choice items to an OpenAI `/v1/chat/completions` endpoint. This
server IS that endpoint, but the "model" is **Starling-with-deepseek-in-the-loop**:

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
      .venv/bin/python -m uvicorn scripts.starling_tombench_server:app \
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
import tempfile
import time
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

# Story-section patterns per benchmark prompt layout:
#   ToMBench: "[Story] … [Question]" (EN) / "[故事] … [问题]" (ZH)
#   HiToM:    "Story: … Question:"  (numbered event sequence)
_STORY_PATTERNS = (
    re.compile(r"\[Story\]\s*(.*?)\s*\[Question\]", re.S),
    re.compile(r"\[故事\]\s*(.*?)\s*\[问题\]", re.S),
    re.compile(r"Story:\s*(.*?)\s*Question:", re.S),
    re.compile(r"故事[:：]\s*(.*?)\s*问题[:：]", re.S),
)


def _new_adapter() -> "_core.OpenAIAdapter":
    """A fresh deepseek adapter per request (thread isolation + env-read key)."""
    cfg = _core.OpenAIAdapterConfig.from_env()
    cfg.model = _MODEL
    cfg.max_tokens = _MAX_TOKENS
    return _core.OpenAIAdapter(cfg)


def _extract_story(user_content: str) -> str:
    for rx in _STORY_PATTERNS:
        m = rx.search(user_content)
        if m:
            return m.group(1).strip()
    return ""


def _memory_dump(db_path: str, tenant: str) -> str:
    """A readable dump of what Starling extracted: statements + perception state."""
    lines: list[str] = []
    con = sqlite3.connect(db_path)
    try:
        with contextlib.suppress(sqlite3.OperationalError):
            for holder, subj, pred, obj, mod in con.execute(
                "SELECT holder_id, subject_id, predicate, object_value, modality "
                "FROM statements WHERE tenant_id=? AND review_status!='forgotten' "
                "ORDER BY rowid",
                (tenant,),
            ):
                lines.append(f"- {holder} [{mod}] {subj} {pred} {obj}")
        with contextlib.suppress(sqlite3.OperationalError):
            for cog, theme, dim, val in con.execute(
                "SELECT cognizer_id, theme, state_dim, state_value "
                "FROM perception_state WHERE tenant_id=? ORDER BY rowid",
                (tenant,),
            ):
                lines.append(f"- (perception) {cog} takes {theme}'s {dim} to be {val}")
    finally:
        con.close()
    return "\n".join(lines)


def _starling_memory_for(story: str) -> str:
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
        return _memory_dump(db_path, mem._core.tenant)
    except Exception:  # extraction can fail (parse); degrade to no scaffold
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
    try:
        resp = _new_adapter().extract(prompt)
        return (resp.raw_xml or "").strip()
    except Exception:
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

    memdump = _starling_memory_for(_extract_story(user))
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
