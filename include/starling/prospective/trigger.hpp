#pragma once
#include <string>
#include <string_view>
#include "starling/persistence/connection.hpp"

namespace starling::prospective {

struct TriggerContext {
    std::string now_iso;
    std::string event_type;      // 当前评估的 bus 事件(post-write);time tick 时为空
    std::string event_primary_id;
    std::string tenant_id;       // 评估所属 commitment 的租户;state kind 查询按此限定
};

// 评估单个 trigger 的 spec_json(kind 决定语义)。返回是否命中。
// time: spec {"at": iso} 且 now>=at;event: spec {"event_type":..} 匹配 ctx;
// state: spec {"field":..,"op":..,"value":..} 查 conn statements 谓词;
// compound: spec {"all_of":[{kind,spec}..]} / {"any_of":[..]} 递归短路。
bool evaluate_trigger(persistence::Connection&, std::string_view kind,
                      std::string_view spec_json, const TriggerContext&);

}  // namespace starling::prospective
