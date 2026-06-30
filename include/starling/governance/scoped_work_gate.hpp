#pragma once
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace starling::governance {

// Lane distinguishes Critical (never silently dropped) from Soft (over-quota drops
// are accounted but not fatal — L3/L8 invariant-5 soft accounting half).
enum class Lane : std::uint8_t { Critical, Soft };

// Reentrancy / identity key. All four fields must match for a call to be considered
// reentrant (L4). Equality is value-semantic — operator== = default.
struct GateKey {
    std::string tenant_id;
    std::string holder_scope;
    std::string aggregate_id;
    Lane lane = Lane::Soft;
    bool operator==(const GateKey&) const = default;
};

// Capacity configuration for one ScopedWorkGate instance.
struct GateConfig {
    int critical_quota = 0;  // reserved slots for Lane::Critical; never starved by soft work
    int soft_quota = 0;      // slots for Lane::Soft; over-quota returns SoftDropped
};

// Typed outcome of acquire() — the [[nodiscard]] tag forces callers to inspect the
// result rather than silently ignoring a rejection (L3).
enum class AdmitStatus : std::uint8_t { Admitted, SoftDropped, CriticalRejected };

struct AcquireOutcome {
    AdmitStatus status = AdmitStatus::Admitted;
    int depth = 0;
};

// In-memory, single-threaded, reentrant work-gate.
//
// Slot identity: (GateKey, task_id). Same (GateKey, task_id) → depth++ (reentrant,
// no new slot consumed). Same GateKey + DIFFERENT task_id → a DISTINCT holder that
// consumes its own slot from the lane quota (NOT reentrant) — L4.
//
// lease_until: canonical ISO-8601 UTC ("YYYY-MM-DDTHH:MM:SSZ", same contract as
// PipelineRun::lease_until / CX-8). No parsing/validation here; the caller's
// contract. Stored on the slot so Task 4.2 sweep_leaked can string-compare vs a
// cutoff_iso and reclaim stale slots.
//
// No std::mutex — single-threaded c1 (L2). M0.9+ adds locking when concurrency lands.
class ScopedWorkGate {
public:
    explicit ScopedWorkGate(GateConfig config);

    // Attempt to acquire a slot for (key, task_id).
    //
    // Reentrant: if the exact (key, task_id) pair already holds a slot, depth++ and
    // return {Admitted, new_depth} without consuming an additional lane quota slot.
    //
    // New holder: check the lane's remaining quota. If the lane has capacity:
    //   insert a slot, return {Admitted, 1}.
    // Soft over-quota: increment dropped_soft_work_count_, return {SoftDropped, 0}.
    //   The slot is NOT held — a subsequent release() for this (key, task_id) throws.
    // Critical over-quota: return {CriticalRejected, 0}. No slot held. No throw.
    //
    // lease_until: stored on the slot (canonical iso8601 UTC) — Task 4.2 sweep_leaked
    // uses this to reclaim slots whose leases have expired.
    [[nodiscard]] AcquireOutcome acquire(const GateKey& key, std::string_view task_id,
                                         std::string_view lease_until);

    // Decrement depth for the (key, task_id) slot. Frees the slot and reclaims the
    // lane quota counter at depth 0. FAIL-LOUD (L5): throws std::runtime_error when:
    //   • the (key, task_id) pair is not currently held;
    //   • the held slot's task_id does not match the supplied task_id (wrong-owner);
    //   • depth would underflow (should not occur if acquire/release are balanced, but
    //     protected defensively).
    void release(const GateKey& key, std::string_view task_id);

    // Number of soft work items dropped since construction.
    [[nodiscard]] long long dropped_soft_work_count() const;

    // Force-release every held slot whose stored lease_until < now_iso (canonical
    // iso8601 UTC string compare, same contract as PipelineRun::lease_until / CX-8 /
    // L6). Reclaims each freed slot's lane quota. Returns the freed task_ids.
    // Slots with lease_until >= now_iso remain held. Empty gate or none expired → {}.
    [[nodiscard]] std::vector<std::string> sweep_leaked(std::string_view now_iso);

    // Number of distinct (GateKey, task_id) pairs currently holding a slot.
    // Test introspection — not a quota counter.
    [[nodiscard]] int active_slot_count() const;

private:
    // One active slot.
    struct Slot {
        GateKey gate_key;
        std::string task_id;
        std::string lease_until;  // canonical iso8601 UTC; used by Task 4.2 sweep_leaked
        int depth = 1;
    };

    // Find a slot matching (key, task_id). Returns nullptr if absent.
    // Linear scan: N is tiny in practice (c1 runs ≤ O(10) concurrent pipelines).
    [[nodiscard]] Slot* find_slot_(const GateKey& key, std::string_view task_id);

    // Count of currently held slots for the given lane.
    [[nodiscard]] int lane_in_use_(Lane lane) const;

    GateConfig config_;
    std::vector<Slot> slots_;    // small vector scanned linearly (L9)
    long long dropped_soft_work_count_ = 0;
};

}  // namespace starling::governance
