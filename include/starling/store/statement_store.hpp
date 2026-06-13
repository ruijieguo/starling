#pragma once
// StatementStore —— statements 六态机转换 + 局部修正的语义动词收编(P3.b1 phase 2)。
// 每法封装一条 statements 写,WHERE 守卫即不变式;转换法返回 int =
// sqlite3_changes(受影响行数),调用方据此门控副作用(事件 emit)。
//
// 主 INSERT(insert_statement / insert_arbitrated_fork)涉及 ExtractedStatement
// 与 outbox event,随 StatementWriter 迁移在 phase 2 末追加;本接口先含转换+修正法。
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace starling::store {

class StatementStore {
public:
    virtual ~StatementStore() = default;

    // ── 六态机转换 ──
    // compress: volatile → consolidated(+replay_count,记 batch)。
    virtual int mark_consolidated(const std::vector<std::string>& ids,
                                  std::string_view tenant,
                                  std::string_view replay_batch_id) = 0;
    // reinforce: → consolidated(+access_count +replay_count,记 batch;无状态守卫)。
    virtual int reinforce(const std::vector<std::string>& ids,
                          std::string_view tenant,
                          std::string_view replay_batch_id) = 0;
    // abstract: +replay_count,记 batch(无状态变更)。
    virtual int bump_replay_count(const std::vector<std::string>& ids,
                                  std::string_view tenant,
                                  std::string_view replay_batch_id) = 0;
    // reconcile: consolidated → replaying_reconsolidating。
    virtual int enter_reconsolidating(std::string_view id,
                                      std::string_view tenant) = 0;
    // recon 兜底: replaying_reconsolidating → consolidated。
    virtual int restore_consolidated(std::string_view id,
                                     std::string_view tenant) = 0;
    // 振荡防护: replay_count>=5 且 state∈(volatile,replaying_consolidating)
    // → consolidated + pending_review。现行为=跨租户 bulk(无 tenant 过滤),
    // 保真;latent cross-tenant scope 已登记,phase 2 不改。
    virtual int force_consolidate_pending_review() = 0;
    // 归档: state=from_state → archived。updated_at 有值时一并刷新(supersede/
    // arbitration);std::nullopt 时不动 updated_at(decay/TTL 路径)——保真。
    virtual int archive(const std::vector<std::string>& ids, std::string_view tenant,
                        std::string_view from_state,
                        std::optional<std::string> updated_at) = 0;

    // ── 局部修正 ──
    // mild-correction(bus): SET confidence + confidence_history_json + updated_at
    // (provenance/state 不动)。confidence 取 max(只升不降)由调用方决定后传入。
    virtual void apply_mild_correction(std::string_view id, std::string_view tenant,
                                       double confidence,
                                       std::string_view history_json,
                                       std::string_view updated_at) = 0;
    // mild-contradict(arbitration): SET confidence + history + state='consolidated'
    // (updated_at/provenance 不动 —— 与 apply_mild_correction 相反的语义)。
    virtual void apply_mild_contradict(std::string_view id, std::string_view tenant,
                                       double confidence,
                                       std::string_view history_json) = 0;
    // severe-archive(arbitration): archived,除非已 archived/forgotten;刷新 updated_at。
    virtual int archive_nonterminal(std::string_view id, std::string_view tenant,
                                    std::string_view updated_at) = 0;
    // 支持仲裁: SET confidence + consolidation_state='consolidated'。
    virtual void set_confidence_consolidated(std::string_view id,
                                             std::string_view tenant,
                                             double confidence) = 0;
    // 二阶 salience 继承: SET salience=MAX(salience,?), affect_json=?。
    virtual void inherit_salience(std::string_view id, std::string_view tenant,
                                  double min_salience,
                                  std::string_view affect_json) = 0;
};

}  // namespace starling::store
