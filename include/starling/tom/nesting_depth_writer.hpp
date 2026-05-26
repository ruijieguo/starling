#pragma once
#include "starling/persistence/connection.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include <stdexcept>

namespace starling::tom {

class NestingDepthOverflow : public std::runtime_error {
public:
    int computed_depth;
    explicit NestingDepthOverflow(int d)
        : std::runtime_error("nesting_depth > 2 hard limit (P2.a)"),
          computed_depth(d) {}
};

namespace nesting_depth_writer {
    // Returns 0 if object_kind != "statement";
    // returns parent.nesting_depth + 1 otherwise (parent looked up by id = object_value);
    // throws NestingDepthOverflow if computed_depth > 2.
    // Throws std::runtime_error if parent not found (parent must be written first).
    int compute_nesting_depth(
        persistence::Connection& conn,
        const extractor::ExtractedStatement& s);
}

}  // namespace starling::tom
