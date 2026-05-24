#!/usr/bin/env python3
"""P1 EVAL harness — runs N rounds of extraction against the EVAL corpus.

Per spec §15.3.3, runs 3 rounds and takes the LAST round's F1 vector as
the verdict. Exits non-zero if any F1 < its threshold.

Usage:
    python scripts/eval_p1_extractor.py \\
        --corpus tests/data/eval_p1_corpus.jsonl \\
        --rounds 3 \\
        --report build/eval_p1_report.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

P1_THRESHOLDS = {
    "holder":              0.85,
    "holder_perspective":  0.80,
    "predicate":           0.75,
    "object":              0.70,
    "nesting_depth_1":     0.60,
}


def f1_score(tp: int, fp: int, fn: int) -> float:
    if tp == 0 and fp == 0 and fn == 0:
        return 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def evaluate_record(record: dict, predicted: list[dict]) -> dict[str, tuple[int, int, int]]:
    """Compute (tp, fp, fn) per field for one record.

    Matches predictions to ground-truth by (predicate, object) since
    that is the most stable pair across language/perspective drift.
    """
    truths = record["ground_truth_statements"]
    counts: dict[str, list[int]] = {
        "holder":             [0, 0, 0],
        "holder_perspective": [0, 0, 0],
        "predicate":          [0, 0, 0],
        "object":              [0, 0, 0],
        "nesting_depth_1":    [0, 0, 0],
    }

    matched_pred_idx: set[int] = set()
    for t in truths:
        match_idx = None
        for i, p in enumerate(predicted):
            if i in matched_pred_idx: continue
            if p.get("predicate") == t.get("predicate") and \
               str(p.get("object")) == str(t.get("object")):
                match_idx = i; break
        if match_idx is None:
            for fld in ("holder", "holder_perspective", "predicate", "object"):
                counts[fld][2] += 1
            if t.get("nesting_depth", 0) >= 1:
                counts["nesting_depth_1"][2] += 1
            continue
        matched_pred_idx.add(match_idx)
        p = predicted[match_idx]
        for fld in ("holder", "holder_perspective", "predicate", "object"):
            if str(p.get(fld)) == str(t.get(fld)):
                counts[fld][0] += 1
            else:
                counts[fld][1] += 1
                counts[fld][2] += 1
        if t.get("nesting_depth", 0) >= 1:
            if p.get("nesting_depth", 0) >= 1:
                counts["nesting_depth_1"][0] += 1
            else:
                counts["nesting_depth_1"][2] += 1
        elif p.get("nesting_depth", 0) >= 1:
            counts["nesting_depth_1"][1] += 1

    for i, p in enumerate(predicted):
        if i in matched_pred_idx: continue
        for fld in ("holder", "holder_perspective", "predicate", "object"):
            counts[fld][1] += 1
        if p.get("nesting_depth", 0) >= 1:
            counts["nesting_depth_1"][1] += 1

    return {k: (v[0], v[1], v[2]) for k, v in counts.items()}


_EXTRACT_PROMPT = """You are an extractor for a Statement-based memory system.

Given a conversation, extract ALL Statements. Output ONLY a JSON array.

Each Statement: {{"holder": str, "holder_perspective": "FIRST_PERSON"|"QUOTED"|"HEARSAY"|"INFERRED", "subject": str, "predicate": str, "object": str, "modality": "BELIEVES"|"DESIRES"|"INTENDS"|"COMMITS"|"ENFORCES"|"OBSERVES", "polarity": "POS"|"NEG"|"UNKNOWN", "nesting_depth": int}}

predicate must be one of: responsible_for, knows, prefers, promises, forbids, requires, located_at, member_of, believes, doubts. Do NOT use free-form English ("is responsible for", "thinks", "is handling") — pick the closest underscore form from the list above.

OBJECT BREVITY: object MUST be the minimal canonical noun phrase. Drop hedges, modifiers, and elaborations. Examples:
- "auth service, especially logins" → "auth"
- "the deployment plan for Q3" → "deployment plan"
- "frontend work on this project" → "frontend"
Strip leading/trailing words like "service", "system", "work", "team's", "the", "尤其是…", "especially…".

HOLDER vs SUBJECT (CRITICAL): holder is the SPEAKER who is asserting the claim in the conversation. subject is WHO/WHAT the claim is about. They are usually different.
- "Alice: I believe Bob is responsible for auth" → holder=Alice, subject=Bob, predicate=responsible_for, object=auth, perspective=FIRST_PERSON
- "Alice: The handoff doc says 'Bob is responsible for auth'" → holder=Alice (she is quoting), subject=Bob, perspective=QUOTED
- "Alice: I read that Carol prefers Python" → holder=Alice, subject=Carol, perspective=HEARSAY
NEVER set holder to the subject of the claim. The holder is the conversation participant who voiced the claim.

HOLDER_PERSPECTIVE rules:
- FIRST_PERSON: speaker directly states their own belief/commitment ("I believe X", "I will Y", "I think Z")
- QUOTED: speaker quotes a written source or another person verbatim ("the doc says…", "Alice said: '…'", '"…"')
- HEARSAY: speaker reports what they heard/read second-hand without quoting ("I heard that…", "I read that…", "听说…")
- INFERRED: claim is implied but not explicitly self-attributed by the speaker

HOLDER SELF-ATTRIBUTION: extract a Statement ONLY when the holder explicitly self-attributes it ("I am responsible for…", "I believe…", "I will…", "I prefer…") OR another speaker explicitly attributes it to them ("Alice told me she…", "Bob said he…"). Do NOT extract one Statement per speaker. Do NOT echo a reply ("OK, got it", "thanks") as a Statement. If speaker B merely acknowledges what A said, B has no Statement.

FOCAL SPEAKER: in most conversations there is ONE focal speaker (usually the first speaker) who introduces the substantive claims. Subsequent speakers typically only confirm, acknowledge, or ask follow-up questions. Extract Statements ONLY from the focal speaker's substantive claims. Do NOT promote a confirmation ("yes, that's right", "I'm on it", "我会跟进") into its own Statement. A reply only becomes a Statement when it introduces an explicit NEW commitment with concrete content ("I promise to deliver X by Friday") — never for generic agreement.

EXCEPTION (commitments from non-focal speakers): if a non-focal speaker says explicitly "I promise…" / "我承诺…" / "I commit to…" with a concrete action and (often) a deadline, DO extract that as a Statement with predicate=promises and that speaker as holder.

EXCEPTION 2 (substantive depth-2 from non-focal speakers): if a non-focal speaker introduces a NEW 2nd-order belief claim ("Bob 刚才还说，他觉得X" / "Bob said he thinks Y"), extract that depth-2 Statement with that speaker as holder and perspective=HEARSAY. This is NOT a confirmation — the speaker is introducing fresh content about a third party's mental state.

ROUTING ≠ COMMITMENT (CRITICAL): when speaker says "I'll route X to Bob", "I'll forward X to Bob", "我把X转给Bob", "如果有问题先找他确认", these are routing/operational remarks, NOT promises and NOT requires Statements. Do NOT extract them as separate Statements. Same for "Bob confirmation", "Bob approval" as object — these aren't requires Statements unless the conversation explicitly states a RULE/POLICY ("policy requires Bob to approve all X").

NESTING DEPTH for 2nd-order beliefs: when text says "Alice believes Bob believes Carol knows X", produce ONE Statement:
  {{"holder": "Alice", "predicate": "believes", "object": "Carol knows X", "nesting_depth": 2, ...}}
The object is the INNERMOST clause ("Carol knows X"), NOT the middle clause ("Bob believes Carol knows X"). nesting_depth counts the layers of belief-about-belief: depth=2 means "A believes B believes Z". Do NOT split into multiple flat Statements.

DEFAULT NESTING DEPTH IS 0. Use nesting_depth=0 for ALL flat first-order Statements: "I am responsible for X" → depth=0; "I believe X" → depth=0; "Alice is responsible for auth" → depth=0. Use depth=2 ONLY for the specific "A believes B believes Z" pattern. Never use depth=1.

PROMISE OBJECT FIDELITY: when extracting "promises", the object must be the FULL action phrase from the conversation, not a noun summary.
- "我承诺周五前提交认证模块测试报告" → object="周五前提交认证模块测试报告" (NOT "认证测试报告")
- "I promise I'll send the audit notes to the team before Friday" → object="send the audit notes to the team before Friday" (NOT "audit notes")
- "我承诺周五下班前提交测试报告" → object="周五下班前提交测试报告" (NOT "测试报告")
Promise objects keep the verb + temporal qualifier. Other predicates (responsible_for, knows, requires, etc.) use the canonical short noun.

PROMISE OBJECT — keep leading prepositions: if the speaker uses "在...前/by...", keep that preposition.
- "我承诺在周五下班前修复登录回调的错误" → object="在周五下班前修复登录回调的错误" (KEEP the leading "在")
- "I promise by Friday I'll fix the bug" → object="by Friday I'll fix the bug" (KEEP "by")
Reproduce the speaker's phrasing verbatim from the moment after "promise"/"承诺".

PROMISE OBJECT — drop leading "to" / "I'll" / "I will" / "我会": after "I promise", drop the immediate "to" or "I'll/I will/我会" if present. The object should start with the action verb directly.
- "I promise to rotate the keys before Friday" → object="rotate the keys before Friday" (DROP leading "to")
- "I promise I'll fix the bug by Friday" → object="fix the bug by Friday" (DROP "I'll")
- "我承诺我会在明天前提交报告" → object="在明天前提交报告" (DROP "我会")
- "我承诺周五前提交报告" → object="周五前提交报告" (already starts cleanly — no change needed)
This rule applies AFTER "PROMISE OBJECT — keep leading prepositions": prepositions like "在/by" are NOT dropped.

CANONICAL OBJECT FOR responsible_for (CRITICAL): when the conversation discusses someone's responsibility, use the SHORTEST canonical area name (e.g., "auth"), NOT a specific sub-task or event ("auth follow-ups", "OAuth rollout", "token outage", "登录验证", "认证模块"). Even when the conversation cites a specific incident, the responsibility Statement is about the broader area.
- "Bob handled the OAuth rollout and login fixes" → responsible_for/auth (NOT responsible_for/OAuth or responsible_for/login fixes)
- "Bob 在看认证模块的代码" → responsible_for/auth (NOT 认证模块)
- "Every auth ticket gets routed to Bob" → responsible_for/auth
- "Bob signs off on the auth deploy" → responsible_for/auth
The English canonical is "auth"; the Chinese canonical is also "auth" when the conversation mixes in "auth" alongside Chinese — only use a Chinese-only canonical (e.g., "认证") if the conversation never uses the word "auth".

POLICY-AS-HOLDER (CRITICAL): when a `requires` or `forbids` claim is grounded in a NAMED policy/rule/regulation (e.g., "公司安全政策要求…", "team policy requires…", "deployment policy requires…", "根据公司规定…"), holder is the POLICY ENTITY (not the speaker), and holder_perspective is QUOTED. Use the policy's name as it appears in the text. The speaker is conveying the policy, not asserting it personally.
- "Alice: 根据公司的安全政策，生产权限需要两次审批。"
  → {{"holder":"公司安全政策","holder_perspective":"QUOTED","subject":"生产权限","predicate":"requires","object":"两次审批",...}}
- "Dana: the team policy requires code review before merging."
  → {{"holder":"team policy","holder_perspective":"FIRST_PERSON","subject":"code review","predicate":"requires","object":"code review",...}}
  (When the speaker simply STATES the policy as a current rule without quoting an external source — "the team policy requires…" rather than "I read that…" — perspective=FIRST_PERSON; holder still = the policy entity.)
- BUT (POSSESSIVE DOWNGRADE): when the policy is named with a POSSESSIVE PRONOUN ("our deployment policy", "our SOP", "我们的部署政策", "my rule"), the speaker is owning the rule, NOT citing an external authority. holder=SPEAKER, perspective=FIRST_PERSON.
  "Alice: our deployment policy requires two approvals" → holder=Alice, perspective=FIRST_PERSON (NOT holder='deployment policy').
- BUT: when the speaker says "I require…" or "我要求…" without naming a policy, holder=speaker, perspective=FIRST_PERSON.
  "Alice: 团队政策要求 auth 相关变更必须经过双人审查" with NO external attribution → holder=Alice, perspective=FIRST_PERSON (she is asserting the rule directly, even if she calls it "团队政策" generically and doesn't quote a specific named regulation).
  Heuristic: name the policy as holder ONLY when (a) the conversation grounds the rule in an external/written authority ("公司安全政策", "the SOP", "GDPR") OR (b) the policy is referred to with a bare "the X policy" / "X policy" — i.e., not preceded by a possessive pronoun. "our team policy", "我们的部署政策", "团队政策" by themselves don't promote — keep speaker as holder.

QUOTE AUTHORSHIP (CRITICAL): when speaker A explicitly reads aloud or paraphrases what NAMED PERSON B wrote/said in a verbatim quote ("A: Alice wrote: 'Bob is responsible for auth'", "A: Alice said: '…'", "A: 在交接记录里，Alice 写道：'…'"), the holder of the QUOTED Statement is **B (the original author)**, NOT A (the reader). perspective=QUOTED.
- "Charlie: In the handoff notes, Alice wrote, 'Bob is responsible for auth.'"
  → {{"holder":"Alice","holder_perspective":"QUOTED","subject":"Bob","predicate":"responsible_for","object":"auth",...}}
- "Charlie: Alice said, 'Bob is responsible for auth.'" → holder=Alice (NOT Charlie), perspective=QUOTED
- Contrast with SELF-QUOTING: when A quotes A's OWN prior utterance ("I said earlier: '…'", "我刚才在群里说过：'…'"), holder=A. The distinguishing test: who wrote/spoke the quoted material? holder = that person.

SELF-QUOTING (CRITICAL): when the speaker EXPLICITLY quotes their OWN prior written/spoken words ("I said earlier: '…'", "我刚才在群里说过：'…'", "I wrote in the doc: '…'"), perspective=QUOTED, NOT FIRST_PERSON. holder=speaker (since speaker authored the quote). The hallmark is verbatim quotation marks around the speaker's prior utterance. (Contrast with QUOTE AUTHORSHIP above: when speaker reads ANOTHER PERSON'S quote, holder is that other person, not the speaker.)

DEPTH-2 PERSPECTIVE — inherit from the OUTER voicing (CRITICAL): for nesting_depth=2 Statements ("A believes/thinks B knows/believes/assumes Z"), perspective is determined by HOW the speaker voices the OUTER belief:
- Explicit self-attribution → FIRST_PERSON: "I believe X believes Y" / "I also believe Carol believes Bob knows Z" / "我也认为X相信Y" / "我觉得X相信Y"
- Reports another's said belief → HEARSAY: "Carol told me Bob believes Z" / "Bob 刚才还说，他觉得Z" / "C said X believes Y"
- Inference from behavior, NO direct self-attribution → INFERRED: "Since Bob keeps assigning runbook checks to Carol, I think he assumes Carol knows auth" / "看Charlie的反应，我也认为Charlie相信Bob负责auth"
The hallmark of INFERRED is justification-from-evidence ("since…", "看…的反应", observed behavior cited).
- "Alice: I also believe Carol believes Bob prefers Postgres." → FIRST_PERSON (explicit "I believe")
- "Alice: Carol told me Bob believes auth needs MFA." → HEARSAY (Carol said it)
- "Alice: Since he keeps doing X, I think he assumes Y." → INFERRED (behavior-driven)
- "Carol: Bob 刚才还说，他觉得缓存问题是 Redis 配置导致的。" → holder=Carol, perspective=HEARSAY (Carol reports what Bob said)

HEARSAY ATTRIBUTION (CRITICAL): when speaker A says "I heard from C that X" / "C告诉我X" / "Carol said X", the resulting Statement has holder=A (the current speaker), perspective=HEARSAY, subject=whoever the claim is about. Do NOT set holder=C. C is only the source A heard from; A is the one voicing the claim now in the conversation.
- "Alice: 我听Carol说，Bob现在负责auth。" → holder=Alice (NOT Carol), perspective=HEARSAY
- BUT: when a non-focal speaker reports something second-hand and the FOCAL speaker then ECHOES/CONFIRMS it ("Carol: 我和平台组确认过Bob负责auth. Alice: 好，我就按你说的理解：Bob负责auth"), the focal speaker becomes the holder with perspective=HEARSAY (Alice repeats Carol's report). When the focal speaker explicitly receives info FROM another participant in this conversation and acts on it as second-hand, they are still the holder with perspective=HEARSAY.

WORKED EXAMPLES (study these carefully):

Conversation:
  Alice: I believe Bob is responsible for auth. I also believe Bob thinks Carol knows the deployment plan.
  Bob: I'm handling the auth service, but I haven't checked what Carol knows.
JSON array:
[
  {{"holder":"Alice","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}},
  {{"holder":"Alice","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"believes","object":"Carol knows the deployment plan","modality":"BELIEVES","polarity":"POS","nesting_depth":2}}
]
(Bob's reply is a confirmation/acknowledgment — NO Statement extracted from Bob.)

Conversation:
  Alice: 我刚在交接记录里写下了这句话："Bob 负责 auth"。
  Bob: 收到，我今天下午会确认 auth 的配置。
JSON array:
[
  {{"holder":"Alice","holder_perspective":"QUOTED","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}}
]
(holder=Alice not Bob — Alice voices the claim. perspective=QUOTED because she quotes a written source. Bob's reply is acknowledgment — NO Statement.)

Conversation:
  Bob: Alice，认证模块的测试报告这周能交吗？
  Alice: 可以，我承诺周五前提交认证模块测试报告。
JSON array:
[
  {{"holder":"Alice","holder_perspective":"FIRST_PERSON","subject":"Alice","predicate":"promises","object":"周五前提交认证模块测试报告","modality":"COMMITS","polarity":"POS","nesting_depth":0}}
]
(Bob's question is NOT a Statement. Alice's promise object keeps the full phrase including the temporal qualifier.)

Conversation:
  Alice: 我认为 Bob 负责 auth。另外，根据公司的安全政策，生产权限需要两次审批。
  Bob: 收到。
JSON array:
[
  {{"holder":"Alice","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}},
  {{"holder":"公司安全政策","holder_perspective":"QUOTED","subject":"生产权限","predicate":"requires","object":"两次审批","modality":"ENFORCES","polarity":"POS","nesting_depth":0}}
]
(POLICY-AS-HOLDER: "根据公司的安全政策…" grounds the requires claim in a named external authority, so holder is the policy entity with perspective=QUOTED.)

Conversation:
  Alice: 我刚才在群里说过：“Bob 负责 auth。”
  Bob: 好的。
JSON array:
[
  {{"holder":"Alice","holder_perspective":"QUOTED","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}}
]
(SELF-QUOTING: Alice quotes her OWN prior utterance verbatim → holder=Alice, perspective=QUOTED.)

Conversation:
  Charlie: In the handoff notes, Alice wrote, "Bob is responsible for auth."
  Bob: I'll keep an eye on it.
JSON array:
[
  {{"holder":"Alice","holder_perspective":"QUOTED","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}}
]
(QUOTE AUTHORSHIP: Charlie reads ALICE's written quote → holder is the AUTHOR (Alice), not the reader (Charlie). perspective=QUOTED.)

Conversation:
  Alice: 我听Carol说，Bob现在负责auth。
  Bob: 收到。
JSON array:
[
  {{"holder":"Alice","holder_perspective":"HEARSAY","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}}
]
(HEARSAY ATTRIBUTION: holder=Alice — she is voicing the claim now. Carol is only the source she heard it from.)

Conversation:
  Alice: I believe Bob is responsible for auth. I also believe Carol believes Bob prefers Postgres.
  Bob: That sounds right for auth.
JSON array:
[
  {{"holder":"Alice","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}},
  {{"holder":"Alice","holder_perspective":"FIRST_PERSON","subject":"Carol","predicate":"believes","object":"Bob prefers Postgres","modality":"BELIEVES","polarity":"POS","nesting_depth":2}}
]
(DEPTH-2 here is FIRST_PERSON because Alice EXPLICITLY says "I also believe…" — direct self-attribution of the outer belief.)

Conversation:
  Alice: I think Bob assumes Carol knows auth, since he keeps assigning the auth runbook to her.
  Bob: Hmm.
JSON array:
[
  {{"holder":"Alice","holder_perspective":"INFERRED","subject":"Bob","predicate":"believes","object":"Carol knows auth","modality":"BELIEVES","polarity":"POS","nesting_depth":2}}
]
(DEPTH-2 here is INFERRED because Alice JUSTIFIES her claim from observed behavior — "since he keeps assigning…".)

Conversation:
  Alice: 我看了今天的值班表，auth 那一栏写的是 Bob，所以判断 auth 归 Bob 负责。
  Carol: 我也这么理解。Bob 刚才还说，他觉得缓存问题是 Redis 配置导致的。
JSON array:
[
  {{"holder":"Alice","holder_perspective":"INFERRED","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}},
  {{"holder":"Carol","holder_perspective":"HEARSAY","subject":"Bob","predicate":"believes","object":"缓存问题是 Redis 配置导致的","modality":"BELIEVES","polarity":"POS","nesting_depth":2}}
]
(Multi-speaker depth-2: Carol introduces NEW content about Bob's said belief → Carol is the holder, perspective=HEARSAY. Alice's responsible_for is INFERRED — judged from the duty roster, not directly self-attributed.)

Conversation:
{convo}

JSON array:"""


def extract_via_gpt(conversation: list[dict], base_url: str, api_key: str, model: str) -> list[dict]:
    convo_str = "\n".join(f'{t["speaker"]}: {t["text"]}' for t in conversation)
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": _EXTRACT_PROMPT.format(convo=convo_str)}],
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(
        url=f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json\n"):
            content = content[len("json\n"):]
    return json.loads(content)


def run_one_round(corpus: list[dict], base_url: str, api_key: str, model: str) -> dict[str, float]:
    totals: dict[str, list[int]] = {
        k: [0, 0, 0] for k in P1_THRESHOLDS.keys()
    }
    for i, rec in enumerate(corpus, 1):
        try:
            predicted = extract_via_gpt(rec["conversation"], base_url, api_key, model)
        except Exception as e:
            print(f"WARN: record {rec.get('id')} extraction failed: {e}", file=sys.stderr)
            predicted = []
        per = evaluate_record(rec, predicted)
        for k, (tp, fp, fn) in per.items():
            totals[k][0] += tp
            totals[k][1] += fp
            totals[k][2] += fn
        print(f"[{i}/{len(corpus)}] {rec.get('id')}", file=sys.stderr)
        time.sleep(1)
    return {k: f1_score(tp, fp, fn) for k, (tp, fp, fn) in totals.items()}


def write_report(path: Path, rounds: list[dict[str, float]], thresholds: dict[str, float]) -> None:
    lines = ["# P1 EVAL Report", ""]
    lines.append("| field | " + " | ".join(f"round {i+1}" for i in range(len(rounds))) + " | threshold | last >= threshold |")
    lines.append("|---|" + "---|" * (len(rounds) + 2))
    for field in P1_THRESHOLDS:
        row = [f"{field}"]
        for r in rounds:
            row.append(f"{r[field]:.3f}")
        row.append(f"{thresholds[field]:.2f}")
        last = rounds[-1][field]
        row.append("PASS" if last >= thresholds[field] else "**FAIL**")
        lines.append("| " + " | ".join(row) + " |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--corpus",  required=True, type=Path)
    p.add_argument("--rounds",  type=int, default=3)
    p.add_argument("--report",  type=Path, default=Path("build/eval_p1_report.md"))
    p.add_argument("--model",   default="gpt-5.5")
    args = p.parse_args(argv)

    api_key  = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 1

    corpus = [json.loads(l) for l in args.corpus.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(corpus)} corpus records", file=sys.stderr)

    rounds = []
    for r in range(args.rounds):
        print(f"=== round {r+1}/{args.rounds} ===", file=sys.stderr)
        rounds.append(run_one_round(corpus, base_url, api_key, args.model))
        print(f"round {r+1} F1: {rounds[-1]}", file=sys.stderr)

    write_report(args.report, rounds, P1_THRESHOLDS)
    last = rounds[-1]
    fail = [f for f, v in last.items() if v < P1_THRESHOLDS[f]]
    if fail:
        print(f"BLOCKED: thresholds not met on last round for fields: {fail}", file=sys.stderr)
        return 1
    print("ALL THRESHOLDS PASSED", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
