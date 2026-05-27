// belief_tracker_internal.hpp — shared declarations for belief_tracker.cpp
// and belief_tracker_handlers.cpp. Not part of the public API.

#pragma once

#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/tom/belief_tracker.hpp"

#include <string>

namespace starling::tom::belief_tracker::detail {

void handle_statement_written(
    const std::string& tenant_id,
    const std::string& primary_id,
    const std::string& payload_json,
    cognizer::CognizerHub& hub,
    cognizer::KnowledgeFrontier& frontier,
    persistence::Connection& conn,
    TickStats& stats);

void handle_evidence_appended(
    const std::string& tenant_id,
    const std::string& primary_id,
    const std::string& payload_json,
    cognizer::KnowledgeFrontier& frontier,
    persistence::Connection& conn,
    TickStats& stats);

void handle_statement_archived(TickStats& stats);
void handle_statement_superseded(TickStats& stats);
void handle_commitment_fulfilled(TickStats& stats);
void handle_commitment_broken(TickStats& stats);

}  // namespace starling::tom::belief_tracker::detail
