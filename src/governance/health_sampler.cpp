#include "starling/governance/health_sampler.hpp"

#include <string>
#include <vector>

#include "starling/governance/runtime_health_event.hpp"
#include "starling/runtime_health.hpp"

namespace starling::governance {

HealthSampler::HealthSampler(HealthSamplerConfig config) : config_(config) {}

HealthDecision HealthSampler::evaluate(const MetricsSnapshot& snapshot) const {
    // Collect names of all ENABLED metrics that exceed their threshold.
    // Order is LOCKED to config-field declaration order (stable trigger string).
    std::vector<std::string> over;

    if (config_.outbox_lag.enabled &&
        snapshot.outbox_lag_sequence > config_.outbox_lag.threshold) {
        over.emplace_back("outbox_lag");
    }
    if (config_.subscriber_failure_rate.enabled &&
        snapshot.subscriber_failure_rate > config_.subscriber_failure_rate.threshold) {
        over.emplace_back("subscriber_failure_rate");
    }
    if (config_.extraction_queue_depth.enabled &&
        snapshot.extraction_queue_depth > config_.extraction_queue_depth.threshold) {
        over.emplace_back("extraction_queue_depth");
    }
    if (config_.projection_lag_seconds.enabled &&
        snapshot.projection_lag_seconds > config_.projection_lag_seconds.threshold) {
        over.emplace_back("projection_lag_seconds");
    }
    if (config_.runtime_event_loop_lag_ms.enabled &&
        snapshot.runtime_event_loop_lag_ms >
            config_.runtime_event_loop_lag_ms.threshold) {
        over.emplace_back("runtime_event_loop_lag_ms");
    }
    if (config_.vector_delete_lag.enabled &&
        snapshot.vector_delete_lag > config_.vector_delete_lag.threshold) {
        over.emplace_back("vector_delete_lag");
    }
    // erased_evidence: no numeric threshold — any visible count > 0 trips.
    if (config_.erased_evidence.enabled &&
        snapshot.erased_evidence_visible_count > 0) {
        over.emplace_back("erased_evidence");
    }

    if (over.empty()) {
        // READY honestly = "all enabled metrics within SLA" (L1).
        // trigger is never empty for READY (L4).
        return HealthDecision{
            .target_status = RuntimeHealth::READY,
            .trigger = "backpressure_recovered",
            .metrics_snapshot = snapshot,
        };
    }

    // Build deterministic comma-joined trigger string (L4).
    std::string trigger_str;
    for (const std::string& name : over) {
        if (!trigger_str.empty()) {
            trigger_str += ',';
        }
        trigger_str += name;
    }

    return HealthDecision{
        .target_status = RuntimeHealth::DEGRADED,
        .trigger = std::move(trigger_str),
        .metrics_snapshot = snapshot,
    };
}

}  // namespace starling::governance
