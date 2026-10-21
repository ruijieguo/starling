// 形态 S §5.5：EmbeddingWorker 的 source 分支。
//
// 钉住五件事：
//   1. pending 的 source unit 被嵌入后置 embedded，写入向量并填 dim/model；
//   2. 失败累加 retry_count，达到 max_retry 后不再被扫（永久 failed）；
//   3. 嵌入成功后 retry_count 归零（重试成功即恢复）；
//   4. 模型/维度变更把 source 向量重置为 pending 且 retry_count=0——否则永久
//      failed 的行会带着 retry_count>=3 永远不被处理；
//   5. 语句分支行为完全不变（同一 tick 里两分支互不影响）。
#include "starling/embedding/embedding_worker.hpp"

#include "starling/embedding/embedding_adapter.hpp"
#include "starling/extractor/claim_contract.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/vector/source_vector_index.hpp"
#include "starling/vector/vector_index.hpp"

#include <gtest/gtest.h>
#include <nlohmann/json.hpp>
#include <sqlite3.h>

#include <deque>
#include <memory>
#include <string>
#include <vector>

namespace starling::embedding {
namespace {

constexpr auto kTenant = "default";
constexpr auto kNow = "2026-06-01T00:00:00Z";

// 可控失败次数的嵌入器：前 N 次对任意文本抛 EmbeddingError。
class FlakyAdapter : public EmbeddingAdapter {
public:
    explicit FlakyAdapter(int dim) : dim_(dim) {}
    EmbeddingResult embed(std::string_view text) override {
        if (failures_left_ > 0) {
            --failures_left_;
            throw EmbeddingError("flaky failure");
        }
        std::vector<float> vec(static_cast<std::size_t>(dim_), 0.0F);
        vec[0] = 1.0F;
        (void)text;
        return EmbeddingResult{.vector = vec, .dim = dim_, .model = model_};
    }
    [[nodiscard]] int dim() const override { return dim_; }
    [[nodiscard]] std::string model() const override { return model_; }
    void set_failures(int count) { failures_left_ = count; }
    void set_model(std::string model) { model_ = std::move(model); }

private:
    int dim_;
    int failures_left_ = 0;
    std::string model_ = "flaky-v1";
};

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(adapter->connection().raw()).migrate_to_latest();
    return adapter;
}

int scalar(persistence::Connection& conn, const std::string& sql) {
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw, nullptr), SQLITE_OK) << sql;
    persistence::StmtHandle handle(raw);
    if (sqlite3_step(handle.get()) != SQLITE_ROW) {
        return -1;
    }
    return sqlite3_column_int(handle.get(), 0);
}

std::string text_value(persistence::Connection& conn, const std::string& sql) {
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw, nullptr), SQLITE_OK) << sql;
    persistence::StmtHandle handle(raw);
    if (sqlite3_step(handle.get()) != SQLITE_ROW) {
        return "<none>";
    }
    const unsigned char* text = sqlite3_column_text(handle.get(), 0);
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    return text != nullptr ? std::string(reinterpret_cast<const char*>(text)) : "<null>";
}

// 造一个带 payload 的 engram，并把它的 unit 入队为 pending。
// 返回 (engram_ref, clause_id)。
struct Seeded {
    std::string engram;
    std::string clause;
};

Seeded seed_source_unit(persistence::Connection& conn, const std::string& turn_text,
                        const std::string& audience_json = R"(["alice"])") {
    const auto payload = extractor::claim_source_turn_payload(
        nlohmann::json::array({{{"speaker", "alice"}, {"text", turn_text},
                                {"session_id", "scene-1"}, {"turn_index", 0},
                                {"audience", nlohmann::json::parse(audience_json)},
                                {"provenance", "source_time"}, {"turn_id", nullptr},
                                {"observed_at", kNow}}})
            .dump(),
        false);

    const std::string engram = "engram-src-1";
    sqlite3_stmt* raw = nullptr;
    // adapter_name/source_item_id 必须显式唯一：0003 的唯一索引把默认空串视为同一个 key。
    EXPECT_EQ(sqlite3_prepare_v2(conn.raw(),
        "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
        "ingest_mode,privacy_class,retention_mode,refcount,payload_inline,created_at,"
        "adapter_name,source_item_id) "
        "VALUES(?1,?2,'hash-src','user_input','store','whole_record','internal',"
        "'audit_retain',0,?3,'2026-06-01T00:00:00Z','test-adapter','item-src')",
        -1, &raw, nullptr), SQLITE_OK);
    sqlite3_bind_text(raw, 1, engram.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, kTenant, -1, SQLITE_TRANSIENT);
    sqlite3_bind_blob(raw, 3, payload.data(), static_cast<int>(payload.size()), SQLITE_TRANSIENT);
    EXPECT_EQ(sqlite3_step(raw), SQLITE_DONE) << sqlite3_errmsg(conn.raw());
    sqlite3_finalize(raw);

    const auto units = nlohmann::json::parse(extractor::claim_source_units(payload));
    const std::string clause = units.at(0).at("clause_id").get<std::string>();

    EXPECT_EQ(sqlite3_prepare_v2(conn.raw(),
        "INSERT INTO source_unit_meta(tenant_id,engram_ref,clause_id,speaker,session_id,"
        "audience_json,turn_index,observed_at,provenance)"
        " VALUES(?1,?2,?3,'alice','scene-1',?4,0,?5,'source_time')", -1, &raw, nullptr),
        SQLITE_OK);
    sqlite3_bind_text(raw, 1, kTenant, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, engram.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 3, clause.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 4, audience_json.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 5, kNow, -1, SQLITE_TRANSIENT);
    EXPECT_EQ(sqlite3_step(raw), SQLITE_DONE) << sqlite3_errmsg(conn.raw());
    sqlite3_finalize(raw);

    EXPECT_EQ(sqlite3_prepare_v2(conn.raw(),
        "INSERT INTO source_unit_vectors(tenant_id,engram_ref,clause_id,status)"
        " VALUES(?1,?2,?3,'pending')", -1, &raw, nullptr), SQLITE_OK);
    sqlite3_bind_text(raw, 1, kTenant, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, engram.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 3, clause.c_str(), -1, SQLITE_TRANSIENT);
    EXPECT_EQ(sqlite3_step(raw), SQLITE_DONE) << sqlite3_errmsg(conn.raw());
    sqlite3_finalize(raw);

    return Seeded{engram, clause};
}

}  // namespace

TEST(EmbeddingWorkerSourceKind, PendingUnitBecomesEmbedded) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    const auto seeded = seed_source_unit(conn, "the code is 4321");

    FlakyAdapter embedder(8);
    vector::SqliteBlobVectorIndex stmt_index;
    vector::SqliteSourceVectorIndex source_index;
    EmbeddingWorker worker(*adapter, embedder, stmt_index, {}, &source_index);

    const auto stats = worker.tick_one_batch(conn, kNow);
    EXPECT_EQ(stats.source_embedded, 1);

    const std::string status = text_value(conn,
        "SELECT status FROM source_unit_vectors WHERE engram_ref='" + seeded.engram + "'");
    EXPECT_EQ(status, "embedded");
    EXPECT_GT(scalar(conn, "SELECT dim FROM source_unit_vectors"), 0);

    // 嵌入结果必须真的能被检索引擎取回（不是只改了个状态位）。
    vector::SourceSearchScope scope;
    scope.tenant_id = kTenant;
    scope.visible_engrams = {seeded.engram};
    scope.as_of = "2026-12-31T00:00:00Z";
    std::vector<float> query(8, 0.0F);
    query[0] = 1.0F;
    const auto hits = source_index.search(conn, query, 5, scope);
    ASSERT_EQ(hits.size(), 1U);
    EXPECT_EQ(hits[0].clause_id, seeded.clause);
}

TEST(EmbeddingWorkerSourceKind, FailureBumpsRetryAndExhausts) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    seed_source_unit(conn, "poison text");

    FlakyAdapter embedder(8);
    vector::SqliteBlobVectorIndex stmt_index;
    vector::SqliteSourceVectorIndex source_index;
    EmbeddingWorker worker(*adapter, embedder, stmt_index, {}, &source_index);

    // max_retry 默认 3：连续三次失败后转 exhausted，不再被扫。
    for (int attempt = 0; attempt < 3; ++attempt) {
        embedder.set_failures(1);
        worker.tick_one_batch(conn, kNow);
    }
    EXPECT_EQ(scalar(conn, "SELECT retry_count FROM source_unit_vectors"), 3);
    EXPECT_EQ(text_value(conn, "SELECT status FROM source_unit_vectors"), "failed");

    // 第四次 tick 不应再尝试（不再累加）。
    embedder.set_failures(1);
    worker.tick_one_batch(conn, kNow);
    EXPECT_EQ(scalar(conn, "SELECT retry_count FROM source_unit_vectors"), 3);
}

TEST(EmbeddingWorkerSourceKind, SuccessResetsRetryCount) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    seed_source_unit(conn, "transient text");

    FlakyAdapter embedder(8);
    vector::SqliteBlobVectorIndex stmt_index;
    vector::SqliteSourceVectorIndex source_index;
    EmbeddingWorker worker(*adapter, embedder, stmt_index, {}, &source_index);

    embedder.set_failures(1);
    worker.tick_one_batch(conn, kNow);
    EXPECT_EQ(scalar(conn, "SELECT retry_count FROM source_unit_vectors"), 1);

    worker.tick_one_batch(conn, kNow);   // 这次成功
    EXPECT_EQ(text_value(conn, "SELECT status FROM source_unit_vectors"), "embedded");
    EXPECT_EQ(scalar(conn, "SELECT retry_count FROM source_unit_vectors"), 0);
}

TEST(EmbeddingWorkerSourceKind, ModelChangeResetsExhaustedUnits) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    seed_source_unit(conn, "exhausted text");

    FlakyAdapter embedder(8);
    vector::SqliteBlobVectorIndex stmt_index;
    vector::SqliteSourceVectorIndex source_index;
    EmbeddingWorker worker(*adapter, embedder, stmt_index, {}, &source_index);

    for (int attempt = 0; attempt < 3; ++attempt) {
        embedder.set_failures(1);
        worker.tick_one_batch(conn, kNow);
    }
    ASSERT_EQ(scalar(conn, "SELECT retry_count FROM source_unit_vectors"), 3);

    // 换模型：已经 retry_count=3 的行必须被重置，否则新模型永远轮不到它。
    embedder.set_model("flaky-v2");
    worker.tick_one_batch(conn, kNow);

    EXPECT_EQ(text_value(conn, "SELECT status FROM source_unit_vectors"), "embedded");
    EXPECT_EQ(text_value(conn, "SELECT model FROM source_unit_vectors"), "flaky-v2");
}

TEST(EmbeddingWorkerSourceKind, StatementBranchUnaffected) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    seed_source_unit(conn, "source text");

    // 同时放一条待嵌入语句，确认两分支在同一次 tick 里各自工作。
    sqlite3_exec(conn.raw(),
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
        "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "perceived_by_json,created_at,updated_at) VALUES('stmt-1','default','alice',"
        "'first_person','entity','Bob','knows','str','auth','aaaa','v1','believes','pos',"
        "0.8,'2026-01-01T00:00:00Z',0.5,'{}',1.0,'2026-01-01T00:00:00Z','user_input',"
        "'consolidated','approved','[\"alice\"]','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')",
        nullptr, nullptr, nullptr);

    FlakyAdapter embedder(8);
    vector::SqliteBlobVectorIndex stmt_index;
    vector::SqliteSourceVectorIndex source_index;
    EmbeddingWorker worker(*adapter, embedder, stmt_index, {}, &source_index);

    const auto stats = worker.tick_one_batch(conn, kNow);
    EXPECT_EQ(stats.embedded, 1);         // 语句分支照旧
    EXPECT_EQ(stats.source_embedded, 1);  // source 分支也跑了
    EXPECT_EQ(scalar(conn, "SELECT COUNT(*) FROM statement_vectors WHERE status='embedded'"), 1);
}

}  // namespace starling::embedding
