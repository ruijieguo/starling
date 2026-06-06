#pragma once

#include "starling/extractor/existing_ref_map.hpp"
#include "starling/extractor/extracted_statement.hpp"

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

namespace starling::extractor {

struct ParseError {
    std::string kind;          // e.g. "not_json_array", "element_not_object"
    std::string detail;        // free text for human consumers
    std::size_t byte_offset;   // approximate; 0 if unknown
};

struct ParseResult {
    std::vector<ExtractedStatement> statements;
    std::vector<ParseError>         errors;
};

// Parses the LLM's JSON-array extraction output into ExtractedStatement list.
// LENIENT per-element: a malformed element (bad enum, missing field) is SKIPPED
// (not added to statements, not added to errors) so a mostly-valid response
// still yields its good statements. Only a non-array / non-JSON top level
// produces a ParseError (the orchestrator then retries the whole attempt).
// LLM supplies the semantic core (holder_perspective/subject/predicate/object/
// modality/polarity/nesting_depth); C++ fills bookkeeping (subject_kind=cognizer,
// object_kind=str or "statement" when nesting_depth>=2, canonical_object_hash
// computed, confidence from optional JSON field (default 0.7), observed_at=now).
// The run() orchestrator fills
// holder_id/holder_tenant_id/chunk_index/source_hash.
ParseResult parse_extractor_json(
    std::string_view raw_json,
    const ExistingRefMap& existing_ref_map);

}  // namespace starling::extractor
