// test_persona_container.cpp — PersonaContainer::rebuild tests.
//
// TC-PC-001  SelfAnchorWinsOverProfile
// TC-PC-002  DivergenceMarksSuspected
// TC-PC-003  ProfileUsedWhenNoSelf
// TC-PC-004  CASIncrementsVersion
// TC-PC-005  CASMismatchThrows

#include "starling/neocortex/persona_container.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>
#include <vector>

using namespace starling::neocortex;
using starling::persistence::SqliteAdapter;

namespace {

// Open fresh in-memory DB with all migrations applied.
std::unique_ptr<SqliteAdapter> open_fresh() {
    return SqliteAdapter::open(":memory:");
}

// Read a single text column from a query.
std::string scol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    const auto* txt = sqlite3_column_text(s, 0);
    std::string v = txt ? reinterpret_cast<const char*>(txt) : "";
    sqlite3_finalize(s);
    return v;
}

// Read a single int column from a query.
int icol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    int v = sqlite3_column_int(s, 0);
    sqlite3_finalize(s);
    return v;
}

}  // namespace

// ── TC-PC-001: SelfAnchorWinsOverProfile ────────────────────────────────────

TEST(PersonaContainer, SelfAnchorWinsOverProfile) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    PersonaContainer pc(*adapter);

    std::vector<AnchorStatement> sources = {
        {"s1", "self_model_anchor", "traits", "calm",    0.9},
        {"s2", "profile_anchor",    "traits", "anxious", 0.5},
    };

    pc.rebuild(conn, "default", "holder-1", sources);

    // content_json should contain "calm" (self wins) and NOT "anxious" as chosen value.
    std::string cj = scol(conn.raw(),
        "SELECT content_json FROM containers WHERE holder_id='holder-1' AND kind='persona'");
    EXPECT_FALSE(cj.empty());
    EXPECT_NE(cj.find("\"calm\""), std::string::npos)
        << "Expected 'calm' (self anchor) in content_json: " << cj;
    // "anxious" must not appear as the dimension's value — it's absent from content_json
    // (profile anchor value is not stored when self wins).
    EXPECT_EQ(cj.find("\"anxious\""), std::string::npos)
        << "Did not expect 'anxious' (profile anchor) in content_json: " << cj;
}

// ── TC-PC-002: DivergenceMarksSuspected ─────────────────────────────────────

TEST(PersonaContainer, DivergenceMarksSuspected) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    PersonaContainer pc(*adapter);

    // self conf=0.9, profile conf=0.2 → diff 0.7 >= 0.5 and values differ → diverge
    std::vector<AnchorStatement> sources = {
        {"s1", "self_model_anchor", "mood", "X", 0.9},
        {"s2", "profile_anchor",    "mood", "Y", 0.2},
    };

    pc.rebuild(conn, "default", "holder-div", sources);

    std::string cj = scol(conn.raw(),
        "SELECT content_json FROM containers WHERE holder_id='holder-div' AND kind='persona'");
    EXPECT_FALSE(cj.empty());
    // Dimension should be marked suspected_diverge:true
    EXPECT_NE(cj.find("\"suspected_diverge\":true"), std::string::npos)
        << "Expected suspected_diverge:true in content_json: " << cj;

    // A persona.suspected_diverge bus event should have been emitted.
    int event_count = icol(conn.raw(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='persona.suspected_diverge'");
    EXPECT_GE(event_count, 1)
        << "Expected persona.suspected_diverge event in bus_events";

    // The event payload should reference the dimension.
    std::string payload = scol(conn.raw(),
        "SELECT payload_json FROM bus_events WHERE event_type='persona.suspected_diverge' LIMIT 1");
    EXPECT_NE(payload.find("mood"), std::string::npos)
        << "Expected dimension 'mood' in event payload: " << payload;
}

// ── TC-PC-003: ProfileUsedWhenNoSelf ────────────────────────────────────────

TEST(PersonaContainer, ProfileUsedWhenNoSelf) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    PersonaContainer pc(*adapter);

    std::vector<AnchorStatement> sources = {
        {"s1", "profile_anchor", "preferences", "tea", 0.7},
    };

    pc.rebuild(conn, "default", "holder-prof", sources);

    std::string cj = scol(conn.raw(),
        "SELECT content_json FROM containers WHERE holder_id='holder-prof' AND kind='persona'");
    EXPECT_FALSE(cj.empty());
    EXPECT_NE(cj.find("\"tea\""), std::string::npos)
        << "Expected 'tea' (profile anchor value) in content_json: " << cj;
}

// ── TC-PC-004: CASIncrementsVersion ─────────────────────────────────────────

TEST(PersonaContainer, CASIncrementsVersion) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    PersonaContainer pc(*adapter);

    std::vector<AnchorStatement> sources = {
        {"s1", "self_model_anchor", "traits", "brave", 0.8},
    };

    // First rebuild → version 1
    pc.rebuild(conn, "default", "holder-cas", sources);
    int v1 = icol(conn.raw(),
        "SELECT version FROM containers WHERE holder_id='holder-cas' AND kind='persona'");
    EXPECT_EQ(v1, 1);

    // Second rebuild → version 2
    pc.rebuild(conn, "default", "holder-cas", sources);
    int v2 = icol(conn.raw(),
        "SELECT version FROM containers WHERE holder_id='holder-cas' AND kind='persona'");
    EXPECT_EQ(v2, 2);
}

// ── TC-PC-005: CASMismatchThrows ────────────────────────────────────────────

TEST(PersonaContainer, CASMismatchThrows) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    PersonaContainer pc(*adapter);

    std::vector<AnchorStatement> sources = {
        {"s1", "self_model_anchor", "traits", "curious", 0.6},
    };

    // First rebuild succeeds → version 1.
    pc.rebuild(conn, "default", "holder-mismatch", sources);

    // Simulate a concurrent write by bumping version directly.
    sqlite3_exec(conn.raw(),
        "UPDATE containers SET version=version+1 "
        "WHERE holder_id='holder-mismatch' AND kind='persona'",
        nullptr, nullptr, nullptr);

    // Second rebuild should see version mismatch and throw ConcurrentRebuildError.
    EXPECT_THROW(
        pc.rebuild(conn, "default", "holder-mismatch", sources),
        ConcurrentRebuildError);
}
