#include "starling/retrieval/claim_evidence.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/evidence/engram.hpp"
#include "starling/extractor/claim_contract.hpp"

#include <algorithm>
#include <cstdio>
#include <cctype>
#include <chrono>
#include <set>
#include <regex>

#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"

namespace starling::retrieval {
namespace {
using json = nlohmann::json;
std::string upper(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(),
                   [](unsigned char c) { return static_cast<char>(std::toupper(c)); });
    return value;
}
// UTC calendar validity must be checked in native storage/retrieval too:
// a syntactically ISO-shaped but impossible date cannot rank a memory.
bool valid_utc_time(const std::string& value) {
    static const std::regex iso(R"(^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$)");
    if (!std::regex_match(value, iso)) return false;
    const auto date = std::chrono::year_month_day{
        std::chrono::year{std::stoi(value.substr(0, 4))},
        std::chrono::month{static_cast<unsigned>(std::stoi(value.substr(5, 2)))},
        std::chrono::day{static_cast<unsigned>(std::stoi(value.substr(8, 2)))}};
    return date.ok() && std::stoi(value.substr(11, 2)) < 24 &&
        std::stoi(value.substr(14, 2)) < 60 && std::stoi(value.substr(17, 2)) < 60;
}
const std::set<std::string> scopes{
    "ASSERTED", "CONDITIONAL", "HYPOTHETICAL", "QUESTIONED", "REPORTED", "NEGATED"};
bool text(const json& j, const char* field) {
    return j.contains(field) && j[field].is_string() && !j[field].get_ref<const std::string&>().empty();
}
}  // namespace

nlohmann::json parse_claim_evidence(const StatementRow& row) {
    // DTO writes and database reads can bypass extraction; validate duplicates
    // before any parse/dump cycle can erase the conflicting source metadata.
    try { return extractor::claim_strict_json(row.semantic_claim_json); }
    catch (const std::exception&) { throw std::invalid_argument("malformed_claim"); }
}

std::string claim_evidence_error(persistence::Connection& conn, const StatementRow& row) {
    if (row.semantic_claim_json.empty()) return {};
    try {
        const auto j = parse_claim_evidence(row);
        if (!j.is_object() || !j.contains("schema_version") || !j["schema_version"].is_number_integer() || j["schema_version"] != 1 ||
            !j.contains("source_span") || !j["source_span"].is_object() ||
            !text(j, "clause_id") || !text(j, "actor") || !text(j, "assertion_scope") ||
            !text(j, "relation_polarity") || !text(j, "relation_modality") ||
            !text(j, "source_time") || !j.contains("event_time") ||
            !j.contains("scope_markers") || !j["scope_markers"].is_array()) {
            return "malformed_claim";
        }
        if (!extractor::is_claim_predicate(row.predicate) || row.subject_kind != "cognizer" ||
            (!row.provenance.empty() && row.provenance != "user_input")) return "inconsistent_claim";
        const auto scope = j["assertion_scope"].get<std::string>();
        if (!scopes.count(scope)) return "unsupported_claim_scope";
        std::set<std::string> markers;
        for (const auto& marker : j["scope_markers"]) {
            if (!marker.is_string()) return "malformed_claim";
            if (!scopes.count(marker.get<std::string>())) return "unsupported_claim_scope";
            if (!markers.insert(marker.get<std::string>()).second) return "malformed_claim";
        }
        if (!markers.count(scope) ||
            (markers.count("ASSERTED") && (markers.count("CONDITIONAL") ||
             markers.count("HYPOTHETICAL") || markers.count("QUESTIONED")))) return "inconsistent_claim";
        if (!j.contains("attributed_to") ||
            (!j["attributed_to"].is_null() && !j["attributed_to"].is_string()) ||
            !j.contains("time_text") || !j["time_text"].is_string()) return "malformed_claim";
        const auto perspective = upper(row.holder_perspective);
        if ((perspective == "FIRST_PERSON" && (!j["attributed_to"].is_null() || markers.count("REPORTED"))) ||
            (perspective == "QUOTED" && (!markers.count("REPORTED") || j["attributed_to"] != row.holder_id)) ||
            (perspective != "FIRST_PERSON" && perspective != "QUOTED")) return "inconsistent_claim";
        const auto& span = j["source_span"];
        if (!text(span, "engram_ref") || !text(span, "source_hash") ||
            !span.contains("span_start") || !span["span_start"].is_number_integer() ||
            !span.contains("span_end") || !span["span_end"].is_number_integer())
            return "malformed_claim";
        const auto start = span["span_start"].get<std::int64_t>();
        const auto end = span["span_end"].get<std::int64_t>();
        if (start < 0 || end <= start || j["actor"] != row.subject_id ||
            upper(j["relation_polarity"].get<std::string>()) != upper(row.polarity) ||
            upper(j["relation_modality"].get<std::string>()) != upper(row.modality) ||
            (upper(row.holder_perspective) == "FIRST_PERSON" && row.subject_id != row.holder_id))
            return "inconsistent_claim";
        if (markers.count("REPORTED") && (!text(j, "attributed_to") || j["attributed_to"] != row.holder_id))
            return "inconsistent_claim";
        if (!j["event_time"].is_null()) {
            const auto& event = j["event_time"];
            if (!event.is_object() || !text(event, "start") || !event.contains("end") ||
                (!event["end"].is_null() && (!text(event, "end") || event["end"] < event["start"])))
                return "malformed_claim";
            if (!valid_utc_time(event["start"].get<std::string>()) ||
                (event["end"].is_string() && !valid_utc_time(event["end"].get<std::string>())))
                return "malformed_claim";
        }
        const auto compat = json::parse(row.source_spans_json, nullptr, false);
        bool matched = false;
        if (compat.is_array()) for (const auto& ref : compat) {
            if (ref.is_object() && ref.value("engram_ref", "") == span["engram_ref"].get<std::string>() &&
                ref.value("source_hash", "") == span["source_hash"].get<std::string>() &&
                ref.contains("span_start") && ref["span_start"] == span["span_start"] &&
                ref.contains("span_end") && ref["span_end"] == span["span_end"]) matched = true;
        }
        if (!matched) return "inconsistent_claim";
        sqlite3_stmt* raw = nullptr;
        const char* sql = "SELECT content_hash,created_at,erased_at,payload_inline,declared_transformations_json FROM engrams WHERE id=? AND tenant_id=?";
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
            throw persistence::detail::make_sqlite_error(conn.raw(), "claim evidence source lookup");
        persistence::StmtHandle stmt(raw);
        persistence::detail::bind_sv(raw, 1, span["engram_ref"].get_ref<const std::string&>());
        persistence::detail::bind_sv(raw, 2, row.tenant_id);
        if (sqlite3_step(raw) != SQLITE_ROW) return "inconsistent_claim";
        auto col = [&](int i) {
            const auto* p = sqlite3_column_text(raw, i);
            return p ? std::string(reinterpret_cast<const char*>(p)) : std::string();
        };
        if (col(1) != j["source_time"].get<std::string>() || !col(2).empty() || sqlite3_column_type(raw, 3) == SQLITE_NULL)
            return "inconsistent_claim";
        const auto* bytes = static_cast<const char*>(sqlite3_column_blob(raw, 3));
        const auto size = sqlite3_column_bytes(raw, 3);
        if (size <= 0 || end > size) return "inconsistent_claim";
        const std::string payload(bytes, static_cast<std::size_t>(size));
        const auto transforms = json::parse(col(4)).get<std::vector<std::string>>();
        const std::vector<std::uint8_t> payload_bytes(payload.begin(), payload.end());
        // SourceSpan hashes raw UTF-8; Engram.content_hash additionally covers
        // its versioned declared transformations. These are distinct hashes.
        if (crypto::sha256_hex(payload) != span["source_hash"].get<std::string>() ||
            evidence::compute_engram_content_hash(payload_bytes, transforms) != col(0))
            return "inconsistent_claim";
        bool source_unit_matches = false;
        bool typed_source_turn = false;
        std::string source_unit;
        json source_units;
        try { source_units = json::parse(extractor::claim_source_units(payload)); }
        catch (const std::exception&) { return "inconsistent_claim"; }
        for (const auto& unit : source_units) {
            if (unit["clause_id"] == j["clause_id"] && unit["byte_start"] == start && unit["byte_end"] == end) {
                source_unit_matches = true;
                typed_source_turn = unit.contains("observed_at");
                source_unit = unit.value("utterance",unit["text"].get<std::string>());
            }
        }
        if (!source_unit_matches) return "inconsistent_claim";
        if (typed_source_turn && !j.contains("source_turn")) return "inconsistent_claim";
        if (!j["event_time"].is_null()) {
            const auto& event = j["event_time"];
            if (source_unit.find(event["start"].get<std::string>()) == std::string::npos ||
                (event["end"].is_string() && source_unit.find(event["end"].get<std::string>()) == std::string::npos))
                return "inconsistent_claim";
        }
        const auto time_text = j["time_text"].get<std::string>();
        if (!time_text.empty() && source_unit.find(time_text) == std::string::npos)
            return "inconsistent_claim";
        // Share the extractor's deterministic relation/scope contract. Merely
        // matching a certificate to a row would permit two consistently invalid
        // values (for example feels/INTENDS) through direct Bus writes. This
        // replay performs no model call and never changes the stored claim.
        json wire_evidence;
        for (const auto* field : {"clause_id", "actor", "attributed_to", "assertion_scope",
                                  "scope_markers", "time_text", "event_time"})
            wire_evidence[field] = j.at(field);
        for (const auto* field : {"topic", "source_turn"})
            if (j.contains(field)) wire_evidence[field] = j.at(field);
        const json wire_row = {
            {"holder", row.holder_id}, {"holder_perspective", perspective},
            {"subject", row.subject_id}, {"subject_kind", row.subject_kind},
            {"predicate", row.predicate}, {"object", row.object_value},
            {"modality", upper(row.modality)}, {"polarity", upper(row.polarity)},
            {"nesting_depth", row.nesting_depth}, {"evidence", wire_evidence}};
        const auto checked = extractor::parse_claim_response(
            json{{"schema_version", 2}, {"statements", json::array({wire_row})}}.dump(),
            payload, row.holder_id);
        if (row.object_kind != "str" || !checked.errors.empty() ||
            !checked.semantic_rejections.empty() || checked.statements.size() != 1)
            return "inconsistent_claim";
        return {};
    } catch (const std::exception&) {
        return "malformed_claim";
    }
}

void record_claim_exclusion(RetrievalReceipt& receipt, const std::string& tenant_id,
                            const std::string& statement_id, const std::string& reason) {
    if (!receipt.claim_exclusions.emplace(std::make_pair(tenant_id, statement_id), reason).second) return;
    ++receipt.candidate_counts.dropped_by_claim_evidence;
    auto counts = json::parse(receipt.claim_exclusion_counts_json);
    counts[reason] = counts.value(reason, std::int64_t{0}) + 1;
    receipt.claim_exclusion_counts_json = counts.dump();
}

void record_claim_link(persistence::Connection& conn, RetrievalReceipt& receipt, const StatementRow& row) {
    if (row.semantic_claim_json.empty()) return;
    auto link = parse_claim_evidence(row);
    link["statement_id"] = row.id;
    link["tenant_id"] = row.tenant_id;
    const auto& span = link.at("source_span");
    const auto start = span.at("span_start").get<std::int64_t>();
    const auto end = span.at("span_end").get<std::int64_t>();
    constexpr std::int64_t excerpt_limit = 4096;
    // Only a selected, already validated source unit is read. SQLite BLOB
    // substr uses byte positions (one-based), not Unicode character positions.
    sqlite3_stmt* raw = nullptr;
    const char* sql = "SELECT substr(payload_inline,?,?) FROM engrams "
        "WHERE id=? AND tenant_id=? AND erased_at IS NULL AND payload_inline IS NOT NULL";
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw persistence::detail::make_sqlite_error(conn.raw(), "selected claim excerpt lookup");
    persistence::StmtHandle stmt(raw);
    sqlite3_bind_int64(raw, 1, start + 1);
    sqlite3_bind_int64(raw, 2, std::min(end - start, excerpt_limit + 4));
    persistence::detail::bind_sv(raw, 3, span.at("engram_ref").get_ref<const std::string&>());
    persistence::detail::bind_sv(raw, 4, row.tenant_id);
    if (sqlite3_step(raw) != SQLITE_ROW)
        throw std::runtime_error("selected claim source became unavailable");
    const auto* bytes = static_cast<const char*>(sqlite3_column_blob(raw, 0));
    const auto size = sqlite3_column_bytes(raw, 0);
    if (size <= 0) throw std::runtime_error("selected claim source excerpt is empty");
    std::string excerpt(bytes, static_cast<std::size_t>(size));
    if (excerpt.size() > static_cast<std::size_t>(excerpt_limit)) {
        auto limit = static_cast<std::size_t>(excerpt_limit);
        while (limit > 0 && (static_cast<unsigned char>(excerpt[limit]) & 0xc0) == 0x80) --limit;
        excerpt.resize(limit);
    }
    link["source_excerpt"] = excerpt;
    link["source_excerpt_span_start"] = start;
    link["source_excerpt_span_end"] = start + static_cast<std::int64_t>(excerpt.size());
    link["source_excerpt_truncated"] = static_cast<std::int64_t>(excerpt.size()) < end - start;
    receipt.trace_retention = "selected_source_excerpts";
    const bool fallback = link["event_time"].is_null();
    link["event_time_status"] = fallback ? "UNKNOWN" : "EXPLICIT";
    link["time_basis"] = fallback ? "source_time_fallback" : "event_time";
    if (fallback) ++receipt.source_time_fallback_count;
    auto links = json::parse(receipt.evidence_links_json);
    links.push_back(std::move(link));
    receipt.evidence_links_json = links.dump();
}
}  // namespace starling::retrieval
