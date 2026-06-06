#include "starling/extractor/json_parser.hpp"

#include "starling/schema/canonicalize.hpp"
#include "starling/schema/statement_enums.hpp"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cctype>
#include <chrono>
#include <ctime>
#include <string>

namespace starling::extractor {
namespace {

std::string to_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return s;
}

// Map the prompt's modality vocabulary onto the C++ Modality enum strings.
// The eval prompt emits e.g. ENFORCES / OBSERVES which are not enum members;
// fold them onto the closest supported value. Unknown values fall through and
// modality_from_string throws (caught per-element).
std::string normalize_modality(std::string m) {
    m = to_lower(m);
    if (m == "enforces") return "norm_ought";
    if (m == "forbids")  return "norm_forbid";
    if (m == "observes") return "knows";
    return m;
}

std::string now_iso8601_utc() {
    const auto now = std::chrono::system_clock::now();
    const std::time_t t = std::chrono::system_clock::to_time_t(now);
    std::tm tm{};
#if defined(_WIN32)
    gmtime_s(&tm, &t);
#else
    gmtime_r(&t, &tm);
#endif
    char buf[32];
    std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm);
    return std::string(buf);
}

// Strip a leading ```json / ``` fence and locate the first '[' .. last ']'.
// A bare "[]" yields a valid empty array (zero statements, zero errors); a
// response with no brackets yields an empty view (caller emits not_json_array).
std::string_view extract_array(std::string_view raw) {
    const auto lb = raw.find('[');
    const auto rb = raw.rfind(']');
    if (lb == std::string_view::npos || rb == std::string_view::npos || rb < lb) {
        return {};
    }
    return raw.substr(lb, rb - lb + 1);
}

}  // namespace

ParseResult parse_extractor_json(
    std::string_view raw_json,
    const ExistingRefMap& /*existing_ref_map*/) {
    ParseResult result;

    const std::string_view arr_text = extract_array(raw_json);
    if (arr_text.empty()) {
        result.errors.push_back({"not_json_array", "no top-level JSON array found", 0});
        return result;
    }

    nlohmann::json arr;
    try {
        arr = nlohmann::json::parse(arr_text);
    } catch (const std::exception& e) {
        result.errors.push_back({"json_parse_error", e.what(), 0});
        return result;
    }
    if (!arr.is_array()) {
        result.errors.push_back({"not_json_array", "top level is not an array", 0});
        return result;
    }

    for (const auto& el : arr) {
        if (!el.is_object()) continue;  // lenient: skip non-objects
        try {
            ExtractedStatement s;
            // NOTE: holder_id is NOT set here — Extractor::run overrides it with
            // the run arg (the agent, e.g. "self"), matching the existing XML path.
            // The LLM "holder" field is advisory; multi-holder attribution is
            // deferred (out-of-scope).
            s.holder_perspective = schema::perspective_from_string(
                to_lower(el.value("holder_perspective", std::string("inferred"))));
            s.subject_kind = "cognizer";
            s.subject_id   = el.value("subject", std::string());
            s.predicate    = el.value("predicate", std::string());
            s.object_value = el.value("object", std::string());
            // nesting_depth>=2 -> object_kind="statement", else "str".
            // value<int> coerces a JSON float (2.0->2) and defaults a non-number
            // (string/bool/absent) to 0 -> "str", the safe default.
            const int nesting_depth = el.value("nesting_depth", 0);
            s.object_kind  = (nesting_depth >= 2) ? "statement" : "str";
            if (s.subject_id.empty() || s.predicate.empty() || s.object_value.empty()) {
                continue;  // lenient: skip incomplete element
            }
            // canonical_object_hash is COMPUTED C++-side (never trusted from LLM);
            // object_value stays the raw object text (matches the old XML path).
            const schema::CanonicalResult cr =
                schema::canonicalize_object(schema::CanonicalInput{std::string(s.object_value)});
            s.canonical_object_hash = cr.sha256_hex;
            s.modality   = schema::modality_from_string(
                normalize_modality(el.value("modality", std::string("believes"))));
            s.polarity   = schema::polarity_from_string(
                to_lower(el.value("polarity", std::string("pos"))));
            s.confidence = 0.7;
            s.observed_at = now_iso8601_utc();
            result.statements.push_back(std::move(s));
        } catch (const std::exception&) {
            continue;  // lenient: bad enum / shape -> skip this element
        }
    }
    return result;
}

}  // namespace starling::extractor
