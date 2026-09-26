#!/usr/bin/env python3
"""Post-hoc envelope sensitivity analysis; never replaces the strict run scores."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import shutil

import eval_socialmem_admission as admission


def envelope_payload(raw):
    match = re.fullmatch(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n```", raw.strip(), re.DOTALL)
    return match.group(1) if match else raw


def analyze(run, out):
    manifest = admission.load(run / "manifest.json")
    verification = admission.load(run / "verification.json")
    assert manifest["execution_mode"] == "real" and verification["status"] == "verified"
    assert verification["run_status"] == manifest["status"]
    for name, fingerprint in verification["artifact_sha256"].items():
        assert admission.digest(run / name) == fingerprint, name
    source = Path(admission.__file__).relative_to(admission.ROOT)
    assert admission.digest(Path(admission.__file__)) == manifest["source_sha256"][str(source)]
    entries = admission.load(run / "inputs.json")
    strict = admission.lines(run / "admissions.jsonl")
    calls = {(r["track"], r["id"]): r for r in admission.lines(run / "admission_calls.jsonl")}
    adjusted, diagnostics = [], []
    for entry, before in zip(entries, strict, strict=True):
        case = entry["case"]
        call = calls.get((case["track"], case["id"]))
        after = before
        changed = False
        if call is not None:
            raw = envelope_payload(call["raw"])
            changed = raw != call["raw"]
            candidates = admission.review_input(entry["original"])["candidates"]
            result = admission.apply_decisions(case, candidates, raw, call["ok"], call["error"])
            after = {**before, **result}
        adjusted.append(after)
        diagnostics.append({"track": case["track"], "id": case["id"], "envelope_removed": changed,
                            "strict": before, "envelope_sensitivity": after})
    metrics = {"claim_level": "post_hoc_offline_envelope_sensitivity_only",
               "new_model_calls": 0, "native_replays": 0, "benchmark_answers": 0,
               "rule": "Accept either the original response or one whole-response json/unlabelled code fence; "
                       "then apply the unchanged strict JSON, schema, source quote and semantic verdict checks. "
                       "No JSON repair, candidate rewriting, native persistence, judge calls or score replacement.",
               "fenced_calls": sum(r["envelope_removed"] for r in diagnostics), "arms": {}}
    for arm, rows in (("strict", strict), ("envelope_sensitivity", adjusted)):
        metrics["arms"][arm] = {
            "controls": admission.control_scores(entries, rows),
            "upstream_failures": sum(not r["upstream_ok"] for r in rows),
            "admission_failures": sum(r["upstream_ok"] and not r["ok"] for r in rows),
            "tracks": {track: {"retained": sum(len(r["retained"]) for r in rows if r["track"] == track),
                                "reasons": dict(Counter(d["reason"] for r in rows if r["track"] == track
                                                         for d in r["decisions"]))}
                       for track in ("p1", "synthetic", "controls", "scoped", "admission_controls")}}
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, out / Path(__file__).name)
    admission.dump(out / "manifest.json", {
        "execution_mode": "offline_analysis", "parent": str(run.resolve()),
        "parent_verification_sha256": admission.digest(run / "verification.json"),
        "analysis_sha256": admission.digest(Path(__file__)),
        "admission_sha256": admission.digest(Path(admission.__file__))})
    admission.dump(out / "diagnostics.json", diagnostics)
    admission.dump(out / "results.json", metrics)
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.run, args.out), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
