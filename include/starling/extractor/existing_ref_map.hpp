#pragma once

#include <map>
#include <string>

namespace starling::extractor {

// short_id ("s1") -> StatementRef.id (UUID). M0.4 always passes an empty
// map from the production extractor path; the XML parser still handles
// <statement_ref id="s1"/> by emitting an unresolved_short_id error when
// the map is empty. M0.6 (basic_retrieve) will populate this with
// recent-Statement candidates so the LLM can reference them by short id
// without hallucinating long UUIDs.
using ExistingRefMap = std::map<std::string, std::string>;

}  // namespace starling::extractor
