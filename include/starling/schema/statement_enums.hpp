#pragma once

#include <stdexcept>
#include <string_view>

namespace starling::schema {

// All Statement-side enums mirror python/starling/schema/enums.py. The
// (string_view) values returned by to_string() and the values accepted by
// *_from_string() must match the Python StrEnum values byte-for-byte; the
// parity is asserted by tests/cpp/test_statement_enums.cpp and the Python
// side test tests/python/test_statement_enums_parity.py.

enum class Perspective {
    FIRST_PERSON,
    QUOTED,
    INFERRED,
    HEARSAY,
};

enum class Modality {
    BELIEVES,
    KNOWS,
    ASSUMES,
    DOUBTS,
    DESIRES,
    INTENDS,
    COMMITS,
    PREFERS,
    NORM_OUGHT,
    NORM_FORBID,
    RECANTED,
    OCCURRED,
};

enum class Polarity {
    POS,
    NEG,
    UNKNOWN,
};

enum class ConsolidationState {
    VOLATILE,
    REPLAYING_CONSOLIDATING,
    REPLAYING_RECONSOLIDATING,
    CONSOLIDATED,
    ARCHIVED,
    FORGOTTEN,
};

enum class ReviewStatus {
    APPROVED,
    PENDING_REVIEW,
    INFERRED_UNREVIEWED,
    REVIEW_REQUESTED,
    REJECTED,
};

enum class StatementProvenance {
    USER_INPUT,
    REPLAY_DERIVED,
    TOM_INFERRED,
    RECONSOLIDATION_DERIVED,
    CONSOLIDATION_ABSTRACT,   // #38-C: a NORM gist written by replay consolidation
};

std::string_view to_string(Perspective);
std::string_view to_string(Modality);
std::string_view to_string(Polarity);
std::string_view to_string(ConsolidationState);
std::string_view to_string(ReviewStatus);
std::string_view to_string(StatementProvenance);

Perspective         perspective_from_string(std::string_view);
Modality            modality_from_string(std::string_view);
Polarity            polarity_from_string(std::string_view);
ConsolidationState  consolidation_state_from_string(std::string_view);
ReviewStatus        review_status_from_string(std::string_view);
StatementProvenance provenance_from_string(std::string_view);

}  // namespace starling::schema
