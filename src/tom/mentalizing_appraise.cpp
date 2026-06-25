// appraise_emotion — appraisal-theory emotion: X's desire vs the actual OCCURRED
// outcome → goal_congruence × agency → discrete emotion. Deterministic precondition;
// abstains (no emit) when there is no outcome to judge a desire against (never fabricate).
//
// Agency convention: in an OCCURRED event, subject_id is the ACTOR (the doer); the event
// INVOLVES x when holder_id==x OR subject_id==x. So agency = (actor==x ? "self" : "other"),
// and "circumstance" when no agentive doer is distinguishable (actor==x, i.e. X is merely
// the experiencer of a non-desired result — no other cognizer caused it).
#include "starling/tom/mentalizing.hpp"

#include "starling/store/sqlite_meta_store.hpp"

#include <string>
#include <vector>

namespace starling::tom::mentalizing {
namespace {

// Two outcomes refer to the same thing iff their canonical hashes match (when both
// present), else by object_value equality.
bool same_object(const retrieval::StatementRow& a, const std::string& d_hash,
                 const std::string& d_value) {
    if (!a.canonical_object_hash.empty() && !d_hash.empty())
        return a.canonical_object_hash == d_hash;
    return a.object_value == d_value;
}

}  // namespace

std::vector<EmotionAppraisal> appraise_emotion(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view tenant,
    std::string_view as_of) {
    std::vector<EmotionAppraisal> out;
    store::SqliteMetaStore meta(adapter.connection());
    const std::string xs(x);

    // 1. Desires X holds: modality ∈ {desires, intends} OR predicate ∈
    //    {prefers, wants, desires, intends}. Query holder=x once per modality and once
    //    by predicate-set, dedup by statement id.
    std::vector<retrieval::StatementRow> desires;
    auto add_desires = [&](std::vector<retrieval::StatementRow>&& rows) {
        for (auto& r : rows) {
            bool seen = false;
            for (const auto& e : desires)
                if (e.id == r.id) { seen = true; break; }
            if (!seen) desires.push_back(std::move(r));
        }
    };
    {
        store::StatementFilter f;
        f.tenant_id = std::string(tenant);
        f.holder_id = xs;
        f.as_of_iso8601 = std::string(as_of);
        f.modality = "desires";
        add_desires(meta.query_statements(f));
        f.modality = "intends";
        add_desires(meta.query_statements(f));
    }
    {
        store::StatementFilter f;
        f.tenant_id = std::string(tenant);
        f.holder_id = xs;
        f.as_of_iso8601 = std::string(as_of);
        f.predicate_in = {"prefers", "wants", "desires", "intends"};
        add_desires(meta.query_statements(f));
    }
    if (desires.empty()) return out;

    // 2. Outcomes: OCCURRED events for the tenant that INVOLVE x (holder_id==x OR
    //    subject_id==x). The query can't OR two columns, so fetch all OCCURRED for the
    //    tenant and filter in-process. ACTOR = subject_id (the doer).
    std::vector<retrieval::StatementRow> outcomes;
    {
        store::StatementFilter f;
        f.tenant_id = std::string(tenant);
        f.modality = "occurred";
        f.as_of_iso8601 = std::string(as_of);
        for (auto& r : meta.query_statements(f))
            if (r.holder_id == xs || r.subject_id == xs)
                outcomes.push_back(std::move(r));
    }

    // 3. Appraise each desire against the outcomes.
    for (const auto& d : desires) {
        const std::string& d_hash = d.canonical_object_hash;
        const std::string& d_val  = d.object_value;

        // realized = an outcome whose object matches the desire's target AND that X
        // actually obtained — i.e. the actor (subject_id) is X, or no distinct other
        // cognizer is the doer. If a DIFFERENT cognizer acted on the desired object
        // (e.g. "Bob take the_toy"), X did NOT realize the desire → fall through to the
        // incongruent path so the other-agency emotion (anger) is appraised.
        const retrieval::StatementRow* realized = nullptr;
        for (const auto& o : outcomes) {
            if (!same_object(o, d_hash, d_val)) continue;
            const bool other_doer = !o.subject_id.empty() && o.subject_id != xs;
            if (!other_doer) { realized = &o; break; }
        }

        if (realized != nullptr) {
            // Goal congruent: X got what they wanted → joy, self-agency.
            EmotionAppraisal e;
            e.cognizer = xs;
            e.emotion = "joy";
            e.goal_congruence = "congruent";
            e.agency = "self";
            e.desire = d;
            e.outcome_value = d_val;
            out.push_back(std::move(e));
            continue;
        }

        if (outcomes.empty()) continue;  // ABSTAIN: no outcome to judge against.

        // Goal incongruent: X experienced an outcome, but did not obtain the desire.
        // Counter-outcome = a non-realizing outcome (deterministic order from
        // query_statements). Prefer one with a distinguishable other-cognizer doer so
        // agency is decided by the actual perpetrator if any — this also captures an
        // event where another cognizer acted on the very object X wanted (e.g. "Bob
        // take the_toy"), which is the salient cause of X's incongruent result.
        const retrieval::StatementRow* counter = nullptr;
        for (const auto& o : outcomes) {
            if (counter == nullptr) counter = &o;
            if (!o.subject_id.empty() && o.subject_id != xs) { counter = &o; break; }
        }
        if (counter == nullptr) continue;  // no outcome → ABSTAIN (unreachable here).

        // agency: actor==x → "self"; a distinct other cognizer doer → "other";
        // no agentive doer distinguishable → "circumstance".
        std::string agency;
        if (!counter->subject_id.empty() && counter->subject_id != xs)
            agency = "other";
        else
            agency = "circumstance";  // X is the experiencer; no other caused it.

        // 4. Incongruent emotion table.
        std::string emotion;
        if (agency == "other")      emotion = "anger";
        else if (agency == "self")  emotion = "regret";
        else                        emotion = "disappointment";  // circumstance

        EmotionAppraisal e;
        e.cognizer = xs;
        e.emotion = emotion;
        e.goal_congruence = "incongruent";
        e.agency = agency;
        e.desire = d;
        e.outcome_value = counter->object_value;
        out.push_back(std::move(e));
    }

    return out;
}

}  // namespace starling::tom::mentalizing
