#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/connection.hpp"
#include <string_view>

namespace starling::tom {

// Consumes statement.derived / statement.consolidated / statement.superseded
// events after Bus.write and rebuilds each affected subject's PersonaContainer
// from that subject's consolidated statements. The affected subject is resolved
// via the event's primary_id (never aggregate_id — it differs across the three
// event types). Owns singleton checkpoint persona_subscriber_checkpoint. Runs as
// a tick_all stage (T2); tested in isolation here.
class PersonaSubscriber {
public:
    [[nodiscard]] static int tick_one_batch(persistence::SqliteAdapter& adapter,
                                            persistence::Connection& conn,
                                            std::string_view now_iso,
                                            int batch_size = 100);
};

}  // namespace starling::tom
