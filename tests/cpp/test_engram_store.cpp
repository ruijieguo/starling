#include <gtest/gtest.h>
#include <sqlite3.h>

#include "starling/evidence/engram_store.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"

#include <cstdint>
#include <stdexcept>
#include <vector>

using starling::evidence::Engram;
using starling::evidence::EngramInput;
using starling::evidence::EngramStore;
using starling::evidence::SourceIdentity;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;
using starling::schema::EngramRetentionMode;
using starling::schema::IngestMode;
using starling::schema::IngestPolicy;
using starling::schema::PrivacyClass;
using starling::schema::SourceKind;

namespace {

Connection migrated_db() {
    auto c = Connection::open(":memory:");
    MigrationRunner(c.raw()).migrate_to_latest();
    return c;
}

EngramInput sample_input() {
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
    inp.payload_bytes = {'h','e','l','l','o'};
    inp.redacted_content = std::nullopt;
    inp.created_at_iso8601 = "2026-05-23T10:00:00Z";
    return inp;
}

}  // namespace

TEST(EngramStore, PutAssignsUuidAndContentHash) {
    auto c = migrated_db();
    auto e = EngramStore::put(sample_input(), IngestPolicy::STORE, c);
    EXPECT_FALSE(e.id.empty());
    EXPECT_EQ(e.id.size(), 36u);  // UUID 8-4-4-4-12 hex chars with dashes
    EXPECT_EQ(e.content_hash.size(), 64u);  // sha256 hex
    EXPECT_EQ(e.ingest_policy, IngestPolicy::STORE);
    EXPECT_EQ(e.refcount, 0);
}

TEST(EngramStore, PutPersistsRowVisibleViaGet) {
    auto c = migrated_db();
    auto written = EngramStore::put(sample_input(), IngestPolicy::STORE, c);
    auto fetched = EngramStore::get(written.id, "t1", c);
    ASSERT_TRUE(fetched.has_value());
    EXPECT_EQ(fetched->id, written.id);
    EXPECT_EQ(fetched->content_hash, written.content_hash);
    EXPECT_EQ(fetched->source.adapter_name, "direct_api");
    EXPECT_EQ(fetched->source.adapter_version, "1.0.0");
    EXPECT_EQ(fetched->source.source_item_id, "msg-1");
    EXPECT_EQ(fetched->source.source_version, "1");
    EXPECT_EQ(fetched->source.chunk_index, 0);
    EXPECT_EQ(fetched->ingest_policy, IngestPolicy::STORE);
    EXPECT_EQ(fetched->ingest_mode, IngestMode::WHOLE_RECORD);
    EXPECT_EQ(fetched->privacy_class, PrivacyClass::INTERNAL);
    EXPECT_EQ(fetched->retention_mode, EngramRetentionMode::AUDIT_RETAIN);
    EXPECT_TRUE(fetched->byte_preserving);
    // payload_inline round-trips raw bytes (null_kms is identity in P1).
    EXPECT_EQ(fetched->content_ciphertext,
              (std::vector<std::uint8_t>{'h','e','l','l','o'}));
}

TEST(EngramStore, GetReturnsNulloptForWrongTenant) {
    auto c = migrated_db();
    auto written = EngramStore::put(sample_input(), IngestPolicy::STORE, c);
    auto fetched = EngramStore::get(written.id, "t2", c);
    EXPECT_FALSE(fetched.has_value());
}

TEST(EngramStore, GetReturnsNulloptForUnknownId) {
    auto c = migrated_db();
    EngramStore::put(sample_input(), IngestPolicy::STORE, c);
    auto fetched = EngramStore::get("nonexistent-id", "t1", c);
    EXPECT_FALSE(fetched.has_value());
}

TEST(EngramStore, PutRejectsDuplicateSourceIdentity) {
    auto c = migrated_db();
    EngramStore::put(sample_input(), IngestPolicy::STORE, c);
    // Second put with identical source identity hits the UNIQUE index from
    // migration 0003. EngramStore::put doesn't pre-check (that's the
    // EvidenceValidator's job in production), so a direct second call throws.
    EXPECT_THROW(
        EngramStore::put(sample_input(), IngestPolicy::STORE, c),
        std::exception);
}

TEST(EngramStore, PutThrowsOnNoStorePolicy) {
    auto c = migrated_db();
    EXPECT_THROW(
        EngramStore::put(sample_input(), IngestPolicy::NO_STORE, c),
        std::invalid_argument);
}

TEST(EngramStore, ContentHashMatchesCanonicalizerOutput) {
    auto c = migrated_db();
    auto inp = sample_input();
    inp.declared_transformations = {"nfc"};
    inp.byte_preserving = false;
    auto e = EngramStore::put(inp, IngestPolicy::STORE, c);
    // Pinned digest from Task 3: sha256_hex("v1\x1fhello\x1fnfc")
    EXPECT_EQ(e.content_hash,
              "17437ac920346fce85efc803a1851dd28867e088be65ef912866eccee6a3df31");
}

TEST(EngramStore, RedactedContentRoundTrips) {
    auto c = migrated_db();
    auto inp = sample_input();
    inp.retention_mode = EngramRetentionMode::REDACTED_RETAIN;
    inp.redacted_content = "[redacted-pii]";
    auto written = EngramStore::put(inp, IngestPolicy::STORE, c);
    auto fetched = EngramStore::get(written.id, "t1", c);
    ASSERT_TRUE(fetched.has_value());
    ASSERT_TRUE(fetched->redacted_content.has_value());
    EXPECT_EQ(*fetched->redacted_content, "[redacted-pii]");
    EXPECT_EQ(fetched->retention_mode, EngramRetentionMode::REDACTED_RETAIN);
}

TEST(EngramStore, BinaryPayloadWithNullsRoundTrips) {
    auto c = migrated_db();
    auto inp = sample_input();
    inp.source.source_item_id = "binary-1";
    inp.payload_bytes = {0x00, 0x01, 0x00, 0xff, 0x00, 0x42};
    auto written = EngramStore::put(inp, IngestPolicy::STORE, c);
    auto fetched = EngramStore::get(written.id, "t1", c);
    ASSERT_TRUE(fetched.has_value());
    EXPECT_EQ(fetched->content_ciphertext,
              (std::vector<std::uint8_t>{0x00, 0x01, 0x00, 0xff, 0x00, 0x42}));
}
