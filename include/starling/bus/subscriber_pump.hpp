#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/connection.hpp"
#include <string_view>

namespace starling::bus {

class SubscriberPump {
public:
    // Called once after Bus::write commit. Runs 5 subscribers in fixed order,
    // each SAVEPOINT-isolated — a single subscriber failure rolls back only
    // itself and does not affect the committed write or other subscribers.
    static void run_post_write(persistence::SqliteAdapter& adapter,
                               persistence::Connection& conn,
                               std::string_view now_iso);
};

}  // namespace starling::bus
