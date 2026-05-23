#pragma once

#include "starling/bus/bus_event.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/persistence/connection.hpp"

#include <optional>
#include <string>
#include <string_view>
#include <variant>

namespace starling::bus {

struct StatementWriteAccepted {
    std::string stmt_id;
    std::string event_id;
    std::int64_t outbox_sequence;
};
struct StatementWriteChunkDuplicate {
    std::string stmt_id;            // newly inserted row, forced review_requested
    std::string original_stmt_id;   // the earlier APPROVED row in the same span
    std::string event_id;
};

using StatementWriteOutcome = std::variant<
    StatementWriteAccepted,
    StatementWriteChunkDuplicate>;

// StatementWriter is the only sanctioned writer to `statements` + the
// `statement.written` outbox event family. It must be invoked inside a
// transaction the caller has already opened (Bus::write opens BEGIN IMMEDIATE
// before delegating; tests open it directly via sqlite3_exec). The writer
// performs the §15.3.2 chunk-duplicate check inside the same transaction so
// reads of `statements` are read-committed against the in-flight INSERT.
class StatementWriter {
public:
    explicit StatementWriter(starling::persistence::Connection& conn) : conn_(conn) {}

    StatementWriteOutcome write(
        const starling::extractor::ExtractedStatement& stmt,
        std::string_view                                evidence_engram_id,
        std::string_view                                extraction_span_key,
        std::optional<std::string>                      causation_parent_event_id);

private:
    starling::persistence::Connection& conn_;
};

}  // namespace starling::bus
