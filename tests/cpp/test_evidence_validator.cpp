#include <gtest/gtest.h>
#include <sqlite3.h>

#include "starling/evidence/evidence_validator.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <variant>

using starling::evidence::EngramInput;
using starling::evidence::EvidenceValidator;
using starling::evidence::SourceIdentity;
using starling::evidence::ValidationIdempotentHit;
using starling::evidence::ValidationNoStore;
using starling::evidence::ValidationProceed;
using starling::evidence::ValidationReject;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;
using starling::schema::EngramRetentionMode;
using starling::schema::IngestMode;
using starling::schema::IngestPolicy;
using starling::schema::PrivacyClass;
using starling::schema::SourceKind;

namespace {

EngramInput valid_user_input() {
    EngramInput inp;
    inp.tenant_id = "t1";
    inp.source.adapter_name = "direct_api";
    inp.source.adapter_version = "1.0.0";
    inp.source.source_item_id = "msg-1";
    inp.source.source_version = "1";
    inp.source.chunk_index = 0;
    inp.source_kind = SourceKind::USER_INPUT;
    inp.ingest_mode = IngestMode::WHOLE_RECORD;
    inp.privacy_class = PrivacyClass::INTERNAL;
    inp.retention_mode = EngramRetentionMode::AUDIT_RETAIN;
    inp.declared_transformations = {};
    inp.byte_preserving = true;
    inp.payload_bytes = {'h','i'};
    inp.redacted_content = std::nullopt;
    inp.created_at_iso8601 = "2026-05-23T10:00:00Z";
    return inp;
}

Connection migrated_db() {
    auto c = Connection::open(":memory:");
    MigrationRunner(c.raw()).migrate_to_latest();
    return c;
}

void run_sql(Connection& c, const char* sql) {
    char* err = nullptr;
    if (sqlite3_exec(c.raw(), sql, nullptr, nullptr, &err) != SQLITE_OK) {
        const std::string msg = err ? err : "(null)";
        sqlite3_free(err);
        FAIL() << "sqlite3_exec failed: " << sql << " - " << msg;
    }
}

}  // namespace

TEST(EvidenceValidator, ValidUserInputProceedsAsStore) {
    auto c = migrated_db();
    auto out = EvidenceValidator::validate(valid_user_input(), c);
    auto* p = std::get_if<ValidationProceed>(&out);
    ASSERT_NE(p, nullptr);
    EXPECT_EQ(p->resolved_policy, IngestPolicy::STORE);
}

TEST(EvidenceValidator, SystemInternalShortCircuitsToNoStore) {
    auto c = migrated_db();
    auto inp = valid_user_input();
    inp.source_kind = SourceKind::SYSTEM_INTERNAL;
    auto out = EvidenceValidator::validate(inp, c);
    EXPECT_NE(std::get_if<ValidationNoStore>(&out), nullptr);
}

TEST(EvidenceValidator, BytePreservingWithTransformationsRejects) {
    auto c = migrated_db();
    auto inp = valid_user_input();
    inp.byte_preserving = true;
    inp.declared_transformations = {"nfc"};
    auto out = EvidenceValidator::validate(inp, c);
    auto* r = std::get_if<ValidationReject>(&out);
    ASSERT_NE(r, nullptr);
    EXPECT_EQ(r->reason, "byte_preserving_requires_empty_transformations");
}

TEST(EvidenceValidator, DuplicateTransformationsReject) {
    auto c = migrated_db();
    auto inp = valid_user_input();
    inp.byte_preserving = false;
    inp.declared_transformations = {"nfc", "trim", "nfc"};
    auto out = EvidenceValidator::validate(inp, c);
    auto* r = std::get_if<ValidationReject>(&out);
    ASSERT_NE(r, nullptr);
    EXPECT_EQ(r->reason, "transformations_must_be_unique");
}

TEST(EvidenceValidator, MissingTenantIdRejects) {
    auto c = migrated_db();
    auto inp = valid_user_input();
    inp.tenant_id = "";
    auto out = EvidenceValidator::validate(inp, c);
    auto* r = std::get_if<ValidationReject>(&out);
    ASSERT_NE(r, nullptr);
    EXPECT_EQ(r->reason, "required_field_missing:tenant_id");
}

TEST(EvidenceValidator, MissingAdapterNameRejects) {
    auto c = migrated_db();
    auto inp = valid_user_input();
    inp.source.adapter_name = "";
    auto out = EvidenceValidator::validate(inp, c);
    auto* r = std::get_if<ValidationReject>(&out);
    ASSERT_NE(r, nullptr);
    EXPECT_EQ(r->reason, "required_field_missing:adapter_name");
}

TEST(EvidenceValidator, MissingSourceItemIdRejects) {
    auto c = migrated_db();
    auto inp = valid_user_input();
    inp.source.source_item_id = "";
    auto out = EvidenceValidator::validate(inp, c);
    auto* r = std::get_if<ValidationReject>(&out);
    ASSERT_NE(r, nullptr);
    EXPECT_EQ(r->reason, "required_field_missing:source_item_id");
}

TEST(EvidenceValidator, MissingSourceVersionRejects) {
    auto c = migrated_db();
    auto inp = valid_user_input();
    inp.source.source_version = "";
    auto out = EvidenceValidator::validate(inp, c);
    auto* r = std::get_if<ValidationReject>(&out);
    ASSERT_NE(r, nullptr);
    EXPECT_EQ(r->reason, "required_field_missing:source_version");
}

TEST(EvidenceValidator, BadCreatedAtRejects) {
    auto c = migrated_db();
    auto inp = valid_user_input();
    inp.created_at_iso8601 = "yesterday";
    auto out = EvidenceValidator::validate(inp, c);
    auto* r = std::get_if<ValidationReject>(&out);
    ASSERT_NE(r, nullptr);
    EXPECT_EQ(r->reason, "created_at_not_iso8601");
}

TEST(EvidenceValidator, RegulatedUserInputDowngradesToRequireReview) {
    auto c = migrated_db();
    auto inp = valid_user_input();
    inp.privacy_class = PrivacyClass::REGULATED;
    auto out = EvidenceValidator::validate(inp, c);
    auto* p = std::get_if<ValidationProceed>(&out);
    ASSERT_NE(p, nullptr);
    EXPECT_EQ(p->resolved_policy, IngestPolicy::REQUIRE_REVIEW);
}

TEST(EvidenceValidator, IdempotentHitReturnsExistingRow) {
    auto c = migrated_db();
    // Insert a row directly that matches valid_user_input's identity tuple.
    run_sql(c,
        "INSERT INTO engrams("
        "  id, tenant_id, content_hash, source_kind, ingest_policy, ingest_mode,"
        "  privacy_class, retention_mode, created_at,"
        "  adapter_name, adapter_version, source_item_id, source_version, chunk_index,"
        "  declared_transformations_json, byte_preserving"
        ") VALUES ("
        "  'pre-existing-id', 't1', 'deadbeef', 'user_input', 'store', 'whole_record',"
        "  'internal', 'audit_retain', '2026-05-23T09:00:00Z',"
        "  'direct_api', '1.0.0', 'msg-1', '1', 0,"
        "  '[]', 1"
        ");");

    auto out = EvidenceValidator::validate(valid_user_input(), c);
    auto* hit = std::get_if<ValidationIdempotentHit>(&out);
    ASSERT_NE(hit, nullptr);
    EXPECT_EQ(hit->existing.id, "pre-existing-id");
    EXPECT_EQ(hit->existing.content_hash, "deadbeef");
    EXPECT_EQ(hit->existing.tenant_id, "t1");
    EXPECT_EQ(hit->existing.source.adapter_name, "direct_api");
    EXPECT_EQ(hit->existing.source.chunk_index, 0);
    EXPECT_EQ(hit->existing.source_kind, SourceKind::USER_INPUT);
    EXPECT_EQ(hit->existing.ingest_policy, IngestPolicy::STORE);
    EXPECT_EQ(hit->existing.retention_mode, EngramRetentionMode::AUDIT_RETAIN);
}

TEST(EvidenceValidator, IdempotentLookupRespectsTenantIsolation) {
    auto c = migrated_db();
    // Same source identity tuple under tenant t2 - must NOT match a t1 query.
    run_sql(c,
        "INSERT INTO engrams("
        "  id, tenant_id, content_hash, source_kind, ingest_policy, ingest_mode,"
        "  privacy_class, retention_mode, created_at,"
        "  adapter_name, adapter_version, source_item_id, source_version, chunk_index,"
        "  declared_transformations_json, byte_preserving"
        ") VALUES ("
        "  'other-tenant', 't2', 'deadbeef', 'user_input', 'store', 'whole_record',"
        "  'internal', 'audit_retain', '2026-05-23T09:00:00Z',"
        "  'direct_api', '1.0.0', 'msg-1', '1', 0,"
        "  '[]', 1"
        ");");

    auto out = EvidenceValidator::validate(valid_user_input(), c);
    EXPECT_NE(std::get_if<ValidationProceed>(&out), nullptr);
}

TEST(EvidenceValidator, NoStoreShortCircuitDoesNotQueryEngrams) {
    // If the validator short-circuits on NO_STORE, an unrelated row must not
    // affect the outcome. Insert a row that would match by source-identity,
    // then assert NO_STORE wins.
    auto c = migrated_db();
    run_sql(c,
        "INSERT INTO engrams("
        "  id, tenant_id, content_hash, source_kind, ingest_policy, ingest_mode,"
        "  privacy_class, retention_mode, created_at,"
        "  adapter_name, adapter_version, source_item_id, source_version, chunk_index,"
        "  declared_transformations_json, byte_preserving"
        ") VALUES ("
        "  'x', 't1', 'h', 'user_input', 'store', 'whole_record',"
        "  'internal', 'audit_retain', '2026-05-23T09:00:00Z',"
        "  'direct_api', '1.0.0', 'msg-1', '1', 0,"
        "  '[]', 1"
        ");");
    auto inp = valid_user_input();
    inp.source_kind = SourceKind::REPLAY_OUTPUT;
    auto out = EvidenceValidator::validate(inp, c);
    EXPECT_NE(std::get_if<ValidationNoStore>(&out), nullptr);
}
