#include <gtest/gtest.h>

#include "starling/extractor/extraction_span_key.hpp"

namespace starling::extractor {

TEST(ExtractionSpanKey, DeterministicForFixedInputs) {
    const std::string k1 = compute_extraction_span_key(
        /*engram_ref_id=*/"engram-aaa",
        /*chunk_index=*/0,
        /*predicate=*/"responsible_for",
        /*canonical_object_hash=*/"deadbeef");
    const std::string k2 = compute_extraction_span_key(
        "engram-aaa", 0, "responsible_for", "deadbeef");
    EXPECT_EQ(k1, k2);
    EXPECT_EQ(k1.size(), 64u);
    for (char c : k1) {
        EXPECT_TRUE((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'));
    }
}

TEST(ExtractionSpanKey, ChunkIndexVariesKey) {
    const std::string k0 = compute_extraction_span_key(
        "engram-x", 0, "p", "h");
    const std::string k1 = compute_extraction_span_key(
        "engram-x", 1, "p", "h");
    EXPECT_NE(k0, k1);
}

TEST(ExtractionSpanKey, PredicateVariesKey) {
    const std::string ka = compute_extraction_span_key(
        "engram-x", 0, "responsible_for", "h");
    const std::string kb = compute_extraction_span_key(
        "engram-x", 0, "manages", "h");
    EXPECT_NE(ka, kb);
}

TEST(ExtractionSpanKey, CanonicalObjectHashVariesKey) {
    const std::string k1 = compute_extraction_span_key(
        "engram-x", 0, "p", "hash1");
    const std::string k2 = compute_extraction_span_key(
        "engram-x", 0, "p", "hash2");
    EXPECT_NE(k1, k2);
}

TEST(ExtractionSpanKey, EngramRefVariesKey) {
    const std::string k1 = compute_extraction_span_key(
        "engram-1", 0, "p", "h");
    const std::string k2 = compute_extraction_span_key(
        "engram-2", 0, "p", "h");
    EXPECT_NE(k1, k2);
}

// Locked vector — pinned with tests/python/test_extraction_span_key.py.
TEST(ExtractionSpanKey, LockedFixtureVector) {
    const std::string k = compute_extraction_span_key(
        /*engram_ref_id=*/"01HZK9PWQ4RXM2NJEAQS37VBFZ",
        /*chunk_index=*/0,
        /*predicate=*/"responsible_for",
        /*canonical_object_hash=*/
        "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8");
    EXPECT_EQ(k, "a1543d3a85b188c8709a168c861612738b9b1b0a7d6002ba1a5c0f0ce01097b5");
}

}  // namespace starling::extractor
