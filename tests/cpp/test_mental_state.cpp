#include "starling/tom/mentalizing.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
#include <memory>
#include <string>

namespace {
std::unique_ptr<starling::persistence::SqliteAdapter> open_migrated() {
    auto a = starling::persistence::SqliteAdapter::open(":memory:");
    starling::persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}
void seed_stmt(starling::persistence::SqliteAdapter& a, const char* tenant, const char* id,
               const char* holder, const char* subject_kind, const char* subject,
               const char* predicate, const char* object, const char* modality,
               const char* observed_at) {
    const std::string sql =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,evidence_json,consolidation_state,review_status,"
        "nesting_depth,created_at,updated_at) VALUES('" + std::string(id) +
        "','" + tenant + "','" + holder + "','FIRST_PERSON','" + subject_kind + "','" + subject +
        "','" + predicate + "','entity','" + object + "','h-" + std::string(id) +
        "','v1','" + modality + "','POS',0.9,'" + observed_at +
        "',0.5,'{}',0.0,'" + observed_at +
        "','user_input','[]','consolidated','approved',0,'" + observed_at + "','" + observed_at + "')";
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(a.connection().raw(), sql.c_str(), nullptr, nullptr, &err), SQLITE_OK)
        << (err ? err : "");
}

// Seed a row with an explicit valid_from (for as_of window testing).
void seed_stmt_with_valid_from(starling::persistence::SqliteAdapter& a, const char* tenant,
                               const char* id, const char* holder, const char* predicate,
                               const char* modality, const char* valid_from) {
    const std::string sql =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,evidence_json,consolidation_state,review_status,"
        "nesting_depth,valid_from,created_at,updated_at) VALUES('" + std::string(id) +
        "','" + tenant + "','" + holder + "','FIRST_PERSON','entity','thing','" +
        predicate + "','entity','value','h-" + std::string(id) +
        "','v1','" + modality + "','POS',0.9,'" + valid_from +
        "',0.5,'{}',0.0,'" + valid_from +
        "','user_input','[]','consolidated','approved',0,'" + valid_from +
        "','" + valid_from + "','" + valid_from + "')";
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(a.connection().raw(), sql.c_str(), nullptr, nullptr, &err), SQLITE_OK)
        << (err ? err : "");
}
}  // namespace

using starling::tom::mentalizing::mental_state_of;

TEST(MentalState, BucketsByAttitude) {
    auto a = open_migrated();
    const char* T = "tm";
    const char* AS = "2026-01-02T00:00:00Z";
    // Stored modality casing confirmed lowercase (Step 1): believes/desires/intends/commits/occurred.
    seed_stmt(*a, T, "s1", "Alice", "entity", "ball",    "located_at",     "box",      "believes", "2026-01-01T00:00:01Z");
    seed_stmt(*a, T, "s2", "Alice", "entity", "keys",    "knows",          "drawer",   "believes", "2026-01-01T00:00:02Z");
    seed_stmt(*a, T, "s3", "Alice", "entity", "weekend", "prefers",        "outdoors", "believes", "2026-01-01T00:00:03Z");
    seed_stmt(*a, T, "s4", "Alice", "entity", "hiking",  "located_at",     "trail",    "desires",  "2026-01-01T00:00:04Z");
    seed_stmt(*a, T, "s5", "Alice", "entity", "report",  "responsible_for","report",   "intends",  "2026-01-01T00:00:05Z");
    seed_stmt(*a, T, "s6", "Alice", "entity", "deck",    "promises",       "friday",   "commits",  "2026-01-01T00:00:06Z");
    seed_stmt(*a, T, "s7", "Bob",   "entity", "ball",    "located_at",     "basket",   "believes", "2026-01-01T00:00:07Z"); // other holder
    seed_stmt(*a, T, "s8", "Alice", "entity", "door",    "located_at",     "shut",     "occurred", "2026-01-01T00:00:08Z"); // dropped

    auto ms = mental_state_of(*a, "Alice", T, AS);
    EXPECT_EQ(ms.beliefs.size(), 1u);      // s1 (modality believes, predicate not knows/prefers)
    EXPECT_EQ(ms.knowledge.size(), 1u);    // s2 (predicate=knows, predicate-first)
    EXPECT_EQ(ms.preferences.size(), 1u);  // s3 (predicate=prefers, predicate-first over modality)
    EXPECT_EQ(ms.desires.size(), 1u);      // s4 (modality=desires, predicate=located_at)
    EXPECT_EQ(ms.intentions.size(), 1u);   // s5 (modality=intends)
    EXPECT_EQ(ms.commitments.size(), 1u);  // s6 (modality=commits)
    for (auto* b : {&ms.beliefs, &ms.knowledge, &ms.preferences, &ms.desires, &ms.intentions, &ms.commitments})
        for (auto& r : *b) EXPECT_EQ(r.holder_id, "Alice"); // Bob/occurred excluded
}

TEST(MentalState, UnknownCognizerEmpty) {
    auto a = open_migrated();
    auto ms = mental_state_of(*a, "Nobody", "tm", "2026-01-02T00:00:00Z");
    EXPECT_TRUE(ms.beliefs.empty() && ms.knowledge.empty() && ms.desires.empty() &&
                ms.intentions.empty() && ms.commitments.empty() && ms.preferences.empty());
}

TEST(MentalState, AsOfBound) {
    // as_of is applied via valid_from (NULL=always visible, set=visible from that date).
    // Seed a row with valid_from=2026-01-05 so it's invisible before that date.
    auto a = open_migrated();
    const char* T = "tb";
    seed_stmt_with_valid_from(*a, T, "e1", "Alice", "located_at", "believes", "2026-01-05T00:00:00Z");
    auto before = mental_state_of(*a, "Alice", T, "2026-01-01T00:00:00Z");
    EXPECT_TRUE(before.beliefs.empty()) << "statement with valid_from after as_of must be excluded";
    auto after = mental_state_of(*a, "Alice", T, "2026-01-06T00:00:00Z");
    EXPECT_EQ(after.beliefs.size(), 1u);
}
