#pragma once
#include "starling/persistence/connection.hpp"

#include <chrono>
#include <cstdint>
#include <string_view>

namespace starling::bus {

// ConsumerCheckpoint records the highest outbox_sequence each consumer has
// successfully handled. advance() is monotonic — it never lowers the stored
// value, so out-of-order completion or replay can't rewind a consumer.
class ConsumerCheckpoint {
public:
    explicit ConsumerCheckpoint(starling::persistence::Connection& c) : conn_(c) {}

    int64_t last_delivered(std::string_view consumer_id);
    void advance(std::string_view consumer_id, int64_t sequence);

private:
    starling::persistence::Connection& conn_;
};

// IdempotencyInbox is the consumer-side dedup table. Each (consumer_id,
// idempotency_key) pair is recorded with a TTL; record_if_new returns false
// when the pair is already present so the caller skips the side-effect.
// purge_expired drops rows whose expires_at is in the past.
class IdempotencyInbox {
public:
    explicit IdempotencyInbox(starling::persistence::Connection& c) : conn_(c) {}

    // Returns true if the (consumer, key) pair was inserted (i.e., not seen).
    // Returns false if it was already present (caller must skip the side-effect).
    bool record_if_new(std::string_view consumer_id,
                       std::string_view idempotency_key,
                       std::chrono::system_clock::time_point now,
                       std::chrono::seconds ttl);

    // Deletes rows whose expires_at < now. Returns rows pruned.
    int64_t purge_expired(std::chrono::system_clock::time_point now);

private:
    starling::persistence::Connection& conn_;
};

}  // namespace starling::bus
