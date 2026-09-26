"""Real SQLite/native storage and evidence-linked retrieval contract tests."""
import hashlib
import json
import sqlite3

import pytest

from starling import _core, runtime

NOW = "2026-09-11T10:00:00Z"
SOURCE = "Mina: 如果离开团队，我会难过。".encode()


@pytest.fixture
def rig(tmp_path):
    path = tmp_path / "claims.db"
    rt = runtime._build_local_store_sqlite_runtime(path)
    rt.start()
    yield rt, path
    del rt


def _claim(engram="eng-default", scope="CONDITIONAL", event=None, payload=SOURCE):
    return {"schema_version": 1, "source_span": {
        "engram_ref": engram, "span_start": 0, "span_end": len(payload),
        "source_hash": hashlib.sha256(payload).hexdigest()},
        "clause_id": "c0", "actor": "Mina", "attributed_to": None,
        "assertion_scope": scope, "scope_markers": [scope],
        "relation_polarity": "POS", "relation_modality": "BELIEVES",
        "source_time": NOW, "time_text": "", "event_time": event}


def _seed(path, *, tenant="default", sid="same", claim=True, payload=SOURCE, obj=None):
    evidence = _claim("eng-" + tenant, payload=payload) if claim is True else claim
    content_hash = hashlib.sha256(b"v1\x1f" + payload + b"\x1f").hexdigest()
    span = evidence["source_span"] if isinstance(evidence, dict) else _claim("eng-" + tenant, payload=payload)["source_span"]
    with sqlite3.connect(path) as db:
        columns = {r[1] for r in db.execute("PRAGMA table_info(statements)")}
        assert "semantic_claim_json" in columns, "migration must add optional native evidence column"
        db.execute("INSERT OR IGNORE INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,ingest_mode,privacy_class,retention_mode,payload_inline,created_at) VALUES(?,?,?,'conversation','default','automatic','private','full',?,?)",
                   ("eng-" + tenant, tenant, content_hash, payload, NOW))
        db.execute("INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,modality,polarity,confidence,observed_at,salience,affect_json,activation,last_accessed,provenance,evidence_json,source_spans_json,consolidation_state,review_status,created_at,updated_at,semantic_claim_json) VALUES(?,?,'Mina','first_person','cognizer','Mina','feels','str',?,'hash','BELIEVES','pos',0.9,?,0.5,'{}',0.0,?,'user_input',?,?,'consolidated','approved',?,?,?)",
                   (sid, tenant, obj or "sad if leaving " + tenant, NOW, NOW,
                    json.dumps([{"engram_ref": "eng-" + tenant, "content_hash": content_hash, "status": "active"}]),
                    json.dumps([span]), NOW, NOW,
                    None if evidence is None else (evidence if isinstance(evidence, str) else json.dumps(evidence))))
    return evidence


def _basic(rt, tenant="default"):
    q = _core.BasicRetrieverParams()
    q.tenant_id = tenant
    q.holder_id = q.subject_id = "Mina"
    q.predicate = "feels"
    q.as_of_iso8601 = NOW
    q.trace_id = "claim-storage"
    q.query_id = "basic-" + tenant
    return _core.BasicRetriever(rt.adapter).run(q)


@pytest.mark.parametrize("mutation", [None, "observed_at", "speaker", "turn_id", "delete"])
def test_typed_turn_metadata_is_verified_on_bus_and_retrieval(rig, mutation):
    rt, path = rig
    payload = b'@starling/source-turn-v1 {"speaker":"Mina","text":"I am sad.","observed_at":"2025-05-05T11:04:00","turn_id":"t1"}'
    evidence = _claim(scope="ASSERTED", payload=payload)
    evidence["source_turn"] = {"speaker": "Mina", "session_id": None,
        "turn_id": "t1", "turn_index": None, "observed_at": "2025-05-05T11:04:00"}
    if mutation == "delete":
        del evidence["source_turn"]
    elif mutation:
        evidence["source_turn"][mutation] = "2099-01-01T00:00:00Z" if mutation == "observed_at" else "other"
    _seed(path, claim=evidence, payload=payload, obj="sad")
    stmt = _statement(payload)
    stmt.object_value = "sad"
    stmt.semantic_claim_json = json.dumps(evidence)
    if mutation:
        assert not _basic(rt).rows
        with pytest.raises(ValueError, match="inconsistent_claim"):
            _core.Bus(rt.adapter).write(stmt, "eng-default", "typed-forged")
    else:
        row, = _basic(rt).rows
        assert json.loads(row.semantic_claim_json)["source_turn"] == evidence["source_turn"]
        assert _core.Bus(rt.adapter).write(stmt, "eng-default", "typed-valid")["stmt_id"]


def test_duplicate_source_turn_keys_are_rejected_before_bus_or_readback(rig):
    rt, path = rig
    payload = b'@starling/source-turn-v1 {"speaker":"Mina","text":"I am sad.","observed_at":"2025-05-05T11:04:00"}'
    evidence = _claim(scope="ASSERTED", payload=payload)
    evidence["source_turn"] = {"speaker":"Mina", "session_id":None, "turn_id":None,
                               "turn_index":None, "observed_at":"2025-05-05T11:04:00"}
    raw = json.dumps(evidence).replace('"observed_at": "2025',
        '"observed_at": "2099-01-01T00:00:00Z", "observed_at": "2025')
    _seed(path, claim=raw, payload=payload, obj="sad")
    assert not _basic(rt).rows
    stmt = _statement(payload)
    stmt.object_value = "sad"
    stmt.semantic_claim_json = raw
    with pytest.raises(ValueError, match="malformed_claim"):
        _core.Bus(rt.adapter).write(stmt, "eng-default", "typed-duplicate")


def _plan(rt, tenant="default"):
    q = _core.PlannerQuery()
    q.tenant_id = tenant
    q.querier = q.subject_id = "Mina"
    q.predicate = "feels"
    q.as_of_iso8601 = NOW
    q.trace_id = "claim-storage"
    q.query_id = "planner-" + tenant
    q.intent = _core.QueryIntent.FACT_LOOKUP
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    semantic = _core.SemanticRetriever(rt.adapter, emb, idx)
    return _core.RetrievalPlanner(rt.adapter, semantic).run(q)


def test_migration_old_rows_are_null_and_basic_legacy_is_unchanged(rig):
    rt, path = rig
    _seed(path, claim=None)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT semantic_claim_json FROM statements").fetchone() == (None,)
    row, = _basic(rt).rows
    assert row.semantic_claim_json == ""
    assert _basic(rt).receipt.source_time_fallback_count == 0


def test_null_topic_survives_native_bus_write_and_retrieval(rig):
    rt, path = rig
    _seed(path, claim=None)
    stmt = _statement()
    stmt.semantic_claim_json = json.dumps({**_claim(), "topic": None})
    sid = _core.Bus(rt.adapter).write(stmt, "eng-default", "nullable-topic")["stmt_id"]
    with sqlite3.connect(path) as db:
        db.execute("UPDATE statements SET consolidation_state='consolidated' WHERE id=? AND tenant_id='default'", (sid,))
    result = _basic(rt)
    stored, = [r for r in result.rows if r.id == sid]
    assert json.loads(stored.semantic_claim_json)["topic"] is None
    assert stored.object_value == "sad if leaving"
    assert result.receipt.candidate_counts.dropped_by_claim_evidence == 0
    link, = json.loads(result.receipt.evidence_links_json)
    assert link["source_excerpt"] == SOURCE.decode()


def test_basic_and_planner_retain_exact_evidence_and_tenant_scope(rig):
    rt, path = rig
    _seed(path, tenant="other", payload="Mina: OTHER TENANT SECRET 我很开心。".encode())
    expected = _seed(path)
    for result, rows in [(r := _basic(rt), r.rows), (p := _plan(rt), [e.row for e in p.entries])]:
        row, = rows
        assert row.tenant_id == "default"
        assert json.loads(row.semantic_claim_json) == expected
        link, = json.loads(result.receipt.evidence_links_json)
        assert link["statement_id"] == "same"
        assert link["tenant_id"] == "default"
        assert link["source_span"] == expected["source_span"]
        assert link["source_excerpt"] == SOURCE.decode()
        assert link["source_excerpt_truncated"] is False
        assert "OTHER TENANT SECRET" not in result.receipt.evidence_links_json
        assert link["event_time_status"] == "UNKNOWN"
        assert link["time_basis"] == "source_time_fallback"
        assert result.receipt.source_time_fallback_count == 1
    assert "scope CONDITIONAL" in p.context_pack
    assert "event_time UNKNOWN" in p.context_pack
    assert "source_time_fallback" in p.context_pack
    assert "eng-other" not in p.context_pack
    assert SOURCE.decode() not in p.context_pack
    assert p.context_pack.startswith("[FACT]")


@pytest.mark.parametrize("bad,reason", [
    ("{", "malformed_claim"),
    ('{"schema_version":1,"schema_version":1}', "malformed_claim"),
    ({**_claim(), "scope_markers": ["CONDITIONAL", "ASSERTED"]}, "inconsistent_claim"),
    (_claim(scope="UNSUPPORTED"), "unsupported_claim_scope"),
    ({**_claim(), "actor": "Jules"}, "inconsistent_claim"),
    ({**_claim(), "source_span": {**_claim()["source_span"], "engram_ref": "eng-other"}}, "inconsistent_claim"),
])
def test_invalid_contract_evidence_is_excluded_before_ranking_and_counted(rig, bad, reason):
    rt, path = rig
    _seed(path, tenant="other")
    _seed(path, claim=bad)
    for result, rows in [(r := _basic(rt), r.rows), (p := _plan(rt), [e.row for e in p.entries])]:
        assert rows == []
        assert result.receipt.candidate_counts.dropped_by_claim_evidence == 1
        assert json.loads(result.receipt.claim_exclusion_counts_json) == {reason: 1}
        assert json.loads(result.receipt.evidence_links_json) == []


def test_explicit_event_time_drives_recency_without_source_time_fallback(rig):
    rt, path = rig
    event = {"start": "2020-01-01T00:00:00Z", "end": "2020-01-02T00:00:00Z"}
    payload = b"Mina: From 2020-01-01T00:00:00Z to 2020-01-02T00:00:00Z I felt sad leaving the team."
    evidence = _claim(scope="ASSERTED", event=event, payload=payload)
    evidence["time_text"] = "2020-01-01T00:00:00Z"
    _seed(path, claim=evidence, payload=payload, obj="sad leaving the team from 2020-01-01T00:00:00Z to 2020-01-02T00:00:00Z")
    result = _plan(rt)
    assert result.receipt.source_time_fallback_count == 0
    link, = json.loads(result.receipt.evidence_links_json)
    assert link["time_basis"] == "event_time"
    assert link["event_time"] == event
    assert result.receipt.score_breakdown[0].recency < 0.001


def _statement(payload=SOURCE):
    s = _core.ExtractedStatement()
    assert hasattr(s, "semantic_claim_json"), "native DTO must carry source evidence"
    s.holder_id = s.subject_id = "Mina"
    s.holder_tenant_id = "default"
    s.holder_perspective = _core.Perspective.FIRST_PERSON
    s.subject_kind = "cognizer"
    s.predicate = "feels"
    s.object_kind = "str"
    s.object_value = "sad if leaving"
    s.canonical_object_hash = "writer-hash"
    s.modality = _core.Modality.BELIEVES
    s.polarity = _core.Polarity.POS
    s.confidence = 0.9
    s.observed_at = NOW
    s.source_hash = hashlib.sha256(payload).hexdigest()
    s.provenance = _core.StatementProvenance.USER_INPUT
    s.review_status = _core.ReviewStatus.APPROVED
    return s


def test_native_writer_persists_contract_and_compatibility_span(rig):
    rt, path = rig
    _seed(path, claim=None)
    s = _statement()
    evidence = _claim()
    evidence["source_time"] = "1900-01-01T00:00:00Z"  # writer must use trusted Engram time
    s.semantic_claim_json = json.dumps(evidence)
    sid = _core.Bus(rt.adapter).write(s, "eng-default", "claim-span")["stmt_id"]
    with sqlite3.connect(path) as db:
        claim, spans = db.execute("SELECT semantic_claim_json,source_spans_json FROM statements WHERE id=? AND tenant_id='default'", (sid,)).fetchone()
        assert json.loads(claim)["source_time"] == NOW
        assert json.loads(spans)[0].items() >= _claim()["source_span"].items()
        db.execute("UPDATE statements SET consolidation_state='consolidated' WHERE id=? AND tenant_id='default'", (sid,))
        assert db.execute("SELECT semantic_claim_json FROM statements WHERE id=?", (sid,)).fetchone() == (claim,)
    s.derived_from = [sid]
    s.object_value = "new inferred emotion"
    s.canonical_object_hash = "derived-hash"
    child = _core.Bus(rt.adapter).write(s, "eng-default", "derived-span")["stmt_id"]
    with sqlite3.connect(path) as db:
        inherited, lineage = db.execute("SELECT semantic_claim_json,derived_from_json FROM statements WHERE id=?", (child,)).fetchone()
        assert inherited is None
        assert json.loads(lineage) == [sid]


def test_additive_migration_preserves_preexisting_row_and_hash(tmp_path):
    from pathlib import Path
    path = tmp_path / "v33.db"
    migrations = Path(__file__).resolve().parents[2] / "migrations"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,name TEXT NOT NULL,applied_at TEXT NOT NULL,checksum TEXT NOT NULL)")
        for migration in sorted(migrations.glob("*.sql")):
            version = int(migration.name.split("_", 1)[0])
            if version >= 34:
                continue
            sql = migration.read_text()
            db.executescript(sql)
            db.execute("INSERT INTO schema_migrations VALUES(?,?,?,?)", (version, migration.stem.split("_", 1)[1], NOW, hashlib.sha256(sql.encode()).hexdigest()))
            db.commit()
        db.execute("INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,modality,polarity,confidence,observed_at,salience,affect_json,activation,last_accessed,provenance,created_at,updated_at) VALUES('old','default','Mina','first_person','cognizer','Mina','feels','str','sad','unchanged-hash','BELIEVES','pos',0.9,?,0.5,'{}',0.0,?,'user_input',?,?)", (NOW, NOW, NOW, NOW))
    rt = runtime._build_local_store_sqlite_runtime(path)
    rt.start()
    try:
        with sqlite3.connect(path) as db:
            columns = {r[1] for r in db.execute("PRAGMA table_info(statements)")}
            assert "semantic_claim_json" in columns
            assert db.execute("SELECT object_value,canonical_object_hash,semantic_claim_json FROM statements WHERE id='old'").fetchone() == ("sad", "unchanged-hash", None)
    finally:
        del rt


def test_direct_semantic_exposes_evidence_receipt_even_when_empty(rig):
    rt, _ = rig
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    result = _core.SemanticRetriever(rt.adapter, emb, idx).vector_recall(
        _core.SemanticRetrieverParams(tenant_id="default", holder_id="Mina", query_text="emotion"))
    assert hasattr(result, "receipt"), "direct semantic retrieval needs counted evidence exclusions"
    assert result.receipt.candidate_counts.returned == 0
    assert json.loads(result.receipt.evidence_links_json) == []


def test_direct_semantic_and_pattern_retrieval_exclude_bad_evidence(rig):
    rt, path = rig
    expected = _seed(path, sid="valid")
    _seed(path, sid="bad", claim="{")
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    _core.EmbeddingWorker(rt.adapter, emb, idx).tick_one_batch(NOW)
    semantic = _core.SemanticRetriever(rt.adapter, emb, idx)
    result = semantic.vector_recall(_core.SemanticRetrieverParams(
        tenant_id="default", holder_id="Mina", query_text="Mina feels sad if leaving default"))
    row, = result.rows
    assert json.loads(row.row.semantic_claim_json) == expected
    assert result.receipt.candidate_counts.dropped_by_claim_evidence == 1
    assert json.loads(result.receipt.evidence_links_json)[0]["source_excerpt"] == SOURCE.decode()
    completion = _core.PatternCompletor(rt.adapter, semantic).complete(
        _core.PatternCompletionParams(tenant_id="default", holder_id="Mina", cue_text="Mina feels sad if leaving default"))
    row, = completion.rows
    assert row.row.id == "valid"
    assert completion.receipt.candidate_counts.dropped_by_claim_evidence == 1
    assert json.loads(completion.receipt.evidence_links_json)[0]["source_excerpt"] == SOURCE.decode()


@pytest.mark.parametrize("event,payload", [
    ({"start": "2020-01-01T00:00:00Z", "end": None}, SOURCE),
    ({"start": "2020-02-31T00:00:00Z", "end": None}, b"Mina: From 2020-02-31T00:00:00Z I felt sad."),
])
def test_event_time_must_be_real_and_supported_by_selected_source_unit(rig, event, payload):
    rt, path = rig
    evidence = _claim(event=event, payload=payload)
    _seed(path, claim=evidence, payload=payload)
    for result, rows in [(r := _basic(rt), r.rows), (p := _plan(rt), [e.row for e in p.entries])]:
        assert rows == []
        assert result.receipt.candidate_counts.dropped_by_claim_evidence == 1
        assert json.loads(result.receipt.evidence_links_json) == []
    statement = _statement(payload)
    statement.semantic_claim_json = json.dumps(evidence)
    with pytest.raises(ValueError, match="claim"):
        _core.Bus(rt.adapter).write(statement, "eng-default", "invalid-time")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM statements").fetchone() == (1,)


def test_receipt_excerpt_is_limited_to_selected_utf8_source_unit(rig):
    rt, path = rig
    prefix = "Mina: 同一来源中未选择的秘密。\n".encode()
    selected = "Mina: 如果离开团队，我会难过。".encode()
    payload = prefix + selected
    evidence = _claim(payload=payload)
    evidence["clause_id"] = "c1"
    evidence["source_span"]["span_start"] = len(prefix)
    _seed(path, claim=evidence, payload=payload)
    link, = json.loads(_plan(rt).receipt.evidence_links_json)
    assert link["source_excerpt"] == selected.decode()
    assert "未选择的秘密" not in link["source_excerpt"]
    assert link["source_excerpt_span_start"] == len(prefix)
    assert link["source_excerpt_span_end"] == len(payload)


def test_long_receipt_excerpt_is_bounded_without_splitting_utf8(rig):
    rt, path = rig
    payload = ("Mina: 如果离开团队，我会难过。" + "更多上下文。" * 1000).encode()
    _seed(path, payload=payload)
    link, = json.loads(_plan(rt).receipt.evidence_links_json)
    excerpt = link["source_excerpt"].encode()
    assert len(excerpt) <= 4096
    assert payload.startswith(excerpt)
    assert link["source_excerpt_truncated"] is True
    assert link["source_excerpt_span_end"] == len(excerpt)


def test_contract_duplicate_detection_distinguishes_actor_polarity_and_clause(rig):
    rt, path = rig
    lines = [b"Mina: I feel sad.", b"Mina: I do not feel sad.",
             b"Mina: Jules said she feels sad.", b"Mina: I feel sad."]
    payload = b"\n".join(lines)
    _seed(path, claim=None, payload=payload)
    bus = _core.Bus(rt.adapter)
    offset = 0
    for i, line in enumerate(lines):
        scope = "NEGATED" if i == 1 else ("REPORTED" if i == 2 else "ASSERTED")
        evidence = _claim(scope=scope, payload=payload)
        evidence["clause_id"] = "c" + str(i)
        evidence["source_span"].update(span_start=offset, span_end=offset + len(line))
        statement = _statement(payload)
        statement.object_value = "sad"
        if i == 1:
            statement.polarity = _core.Polarity.NEG
            evidence["relation_polarity"] = "NEG"
        if i == 2:
            statement.subject_id = "Jules"
            statement.holder_perspective = _core.Perspective.QUOTED
            evidence.update(actor="Jules", attributed_to="Mina")
        statement.semantic_claim_json = json.dumps(evidence)
        assert bus.write(statement, "eng-default", "shared-span")["kind"] == "accepted"
        # Bus.write uses the legacy default vocabulary policy. Explicitly
        # approve each fixture, as duplicate detection considers APPROVED rows;
        # the real contract extractor supplies its extra-predicate policy.
        with sqlite3.connect(path) as db:
            db.execute("UPDATE statements SET review_status='approved' WHERE semantic_claim_json IS NOT NULL")
        offset += len(line) + 1
    assert bus.write(statement, "eng-default", "shared-span")["kind"] == "chunk_duplicate"


@pytest.mark.parametrize("bridge_valid", [False, True])
def test_invalid_claim_cannot_bridge_pattern_activation_to_other_rows(rig, bridge_valid):
    rt, path = rig
    _seed(path, sid="seed", obj="seed phrase")
    _seed(path, sid="bridge", claim=True if bridge_valid else "{", obj="bridge phrase")
    _seed(path, sid="downstream", claim=None, obj="downstream only through bridge")
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    _core.EmbeddingWorker(rt.adapter, emb, idx).tick_one_batch(NOW)
    # Pin the only graph route after worker-generated overlap edges exist.
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM statement_edges")
        for edge_id, src, dst in [("first", "seed", "bridge"), ("second", "bridge", "downstream")]:
            db.execute("INSERT INTO statement_edges(id,tenant_id,src_id,dst_id,edge_kind,weight,created_at) VALUES(?,'default',?,?,'derived_from',1.0,?)", (edge_id, src, dst, NOW))
    semantic = _core.SemanticRetriever(rt.adapter, emb, idx)
    completion = _core.PatternCompletor(rt.adapter, semantic).complete(
        _core.PatternCompletionParams(tenant_id="default", holder_id="Mina",
            cue_text="Mina feels seed phrase", seed_k=1))
    expected = {"seed", "bridge", "downstream"} if bridge_valid else {"seed"}
    assert {entry.row.id for entry in completion.rows} == expected
    assert completion.receipt.candidate_counts.dropped_by_claim_evidence == (0 if bridge_valid else 1)
    assert json.loads(completion.receipt.claim_exclusion_counts_json) == ({} if bridge_valid else {"malformed_claim": 1})


@pytest.mark.parametrize("modality", ["BELIEVES", "believes"])
def test_contract_modality_matches_native_and_wire_case_conventions(rig, modality):
    rt, path = rig
    expected = _seed(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE statements SET modality=? WHERE id='same' AND tenant_id='default'", (modality,))
    result = _basic(rt)
    row, = result.rows
    assert json.loads(row.semantic_claim_json) == expected
    assert result.receipt.candidate_counts.dropped_by_claim_evidence == 0


@pytest.mark.parametrize("violation", [
    "emotion_intends", "decision_believes", "negative_uncertainty",
    "negative_without_marker", "conditional_asserted", "nested_direct_claim",
    "object_drops_time",
])
def test_direct_writer_and_persisted_rows_reuse_native_claim_contract(rig, violation):
    rt, path = rig
    payload = SOURCE if violation != "object_drops_time" else b"Mina: Yesterday I felt sad."
    evidence = _claim(payload=payload)
    statement = _statement(payload)
    if violation == "emotion_intends":
        statement.modality = _core.Modality.INTENDS
        evidence["relation_modality"] = "INTENDS"
    elif violation == "decision_believes":
        statement.predicate = "decided_on"
    elif violation == "negative_uncertainty":
        statement.predicate = "uncertain_about"
        statement.polarity = _core.Polarity.NEG
        evidence["relation_polarity"] = "NEG"
        evidence["scope_markers"].append("NEGATED")
    elif violation == "negative_without_marker":
        statement.polarity = _core.Polarity.NEG
        evidence["relation_polarity"] = "NEG"
    elif violation == "conditional_asserted":
        evidence.update(assertion_scope="ASSERTED", scope_markers=["ASSERTED"])
    elif violation == "nested_direct_claim":
        statement.object_kind, statement.object_value = "statement", "same"
    else:
        evidence.update(assertion_scope="ASSERTED", scope_markers=["ASSERTED"], time_text="Yesterday")
    statement.semantic_claim_json = json.dumps(evidence)
    _seed(path, claim=None, payload=payload)
    with pytest.raises(ValueError, match="claim"):
        _core.Bus(rt.adapter).write(statement, "eng-default", "invalid-contract")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM statements").fetchone() == (1,)
        db.execute("UPDATE statements SET predicate=?,modality=?,polarity=?,nesting_depth=?,semantic_claim_json=?",
                   (statement.predicate, evidence["relation_modality"], evidence["relation_polarity"],
                    1 if violation == "nested_direct_claim" else 0, statement.semantic_claim_json))
    query = _core.BasicRetrieverParams()
    query.tenant_id, query.holder_id, query.as_of_iso8601 = "default", "Mina", NOW
    query.subject_id, query.predicate = "Mina", statement.predicate
    basic = _core.BasicRetriever(rt.adapter).run(query)
    assert list(basic.rows) == []
    assert basic.receipt.candidate_counts.dropped_by_claim_evidence == 1
    query = _core.PlannerQuery()
    query.tenant_id, query.querier, query.as_of_iso8601 = "default", "Mina", NOW
    query.query_id = "invalid-contract-" + violation
    query.intent = _core.QueryIntent.FACT_LOOKUP
    query.subject_id, query.predicate = "Mina", statement.predicate
    emb, idx = _core.StubEmbeddingAdapter(8), _core.SqliteBlobVectorIndex()
    semantic = _core.SemanticRetriever(rt.adapter, emb, idx)
    planned = _core.RetrievalPlanner(rt.adapter, semantic).run(query)
    assert list(planned.entries) == []
    assert planned.receipt.candidate_counts.dropped_by_claim_evidence == 1


@pytest.mark.parametrize("obj,valid", [
    ("prefer the window seat", False),
    ("偏好靠窗座位", False),
    ("sad about preferring the window seat", True),
    ("对偏好变化感到焦虑", True),
    ("偏好被否定让我很难过", True),
    ("preferred seat being taken makes me sad", True),
    ("have preferred the window seat", False),
    ("倾向于靠窗座位", False),
])
def test_preference_emotion_boundary_is_shared_by_bus_and_readback(rig, obj, valid):
    rt, path = rig
    payload = ("Mina: " + obj + ".").encode()
    evidence = _claim(scope="ASSERTED", payload=payload)
    _seed(path, claim=evidence, payload=payload, obj=obj)
    statement = _statement(payload)
    statement.object_value = obj
    statement.semantic_claim_json = json.dumps(evidence)
    basic = _basic(rt)
    if valid:
        row, = basic.rows
        assert row.object_value == obj
        assert _core.Bus(rt.adapter).write(statement, "eng-default", "valid-emotion")["stmt_id"]
    else:
        assert not basic.rows
        assert basic.receipt.candidate_counts.dropped_by_claim_evidence == 1
        with pytest.raises(ValueError, match="inconsistent_claim"):
            _core.Bus(rt.adapter).write(statement, "eng-default", "invalid-preference")
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT COUNT(*) FROM statements").fetchone() == (1,)


@pytest.mark.parametrize("mutation", [None, "question", "actor", "clause", "hash", "erased", "tenant"])
def test_leading_scope_uses_same_native_rule_on_bus_and_retrieval(rig, mutation):
    rt, path = rig
    payload = b"Mina: I am relieved about the rehearsal. Can you bring the chairs?"
    obj = "relieved about the rehearsal"
    evidence = _claim(scope="ASSERTED", payload=payload)
    if mutation == "question":
        payload = payload.replace(b"rehearsal.", b"rehearsal?")
        evidence = _claim(scope="ASSERTED", payload=payload)
    elif mutation == "actor":
        evidence["actor"] = "Other"
    elif mutation == "clause":
        evidence["clause_id"] = "c88"
    elif mutation == "hash":
        evidence["source_span"]["source_hash"] = "0" * 64
    _seed(path, claim=evidence, payload=payload, obj=obj)
    if mutation == "erased":
        with sqlite3.connect(path) as db:
            db.execute("UPDATE engrams SET erased_at=? WHERE id='eng-default'", (NOW,))
    stmt = _statement(payload)
    stmt.object_value = obj
    stmt.semantic_claim_json = json.dumps(evidence)
    if mutation == "tenant":
        assert not _basic(rt, "other").rows
        stmt.holder_tenant_id = "other"
    if mutation:
        if mutation != "tenant":
            assert not _basic(rt).rows
        with pytest.raises((ValueError, RuntimeError)):
            _core.Bus(rt.adapter).write(stmt, "eng-default", "localized-forged")
    else:
        stored, = _basic(rt).rows
        assert stored.object_value == obj
        sid = _core.Bus(rt.adapter).write(stmt, "eng-default", "localized-valid")["stmt_id"]
        assert sid
        link, = json.loads(_basic(rt).receipt.evidence_links_json)
        assert link["source_excerpt"] == payload.decode()
