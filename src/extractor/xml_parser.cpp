#include "starling/extractor/xml_parser.hpp"

#include "starling/schema/statement_enums.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstddef>
#include <set>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace starling::extractor {

namespace {

const std::set<std::string> kKnownTags = {
    "extraction", "statement", "holder", "perspective", "subject",
    "predicate", "object", "modality", "polarity", "confidence",
    "observed_at", "perceived_by", "statement_ref",
};

const std::set<std::string> kKnownObjectKinds = {
    "bool", "int", "float", "str", "datetime", "cognizer", "entity", "statement",
};

const std::set<std::string> kKnownPerspectives = {
    "first_person", "quoted", "hearsay", "inferred",
};

const std::set<std::string> kKnownSubjectKinds = {
    "cognizer", "entity",
};

// Maximum tokenizer nesting depth. Element owns std::vector<Element> children,
// so destroying a deeply-nested tree recurses through ~Element → ~vector →
// ~Element ... A pathologically nested LLM response could blow the C++ call
// stack on parse_extractor_xml return even though tokenization is iterative.
// 64 gives generous headroom (real schema nests ~3-4 deep) while protecting
// the stack from DoS-style malformed input.
constexpr std::size_t kMaxNestingDepth = 64;

struct Element {
    std::string                                  name;
    std::unordered_map<std::string, std::string> attrs;
    std::vector<Element>                         children;
    std::string                                  text;
    std::size_t                                  offset = 0;
};

bool is_space(char c) {
    return std::isspace(static_cast<unsigned char>(c)) != 0;
}

bool is_name_start(char c) {
    unsigned char u = static_cast<unsigned char>(c);
    return std::isalpha(u) || c == '_';
}

bool is_name_char(char c) {
    unsigned char u = static_cast<unsigned char>(c);
    return std::isalnum(u) || c == '_' || c == '-' || c == '.' || c == ':';
}

std::string trim(const std::string& s) {
    std::size_t b = 0;
    while (b < s.size() && is_space(s[b])) ++b;
    std::size_t e = s.size();
    while (e > b && is_space(s[e - 1])) --e;
    return s.substr(b, e - b);
}

// (1) Tokenize: produce vector<Element> from raw XML.
//     Pushes "unbalanced_tag" / "missing_required_attribute" into errors.
//     Tokenizer does NOT reject unknown tags — that's the validator's job.
std::vector<Element> tokenize(std::string_view xml,
                              std::vector<ParseError>& errors) {
    std::vector<Element> roots;
    std::vector<Element*> stack;  // pointers into the tree we're building
    std::string text_buf;          // accumulated text for the current element

    // Mixed-content detection: a single element should be either text-only
    // (e.g. <predicate>foo</predicate>) or container-only (e.g. <statement>
    // with element children). If non-empty trimmed text accumulates into a
    // container that already has element children, the LLM has produced
    // something like <predicate>foo<bar/>baz</predicate>, where naive merging
    // would yield "foobaz" with no separator. We surface this as a
    // "mixed_content" error so the validator/triage layer can reject the
    // fragment instead of silently losing structure.
    auto flush_text = [&](Element* container, std::size_t pos) {
        if (!container) {
            text_buf.clear();
            return;
        }
        std::string trimmed = trim(text_buf);
        if (!trimmed.empty()) {
            container->text += trimmed;
            if (!container->children.empty()) {
                errors.push_back({"mixed_content",
                                  "<" + container->name +
                                      "> has both text and child elements",
                                  pos});
            }
        }
        text_buf.clear();
    };

    auto append_child = [&](Element&& el) -> Element* {
        if (stack.empty()) {
            roots.push_back(std::move(el));
            return &roots.back();
        }
        Element* parent = stack.back();
        parent->children.push_back(std::move(el));
        return &parent->children.back();
    };

    std::size_t i = 0;
    const std::size_t n = xml.size();

    while (i < n) {
        if (xml[i] != '<') {
            text_buf.push_back(xml[i]);
            ++i;
            continue;
        }

        // Encountered '<'. Flush text into current container.
        Element* current = stack.empty() ? nullptr : stack.back();
        flush_text(current, i);

        // Comment <!-- ... -->
        if (i + 3 < n && xml.compare(i, 4, "<!--") == 0) {
            std::size_t end = xml.find("-->", i + 4);
            if (end == std::string_view::npos) {
                errors.push_back({"unbalanced_tag", "unterminated comment", i});
                return roots;
            }
            i = end + 3;
            continue;
        }

        // CDATA <![CDATA[ ... ]]>
        if (i + 8 < n && xml.compare(i, 9, "<![CDATA[") == 0) {
            std::size_t end = xml.find("]]>", i + 9);
            if (end == std::string_view::npos) {
                errors.push_back({"unbalanced_tag", "unterminated CDATA", i});
                return roots;
            }
            text_buf.append(xml.data() + i + 9, end - (i + 9));
            i = end + 3;
            continue;
        }

        // Processing instruction <? ... ?> or XML declaration <?xml ... ?>
        if (i + 1 < n && xml[i + 1] == '?') {
            std::size_t end = xml.find("?>", i + 2);
            if (end == std::string_view::npos) {
                errors.push_back({"unbalanced_tag", "unterminated processing instruction", i});
                return roots;
            }
            i = end + 2;
            continue;
        }

        // DOCTYPE / other <!...>
        if (i + 1 < n && xml[i + 1] == '!') {
            std::size_t end = xml.find('>', i + 2);
            if (end == std::string_view::npos) {
                errors.push_back({"unbalanced_tag", "unterminated declaration", i});
                return roots;
            }
            i = end + 1;
            continue;
        }

        // Closing tag </name>
        if (i + 1 < n && xml[i + 1] == '/') {
            std::size_t name_start = i + 2;
            std::size_t j = name_start;
            while (j < n && is_name_char(xml[j])) ++j;
            std::string close_name(xml.data() + name_start, j - name_start);
            // Skip optional trailing whitespace before '>'
            while (j < n && is_space(xml[j])) ++j;
            if (j >= n || xml[j] != '>') {
                errors.push_back({"unbalanced_tag", "malformed closing tag", i});
                return roots;
            }
            if (stack.empty()) {
                errors.push_back({"unbalanced_tag", "closing tag with no open: " + close_name, i});
                return roots;
            }
            if (stack.back()->name != close_name) {
                errors.push_back({"unbalanced_tag",
                                  "mismatched close: expected </" + stack.back()->name +
                                      "> got </" + close_name + ">",
                                  i});
                return roots;
            }
            stack.pop_back();
            i = j + 1;
            continue;
        }

        // Opening tag <name attrs...> or self-closing <name attrs.../>
        std::size_t tag_offset = i;
        std::size_t j = i + 1;
        if (j >= n || !is_name_start(xml[j])) {
            errors.push_back({"unbalanced_tag", "malformed opening tag", i});
            return roots;
        }
        std::size_t name_start = j;
        while (j < n && is_name_char(xml[j])) ++j;
        std::string tag_name(xml.data() + name_start, j - name_start);

        Element el;
        el.name = tag_name;
        el.offset = tag_offset;

        // Parse attributes.
        bool self_closing = false;
        bool tag_done = false;
        while (j < n && !tag_done) {
            // Skip whitespace.
            while (j < n && is_space(xml[j])) ++j;
            if (j >= n) {
                errors.push_back({"unbalanced_tag", "unterminated opening tag", tag_offset});
                return roots;
            }
            if (xml[j] == '>') {
                ++j;
                tag_done = true;
                break;
            }
            if (xml[j] == '/' && j + 1 < n && xml[j + 1] == '>') {
                self_closing = true;
                j += 2;
                tag_done = true;
                break;
            }
            // Attribute name.
            if (!is_name_start(xml[j])) {
                errors.push_back({"unbalanced_tag", "malformed attribute name", j});
                return roots;
            }
            std::size_t aname_start = j;
            while (j < n && is_name_char(xml[j])) ++j;
            std::string attr_name(xml.data() + aname_start, j - aname_start);

            // Allow optional whitespace, then '='.
            while (j < n && is_space(xml[j])) ++j;
            if (j >= n || xml[j] != '=') {
                errors.push_back({"unbalanced_tag", "attribute missing '=': " + attr_name, j});
                return roots;
            }
            ++j;
            while (j < n && is_space(xml[j])) ++j;
            if (j >= n || (xml[j] != '"' && xml[j] != '\'')) {
                errors.push_back({"unbalanced_tag", "attribute value not quoted: " + attr_name, j});
                return roots;
            }
            char quote = xml[j];
            ++j;
            std::size_t aval_start = j;
            while (j < n && xml[j] != quote) ++j;
            if (j >= n) {
                errors.push_back({"unbalanced_tag", "unterminated attribute value: " + attr_name, j});
                return roots;
            }
            std::string attr_value(xml.data() + aval_start, j - aval_start);
            ++j;  // consume closing quote
            el.attrs[attr_name] = std::move(attr_value);
        }

        if (!tag_done) {
            errors.push_back({"unbalanced_tag", "unterminated opening tag", tag_offset});
            return roots;
        }

        if (self_closing) {
            append_child(std::move(el));
        } else {
            // Cap nesting depth: Element's recursive destructor would otherwise
            // stack-overflow on pathologically nested LLM output. The schema
            // only nests ~3-4 deep in practice, so 64 is generous headroom.
            if (stack.size() >= kMaxNestingDepth) {
                errors.push_back({"nesting_too_deep",
                                  "exceeded max nesting depth (64)",
                                  i});
                return roots;
            }
            Element* added = append_child(std::move(el));
            stack.push_back(added);
        }
        i = j;
    }

    // EOF: any trailing text in current container is harmless (and trimmed).
    Element* current = stack.empty() ? nullptr : stack.back();
    flush_text(current, xml.size());

    if (!stack.empty()) {
        errors.push_back({"unbalanced_tag",
                          "unclosed tag at EOF: <" + stack.back()->name + ">",
                          xml.size()});
    }
    return roots;
}

// Helper: find first child by name. Returns nullptr if not found.
const Element* find_child(const Element& parent, const std::string& name) {
    for (const auto& c : parent.children) {
        if (c.name == name) return &c;
    }
    return nullptr;
}

// Helper: collect all children matching a name in document order.
std::vector<const Element*> find_all_children(const Element& parent,
                                              const std::string& name) {
    std::vector<const Element*> out;
    for (const auto& c : parent.children) {
        if (c.name == name) out.push_back(&c);
    }
    return out;
}

// Helper: return attribute value or empty string if absent.
const std::string* get_attr(const Element& el, const std::string& name) {
    auto it = el.attrs.find(name);
    if (it == el.attrs.end()) return nullptr;
    return &it->second;
}

// (2) Per-statement validator + extractor.
//     Validates each required tag, attribute, and value whitelist; resolves
//     short ids; returns a populated ExtractedStatement (or pushes errors and
//     returns whatever it has — caller suppresses partial result if errors).
ExtractedStatement extract_statement(const Element& stmt_elem,
                                     const ExistingRefMap& refs,
                                     std::vector<ParseError>& errors) {
    ExtractedStatement out;

    // First, scan children for any unknown tags.
    for (const auto& c : stmt_elem.children) {
        if (kKnownTags.find(c.name) == kKnownTags.end()) {
            errors.push_back({"unknown_tag",
                              "unknown tag inside <statement>: " + c.name,
                              c.offset});
        }
    }

    // <holder ref="..."/>
    if (const Element* holder = find_child(stmt_elem, "holder")) {
        if (const std::string* ref = get_attr(*holder, "ref"); ref && !ref->empty()) {
            out.holder_id = *ref;
        } else {
            errors.push_back({"missing_required_attribute",
                              "<holder> missing 'ref'",
                              holder->offset});
        }
    } else {
        errors.push_back({"missing_required_attribute",
                          "<statement> missing <holder>",
                          stmt_elem.offset});
    }

    // <perspective>...</perspective>
    if (const Element* persp = find_child(stmt_elem, "perspective")) {
        const std::string& v = persp->text;
        if (kKnownPerspectives.find(v) == kKnownPerspectives.end()) {
            errors.push_back({"invalid_enum_value",
                              "<perspective> has invalid value: " + v,
                              persp->offset});
        } else {
            out.holder_perspective = schema::perspective_from_string(v);
        }
    } else {
        errors.push_back({"missing_required_attribute",
                          "<statement> missing <perspective>",
                          stmt_elem.offset});
    }

    // <subject kind="..." id="..."/>
    if (const Element* subj = find_child(stmt_elem, "subject")) {
        const std::string* kind = get_attr(*subj, "kind");
        const std::string* id   = get_attr(*subj, "id");
        if (!kind || kind->empty()) {
            errors.push_back({"missing_required_attribute",
                              "<subject> missing 'kind'",
                              subj->offset});
        } else if (kKnownSubjectKinds.find(*kind) == kKnownSubjectKinds.end()) {
            errors.push_back({"invalid_enum_value",
                              "<subject kind=...> invalid value: " + *kind,
                              subj->offset});
        } else {
            out.subject_kind = *kind;
        }
        if (!id || id->empty()) {
            errors.push_back({"missing_required_attribute",
                              "<subject> missing 'id'",
                              subj->offset});
        } else {
            out.subject_id = *id;
        }
    } else {
        errors.push_back({"missing_required_attribute",
                          "<statement> missing <subject>",
                          stmt_elem.offset});
    }

    // <predicate>...</predicate>
    if (const Element* pred = find_child(stmt_elem, "predicate")) {
        if (pred->text.empty()) {
            errors.push_back({"missing_required_attribute",
                              "<predicate> empty",
                              pred->offset});
        } else {
            out.predicate = pred->text;
        }
    } else {
        errors.push_back({"missing_required_attribute",
                          "<statement> missing <predicate>",
                          stmt_elem.offset});
    }

    // <object kind="..." canonical_hash="...">...</object>
    if (const Element* obj = find_child(stmt_elem, "object")) {
        const std::string* kind = get_attr(*obj, "kind");
        const std::string* hash = get_attr(*obj, "canonical_hash");
        bool kind_ok = false;
        if (!kind || kind->empty()) {
            errors.push_back({"missing_required_attribute",
                              "<object> missing 'kind'",
                              obj->offset});
        } else if (kKnownObjectKinds.find(*kind) == kKnownObjectKinds.end()) {
            errors.push_back({"value_type_unsupported",
                              "<object kind=...> unsupported: " + *kind,
                              obj->offset});
        } else {
            out.object_kind = *kind;
            kind_ok = true;
        }
        if (!hash || hash->empty()) {
            errors.push_back({"missing_required_attribute",
                              "<object> missing 'canonical_hash'",
                              obj->offset});
        } else {
            out.canonical_object_hash = *hash;
        }
        if (kind_ok) {
            if (out.object_kind == "statement") {
                // Look for <statement_ref id="..."/> child. Any non-
                // <statement_ref> child is a strict-mode error.
                for (const auto& c : obj->children) {
                    if (c.name != "statement_ref") {
                        errors.push_back({"unknown_tag",
                                          "<object kind=\"statement\"> may only "
                                          "contain <statement_ref/>, got: " +
                                              c.name,
                                          c.offset});
                    }
                }
                const Element* sref = find_child(*obj, "statement_ref");
                if (!sref) {
                    errors.push_back({"missing_required_attribute",
                                      "<object kind=\"statement\"> missing <statement_ref/>",
                                      obj->offset});
                } else {
                    const std::string* sid = get_attr(*sref, "id");
                    if (!sid || sid->empty()) {
                        errors.push_back({"missing_required_attribute",
                                          "<statement_ref> missing 'id'",
                                          sref->offset});
                    } else {
                        auto it = refs.find(*sid);
                        if (it == refs.end()) {
                            errors.push_back({"unresolved_short_id",
                                              "no resolution for short id: " + *sid,
                                              sref->offset});
                        } else {
                            out.object_value = it->second;
                        }
                    }
                }
            } else {
                // Primitive / cognizer / entity: text content is the value.
                // No element children are allowed; anything else is a strict-
                // mode error so an LLM cannot smuggle structure into a value.
                if (!obj->children.empty()) {
                    errors.push_back({"unknown_tag",
                                      "<object kind=\"" + out.object_kind +
                                          "\"> may not contain element children",
                                      obj->offset});
                }
                out.object_value = obj->text;
            }
        }
    } else {
        errors.push_back({"missing_required_attribute",
                          "<statement> missing <object>",
                          stmt_elem.offset});
    }

    // <modality>...</modality>
    if (const Element* mod = find_child(stmt_elem, "modality")) {
        if (mod->text.empty()) {
            errors.push_back({"missing_required_attribute",
                              "<modality> empty",
                              mod->offset});
        } else {
            try {
                out.modality = schema::modality_from_string(mod->text);
            } catch (const std::invalid_argument&) {
                errors.push_back({"invalid_enum_value",
                                  "<modality> invalid value: " + mod->text,
                                  mod->offset});
            }
        }
    } else {
        errors.push_back({"missing_required_attribute",
                          "<statement> missing <modality>",
                          stmt_elem.offset});
    }

    // <polarity>...</polarity>
    if (const Element* pol = find_child(stmt_elem, "polarity")) {
        if (pol->text.empty()) {
            errors.push_back({"missing_required_attribute",
                              "<polarity> empty",
                              pol->offset});
        } else {
            try {
                out.polarity = schema::polarity_from_string(pol->text);
            } catch (const std::invalid_argument&) {
                errors.push_back({"invalid_enum_value",
                                  "<polarity> invalid value: " + pol->text,
                                  pol->offset});
            }
        }
    } else {
        errors.push_back({"missing_required_attribute",
                          "<statement> missing <polarity>",
                          stmt_elem.offset});
    }

    // <confidence>...</confidence>
    if (const Element* conf = find_child(stmt_elem, "confidence")) {
        if (conf->text.empty()) {
            errors.push_back({"missing_required_attribute",
                              "<confidence> empty",
                              conf->offset});
        } else {
            // The element's text is already trimmed by flush_text, so a clean
            // numeric like "0.5" must consume the entire string. Anything else
            // ("0.5xyz", "NaN", "Inf", out-of-range) is rejected here so the
            // strict-mode parser surfaces it as invalid_number rather than
            // silently rounding/truncating it for the validator.
            const std::string& s = conf->text;
            try {
                std::size_t pos = 0;
                double v = std::stod(s, &pos);
                if (pos != s.size()) {
                    errors.push_back({"invalid_number",
                                      "<confidence> trailing garbage: " + s,
                                      conf->offset});
                } else if (std::isnan(v) || std::isinf(v)) {
                    errors.push_back({"invalid_number",
                                      "<confidence> not finite: " + s,
                                      conf->offset});
                } else if (v < 0.0 || v > 1.0) {
                    errors.push_back({"invalid_number",
                                      "<confidence> out of range [0,1]: " + s,
                                      conf->offset});
                } else {
                    out.confidence = v;
                }
            } catch (const std::exception&) {
                errors.push_back({"invalid_number",
                                  "<confidence> not a number: " + s,
                                  conf->offset});
            }
        }
    } else {
        errors.push_back({"missing_required_attribute",
                          "<statement> missing <confidence>",
                          stmt_elem.offset});
    }

    // <observed_at>...</observed_at>
    if (const Element* obs = find_child(stmt_elem, "observed_at")) {
        if (obs->text.empty()) {
            errors.push_back({"missing_required_attribute",
                              "<observed_at> empty",
                              obs->offset});
        } else {
            out.observed_at = obs->text;
        }
    } else {
        errors.push_back({"missing_required_attribute",
                          "<statement> missing <observed_at>",
                          stmt_elem.offset});
    }

    // <perceived_by ref="..."/> — 1..N
    auto pby = find_all_children(stmt_elem, "perceived_by");
    if (pby.empty()) {
        errors.push_back({"missing_required_attribute",
                          "<statement> missing <perceived_by>",
                          stmt_elem.offset});
    } else {
        for (const Element* p : pby) {
            const std::string* ref = get_attr(*p, "ref");
            if (!ref || ref->empty()) {
                errors.push_back({"missing_required_attribute",
                                  "<perceived_by> missing 'ref'",
                                  p->offset});
            } else {
                out.perceived_by.push_back(*ref);
            }
        }
    }

    // source_speaker attribute on <statement>: append to perceived_by if absent.
    if (const std::string* ss = get_attr(stmt_elem, "source_speaker"); ss && !ss->empty()) {
        if (std::find(out.perceived_by.begin(), out.perceived_by.end(), *ss)
            == out.perceived_by.end()) {
            out.perceived_by.push_back(*ss);
        }
    }

    return out;
}

}  // namespace

ParseResult parse_extractor_xml(
        std::string_view raw_xml,
        const ExistingRefMap& existing_ref_map) {
    ParseResult result;

    bool any_non_ws = false;
    for (char c : raw_xml) {
        if (!is_space(c)) { any_non_ws = true; break; }
    }
    if (!any_non_ws) {
        result.errors.push_back({"empty_input", "no XML content", 0});
        return result;
    }

    std::vector<Element> roots = tokenize(raw_xml, result.errors);
    if (!result.errors.empty()) return result;
    if (roots.size() != 1 || roots.front().name != "extraction") {
        result.errors.push_back({"missing_root",
                                 "expected single <extraction> root", 0});
        return result;
    }

    for (const auto& child : roots.front().children) {
        if (child.name != "statement") {
            result.errors.push_back({"unknown_tag",
                                     "unexpected top-level: " + child.name,
                                     child.offset});
            continue;
        }
        std::vector<ParseError> stmt_errors;
        ExtractedStatement s = extract_statement(child, existing_ref_map, stmt_errors);
        if (!stmt_errors.empty()) {
            for (auto& e : stmt_errors) result.errors.push_back(std::move(e));
        } else {
            result.statements.push_back(std::move(s));
        }
    }

    return result;
}

}  // namespace starling::extractor
