#pragma once
// Affect Buffer(06_hippocampus §5/§淘汰策略,P3.a3):高 salience VOLATILE
// 候选的优先级集合。
//
// 实现形态:**派生视图**而非物化队列——成员 = 该租户 VOLATILE 中
// salience >= θ_buffer 的 top-C(salience 降序,先入优先)。与 spec 的
// 堆语义逐条等价:容量淘汰=top-C 截断;"被替换者仍留 VOLATILE 不丢"=
// 平凡成立;跨重启=天然成立。零新表、零写路径。
//
// 参与采样的两个消费点:
//  1) Replay 采样权重已含 salience(P2.c sample_weight)——buffer 的优先
//     语义由权重携带;
//  2) VOLATILE TTL 兜底豁免(10_replay:"超 7 天 AND not in Affect Buffer
//     → ARCHIVED")——sweep_volatile_ttl 跳过成员(本模块的硬消费点)。
#include "starling/persistence/connection.hpp"

#include <string>
#include <string_view>
#include <unordered_set>
#include <vector>

namespace starling::hippocampus::affect_buffer {

struct Config {
    double theta_buffer = 0.6;   // 入队阈
    int capacity = 64;           // 每租户容量 C
};

// 该租户当前的 buffer 成员(top-C 高 salience volatile)。
std::vector<std::string> member_ids(persistence::Connection& conn,
                                    std::string_view tenant_id,
                                    const Config& cfg = {});

// 成员判定(member_ids 的集合封装;TTL sweep 逐租户缓存用)。
std::unordered_set<std::string> member_set(persistence::Connection& conn,
                                           std::string_view tenant_id,
                                           const Config& cfg = {});

}  // namespace starling::hippocampus::affect_buffer
