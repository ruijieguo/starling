#include "starling/schema/statement_enums.hpp"

#include <stdexcept>
#include <string>

namespace starling::schema {

std::string_view to_string(Perspective p) {
    switch (p) {
        case Perspective::FIRST_PERSON: return "first_person";
        case Perspective::QUOTED:       return "quoted";
        case Perspective::INFERRED:     return "inferred";
        case Perspective::HEARSAY:      return "hearsay";
    }
    throw std::invalid_argument("unknown Perspective");
}

std::string_view to_string(Modality m) {
    switch (m) {
        case Modality::BELIEVES:    return "believes";
        case Modality::KNOWS:       return "knows";
        case Modality::ASSUMES:     return "assumes";
        case Modality::DOUBTS:      return "doubts";
        case Modality::DESIRES:     return "desires";
        case Modality::INTENDS:     return "intends";
        case Modality::COMMITS:     return "commits";
        case Modality::PREFERS:     return "prefers";
        case Modality::NORM_OUGHT:  return "norm_ought";
        case Modality::NORM_FORBID: return "norm_forbid";
        case Modality::RECANTED:    return "recanted";
    }
    throw std::invalid_argument("unknown Modality");
}

std::string_view to_string(Polarity p) {
    switch (p) {
        case Polarity::POS:     return "pos";
        case Polarity::NEG:     return "neg";
        case Polarity::UNKNOWN: return "unknown";
    }
    throw std::invalid_argument("unknown Polarity");
}

std::string_view to_string(ConsolidationState s) {
    switch (s) {
        case ConsolidationState::VOLATILE:                  return "volatile";
        case ConsolidationState::REPLAYING_CONSOLIDATING:   return "replaying_consolidating";
        case ConsolidationState::REPLAYING_RECONSOLIDATING: return "replaying_reconsolidating";
        case ConsolidationState::CONSOLIDATED:              return "consolidated";
        case ConsolidationState::ARCHIVED:                  return "archived";
        case ConsolidationState::FORGOTTEN:                 return "forgotten";
    }
    throw std::invalid_argument("unknown ConsolidationState");
}

std::string_view to_string(ReviewStatus r) {
    switch (r) {
        case ReviewStatus::APPROVED:            return "approved";
        case ReviewStatus::PENDING_REVIEW:      return "pending_review";
        case ReviewStatus::INFERRED_UNREVIEWED: return "inferred_unreviewed";
        case ReviewStatus::REVIEW_REQUESTED:    return "review_requested";
        case ReviewStatus::REJECTED:            return "rejected";
    }
    throw std::invalid_argument("unknown ReviewStatus");
}

std::string_view to_string(StatementProvenance p) {
    switch (p) {
        case StatementProvenance::USER_INPUT:              return "user_input";
        case StatementProvenance::REPLAY_DERIVED:          return "replay_derived";
        case StatementProvenance::TOM_INFERRED:            return "tom_inferred";
        case StatementProvenance::RECONSOLIDATION_DERIVED: return "reconsolidation_derived";
    }
    throw std::invalid_argument("unknown StatementProvenance");
}

Perspective perspective_from_string(std::string_view s) {
    if (s == "first_person") return Perspective::FIRST_PERSON;
    if (s == "quoted")       return Perspective::QUOTED;
    if (s == "inferred")     return Perspective::INFERRED;
    if (s == "hearsay")      return Perspective::HEARSAY;
    throw std::invalid_argument(std::string("unknown Perspective: ") + std::string(s));
}

Modality modality_from_string(std::string_view s) {
    if (s == "believes")    return Modality::BELIEVES;
    if (s == "knows")       return Modality::KNOWS;
    if (s == "assumes")     return Modality::ASSUMES;
    if (s == "doubts")      return Modality::DOUBTS;
    if (s == "desires")     return Modality::DESIRES;
    if (s == "intends")     return Modality::INTENDS;
    if (s == "commits")     return Modality::COMMITS;
    if (s == "prefers")     return Modality::PREFERS;
    if (s == "norm_ought")  return Modality::NORM_OUGHT;
    if (s == "norm_forbid") return Modality::NORM_FORBID;
    if (s == "recanted")    return Modality::RECANTED;
    throw std::invalid_argument(std::string("unknown Modality: ") + std::string(s));
}

Polarity polarity_from_string(std::string_view s) {
    if (s == "pos")     return Polarity::POS;
    if (s == "neg")     return Polarity::NEG;
    if (s == "unknown") return Polarity::UNKNOWN;
    throw std::invalid_argument(std::string("unknown Polarity: ") + std::string(s));
}

ConsolidationState consolidation_state_from_string(std::string_view s) {
    if (s == "volatile")                  return ConsolidationState::VOLATILE;
    if (s == "replaying_consolidating")   return ConsolidationState::REPLAYING_CONSOLIDATING;
    if (s == "replaying_reconsolidating") return ConsolidationState::REPLAYING_RECONSOLIDATING;
    if (s == "consolidated")              return ConsolidationState::CONSOLIDATED;
    if (s == "archived")                  return ConsolidationState::ARCHIVED;
    if (s == "forgotten")                 return ConsolidationState::FORGOTTEN;
    throw std::invalid_argument(std::string("unknown ConsolidationState: ") + std::string(s));
}

ReviewStatus review_status_from_string(std::string_view s) {
    if (s == "approved")            return ReviewStatus::APPROVED;
    if (s == "pending_review")      return ReviewStatus::PENDING_REVIEW;
    if (s == "inferred_unreviewed") return ReviewStatus::INFERRED_UNREVIEWED;
    if (s == "review_requested")    return ReviewStatus::REVIEW_REQUESTED;
    if (s == "rejected")            return ReviewStatus::REJECTED;
    throw std::invalid_argument(std::string("unknown ReviewStatus: ") + std::string(s));
}

StatementProvenance provenance_from_string(std::string_view s) {
    if (s == "user_input")              return StatementProvenance::USER_INPUT;
    if (s == "replay_derived")          return StatementProvenance::REPLAY_DERIVED;
    if (s == "tom_inferred")            return StatementProvenance::TOM_INFERRED;
    if (s == "reconsolidation_derived") return StatementProvenance::RECONSOLIDATION_DERIVED;
    throw std::invalid_argument(std::string("unknown StatementProvenance: ") + std::string(s));
}

}  // namespace starling::schema
