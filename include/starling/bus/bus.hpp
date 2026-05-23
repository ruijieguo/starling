#pragma once

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/evidence/engram.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <optional>
#include <string>
#include <variant>

namespace starling::bus {

struct AppendEvidenceAccepted {
    starling::evidence::EngramRef ref;
    std::string event_id;
    int64_t outbox_sequence;
};
struct AppendEvidenceIdempotent {
    starling::evidence::EngramRef ref;
    std::string audit_event_id;
};
struct AppendEvidenceNoStore {
    std::string audit_event_id;
};
struct AppendEvidenceRejected {
    std::string reason;
};

using AppendEvidenceOutcome = std::variant<
    AppendEvidenceAccepted,
    AppendEvidenceIdempotent,
    AppendEvidenceNoStore,
    AppendEvidenceRejected>;

class Bus {
public:
    explicit Bus(starling::persistence::SqliteAdapter& adapter);

    AppendEvidenceOutcome append_evidence(
        const starling::evidence::EngramInput& input,
        std::optional<std::string> causation_parent_event_id);

private:
    starling::persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::bus
