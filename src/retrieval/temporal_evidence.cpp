#include "starling/retrieval/temporal_evidence.hpp"
#include "starling/extractor/claim_contract.hpp"
#include <algorithm>
#include <cctype>
#include <cmath>
#include <map>
#include <set>
#include <tuple>
#include <nlohmann/json.hpp>

namespace starling::retrieval {
namespace {
using Json=nlohmann::json;
struct OrderedCandidate {
    TemporalEvidenceRef ref;
    std::size_t session_order;
    double score;
};
Json reference(const TemporalEvidenceRef& ref) {
    return {{"tenant_id",ref.tenant_id},{"statement_id",ref.statement_id},
        {"session_id",ref.session_id},{"turn_index",ref.turn_index}};
}
bool blank(const std::string& value) {
    return value.empty() || std::all_of(value.begin(),value.end(),[](unsigned char c){return std::isspace(c);});
}
bool score_first(const OrderedCandidate& a,const OrderedCandidate& b) {
    if(a.score!=b.score) return a.score>b.score;
    return std::tie(a.ref.tenant_id,a.ref.statement_id)<std::tie(b.ref.tenant_id,b.ref.statement_id);
}
auto position(const OrderedCandidate& value) {return std::make_pair(value.session_order,value.ref.turn_index);}
}
TemporalEvidenceView select_temporal_evidence(const std::vector<TemporalEvidenceCandidate>& candidates,
                                              const TemporalEvidenceRequest& request) {
    TemporalEvidenceView view;view.topic=request.topic;view.input_candidates=candidates.size();
    if(blank(request.tenant_id) || blank(request.actor_id)) {view.insufficiency_reason="missing_scope";return view;}
    if(blank(request.topic)) {view.ambiguous=true;view.insufficiency_reason="missing_topic";return view;}
    if(request.limit<2) {view.insufficiency_reason="budget_too_small";return view;}
    std::map<std::string,std::size_t> sessions;
    for(const auto& session:request.ordered_session_ids) {
        if(blank(session) || !sessions.emplace(session,sessions.size()).second) {
            view.ambiguous=true;view.insufficiency_reason="invalid_session_order";return view;
        }
    }
    const auto cutoff=sessions.find(request.through_session_id);
    if(cutoff==sessions.end()) {view.insufficiency_reason="missing_cutoff_session";return view;}
    std::map<std::pair<std::string,std::string>,OrderedCandidate> unique;
    for(const auto& candidate:candidates) {
        const auto& row=candidate.row;
        if(row.tenant_id!=request.tenant_id || row.subject_id!=request.actor_id || row.subject_kind!="cognizer") {
            ++view.excluded_scope;continue;
        }
        try {
            const auto claim=extractor::claim_strict_json(row.semantic_claim_json);
            if(row.id.empty() || !std::isfinite(candidate.score) || claim.at("actor")!=request.actor_id) {
                ++view.excluded_invalid_evidence;continue;
            }
            const auto& span=claim.at("source_span");
            const auto spans=extractor::claim_strict_json(row.source_spans_json);
            bool matched=false;
            if(spans.is_array()) for(const auto& ref:spans) {
                if(ref.is_object() && ref.contains("engram_ref") && ref.contains("source_hash") &&
                    ref.contains("span_start") && ref.contains("span_end") &&
                    ref["engram_ref"]==span.at("engram_ref") && ref["source_hash"]==span.at("source_hash") &&
                    ref["span_start"]==span.at("span_start") && ref["span_end"]==span.at("span_end")) matched=true;
            }
            if(!matched) {++view.excluded_invalid_evidence;continue;}
            if(!claim.contains("topic") || !claim["topic"].is_string() || claim["topic"]!=request.topic) {
                ++view.excluded_topic;continue;
            }
            if(!claim.contains("source_turn") || !claim["source_turn"].is_object()) {
                ++view.excluded_missing_order;continue;
            }
            const auto& turn=claim["source_turn"];
            if(!turn.contains("session_id") || !turn["session_id"].is_string() ||
                !turn.contains("turn_index") || !turn["turn_index"].is_number_integer()) {
                ++view.excluded_missing_order;continue;
            }
            const auto session=turn["session_id"].get<std::string>();
            const auto order=sessions.find(session);
            const auto index=turn["turn_index"].get<std::int64_t>();
            if(order==sessions.end() || index<0) {++view.excluded_missing_order;continue;}
            if(order->second>cutoff->second) {++view.excluded_after_cutoff;continue;}
            if(turn.at("speaker")!=row.holder_id) {++view.excluded_invalid_evidence;continue;}
            OrderedCandidate value={{row.tenant_id,row.id,session,index},order->second,candidate.score};
            const auto identity=std::make_pair(row.tenant_id,row.id);
            auto [it,inserted]=unique.emplace(identity,value);
            if(!inserted) {++view.duplicates;if(score_first(value,it->second)) it->second=std::move(value);}
        } catch(const std::exception&) {++view.excluded_invalid_evidence;}
    }
    std::vector<OrderedCandidate> eligible;
    for(const auto& [identity,value]:unique) eligible.push_back(value);
    view.eligible_candidates=eligible.size();
    if(eligible.empty()) {view.insufficiency_reason="no_ordered_topic_evidence";return view;}
    std::sort(eligible.begin(),eligible.end(),[](const auto& a,const auto& b) {
        if(position(a)!=position(b)) return position(a)<position(b);
        return score_first(a,b);
    });
    const auto early=eligible.front();
    const auto latest_position=position(eligible.back());
    const auto late=*std::find_if(eligible.begin(),eligible.end(),[&](const auto& value){return position(value)==latest_position;});
    view.early=early.ref;view.late=late.ref;
    std::set<std::pair<std::string,std::string>> selected;
    selected.emplace(early.ref.tenant_id,early.ref.statement_id);
    selected.emplace(late.ref.tenant_id,late.ref.statement_id);
    std::sort(eligible.begin(),eligible.end(),score_first);
    for(const auto& value:eligible) {
        if(selected.size()>=static_cast<std::size_t>(request.limit)) break;
        selected.emplace(value.ref.tenant_id,value.ref.statement_id);
    }
    for(const auto& value:eligible) if(selected.contains({value.ref.tenant_id,value.ref.statement_id}))
        view.selected.push_back(value.ref);
    view.sufficient=position(early)!=position(late);
    if(!view.sufficient) view.insufficiency_reason="no_distinct_ordered_sources";
    return view;
}
std::string temporal_evidence_json(const TemporalEvidenceView& view) {
    Json selected=Json::array();
    for(const auto& ref:view.selected) { selected.push_back(reference(ref)); }
    return Json{{"schema_version",1},{"sufficient",view.sufficient},{"ambiguous",view.ambiguous},
        {"insufficiency_reason",view.insufficiency_reason},{"topic",view.topic},
        {"selection_scope","visible_bounded_candidates"},{"order_basis","request_session_order_then_turn_index"},
        {"event_time_inferred",false},{"early",view.early?reference(*view.early):Json(nullptr)},
        {"late",view.late?reference(*view.late):Json(nullptr)},{"selected",selected},
        {"input_candidates",view.input_candidates},{"eligible_candidates",view.eligible_candidates},
        {"excluded_after_cutoff",view.excluded_after_cutoff},{"excluded_scope",view.excluded_scope},
        {"excluded_topic",view.excluded_topic},{"excluded_missing_order",view.excluded_missing_order},
        {"excluded_invalid_evidence",view.excluded_invalid_evidence},{"duplicates",view.duplicates}}.dump();
}
} // namespace starling::retrieval
