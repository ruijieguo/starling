#include "claim_scope.hpp"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <cstdint>
#include <set>
#include <vector>

namespace starling::extractor {
namespace {
bool letter(char c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'); }
bool digit(char c) { return c >= '0' && c <= '9'; }
bool word(char c) { return letter(c) || digit(c) || c == '_'; }
bool space(char c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; }
std::size_t space_width(std::string_view s, std::size_t i) {
    if (space(s[i])) { return 1;
}
    if (s.substr(i).starts_with(" ")) { return 2;
}
    if (s.substr(i).starts_with("　")) { return 3;
}
    return 0;
}
std::string fold(std::string_view s) {
    std::string result(s);
    for (auto& c : result) if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
    return result;
}
bool contains(std::string_view s, std::initializer_list<std::string_view> values) {
    return std::any_of(values.begin(), values.end(), [&](auto v) { return s.find(v) != s.npos; });
}
std::vector<std::string> words(std::string_view s) {
    std::vector<std::string> result;
    for (std::size_t i = 0; i < s.size();) {
        if (!letter(s[i])) { ++i; continue; }
        const auto start = i++;
        while (i < s.size() && letter(s[i])) { ++i;
}
        result.push_back(fold(s.substr(start, i - start)));
    }
    return result;
}
bool any_word(std::string_view s, const std::set<std::string>& values) {
    for (const auto& w : words(s)) if (values.contains(w)) return true;
    return false;
}
// JSON/source_units 已校验 UTF-8；只识别汉字相邻片段，用于保守碰撞回退。
std::set<std::string> han_pairs(std::string_view s) {
    std::set<std::string> result;
    std::string previous;
    for (std::size_t i = 0; i < s.size();) {
        auto c = static_cast<unsigned char>(s[i]);
        const std::size_t width = c < 0x80 ? 1 : c < 0xE0 ? 2 : c < 0xF0 ? 3 : 4;
        if (i + width > s.size()) { break;
}
        std::uint32_t cp = c & (width == 1 ? 0x7F : width == 2 ? 0x1F : width == 3 ? 0x0F : 0x07);
        for (std::size_t k = 1; k < width; ++k) { cp = (cp << 6) | (static_cast<unsigned char>(s[i+k]) & 0x3F);
}
        const bool han = (cp >= 0x3400 && cp <= 0x9FFF) || (cp >= 0x20000 && cp <= 0x3134F);
        if (han) {
            const std::string current(s.substr(i,width));
            if (!previous.empty()) { result.insert(previous+current);
}
            previous=current;
        } else { previous.clear();
}
        i += width;
    }
    return result;
}
struct Sentence { std::size_t begin, end; bool question; };
// 受限边界扫描；不尝试恢复引号、缩写、代码或跨行歧义。
bool sentences(std::string_view s, std::size_t begin, std::vector<Sentence>& out) {
    static const std::set<std::string> abbreviations{
        "mr","mrs","ms","dr","prof","sr","jr","st","vs","etc","e","g","i"};
    std::size_t start=begin;
    while (start < s.size()) {
        if (s[start]=='\n' || s[start]=='\r') { return false;
}
        const auto n=space_width(s,start);
        if (!n) { break;
}
        start+=n;
    }
    for (std::size_t i=start; i<s.size();) {
        const auto rest=s.substr(i);
        if (contains(rest.substr(0,1),{"\n","\r","\"","`","(",")","[","]","{","}",":","@","\\"}) ||
            rest.starts_with("“") || rest.starts_with("”") || rest.starts_with("‘") || rest.starts_with("’") ||
            rest.starts_with("（") || rest.starts_with("）") || rest.starts_with("：") ||
            rest.starts_with("「") || rest.starts_with("」") || rest.starts_with("…")) { return false;
}
        if (s[i]=='\'' && !(i>0 && i+1<s.size() && letter(s[i-1]) && letter(s[i+1]))) { return false;
}
        std::size_t width=0;
        const bool question=s[i]=='?' || rest.starts_with("？");
        if (s[i]=='.' || s[i]=='!' || s[i]=='?') { width=1;
        } else if (rest.starts_with("。") || rest.starts_with("！") || rest.starts_with("？")) { width=3;
}
        if (!width) { ++i; continue; }
        if (i==start) { return false; // 连续标点或没有内容。
}
        if (s[i]=='.') {
            if ((i+1<s.size() && !space_width(s,i+1)) || (i>0 && digit(s[i-1]))) { return false;
}
            std::size_t w=i;
            while (w>start && letter(s[w-1])) { --w;
}
            const auto token=fold(s.substr(w,i-w));
            if (abbreviations.contains(token) || token.size()==1) { return false;
}
        }
        out.push_back({start,i+width,question});
        i+=width;
        while (i<s.size()) {
            if (s[i]=='\n' || s[i]=='\r') { return false;
}
            const auto n=space_width(s,i); if (!n) { break; }
            i+=n;
        }
        start=i;
    }
    // 未闭合尾文可能是省略问句或撤回，不能作为普通陈述跳过。
    if (start<s.size()) { return false;
}
    return !out.empty();
}
bool overlap(std::string_view question, std::string_view object) {
    if (question.find(object)!=question.npos) { return true;
}
    const auto qs=words(question);
    for (const auto& token:words(object))
        if (token.size()>=4 && std::find(qs.begin(),qs.end(),token)!=qs.end()) return true;
    const auto pairs=han_pairs(question);
    for (const auto& pair:han_pairs(object)) if (pairs.contains(pair)) return true;
    return false;
}
}

ClaimScopeResolution resolve_claim_question_scope(
        std::string_view source, std::string_view coordinate_space,
        const nlohmann::json& row, const nlohmann::json& evidence, bool source_self_report) {
    ClaimScopeResolution result;
    result.coordinate_space=coordinate_space;
    result.clause_id=evidence.at("clause_id").get<std::string>();
    auto fallback=[&](const char* reason) { result.reason=reason; return result; };
    if (!contains(source,{"?","？"})) { return fallback("no_question");
}
    if (row.at("holder_perspective")!="FIRST_PERSON" || row.at("polarity")!="POS" ||
        evidence.at("scope_markers")!=nlohmann::json::array({"ASSERTED"})) { return fallback("ineligible_claim");
}
    std::size_t begin=0;
    while (begin<source.size() && space_width(source,begin)) {
        if (source[begin]=='\n' || source[begin]=='\r') { return fallback("ambiguous_boundary");
}
        begin+=space_width(source,begin);
    }
    const auto holder=row.at("holder").get<std::string>();
    bool prefix=false;
    if (coordinate_space=="source_unit_text_utf8") {
        for (const auto* colon:{":","："}) {
            const auto header=holder+colon;
            if (source.substr(begin).starts_with(header)) { begin+=header.size(); prefix=true; break; }
        }
    }
    if (!source_self_report && !prefix) { return fallback("unverified_speaker");
}
    const auto object=row.at("object").get<std::string>();
    if (object.empty()) { return fallback("object_not_literal");
}
    std::vector<std::size_t> matches;
    for (auto p=source.find(object); p!=source.npos; p=source.find(object,p+1)) {
        if (word(object.front()) && p>0 && word(source[p-1])) { continue;
}
        if (word(object.back()) && p+object.size()<source.size() && word(source[p+object.size()])) { continue;
}
        matches.push_back(p);
    }
    if (matches.empty()) { return fallback("object_not_literal");
}
    if (matches.size()!=1) { return fallback("ambiguous_object");
}
    std::vector<Sentence> spans;
    if (!sentences(source,begin,spans)) { return fallback("ambiguous_boundary");
}
    const auto& leading=spans.front();
    if (matches.front()<leading.begin || matches.front()+object.size()>leading.end) {
        return fallback("nonleading_object");
}
    if (leading.question || spans.size()<2) { return fallback("context_dependency");
}
    const auto local=source.substr(leading.begin,leading.end-leading.begin);
    static const std::set<std::string> question_openers{
        "am","are","is","was","were","do","does","did","can","could","will","would",
        "should","shall","may","might","have","has","what","why","how","when","where","who","whether"};
    const auto leading_words=words(local);
    if ((!leading_words.empty() && question_openers.contains(leading_words.front())) ||
        local.starts_with("请问") || local.starts_with("是否")) { return fallback("context_dependency");
}
    for (const auto* field:{"topic","time_text"}) {
        if (evidence.contains(field) && evidence[field].is_string() &&
            local.find(evidence[field].get<std::string>())==local.npos) return fallback("context_dependency");
    }
    if (evidence["event_time"].is_object()) for (const auto* field:{"start","end"}) {
        if (evidence["event_time"][field].is_string() &&
            local.find(evidence["event_time"][field].get<std::string>())==local.npos) return fallback("context_dependency");
    }
    static const std::set<std::string> bare{"it","that","this","those","these","either way","这","那个"};
    static const std::set<std::string> global_risk{
        "if","unless","imagine","suppose","hypothetically","said","says","reported",
        "not","never","joking","kidding"};
    const auto content=source.substr(begin);
    const auto lowered=fold(content);
    if (bare.contains(fold(object)) || any_word(content,global_risk) ||
        contains(lowered,{"provided that","according to","told me","n't","just imagining"}) ||
        contains(content,{"如果","假如","要是","除非","只要","假设","设想","据说","表示",
                          "不","没","无","开玩笑","更正","撤回"})) { return fallback("context_dependency");
}
    static const std::set<std::string> backrefs{"i","me","my","mine","myself","it","this","that","these","those","them","so"};
    for (std::size_t n=1;n<spans.size();++n) {
        if (!spans[n].question) { continue;
}
        const auto q=source.substr(spans[n].begin,spans[n].end-spans[n].begin);
        if (any_word(q,backrefs) || contains(q,{"我","这","那","上述","刚才","如此"}) || overlap(q,object)) {
            return fallback("context_dependency");
}
        if (evidence.contains("topic") && evidence["topic"].is_string() &&
            q.find(evidence["topic"].get<std::string>())!=q.npos) { return fallback("context_dependency");
}
        const auto tokens=words(q);
        const bool english=tokens.size()>=3 && tokens[1]=="you" &&
            (tokens[0]=="do" || tokens[0]=="can" || tokens[0]=="could" || tokens[0]=="will" || tokens[0]=="would") &&
            fold(q).starts_with(tokens[0]+" you ");
        if (!english && !q.starts_with("请问")) { return fallback("unsupported_question_form");
}
    }
    result.mode="leading_statement";
    result.reason="unique_leading_statement";
    result.begin=leading.begin;
    result.end=leading.end;
    return result;
}
}
