#!/usr/bin/env python3
"""Freeze previews and supervise isolated S/T workers with exact budgets."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "scripts/eval_socialmem_scope_latency.py"
EXPERIMENT_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1"
S_BUDGET = 28
T_BUDGET = 24
ARM_SPECS = {"S": {"S0": 60000, "S1": 60000},
             "T": {"T60": 60000, "T120": 120000}}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_sha256(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text())


def write_json_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def paired_schedule(experiment, sources, arm_names):
    require(experiment in ("S", "T"), "unknown experiment")
    require(len(arm_names) == 2 and arm_names[0] != arm_names[1], "two distinct arms required")
    schedule = []
    for source_index, source in enumerate(sources):
        order = arm_names if source_index % 2 == 0 else arm_names[::-1]
        for pair_position, arm in enumerate(order):
            schedule.append({"sequence": len(schedule), "experiment": experiment,
                "source_index": source_index, "pair_position": pair_position,
                "arm": arm, **source})
    return schedule


def scope_schedule(pairs, arm_names):
    sources = []
    for pair_index, pair in enumerate(pairs):
        for role in ("target", "control"):
            sources.append({**pair[role], "scope_pair": pair_index, "scope_role": role})
    return paired_schedule("S", sources, arm_names)


def verify_experiment_shape(plan):
    experiment = plan.get("experiment")
    require(experiment in ARM_SPECS, "unknown experiment")
    actual_arms = tuple((arm["name"], arm["timeout_ms"]) for arm in plan["arms"])
    require(actual_arms == tuple(ARM_SPECS[experiment].items()),
            "fixed arm/timeout mapping drift")
    expected_budget = S_BUDGET if experiment == "S" else T_BUDGET
    schedule = plan["schedule"]
    require(plan.get("extraction_budget") == expected_budget and
            len(schedule) == expected_budget, "fixed extraction budget drift")
    names = tuple(ARM_SPECS[experiment])
    for source_index in range(expected_budget // 2):
        pair = schedule[2 * source_index:2 * source_index + 2]
        require([entry.get("sequence") for entry in pair] ==
                [2 * source_index, 2 * source_index + 1] and
                all(entry.get("experiment") == experiment and
                    entry.get("source_index") == source_index for entry in pair),
                "fixed schedule sequence drift")
        identity_keys = ("id", "track", "holder", "passage", "source_sha256")
        require(all(pair[0].get(key) == pair[1].get(key) for key in identity_keys),
                "paired source identity drift")
        expected_order = names if source_index % 2 == 0 else names[::-1]
        require(tuple(entry.get("arm") for entry in pair) == expected_order and
                [entry.get("pair_position") for entry in pair] == [0, 1],
                "paired arm alternation drift")
    if experiment == "S":
        sources = schedule[::2]
        require([entry.get("scope_role") for entry in sources] ==
                [role for _ in range(7) for role in ("target", "control")] and
                [entry.get("scope_pair") for entry in sources] ==
                [index for index in range(7) for _ in range(2)],
                "S target/control pairing drift")
    return True


def _manifest_body(arm):
    return {key: value for key, value in arm.items() if key != "manifest_sha256"}


def seal_arm_manifest(arm):
    require(Path(arm["report"]).is_file(), "capability report is missing")
    arm["config_sha256"] = canonical_sha256(arm["config"])
    arm["report_sha256"] = file_sha256(arm["report"])
    arm["manifest_sha256"] = canonical_sha256(_manifest_body(arm))
    return arm


def verify_arm_manifest(arm):
    required = ("arm", "config", "config_sha256", "core_sha256", "schema_sha256",
                "report", "report_sha256", "created_at", "manifest_sha256")
    require(all(key in arm for key in required), "arm manifest is incomplete")
    require(arm["config_sha256"] == canonical_sha256(arm["config"]), "config identity drift")
    require(Path(arm["report"]).is_file() and
            arm["report_sha256"] == file_sha256(arm["report"]), "capability report drift")
    require(arm["manifest_sha256"] == canonical_sha256(_manifest_body(arm)),
            "arm identity drift")
    config = arm["config"]
    require(config.get("max_tokens") == 4096 and config.get("max_retries") == 0 and
            config.get("temperature") == 0 and
            config.get("output_mode") == "json_schema_strict", "config policy drift")
    return True


def execute_frozen_schedule(arms, schedule, *, validate, extract, started_at,
                            extraction_budget):
    require(len(schedule) == extraction_budget, "extraction budget does not match frozen schedule")
    experiments = {entry.get("experiment") for entry in schedule}
    require(len(experiments) == 1 and experiments <= {"S", "T"}, "schedule experiment drift")
    expected_budget = S_BUDGET if experiments == {"S"} else T_BUDGET
    require(extraction_budget == expected_budget, "extraction budget exceeded")
    by_name = {arm["arm"]: arm for arm in arms}
    require(len(by_name) == 2 and all(entry["arm"] in by_name for entry in schedule),
            "schedule arm identity drift")
    for arm in arms:
        verify_arm_manifest(arm)
    readiness = []
    for arm in arms:
        result = validate(arm, started_at)
        readiness.append(result)
    reasons = [reason for result in readiness if not result.get("ready")
               for reason in result.get("reasons", ["unknown capability failure"])]
    if reasons:
        suffix = " expired" if any("expired" in reason for reason in reasons) else ""
        raise ValueError(f"capability{suffix} gate failed: {reasons}")
    results = []
    for entry in schedule:
        # A failed action is an observed result. It is archived once and never retried.
        results.append(extract(by_name[entry["arm"]], entry))
    require(len(results) == extraction_budget, "extraction action count drift")
    return results


def worker_command(python, worker, stage, action, out):
    return [str(python), "-S", str(worker), action,
            "--stage", str(Path(stage).resolve()), "--out", str(out)]


def verify_preview_pair(experiment, left, right):
    require(experiment in ("S", "T"), "unknown experiment")
    configs = (left["config"], right["config"])
    identities = (left["identity"], right["identity"])
    if experiment == "T":
        require(sorted(config["timeout_ms"] for config in configs) == [60000, 120000],
                "T timeout config drift")
        require({key: value for key, value in configs[0].items() if key != "timeout_ms"} ==
                {key: value for key, value in configs[1].items() if key != "timeout_ms"},
                "T non-timeout config drift")
        require(identities[0]["core_sha256"] == identities[1]["core_sha256"] and
                identities[0]["schema_sha256"] == identities[1]["schema_sha256"],
                "T native identity drift")
    else:
        require(configs[0] == configs[1] and configs[0]["timeout_ms"] == 60000,
                "S config drift")
        require(identities[0]["core_sha256"] != identities[1]["core_sha256"] and
                identities[0]["schema_sha256"] == identities[1]["schema_sha256"],
                "S native identity drift")
    left_bodies = [request["body"] for request in left["requests"]]
    right_bodies = [request["body"] for request in right["requests"]]
    require(len(left_bodies) == len(right_bodies), "preview request count drift")
    require(all((left_request["method"], left_request["path"]) ==
                (right_request["method"], right_request["path"])
                for left_request, right_request in zip(left["requests"], right["requests"])),
            "cross-arm request method/path drift")
    for preview in (left, right):
        require(not any(key.lower() in ("authorization", "proxy-authorization", "x-api-key", "api-key")
                        for request in preview["requests"] for key in request["headers"]),
                "preview contains credential header")
    if experiment == "T":
        require(left_bodies == right_bodies, "T native request drift")
    else:
        def without_content(body):
            value = json.loads(json.dumps(body))
            for message in value.get("messages", []):
                message["content"] = "<native-prompt>"
            return value
        require(all(without_content(left_body) == without_content(right_body)
                    for left_body, right_body in zip(left_bodies, right_bodies)),
                "S non-prompt request drift")
        require(any(left_body != right_body
                    for left_body, right_body in zip(left_bodies, right_bodies)),
                "S native prompt did not change")
    return True


def preflight_then_probe(arms, *, preflight, probe, probe_ready):
    snapshots = []
    for arm in arms:
        snapshot = preflight(arm)
        require(snapshot.get("config") == arm["config"] and
                snapshot.get("identity") == arm["identity"] and
                snapshot.get("request_sha256s") == arm["request_sha256s"],
                f"preflight identity drift: {arm['name']}")
        snapshots.append(snapshot)
    # No capability request is allowed until every arm passed local identity checks.
    results = []
    for arm in arms:
        result = probe(arm)
        require(probe_ready(result), f"capability gate failed after {arm['name']}")
        results.append(result)
    return results


def invoke_worker(python, worker, stage, action, out, extra=()):
    command = worker_command(python, worker, stage, action, out) + [str(value) for value in extra]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(f"worker {action} failed ({completed.returncode}): {completed.stderr.strip()}")
    return load_json(out)


def parse_arm(value):
    parts = value.split("=", 2)
    require(len(parts) == 3, "arm must be NAME=STAGE=TIMEOUT_MS")
    name, stage, timeout = parts
    timeout_ms = int(timeout)
    require(name and Path(stage).is_dir() and timeout_ms > 0, "invalid arm specification")
    return {"name": name, "stage": str(Path(stage).resolve()), "timeout_ms": timeout_ms}


def _seal_plan(plan):
    plan["plan_sha256"] = canonical_sha256(
        {key: value for key, value in plan.items() if key != "plan_sha256"})
    return plan


def verify_plan(plan, plan_path):
    expected = canonical_sha256({key: value for key, value in plan.items()
                                 if key != "plan_sha256"})
    require(plan.get("plan_sha256") == expected, "preview plan drift")
    require(plan.get("mode") == "preview" and plan.get("experiment") in ("S", "T"),
            "invalid preview plan")
    verify_experiment_shape(plan)
    orchestration = plan.get("orchestration", {})
    require(orchestration.get("supervisor_path") == str(Path(__file__).resolve()) and
            orchestration.get("supervisor_sha256") == file_sha256(__file__),
            "supervisor source drift")
    require(Path(orchestration.get("worker_path", "")).resolve() == WORKER.resolve() and
            orchestration.get("worker_sha256") == file_sha256(WORKER),
            "worker source drift")
    parent = Path(plan_path).resolve().parent
    for arm in plan["arms"]:
        preview = parent / arm["preview"]
        require(preview.is_file() and file_sha256(preview) == arm["preview_sha256"],
                f"preview artifact drift: {arm['name']}")
        cases = parent / arm["cases"]
        require(cases.is_file() and file_sha256(cases) == arm["cases_sha256"],
                f"preview cases drift: {arm['name']}")
        require(len(arm["probe_request_sha256s"]) == 8 and
                arm["request_sha256s"] == arm["probe_request_sha256s"] +
                arm["extraction_request_sha256s"] and
                all(len(value) == 64 for value in arm["request_sha256s"]),
                f"preview request identity drift: {arm['name']}")
        scheduled = [entry["request_sha256"] for entry in plan["schedule"]
                     if entry["arm"] == arm["name"]]
        require(scheduled == arm["extraction_request_sha256s"],
                f"scheduled request identity drift: {arm['name']}")
    require(Path(plan["source_archive"]).is_file() and
            file_sha256(plan["source_archive"]) == plan["source_archive_sha256"],
            "source archive drift")
    if plan["source_calls"] is not None:
        require(Path(plan["source_calls"]).is_file() and
                file_sha256(plan["source_calls"]) == plan["source_calls_sha256"],
                "source call archive drift")
    require(canonical_sha256(plan["schedule"]) == plan["schedule_sha256"], "schedule drift")
    return True


def preview_experiment(*, experiment, arms, inputs, calls, out, endpoint,
                       model, python, worker=WORKER):
    out = Path(out)
    require(not out.exists(), "preview output already exists")
    require(len(arms) == 2 and len({arm["name"] for arm in arms}) == 2,
            "preview needs two distinct arms")
    require(model == "qwen3.7-plus", "experiment model drift")
    require(endpoint == EXPERIMENT_ENDPOINT, "experiment endpoint drift")
    require(tuple(arm["name"] for arm in arms) == tuple(ARM_SPECS.get(experiment, ())) and
            {arm["name"]: arm["timeout_ms"] for arm in arms} == ARM_SPECS.get(experiment),
            "fixed arm/timeout mapping drift")
    out.mkdir(parents=True)
    selected_path = out / "selected_sources.json"
    action = "select-scope" if experiment == "S" else "select-timeout"
    extra = ["--inputs", Path(inputs).resolve()]
    require(calls is not None, f"{experiment} preview requires A extraction calls")
    extra += ["--calls", Path(calls).resolve()]
    selected = invoke_worker(python, worker, arms[0]["stage"], action,
                             selected_path, extra)
    schedule = (scope_schedule(selected, tuple(arm["name"] for arm in arms))
                if experiment == "S" else
                paired_schedule("T", selected, tuple(arm["name"] for arm in arms)))
    expected_budget = S_BUDGET if experiment == "S" else T_BUDGET
    require(len(schedule) == expected_budget, "selected source budget drift")
    arm_records, preview_values = [], []
    for arm in arms:
        cases = [{key: entry[key] for key in ("id", "track", "holder", "passage")}
                 for entry in schedule if entry["arm"] == arm["name"]]
        cases_path = out / f"{arm['name']}-cases.json"
        write_json_new(cases_path, cases)
        preview_path = out / f"{arm['name']}-preview.json"
        preview = invoke_worker(python, worker, arm["stage"], "preview", preview_path,
            ["--cases", cases_path.resolve(), "--model", model,
             "--timeout-ms", arm["timeout_ms"], "--endpoint", endpoint])
        require(preview["extraction_request_count"] == len(cases) and
                preview["probe_request_count"] == 8, "preview request budget drift")
        preview_values.append(preview)
        request_hashes = [request["request_sha256"] for request in preview["requests"]]
        probe_hashes = request_hashes[:preview["probe_request_count"]]
        extraction_hashes = request_hashes[preview["probe_request_count"]:]
        arm_entries = [entry for entry in schedule if entry["arm"] == arm["name"]]
        require(len(arm_entries) == len(extraction_hashes), "preview extraction identity drift")
        for entry, request_hash in zip(arm_entries, extraction_hashes):
            entry["request_sha256"] = request_hash
        arm_records.append({**arm, "config": preview["config"],
            "identity": preview["identity"], "cases": cases_path.name,
            "cases_sha256": file_sha256(cases_path), "preview": preview_path.name,
            "preview_sha256": file_sha256(preview_path),
            "request_sha256s": request_hashes,
            "probe_request_sha256s": probe_hashes,
            "extraction_request_sha256s": extraction_hashes})
    verify_preview_pair(experiment, preview_values[0], preview_values[1])
    verify_experiment_shape({"experiment": experiment, "arms": arm_records,
        "schedule": schedule, "extraction_budget": expected_budget})
    plan = _seal_plan({"schema_version": 1, "mode": "preview", "experiment": experiment,
        "created_at": datetime.now(timezone.utc).isoformat(), "model": model,
        "endpoint": endpoint, "arms": arm_records, "schedule": schedule,
        "schedule_sha256": canonical_sha256(schedule),
        "extraction_budget": expected_budget,
        "candidate_request_budget": expected_budget + 16,
        "source_archive": str(Path(inputs).resolve()),
        "source_archive_sha256": file_sha256(inputs),
        "source_calls": str(Path(calls).resolve()) if calls else None,
        "source_calls_sha256": file_sha256(calls) if calls else None,
        "orchestration": {"supervisor_path": str(Path(__file__).resolve()),
            "supervisor_sha256": file_sha256(__file__),
            "worker_path": str(Path(worker).resolve()),
            "worker_sha256": file_sha256(worker)}})
    write_json_new(out / "plan.json", plan)
    return plan


def run_experiment(*, plan_path, out, python, worker=WORKER):
    plan_path, out = Path(plan_path).resolve(), Path(out)
    plan = load_json(plan_path)
    verify_plan(plan, plan_path)
    require(not out.exists(), "run output already exists")
    out.mkdir(parents=True)
    expected_paths = {}
    for arm in plan["arms"]:
        expected_path = out / f"{arm['name']}-frozen-preview-identity.json"
        write_json_new(expected_path, {"config": arm["config"], "identity": arm["identity"],
            "request_sha256s": arm["request_sha256s"],
            "probe_request_sha256s": arm["probe_request_sha256s"]})
        expected_paths[arm["name"]] = expected_path

    def preflight(arm):
        result_path = out / f"{arm['name']}-preflight.json"
        return invoke_worker(python, worker, arm["stage"], "preflight", result_path,
            ["--expected", expected_paths[arm["name"]],
             "--cases", plan_path.parent / arm["cases"], "--model", plan["model"],
             "--timeout-ms", arm["timeout_ms"], "--endpoint", plan["endpoint"]])

    def probe(arm):
        package_path = out / f"{arm['name']}-probe-package.json"
        return invoke_worker(python, worker, arm["stage"], "probe", package_path,
            ["--model", plan["model"], "--timeout-ms", arm["timeout_ms"],
             "--endpoint", plan["endpoint"],
             "--expected", expected_paths[arm["name"]]])

    packages = preflight_then_probe(plan["arms"], preflight=preflight, probe=probe,
        probe_ready=lambda package: package["readiness"]["ready"])
    manifests = []
    for arm, package in zip(plan["arms"], packages):
        require(package["config"] == arm["config"], f"{arm['name']} config drift")
        require(package["identity"]["core_sha256"] == arm["identity"]["core_sha256"] and
                package["identity"]["schema_sha256"] == arm["identity"]["schema_sha256"],
                f"{arm['name']} native identity drift")
        report_path = out / f"{arm['name']}-capability.json"
        write_json_new(report_path, package["report"])
        manifest_path = out / f"{arm['name']}-manifest.json"
        manifest = seal_arm_manifest({"arm": arm["name"], "stage": arm["stage"],
            "config": package["config"], "config_sha256": "",
            "core_sha256": package["identity"]["core_sha256"],
            "schema_sha256": package["identity"]["schema_sha256"],
            "report": str(report_path.resolve()), "report_sha256": "",
            "created_at": package["created_at"],
            "worker_sha256": arm["identity"]["worker_sha256"],
            "probe_helper_sha256": arm["identity"]["probe_helper_sha256"],
            "supervisor_path": plan["orchestration"]["supervisor_path"],
            "supervisor_sha256": plan["orchestration"]["supervisor_sha256"],
            "manifest_path": str(manifest_path.resolve())})
        write_json_new(manifest_path, manifest)
        manifests.append(manifest)
    started_at = datetime.now(timezone.utc)
    validation_index = 0
    extraction_index = 0

    def validate(arm, at):
        nonlocal validation_index
        result_path = out / f"validation-{validation_index:02d}-{arm['arm']}.json"
        validation_index += 1
        return invoke_worker(python, worker, arm["stage"], "check", result_path,
            ["--manifest", arm["manifest_path"], "--at", at.isoformat()])

    def extract(arm, entry):
        nonlocal extraction_index
        case_path = out / f"case-{extraction_index:02d}.json"
        result_path = out / f"receipt-{extraction_index:02d}.json"
        extraction_index += 1
        write_json_new(case_path, [{key: entry[key] for key in
            ("id", "track", "holder", "passage")}])
        return invoke_worker(python, worker, arm["stage"], "extract", result_path,
            ["--cases", case_path, "--manifest", arm["manifest_path"],
             "--expected-request-sha256", entry["request_sha256"],
             "--model", plan["model"], "--timeout-ms", arm["config"]["timeout_ms"],
             "--endpoint", plan["endpoint"]])

    results = execute_frozen_schedule(manifests, plan["schedule"], validate=validate,
        extract=extract, started_at=started_at, extraction_budget=plan["extraction_budget"])
    summary = {"schema_version": 1, "status": "complete_with_observations",
        "experiment": plan["experiment"], "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "plan_sha256": file_sha256(plan_path), "request_count": 16 + len(results),
        "probe_request_limit": 16, "extraction_request_count": len(results),
        "retries": 0, "quality": None}
    write_json_new(out / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    preview = sub.add_parser("preview")
    preview.add_argument("--experiment", choices=("S", "T"), required=True)
    preview.add_argument("--arm", action="append", type=parse_arm, required=True)
    preview.add_argument("--inputs", type=Path, required=True)
    preview.add_argument("--calls", type=Path)
    preview.add_argument("--out", type=Path, required=True)
    preview.add_argument("--endpoint", required=True)
    preview.add_argument("--model", default="qwen3.7-plus")
    preview.add_argument("--python", type=Path, default=Path(sys.executable))
    run = sub.add_parser("run")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args(argv)
    if args.mode == "preview":
        result = preview_experiment(experiment=args.experiment, arms=args.arm,
            inputs=args.inputs, calls=args.calls, out=args.out, endpoint=args.endpoint,
            model=args.model, python=args.python)
    else:
        result = run_experiment(plan_path=args.plan, out=args.out, python=args.python)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
