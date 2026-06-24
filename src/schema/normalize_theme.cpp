#include "starling/schema/normalize_theme.hpp"
#include <array>
#include <cctype>
#include <utility>
namespace starling::schema {
namespace {
std::string to_lower(std::string_view s) {
    std::string o; o.reserve(s.size());
    for (char c : s) o.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
    return o;
}
bool ends_with(const std::string& s, std::string_view suf) {
    return s.size() >= suf.size() && s.compare(s.size() - suf.size(), suf.size(), suf) == 0;
}
// irregular plural → singular (lowercase keys)
constexpr std::array<std::pair<std::string_view, std::string_view>, 6> kIrregular = {{
    {"leaves", "leaf"}, {"knives", "knife"}, {"lives", "life"},
    {"wolves", "wolf"}, {"shelves", "shelf"}, {"children", "child"},
}};
// words that look like plurals but are NOT — leave entirely unchanged
bool is_uninflected(const std::string& s) {
    // -ss, -us, -is suffixes are not plurals; explicit stoplist for ambiguous forms
    return ends_with(s, "ss") || ends_with(s, "us") || ends_with(s, "is") ||
           s == "bus" || s == "lens" || s == "series" || s == "species" || s == "news";
}
std::string singularize(const std::string& w) {
    if (is_uninflected(w)) return w;   // stoplist check first — before any suffix rule
    for (const auto& [pl, sg] : kIrregular) if (w == pl) return std::string(sg);
    if (w.size() > 3 && ends_with(w, "ies")) return w.substr(0, w.size() - 3) + "y";
    if (w.size() > 3 && ends_with(w, "es")) {
        const std::string stem = w.substr(0, w.size() - 2);
        if (ends_with(stem, "s") || ends_with(stem, "x") || ends_with(stem, "z") ||
            ends_with(stem, "ch") || ends_with(stem, "sh") || ends_with(stem, "o"))
            return stem;
    }
    if (w.size() > 1 && ends_with(w, "s")) return w.substr(0, w.size() - 1);
    return w;
}
}  // namespace

std::string normalize_theme(std::string_view surface) {
    std::string s = to_lower(surface);
    while (!s.empty() && std::isspace(static_cast<unsigned char>(s.front()))) s.erase(s.begin());
    while (!s.empty() && std::isspace(static_cast<unsigned char>(s.back()))) s.pop_back();
    bool stripped = true;
    while (stripped) {
        stripped = false;
        for (std::string_view det : {"the ", "a ", "an ", "all ", "both ", "some "}) {
            if (s.size() > det.size() && s.compare(0, det.size(), det) == 0) {
                s = s.substr(det.size());
                while (!s.empty() && std::isspace(static_cast<unsigned char>(s.front()))) s.erase(s.begin());
                stripped = true;
                break;
            }
        }
    }
    return singularize(s);
}
}  // namespace starling::schema
