#pragma once
#include "starling/persistence/connection.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include <stdexcept>
#include <string>

namespace starling::tom {

class NestingDepthOverflow : public std::runtime_error {
public:
    int computed_depth;
    explicit NestingDepthOverflow(int d)
        : std::runtime_error(
              "nesting_depth exceeds configured max_nesting_depth (runaway guard)"),
          computed_depth(d) {}
};

class NestingCycle : public std::runtime_error {
public:
    std::string cycle_id;  // the statement id revisited while walking ancestors
    explicit NestingCycle(std::string id)
        : std::runtime_error("nested-belief object_value chain contains a cycle"),
          cycle_id(std::move(id)) {}
};

namespace nesting_depth_writer {
    // Default soft ceiling on nesting depth (max_nesting_depth). Surfacing this
    // to runtime config is a follow-up — kept as a named constant for now.
    // 0 => unbounded (the cycle guard still applies).
    inline constexpr int kDefaultMaxNestingDepth = 32;

    // Returns 0 if object_kind != "statement". Otherwise walks the object_value
    // ancestor chain to a flat (non-statement) leaf, returning the chain length
    // (== parent.nesting_depth + 1). Throws NestingCycle if an id repeats on the
    // walk; throws NestingDepthOverflow if the chain length exceeds max_depth
    // (when max_depth > 0); throws std::runtime_error if a parent is missing.
    int compute_nesting_depth(
        persistence::Connection& conn,
        const extractor::ExtractedStatement& s,
        int max_depth = kDefaultMaxNestingDepth);
}

}  // namespace starling::tom
