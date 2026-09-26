"""Persistent request budget and frozen native-identity checks for SocialMem runs."""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import hmac
import json
from pathlib import Path


ARMS = ("C0", "C1")
PHASES = ("probe", "extract", "admission")
_HEADER_KEYS = {"type", "version", "run_id", "arms", "created_at", "prev_sha256", "sha256"}
_RESERVATION_KEYS = {"type", "run_id", "arm", "phase", "request_id", "count",
                     "reserved_at", "prev_sha256", "sha256"}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _canonical_bytes(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("identity is not JSON serializable") from exc


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path):
    return _sha256_bytes(Path(path).read_bytes())


def _record_hash(record):
    return _sha256_bytes(_canonical_bytes({key: value for key, value in record.items()
                                           if key != "sha256"}))


def _sealed_record(record):
    return record | {"sha256": _record_hash(record)}


def _source_identity(case):
    _require(type(case) is dict, "case must be an object")
    keys = ("id", "track", "holder", "passage")
    _require(all(type(case.get(key)) is str and case[key] for key in keys),
             "case source identity is incomplete")
    source = {key: case[key] for key in keys}
    digest = _sha256_bytes(_canonical_bytes(source))
    if "source_sha256" in case:
        _require(case["source_sha256"] == digest, "case source_sha256 drift")
    return source, digest


def _contract_schemas(core):
    return {
        "claim_extraction_v2": core.structured_output_schema_sha256(
            core.OutputContractKind.ClaimExtractionV2),
        "claim_admission_v1": core.structured_output_schema_sha256(
            core.OutputContractKind.ClaimAdmissionV1),
    }


class RequestLedger:
    """Append-only, locked reservations. Failed calls intentionally remain spent."""

    def __init__(self, path, run_id, arms=ARMS, create=False):
        self.path = Path(path)
        self.run_id = run_id
        self.arms = tuple(arms)
        _require(type(run_id) is str and run_id, "run_id must be non-empty")
        _require(self.arms and len(set(self.arms)) == len(self.arms) and
                 all(type(arm) is str and arm for arm in self.arms), "invalid arms")
        if create:
            self._create()
        else:
            _require(self.path.is_file(), "ledger does not exist")
            with self.path.open("rb") as stream:
                fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
                try:
                    self._parse(stream.read())
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _create(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _require(not self.path.exists(), "ledger already exists")
        header = _sealed_record({"type": "socialmem_request_ledger", "version": 1,
                                 "run_id": self.run_id, "arms": list(self.arms),
                                 "created_at": _utc_now(), "prev_sha256": None})
        try:
            with self.path.open("xb") as stream:
                stream.write(_canonical_bytes(header) + b"\n")
                stream.flush()
                __import__("os").fsync(stream.fileno())
        except FileExistsError as exc:
            raise ValueError("ledger already exists") from exc

    def _parse(self, payload):
        _require(payload and payload.endswith(b"\n"), "ledger is malformed")
        lines = payload.splitlines()
        _require(lines and all(line for line in lines), "ledger is malformed")
        records = []
        for line in lines:
            try:
                value = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("ledger is malformed") from exc
            _require(type(value) is dict, "ledger is malformed")
            records.append(value)
        header = records[0]
        _require(set(header) == _HEADER_KEYS and header.get("type") == "socialmem_request_ledger" and
                 header.get("version") == 1 and header.get("prev_sha256") is None and
                 type(header.get("created_at")) is str and
                 hmac.compare_digest(header.get("sha256", ""), _record_hash(header)),
                 "ledger identity or header is invalid")
        _require(header.get("run_id") == self.run_id, "ledger run_id drift")
        _require(header.get("arms") == list(self.arms), "ledger arms drift")
        previous = header["sha256"]
        seen = set()
        totals = {arm: {phase: 0 for phase in PHASES} for arm in self.arms}
        for record in records[1:]:
            _require(set(record) == _RESERVATION_KEYS and record.get("type") == "reservation" and
                     record.get("run_id") == self.run_id and record.get("arm") in totals and
                     record.get("phase") in PHASES and type(record.get("request_id")) is str and
                     bool(record["request_id"]) and type(record.get("count")) is int and
                     type(record.get("reserved_at")) is str and record.get("prev_sha256") == previous and
                     hmac.compare_digest(record.get("sha256", ""), _record_hash(record)),
                     "ledger reservation is malformed")
            expected_count = 2 if record["phase"] == "probe" else 1
            _require(record["count"] == expected_count, "ledger reservation count is invalid")
            key = record["arm"], record["phase"], record["request_id"]
            _require(key not in seen, "ledger has duplicate request identity")
            seen.add(key)
            totals[record["arm"]][record["phase"]] += record["count"]
            _require(totals[record["arm"]][record["phase"]] <= 8, "ledger phase budget exceeded")
            previous = record["sha256"]
        _require(sum(sum(phases.values()) for phases in totals.values()) <= 48,
                 "ledger total budget exceeded")
        return seen, totals, previous

    def reserve(self, arm, phase, request_id, count=1):
        _require(arm in self.arms and phase in PHASES and type(request_id) is str and request_id,
                 "invalid reservation identity")
        expected_count = 2 if phase == "probe" else 1
        _require(type(count) is int and count == expected_count, "invalid reservation count")
        with self.path.open("r+b") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                seen, totals, previous = self._parse(stream.read())
                key = arm, phase, request_id
                _require(key not in seen, "duplicate reservation")
                _require(totals[arm][phase] + count <= 8, "phase budget exceeded")
                _require(sum(sum(values.values()) for values in totals.values()) + count <= 48,
                         "total budget exceeded")
                record = _sealed_record({"type": "reservation", "run_id": self.run_id,
                                         "arm": arm, "phase": phase, "request_id": request_id,
                                         "count": count, "reserved_at": _utc_now(),
                                         "prev_sha256": previous})
                stream.seek(0, 2)
                stream.write(_canonical_bytes(record) + b"\n")
                stream.flush()
                __import__("os").fsync(stream.fileno())
                return record
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def snapshot(self):
        with self.path.open("rb") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
            try:
                _seen, totals, _previous = self._parse(stream.read())
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        used = {phase: sum(totals[arm][phase] for arm in self.arms) for phase in PHASES}
        return {"run_id": self.run_id, "used": used, "arms": totals,
                "reserved_total": sum(used.values())}


def frozen_identity(core, config, cases, code_paths=()):
    """Freeze only C++ identities and model inputs; never derive model semantics."""
    _require(type(config) is dict, "config must be an object")
    frozen_config = json.loads(_canonical_bytes(config))
    core_path = Path(core.__file__).resolve()
    _require(core_path.is_file(), "native core path is unavailable")
    sources, prompts = {}, {}
    for case in cases:
        source, digest = _source_identity(case)
        case_id = source["id"]
        _require(case_id not in sources, "case ids must be unique")
        sources[case_id] = digest
        prompt = core.claim_extraction_prompt(source["passage"], source["holder"])
        _require(type(prompt) is str, "native extraction prompt is invalid")
        prompts[case_id] = _sha256_bytes(prompt.encode("utf-8"))
    code = {}
    for raw_path in code_paths:
        code_path = Path(raw_path).resolve()
        _require(code_path.is_file(), "code path is unavailable")
        key = str(code_path)
        _require(key not in code, "duplicate code path")
        code[key] = _file_sha256(code_path)
    return {"identity_version": 1, "frozen_at": _utc_now(), "core_path": str(core_path),
            "core_sha256": _file_sha256(core_path), "schemas": _contract_schemas(core),
            "config": frozen_config, "sources": sources, "prompt_sha256": prompts,
            "code_sha256": code}


def verify_identity(core, config, frozen, case=None):
    _require(type(frozen) is dict and frozen.get("identity_version") == 1, "invalid frozen identity")
    _require(type(config) is dict and frozen.get("config") == json.loads(_canonical_bytes(config)),
             "config identity drift")
    core_path = Path(core.__file__).resolve()
    _require(frozen.get("core_path") == str(core_path) and core_path.is_file() and
             hmac.compare_digest(frozen.get("core_sha256", ""), _file_sha256(core_path)),
             "native core identity drift")
    _require(frozen.get("schemas") == _contract_schemas(core), "native schema identity drift")
    code = frozen.get("code_sha256")
    _require(type(code) is dict, "code identity is invalid")
    for raw_path, expected in code.items():
        path = Path(raw_path)
        _require(path.is_absolute() and path.is_file() and type(expected) is str and
                 hmac.compare_digest(expected, _file_sha256(path)), "code identity drift")
    sources, prompts = frozen.get("sources"), frozen.get("prompt_sha256")
    _require(type(sources) is dict and type(prompts) is dict and set(sources) == set(prompts),
             "frozen source identity is invalid")
    if case is not None:
        source, digest = _source_identity(case)
        case_id = source["id"]
        _require(case_id in sources and sources[case_id] == digest, "source identity drift")
        prompt = core.claim_extraction_prompt(source["passage"], source["holder"])
        _require(type(prompts[case_id]) is str and
                 hmac.compare_digest(prompts[case_id], _sha256_bytes(prompt.encode("utf-8"))),
                 "extraction prompt identity drift")
    return True


def verify_capability(core, config, frozen, report_path, expected_report_sha256, *, at=None,
                      check_freshness=True):
    """Verify frozen identity then invoke the existing C++-backed capability verifier."""
    verify_identity(core, config, frozen)
    path = Path(report_path)
    _require(path.is_file() and type(expected_report_sha256) is str and
             hmac.compare_digest(expected_report_sha256, _file_sha256(path)),
             "capability report hash drift")
    try:
        report = json.loads(path.read_text())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("capability report is malformed") from exc
    _require(type(report) is dict and report.get("request_count") == 8,
             "capability report must record exactly eight requests")
    _require(type(config.get("endpoint")) is str and type(config.get("model")) is str,
             "capability transport config is incomplete")
    from probe_socialmem_output_capability import check_report
    return check_report(core, report, {"endpoint": config["endpoint"], "model": config["model"]},
                        "json_schema_strict", at=at, check_freshness=check_freshness)


class GuardedRequestGate:
    """每次样本请求均先复验身份、能力，再持久预约；只用于实验编排。"""

    def __init__(self, core, config, frozen, *, case, ledger, arm, request_id,
                 report_path, report_sha256, at):
        _require(isinstance(ledger, RequestLedger), 'persistent request ledger required')
        self.core, self.config, self.frozen = core, config, frozen
        self.case, self.ledger, self.arm = case, ledger, arm
        self.request_id = request_id
        self.report_path, self.report_sha256, self.at = report_path, report_sha256, at

    def __call__(self, phase):
        _require(phase in ('extract', 'admission'), 'invalid sample request phase')
        verify_identity(self.core, self.config, self.frozen, self.case)
        ready = verify_capability(self.core, self.config, self.frozen, self.report_path,
                                  self.report_sha256, at=self.at)
        _require(ready['ready'], 'capability gate failed: ' + str(ready['reasons']))
        return self.ledger.reserve(self.arm, phase, self.request_id, 1)
