#!/usr/bin/env python3
"""Frozen text/evidence coverage for supplemental synthetic targets.

This is an evaluation proxy, not a semantic validator or a product speech-act
classifier. Object fragments use case-insensitive literal substring coverage,
with only the alternatives explicitly declared by each label. Actor, predicate,
topic, scope arrays and time fields match exactly; native enum casing alone is
normalized. No topic completion, date inference, stemming or model calls occur.

Each dimension has its own maximum-cardinality one-to-one target/row matching.
Joint coverage requires every dimension on the same row. Speech-act groups are
derived from these global assignments, so their counts sum to the overall score.
Unmatched predictions means supplemental rows unmatched by the joint assignment;
the incomplete labels make this a diagnostic count, not a false-positive count.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


LABEL_PATH = Path(__file__).resolve().parents[1] / "tests/data/eval_socialmem_extended_labels.json"
METRIC = "declared_text_and_evidence_coverage"
PREDICATES = frozenset(("feels", "uncertain_about", "decided_on", "indifferent_to", "trusts"))
DIMENSIONS = ("object", "topic", "scope", "time", "joint")
TARGET_COUNTS = ("targets", "valid_targets", "technical_failed_targets") + tuple(
    f"{dimension}_covered" for dimension in DIMENSIONS)
PREDICTION_COUNTS = ("predictions", "excluded_predictions", "unmatched_predictions")


def _counts():
    return dict.fromkeys(TARGET_COUNTS, 0)


def _rates(score):
    for name, denominator in (("strict_rates", "targets"), ("valid_rates", "valid_targets")):
        score[name] = {dimension: score[f"{dimension}_covered"] / score[denominator]
                       if score[denominator] else None for dimension in DIMENSIONS}
    return score


def _evidence(row):
    try:
        evidence = json.loads(row.get("semantic_claim_json") or "null")
    except (TypeError, ValueError):
        return {}
    return evidence if isinstance(evidence, dict) else {}


def _covers(target, row, evidence):
    identity = (row.get("subject_id") == target["actor"]
                and row.get("predicate") == target["predicate"]
                and str(row.get("polarity", "")).upper() == target["polarity"]
                and str(row.get("modality", "")).upper() == target["modality"])
    object_value = row.get("object_value")
    covered = {
        "object": isinstance(object_value, str) and all(
            any(fragment.casefold() in object_value.casefold() for fragment in alternatives)
            for alternatives in target["object_all"]),
        "topic": "topic" in evidence and evidence["topic"] in target["topic_any"],
        "scope": "scope_markers" in evidence and evidence["scope_markers"] in target["scope_options"],
        "time": all(field in evidence and evidence[field] == target[field]
                    for field in ("time_text", "event_time")),
    }
    covered["joint"] = all(covered.values())
    return {dimension: identity and value for dimension, value in covered.items()}


def _maximum_matching(edges):
    """Return target -> prediction using augmenting paths, in stable input order."""
    prediction_to_target = {}

    def augment(target, visited):
        for prediction in edges[target]:
            if prediction in visited:
                continue
            visited.add(prediction)
            previous = prediction_to_target.get(prediction)
            if previous is None or augment(previous, visited):
                prediction_to_target[prediction] = target
                return True
        return False

    for target in range(len(edges)):
        augment(target, set())
    return {target: prediction for prediction, target in prediction_to_target.items()}


def score_case(targets, rows, *, native_ok):
    """Score final native rows; failed cases retain targets but receive no credit.

    Returned matches use zero-based indices into the original targets and rows.
    Predictions outside the five supplemental predicates are counted separately.
    Speech-act group rates use the same strict/technically-valid denominators.
    """
    predictions = [(index, row) for index, row in enumerate(rows) if row.get("predicate") in PREDICATES]
    score = _counts()
    score.update(targets=len(targets), valid_targets=len(targets) if native_ok else 0,
                 technical_failed_targets=0 if native_ok else len(targets),
                 predictions=len(predictions), excluded_predictions=len(rows) - len(predictions))
    groups = {}
    for target in targets:
        group = groups.setdefault(target["speech_act"], _counts())
        group["targets"] += 1
        group["valid_targets" if native_ok else "technical_failed_targets"] += 1
    matrix = [[_covers(target, row, _evidence(row)) for _, row in predictions] for target in targets]
    matches = {}
    for dimension in DIMENSIONS:
        edges = [[index for index, covered in enumerate(target_rows)
                  if native_ok and covered[dimension]] for target_rows in matrix]
        assignment = _maximum_matching(edges)
        matches[dimension] = [{"target_index": target_index,
                               "prediction_index": predictions[prediction_index][0]}
                              for target_index, prediction_index in sorted(assignment.items())]
        score[f"{dimension}_covered"] = len(assignment)
        for target_index in assignment:
            groups[targets[target_index]["speech_act"]][f"{dimension}_covered"] += 1
    score["unmatched_predictions"] = len(predictions) - score["joint_covered"]
    score["matches"] = matches
    score["speech_act"] = {name: _rates(group) for name, group in sorted(groups.items())}
    return _rates(score)


def _by_id(entries, kind):
    indexed = {}
    for entry in entries:
        identity = entry.get("id")
        if not isinstance(identity, str) or not identity or identity in indexed:
            raise ValueError(f"invalid or duplicate {kind} id: {identity!r}")
        indexed[identity] = entry
    return indexed


def summarize(labels, cases, results):
    """Recompute a complete frozen-label summary from runner-native results.

    ``cases`` is the synthetic source cohort (each has id/passage); ``results``
    may contain the full runner journal, selected strictly by track=synthetic.
    Only ``rows`` is scored, never baseline-inclusive ``after``. Every label's
    UTF-8 source SHA-256 is checked before scoring, including excluded cases.
    Labels and sources must have identical unique IDs. Missing result records
    count as technical failures so a partial journal cannot shrink denominators.
    Other tracks are ignored; duplicate or unknown synthetic IDs are rejected.

    The result has aggregate target/prediction counts, strict_rates/valid_rates,
    speech_act groups, explicit case exclusions and a deterministic case_scores
    list carrying status, coverage and the per-dimension matching indices.
    """
    if labels.get("schema_version") != 1:
        raise ValueError("unsupported extended label schema version")
    if labels.get("metric", METRIC) != METRIC:
        raise ValueError("unsupported extended label metric")
    labelled = _by_id(labels["cases"], "label source")
    sources = _by_id(cases, "source")
    if labelled.keys() != sources.keys():
        raise ValueError("label/source case IDs differ")
    for identity, label in labelled.items():
        passage = sources[identity].get("passage")
        if not isinstance(passage, str) or hashlib.sha256(passage.encode("utf-8")).hexdigest() != label.get("source_sha256"):
            raise ValueError(f"extended label source SHA-256 mismatch: {identity}")
    native = _by_id([result for result in results if result.get("track") == "synthetic"], "synthetic result")
    if not native.keys() <= labelled.keys():
        raise ValueError("unknown synthetic result source ID")

    summary = {**_counts(), **dict.fromkeys(PREDICTION_COUNTS, 0)}
    summary.update(schema_version=1, metric=METRIC, label_origin=labels.get("label_origin"),
                   cases=len(labelled), evaluated_cases=0, excluded_cases=0,
                   missing_result_cases=0, technical_failed_cases=0,
                   excluded_case_predictions=0, speech_act={}, case_scores=[])
    for identity, label in labelled.items():
        result = native.get(identity)
        rows = result["rows"] if result is not None else []
        base_receipt = result.get("base_receipt") if result is not None else None
        native_ok = bool(result is not None and result.get("native_ok") is True
                         and not (base_receipt and base_receipt.get("extraction_failed")))
        score = score_case(label["targets"], rows, native_ok=native_ok)
        excluded = not label["targets"]
        status = ("excluded" if excluded else "missing_result" if result is None
                  else "ok" if native_ok else "technical_failure")
        summary["case_scores"].append({"id": identity, "source_sha256": label["source_sha256"],
                                       "coverage": label.get("coverage"), "status": status,
                                       "native_ok": native_ok, **score})
        summary["missing_result_cases"] += result is None
        if excluded:
            summary["excluded_cases"] += 1
            summary["excluded_case_predictions"] += len(rows)
            continue
        summary["evaluated_cases"] += 1
        summary["technical_failed_cases"] += not native_ok
        for field in TARGET_COUNTS + PREDICTION_COUNTS:
            summary[field] += score[field]
        for name, group_score in score["speech_act"].items():
            group = summary["speech_act"].setdefault(name, _counts())
            for field in TARGET_COUNTS:
                group[field] += group_score[field]
    summary["speech_act"] = {name: _rates(group) for name, group in sorted(summary["speech_act"].items())}
    return _rates(summary)
