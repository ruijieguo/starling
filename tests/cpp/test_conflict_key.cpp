#include "starling/bus/conflict_key.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/schema/statement_enums.hpp"

#include <gtest/gtest.h>
#include <iostream>

namespace {
using namespace starling;
using namespace starling::bus;

extractor::ExtractedStatement make_parity_stmt() {
    extractor::ExtractedStatement s;
    s.holder_id             = "holder-uuid-parity";
    s.holder_tenant_id      = "tenant-parity";
    s.subject_kind          = "entity";
    s.subject_id            = "entity-uuid-parity";
    s.predicate             = "responsible_for";
    s.object_kind           = "str";
    s.object_value          = "auth";
    s.canonical_object_hash = "aaaa1111bbbb2222cccc3333dddd4444eeee5555ffff6666aaaa1111bbbb2222";
    s.modality              = schema::Modality::BELIEVES;
    s.polarity              = schema::Polarity::POS;
    s.confidence            = 0.9;
    s.observed_at           = "2026-01-01T00:00:00Z";
    return s;
}

TEST(ConflictKey, ParityFixtureHex) {
    auto stmt = make_parity_stmt();
    auto hex = canonical_conflict_key_hex(stmt);
    std::cout << "PARITY_HEX=" << hex << std::endl;
    EXPECT_EQ(hex.size(), 64u);
    EXPECT_EQ(hex, "128e262474462a27c39126dbfc4c3876cac63f6d11f53a0161a8b6c8b66f8790");
}

TEST(ConflictKey, DifferentHolderProducesDifferentKey) {
    auto s1 = make_parity_stmt();
    auto s2 = make_parity_stmt();
    s2.holder_id = "different-holder";
    EXPECT_NE(canonical_conflict_key_hex(s1), canonical_conflict_key_hex(s2));
}

TEST(ConflictKey, DifferentModalityProducesDifferentKey) {
    auto s1 = make_parity_stmt();
    auto s2 = make_parity_stmt();
    s2.modality = schema::Modality::KNOWS;
    EXPECT_NE(canonical_conflict_key_hex(s1), canonical_conflict_key_hex(s2));
}

TEST(ConflictKey, DifferentObjectHashProducesDifferentKey) {
    auto s1 = make_parity_stmt();
    auto s2 = make_parity_stmt();
    s2.canonical_object_hash = "0000000000000000000000000000000000000000000000000000000000000000";
    EXPECT_NE(canonical_conflict_key_hex(s1), canonical_conflict_key_hex(s2));
}

TEST(ConflictKey, SameInputProducesSameKey) {
    auto s1 = make_parity_stmt();
    auto s2 = make_parity_stmt();
    EXPECT_EQ(canonical_conflict_key_hex(s1), canonical_conflict_key_hex(s2));
}

TEST(ConflictKey, IntervalParticipatesInKey) {
    auto s1 = make_parity_stmt();
    auto s2 = make_parity_stmt();
    s2.valid_from = "2026-01-01T00:00:00Z";
    EXPECT_NE(canonical_conflict_key_hex(s1), canonical_conflict_key_hex(s2));
}

}  // namespace
