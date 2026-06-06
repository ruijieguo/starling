#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/connection.hpp"
#include <string_view>

namespace starling::tom {

// Consumes statement.written events after Bus.write (via SubscriberPump) and
// drives the CommonGround grounding lifecycle: assert new dialogue statements
// (scope_parties>=2) into asserted_unack; acknowledge on same-proposition
// restatement by the other party (#1/#3); repair on opposite-polarity restatement;
// then rebuild the CommonGroundContainer projection. Co-presence(#2)/timeout are
// Task 5. Own singleton checkpoint common_ground_subscriber_checkpoint.
class CommonGroundSubscriber {
public:
    static int tick_one_batch(persistence::SqliteAdapter& adapter,
                              persistence::Connection& conn,
                              std::string_view now_iso,
                              int batch_size = 100);
};

}  // namespace starling::tom
