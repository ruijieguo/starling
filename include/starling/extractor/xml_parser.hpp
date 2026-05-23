#pragma once

#include "starling/extractor/existing_ref_map.hpp"
#include "starling/extractor/extracted_statement.hpp"

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

namespace starling::extractor {

struct ParseError {
    std::string kind;          // e.g. "unknown_tag", "missing_required_attribute"
    std::string detail;        // free text for human consumers
    std::size_t byte_offset;   // approximate; 0 if unknown
};

struct ParseResult {
    std::vector<ExtractedStatement> statements;
    std::vector<ParseError>         errors;
};

// Strict-mode parser for the M0.4 extractor XML schema. Single root
// <extraction>, with 0..N <statement> children. Unknown tags, missing
// required attributes, malformed nesting, unresolved short ids in
// <statement_ref id="..."/> objects, and unsupported value kinds (list,
// dict, anything not in {bool,int,float,str,datetime,cognizer,entity,
// statement}) all produce ParseError entries. The parser does not throw;
// all failures travel through ParseResult.errors so the caller (extractor
// orchestrator) can record them as rejected_fragments without unwinding.
ParseResult parse_extractor_xml(
    std::string_view raw_xml,
    const ExistingRefMap& existing_ref_map);

}  // namespace starling::extractor
