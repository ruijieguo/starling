// sub-project B phase 1 Task 1.2: PerceptionReconstructor 实现。
//
// 后置管线:扫描一个租户的全部 OCCURRED 事件,在一条 (observed_at, seq) 时间线上
// 重建场景级在场时间线(默认全员在场;enter/leave 覆盖),并把每个物理 location
// 事件的结果位置写入在场见证者的 perception_state(append-only,幂等 upsert)。
// 事件已在前面的管线提交,故本类在自己的顶层 TransactionGuard 里跑——失败回滚
// 也不会动到已提交的事件(TransactionGuard 析构默认 rollback,需显式 .commit(),
// 镜像 src/extractor/episodic_extractor.cpp 的提交语义)。
//
// 注:TransactionGuard 声明在 persistence/connection.hpp(无独立 transaction_guard.hpp),
// 已由 perception_reconstructor.hpp 传递包含。
#include "starling/cognizer/perception_reconstructor.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/store/perception_state_store.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include <sqlite3.h>
#include <nlohmann/json.hpp>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <vector>
namespace starling::cognizer {
namespace {
struct ScanEvent {
    std::string stmt_id, actor, predicate, theme, observed_at, location, participants_json,
        evidence_json;
    long long seq = 0;
};
// The OCCURRED statement's evidence_json is a JSON array of evidence anchors. The
// episodic write path records the engram as {"engram_ref": "<id>", ...}; some test
// fixtures use {"engram_id": "<id>"}. Return the first anchor's engram id, or "".
std::string engram_id_of(const std::string& evidence_json) {
    if (evidence_json.empty()) return {};
    auto j = nlohmann::json::parse(evidence_json, nullptr, /*allow_exceptions=*/false);
    if (!j.is_array()) return {};
    for (const auto& a : j) {
        if (!a.is_object()) continue;
        if (auto it = a.find("engram_ref"); it != a.end() && it->is_string())
            return it->get<std::string>();
        if (auto it = a.find("engram_id"); it != a.end() && it->is_string())
            return it->get<std::string>();
    }
    return {};
}
bool is_leave(const std::string& p) { return p == "leave" || p == "exit" || p == "depart"; }
bool is_enter(const std::string& p) { return p == "enter" || p == "return" || p == "arrive"; }
bool is_presence_change(const std::string& p) { return is_leave(p) || is_enter(p); }
// tell/inform: informational channel — does NOT establish physical presence (N1).
bool is_tell(const std::string& p) { return p == "tell" || p == "inform"; }
// Content channel (phase 4: unexpected contents). see/look read a closed labelled
// container's APPARENT content; open/reveal expose its ACTUAL content. Both carry
// the content value in the location field and write state_dim="content". Unlike
// tell, the see/open actor IS physically present, so they stay in the physical cast.
bool is_see(const std::string& p) { return p == "see" || p == "look"; }
bool is_reveal(const std::string& p) { return p == "open" || p == "reveal"; }
bool is_content(const std::string& p) { return is_see(p) || is_reveal(p); }
// close: hides container contents (physical state change only) — no new location
// or content knowledge is conveyed to witnesses, so write NO perception row.
bool is_close(const std::string& p) { return p == "close"; }
// Task 5.1: feed the cognizers who perceived an event into the KnowledgeFrontier
// presence_log, anchored on the event's engram. No-op if no frontier (adapter-less
// ctor), no perceivers, or the OCCURRED statement carries no engram in evidence_json.
void record_frontier(KnowledgeFrontier* frontier, std::string_view tenant,
                     const std::set<std::string>& perceived_set,
                     const std::string& evidence_json, const std::string& observed_at,
                     persistence::Connection& conn) {
    if (frontier == nullptr || perceived_set.empty()) return;
    const std::string engram_id = engram_id_of(evidence_json);
    if (engram_id.empty()) return;
    const std::vector<std::string> perceived_by(perceived_set.begin(), perceived_set.end());
    frontier->record_presence_from_statement(tenant, perceived_by, engram_id, observed_at, conn);
}
std::vector<std::string> participants_of(const ScanEvent& ev) {
    std::vector<std::string> ps;
    if (!ev.actor.empty()) ps.push_back(ev.actor);
    if (!ev.participants_json.empty()) {
        auto j = nlohmann::json::parse(ev.participants_json, nullptr, /*allow_exceptions=*/false);
        if (j.is_array()) for (auto& p : j) if (p.is_string()) ps.push_back(p.get<std::string>());
    }
    return ps;
}
}  // namespace

PerceptionReconstructor::PerceptionReconstructor(persistence::Connection& conn) : conn_(conn) {}

PerceptionReconstructor::PerceptionReconstructor(persistence::Connection& conn,
                                                 persistence::SqliteAdapter& adapter)
    : conn_(conn), adapter_(&adapter) {}

void PerceptionReconstructor::reconstruct(std::string_view tenant) {
    sqlite3* db = conn_.raw();
    // 1. Scan ALL OCCURRED events for the tenant on one timeline (observed_at, seq).
    //    evidence_json carries the engram anchor used for does_X_know awareness (5.1).
    const char* sql =
        "SELECT s.id, s.subject_id, s.predicate, s.object_value, s.observed_at, "
        "e.seq, e.location, e.participants_json, s.evidence_json "
        "FROM statements s JOIN episodic_events e "
        "ON e.statement_id=s.id AND e.tenant_id=s.tenant_id "
        "WHERE s.tenant_id=? AND s.modality='occurred' "
        "ORDER BY s.observed_at, e.seq";
    std::vector<ScanEvent> events;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
            throw persistence::detail::make_sqlite_error(db, "PerceptionReconstructor scan prepare");
        persistence::StmtHandle h(raw);
        persistence::detail::bind_sv(h.get(), 1, tenant);
        auto col = [&](int i) {
            const auto* t = sqlite3_column_text(h.get(), i);
            return t ? std::string(reinterpret_cast<const char*>(t)) : std::string();
        };
        int rc;
        while ((rc = sqlite3_step(h.get())) == SQLITE_ROW) {
            ScanEvent ev;
            ev.stmt_id = col(0); ev.actor = col(1); ev.predicate = col(2); ev.theme = col(3);
            ev.observed_at = col(4); ev.seq = sqlite3_column_int64(h.get(), 5);
            ev.location = col(6); ev.participants_json = col(7); ev.evidence_json = col(8);
            events.push_back(std::move(ev));
        }
        if (rc != SQLITE_DONE)
            throw persistence::detail::make_sqlite_error(db, "PerceptionReconstructor scan step");
    }
    if (events.empty()) return;

    // 2. Physical cast = everyone named in a physical / presence-change event.
    //    tell/inform events are excluded — a cognizer named ONLY in a tell must NOT
    //    be presumed physically present (N1: e.g. "Anne phones absent Bob" must not
    //    make Bob a witness of the room's events).
    std::set<std::string> cast;
    for (const auto& ev : events) {
        if (is_tell(ev.predicate)) continue;  // tell does not establish physical presence
        for (const auto& p : participants_of(ev)) cast.insert(p);
    }

    // 3. Walk events; present set defaults to the whole cast; enter/leave override;
    //    physical witnesses (present ∪ this event's actor/participants) learn the location.
    store::PerceptionStateStore ps(conn_);
    // Task 5.1: when an adapter is present, also feed each event's witnesses into the
    // KnowledgeFrontier presence_log so does_X_know() reflects event perception. The
    // frontier records on the OCCURRED statement's engram (from evidence_json).
    std::unique_ptr<KnowledgeFrontier> frontier;
    if (adapter_) frontier = std::make_unique<KnowledgeFrontier>(*adapter_);
    persistence::TransactionGuard tx(conn_);  // own top-level tx (events already committed)
    std::set<std::string> present(cast.begin(), cast.end());
    // Room-scoping (multi-room fix): track each agent's current room so that physical
    // and content events are only witnessed by agents co-located with the event.
    // An empty string means "unknown/legacy single-room" and matches any event room.
    std::map<std::string, std::string> agent_room;
    auto room_of = [&](const std::string& agent) -> std::string {
        auto found = agent_room.find(agent);
        return found != agent_room.end() ? found->second : std::string();
    };
    // Two empty strings (one party unknown) → treated as same scene (legacy compat).
    // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
    auto same_scene = [&](const std::string& w_room, const std::string& ev_room) -> bool {
        return w_room.empty() || ev_room.empty() || w_room == ev_room;
    };
    // L1b: themes whose ACTUAL content has been revealed by an open/reveal. A label's
    // apparent reading (see/look) seeds the initial content-BELIEF, but once the
    // container is opened the truth is authoritative: a later see/look that merely
    // re-states the label must NOT be re-emitted as a content perception at a higher
    // position (the cabbage->hat->cabbage thrash that made latest_actual / the deepest
    // chain belief pick the label instead of the opened truth).
    std::set<std::string> revealed_themes;
    long long position = 0;
    for (const auto& ev : events) {
        const auto evp = participants_of(ev);
        std::set<std::string> witnesses(present.begin(), present.end());
        for (const auto& p : evp) witnesses.insert(p);  // actor/participants present at their event
        // Cognizers who perceived THIS event (for the frontier presence_log, 5.1).
        std::set<std::string> perceived_set;
        if (is_tell(ev.predicate)) {
            // Told channel: recipient(s) = participants minus the teller (index 0).
            // Write each recipient's perception_state regardless of physical presence.
            // A tell is neither a presence change nor a physical witnessing.
            if (!ev.location.empty()) {
                for (std::size_t i = 1; i < evp.size(); ++i) {
                    store::PerceptionStateRow row;
                    row.tenant_id = std::string(tenant); row.cognizer_id = evp[i];
                    row.theme_id = ev.theme; row.state_dim = "location"; row.state_value = ev.location;
                    row.observed_at = ev.observed_at; row.position = position; row.source_event_id = ev.stmt_id;
                    ps.upsert(row);
                    perceived_set.insert(evp[i]);  // the recipient learns the told engram
                }
            }
            record_frontier(frontier.get(), tenant, perceived_set, ev.evidence_json, ev.observed_at, conn_);
            ++position; continue;  // skip presence update and physical witness branch
        } else if (is_presence_change(ev.predicate)) {
            // Those present at the moment of an enter/leave witnessed it happening.
            perceived_set = witnesses;
            if (is_leave(ev.predicate)) {
                for (const auto& who : evp) { present.erase(who); }   // gone AFTER this
                // Do NOT clear agent_room on leave — present.erase already drops them
                // as a witness candidate; a later re-enter will update agent_room.
            } else {
                for (const auto& who : evp) {
                    present.insert(who);          // here from now
                    agent_room[who] = ev.theme;   // ev.theme = the room entered
                }
            }
        } else if (is_content(ev.predicate)) {  // content event (see/look apparent; open/reveal actual)
            // Present witnesses (present ∪ actor/participants) learn the container's
            // content. Ordered BEFORE the physical-location branch so a see/open writes
            // state_dim="content", not "location". The see/open actor is present.
            //
            // L1b: an open/reveal exposes the TRUTH and marks the theme revealed; a
            // see/look is only the APPARENT label reading. Once the truth is out, a
            // later see/look that re-states the label is suppressed — it must NOT be
            // re-emitted as a content perception after the opened truth (no A→B→A
            // content thrash). An apparent reading BEFORE the open is unaffected (it
            // seeds the initial content-belief). reveal always emits.
            const bool reveal = is_reveal(ev.predicate);
            const bool suppressed = !reveal && revealed_themes.count(ev.theme) != 0;
            if (!ev.location.empty() && !suppressed) {
                // Room-scope: compute the event's room from the actor (first participant).
                const std::string ev_room = room_of(evp.empty() ? std::string() : evp[0]);
                for (const auto& w : witnesses) {
                    if (!same_scene(room_of(w), ev_room)) { continue; }  // witness in a different room
                    store::PerceptionStateRow row;
                    row.tenant_id = std::string(tenant); row.cognizer_id = w;
                    row.theme_id = ev.theme; row.state_dim = "content"; row.state_value = ev.location;
                    row.observed_at = ev.observed_at; row.position = position; row.source_event_id = ev.stmt_id;
                    ps.upsert(row);
                    perceived_set.insert(w);
                }
            }
            if (reveal) revealed_themes.insert(ev.theme);  // truth established for this theme
        } else if (is_close(ev.predicate)) {
            // Closing a container hides its contents but conveys no new state to
            // witnesses — write no perception (physical state change only). Present
            // cognizers still witnessed the act, so the engram is visible to them.
            perceived_set = witnesses;
        } else if (!ev.location.empty()) {  // physical location event
            // Room-scope: compute the event's room from the actor (first participant).
            const std::string ev_room = room_of(evp.empty() ? std::string() : evp[0]);
            for (const auto& w : witnesses) {
                if (!same_scene(room_of(w), ev_room)) { continue; }  // witness in a different room
                store::PerceptionStateRow row;
                row.tenant_id = std::string(tenant); row.cognizer_id = w;
                row.theme_id = ev.theme; row.state_dim = "location"; row.state_value = ev.location;
                row.observed_at = ev.observed_at; row.position = position; row.source_event_id = ev.stmt_id;
                ps.upsert(row);
                perceived_set.insert(w);
            }
        }
        record_frontier(frontier.get(), tenant, perceived_set, ev.evidence_json, ev.observed_at, conn_);
        ++position;
    }
    tx.commit();  // TransactionGuard dtor rolls back unless committed (see episodic_extractor.cpp).
}
}  // namespace starling::cognizer
