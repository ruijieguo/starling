#include "starling/schema/statement_enums.hpp"
#include <gtest/gtest.h>

#include <algorithm>
#include <cctype>
#include <string>

using namespace starling::schema;

TEST(OccurredModality, RoundTrips) {
    EXPECT_EQ(to_string(Modality::OCCURRED), "occurred");
    EXPECT_EQ(modality_from_string("occurred"), Modality::OCCURRED);
}

// Task 1.2: the extractor's JSON parser emits UPPER-case modality strings
// (e.g. "BELIEVES") and lowercases them generically before calling
// modality_from_string (src/extractor/json_parser.cpp: to_lower /
// normalize_modality). Mirror that lowercasing here to prove an upper-case
// "OCCURRED" from extraction resolves to Modality::OCCURRED with no
// parser-specific aliasing needed.
TEST(OccurredModality, ExtractorUpperCaseLowercasesToOccurred) {
    std::string m = "OCCURRED";
    std::transform(m.begin(), m.end(), m.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    EXPECT_EQ(m, "occurred");
    EXPECT_EQ(modality_from_string(m), Modality::OCCURRED);
}
