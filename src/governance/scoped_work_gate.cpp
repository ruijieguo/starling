#include "starling/governance/scoped_work_gate.hpp"

#include <algorithm>
#include <stdexcept>
#include <string>

namespace starling::governance {

ScopedWorkGate::ScopedWorkGate(GateConfig config) : config_(config) {}

// ── private helpers ──────────────────────────────────────────────────────────

ScopedWorkGate::Slot* ScopedWorkGate::find_slot_(const GateKey& key,
                                                  std::string_view task_id) {
    auto found = std::ranges::find_if(slots_, [&key, &task_id](const Slot& slot) {
        return slot.gate_key == key && slot.task_id == task_id;
    });
    return (found != slots_.end()) ? &*found : nullptr;
}

int ScopedWorkGate::lane_in_use_(Lane lane) const {
    return static_cast<int>(std::ranges::count_if(slots_, [lane](const Slot& slot) {
        return slot.gate_key.lane == lane;
    }));
}

// ── public interface ─────────────────────────────────────────────────────────

AcquireOutcome ScopedWorkGate::acquire(const GateKey& key,
                                        std::string_view task_id,
                                        std::string_view lease_until) {
    // Reentrancy check: same (GateKey, task_id) — depth++ (L4).
    Slot* existing = find_slot_(key, task_id);
    if (existing != nullptr) {
        existing->depth += 1;
        return AcquireOutcome{.status = AdmitStatus::Admitted, .depth = existing->depth};
    }

    // New holder: check lane quota.
    if (key.lane == Lane::Critical) {
        const int in_use = lane_in_use_(Lane::Critical);
        if (in_use >= config_.critical_quota) {
            return AcquireOutcome{.status = AdmitStatus::CriticalRejected, .depth = 0};
        }
    } else {
        // Lane::Soft
        const int in_use = lane_in_use_(Lane::Soft);
        if (in_use >= config_.soft_quota) {
            dropped_soft_work_count_ += 1;
            return AcquireOutcome{.status = AdmitStatus::SoftDropped, .depth = 0};
        }
    }

    // Quota available — insert slot.
    slots_.push_back(Slot{
        .gate_key    = key,
        .task_id     = std::string(task_id),
        .lease_until = std::string(lease_until),
        .depth       = 1,
    });
    return AcquireOutcome{.status = AdmitStatus::Admitted, .depth = 1};
}

void ScopedWorkGate::release(const GateKey& key, std::string_view task_id) {
    // First: look for a slot with this GateKey (any task_id) to give a better error
    // message when the GateKey exists but with the wrong task_id.
    const Slot* key_holder = nullptr;
    Slot* exact_slot = nullptr;
    for (Slot& slot : slots_) {
        if (slot.gate_key == key) {
            key_holder = &slot;
            if (slot.task_id == task_id) {
                exact_slot = &slot;
                break;
            }
        }
    }

    if (exact_slot == nullptr) {
        if (key_holder != nullptr) {
            throw std::runtime_error(
                "ScopedWorkGate::release: GateKey is held but by a different task_id "
                "(wrong owner)");
        }
        throw std::runtime_error(
            "ScopedWorkGate::release: (GateKey, task_id) is not currently held");
    }

    // Defensive underflow guard (should be unreachable if acquire/release are balanced).
    if (exact_slot->depth <= 0) {
        throw std::runtime_error(
            "ScopedWorkGate::release: depth underflow — release called more times than acquire");
    }

    exact_slot->depth -= 1;

    if (exact_slot->depth == 0) {
        // Erase the slot and reclaim the lane quota.
        std::erase_if(slots_, [&key, &task_id](const Slot& slot) {
            return slot.gate_key == key && slot.task_id == task_id;
        });
    }
}

std::vector<std::string> ScopedWorkGate::sweep_leaked(std::string_view now_iso) {
    // Collect task_ids of every expired slot (lease_until < now_iso, L6 string compare).
    std::vector<std::string> freed;
    for (const Slot& slot : slots_) {
        if (slot.lease_until < now_iso) {
            freed.push_back(slot.task_id);
        }
    }

    // Erase expired slots and reclaim their lane quota.
    // std::erase_if removes all elements satisfying the predicate — quota is implicit
    // in the remaining slot count (lane_in_use_ counts slots_ directly), so erasing
    // the slot is sufficient to reclaim the quota.
    std::erase_if(slots_, [&now_iso](const Slot& slot) {
        return slot.lease_until < now_iso;
    });

    return freed;
}

long long ScopedWorkGate::dropped_soft_work_count() const {
    return dropped_soft_work_count_;
}

int ScopedWorkGate::active_slot_count() const {
    return static_cast<int>(slots_.size());
}

}  // namespace starling::governance
