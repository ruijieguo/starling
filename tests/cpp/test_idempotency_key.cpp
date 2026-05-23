#include <gtest/gtest.h>
#include "starling/bus/bus_event.hpp"

using starling::bus::compute_idempotency_key;

TEST(IdempotencyKey, SameInputsSameDigest) {
    const auto a = compute_idempotency_key("statement.created", "h1", "k1", "", "");
    const auto b = compute_idempotency_key("statement.created", "h1", "k1", "", "");
    EXPECT_EQ(a, b);
    EXPECT_EQ(a.size(), 64u);  // sha256 hex
}

TEST(IdempotencyKey, FieldChangesPropagate) {
    const auto base = compute_idempotency_key("e", "h", "k", "", "");
    EXPECT_NE(base, compute_idempotency_key("e", "h", "k2", "", ""));
    EXPECT_NE(base, compute_idempotency_key("e", "h2", "k", "", ""));
    EXPECT_NE(base, compute_idempotency_key("e2", "h", "k", "", ""));
    EXPECT_NE(base, compute_idempotency_key("e", "h", "k", "root", ""));
    EXPECT_NE(base, compute_idempotency_key("e", "h", "k", "", "bucket"));
}

TEST(IdempotencyKey, SeparatorPreventsCollision) {
    // "ab" + "" must differ from "a" + "b".
    EXPECT_NE(
        compute_idempotency_key("ab", "", "", "", ""),
        compute_idempotency_key("a", "b", "", "", ""));
}
