#include "starling/final_query_assertion.hpp"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <string>

namespace starling {
namespace {

// NOTE: only `--` line comments are stripped. Block `/* ... */` comments are
// passed through unchanged — see header LIMITATIONS for rationale.
std::string strip_line_comments(std::string_view sql) {
    std::string out;
    out.reserve(sql.size());
    size_t i = 0;
    while (i < sql.size()) {
        if (i + 1 < sql.size() && sql[i] == '-' && sql[i + 1] == '-') {
            while (i < sql.size() && sql[i] != '\n') {
                ++i;
            }
        } else {
            out.push_back(sql[i]);
            ++i;
        }
    }
    return out;
}

std::string to_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return s;
}

}  // namespace

bool is_final_query_safe(std::string_view sql) noexcept {
    const std::string lowered = to_lower(strip_line_comments(sql));
    const bool has_tenant = lowered.find("tenant_id") != std::string::npos;
    const bool has_holder = lowered.find("holder_scope") != std::string::npos;
    return has_tenant && has_holder;
}

void assert_final_query_safe(std::string_view sql) {
    const std::string lowered = to_lower(strip_line_comments(sql));
    const bool has_tenant = lowered.find("tenant_id") != std::string::npos;
    const bool has_holder = lowered.find("holder_scope") != std::string::npos;
    if (has_tenant && has_holder) {
        return;
    }
    std::ostringstream msg;
    msg << "final query missing required guard predicates:";
    if (!has_tenant) {
        msg << " tenant_id";
    }
    if (!has_holder) {
        msg << " holder_scope";
    }
    throw FinalQueryAssertionError(msg.str());
}

}  // namespace starling
