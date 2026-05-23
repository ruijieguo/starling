#include <gtest/gtest.h>

#include "starling/evidence/engram.hpp"

#include <string>
#include <vector>

using starling::evidence::canonicalize_engram_payload;
using starling::evidence::compute_engram_content_hash;

namespace {
std::vector<std::uint8_t> bytes(const std::string& s) {
    return {s.begin(), s.end()};
}
}  // namespace

TEST(EngramContentHash, DifferentPayloadsProduceDifferentHashes) {
    const auto a = compute_engram_content_hash(bytes("hello"), {});
    const auto b = compute_engram_content_hash(bytes("hellp"), {});
    EXPECT_NE(a, b);
    EXPECT_EQ(a.size(), 64u);  // sha256 hex
}

TEST(EngramContentHash, DeclaredTransformationsAffectHash) {
    const auto raw = compute_engram_content_hash(bytes("hello"), {});
    const auto normalized = compute_engram_content_hash(bytes("hello"), {"nfc"});
    EXPECT_NE(raw, normalized);
}

TEST(EngramContentHash, TransformationsAreOrderIndependent) {
    const auto ab = compute_engram_content_hash(bytes("hello"), {"nfc", "trim"});
    const auto ba = compute_engram_content_hash(bytes("hello"), {"trim", "nfc"});
    EXPECT_EQ(ab, ba);
}

TEST(EngramContentHash, DuplicateTransformationsDoNotChangeHash) {
    // Canonical form deduplicates; producer-order accidents shouldn't fork the hash.
    const auto unique = compute_engram_content_hash(bytes("hello"), {"nfc"});
    const auto with_dup = compute_engram_content_hash(bytes("hello"), {"nfc", "nfc"});
    EXPECT_EQ(unique, with_dup);
}

TEST(EngramContentHash, PinnedDigests) {
    // Pin three digests so future refactors of the canonicalizer can't silently
    // change the hash domain. Computed against:
    //   body = b"v1\x1f" + payload + b"\x1f" + b"\x1f".join(sorted(set(transforms)))
    //   sha256_hex(body)
    EXPECT_EQ(
        compute_engram_content_hash(bytes("hello"), {}),
        "8f0a4fd76563f60c50e7fe49ab055885fc6f0d19034893c11ff51f7d2f4bed4a");
    EXPECT_EQ(
        compute_engram_content_hash(bytes("hello"), {"nfc"}),
        "17437ac920346fce85efc803a1851dd28867e088be65ef912866eccee6a3df31");
    EXPECT_EQ(
        compute_engram_content_hash(bytes(""), {}),
        "6b9835adb93d6a91dc43391f94c9f0c71fafa5d4e9919120327635152b6eeb18");
}

TEST(EngramContentHash, CanonicalFormHasV1Prefix) {
    // The canonical form starts with "v1\x1f"; the version prefix lets us
    // bump the canonical form later without colliding with M0.3 hashes.
    const auto canonical = canonicalize_engram_payload(bytes("hello"), {});
    ASSERT_GE(canonical.size(), 3u);
    EXPECT_EQ(canonical[0], 'v');
    EXPECT_EQ(canonical[1], '1');
    EXPECT_EQ(canonical[2], '\x1f');
}
