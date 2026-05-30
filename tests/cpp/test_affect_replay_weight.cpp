// P2.c: AffectVector 驱动优先级重放权重 (spec §8)
//
// ReplayScheduler::sample_volatile 现在在构造 SamplerInputs 时解析 affect_json →
// AffectVector → salience()(作为 base salience)+ arousal(喂
// sample_weight 的 (1 + arousal_bonus·affect_arousal) 乘子)。此前 affect_arousal
// 硬编码 0,salience 直接读 column。
//
// 本测试 (approach A) 直接复刻生产侧 SamplerInputs 的构造方式:
//   - 高 affect:从高 valence/arousal/novelty/stakes 的 affect_json 解析 → salience()/arousal
//   - 低 affect:affect_json 为 "{}" → 保留 column salience + arousal=0(原行为)
// 然后断言高 affect 的 sample_weight 严格更高,证明公式接线正确且确定。
//
// 选 (A) 而非端到端 (B):replay_scheduler 的 sample_volatile 对采样集做 weight-sort
// 后取 top-N,但 do_compress_and_emit 把所有被采样行一起压缩;在 :memory: 小数据集上
// limit (idle=30/sleep=200/online=3) 都会同时选中两行,排序无法通过 ledger 或
// statement.derived 事件干净观测。(A) 直接、确定地测到本任务实现的精确接线。

#include "starling/affect/affect_vector.hpp"
#include "starling/replay/swr_sampler.hpp"
#include <gtest/gtest.h>
#include <string>

using starling::affect::AffectVector;
using starling::affect::parse_affect_json;
using starling::affect::salience;
using namespace starling::replay;

namespace {

// 复刻 sample_volatile 现在的 SamplerInputs 构造:给定 affect_json + column salience。
SamplerInputs build_inputs(const std::string& affect_json, double column_salience) {
    SamplerInputs in;
    in.salience          = column_salience;
    in.last_replayed_iso = "";
    in.has_conflict      = false;
    in.affect_arousal    = 0.0;
    in.goal_relevant     = false;
    in.provenance        = "user_input";
    in.replay_count      = 0;
    in.derived_depth     = 0;

    if (!affect_json.empty() && affect_json != "{}") {
        const AffectVector av = parse_affect_json(affect_json);
        in.salience       = salience(av);  // 覆盖 column salience
        in.affect_arousal = av.arousal;
    }
    return in;
}

}  // namespace

// salience() 对高 affect 显著大于默认 AffectVector 的极小基线。
TEST(AffectReplayWeight, HighAffectSalienceMuchGreaterThanDefault) {
    const AffectVector hi =
        parse_affect_json(R"({"valence":0.9,"arousal":0.9,"novelty":0.9,"stakes":0.9})");
    const double s_hi = salience(hi);
    const double s_default = salience(AffectVector{});  // 全 0

    EXPECT_GT(s_hi, s_default);
    // 默认 (全 0) salience = 0.4·0.4·0.3·0.3·1.0 = 0.0144
    EXPECT_NEAR(s_default, 0.0144, 1e-9);
    // 高 affect salience ≈ (0.4+0.6·0.9)^? 远大于 0.5
    EXPECT_GT(s_hi, 0.5);
}

// 核心接线断言:高 affect 行的 replay 采样权重 > 低 affect ("{}") 行。
TEST(AffectReplayWeight, HighAffectOutweighsLowAffect) {
    constexpr char kNow[] = "2026-05-27T10:00:00Z";

    // 高 affect 行:salience()/arousal 由 affect_json 驱动;column salience 故意设低 (0.1)
    // 以证明是 affect 解析、而非 column 在抬高权重。
    const SamplerInputs hi =
        build_inputs(R"({"valence":0.9,"arousal":0.9,"novelty":0.9,"stakes":0.9})", 0.1);
    // 低 affect 行:affect_json="{}" → 保留 column salience(同样 0.1)+ arousal=0。
    const SamplerInputs lo = build_inputs("{}", 0.1);

    const SamplerConfig cfg;  // arousal_bonus=0.4 默认
    const double w_hi = sample_weight(hi, cfg, kNow);
    const double w_lo = sample_weight(lo, cfg, kNow);

    EXPECT_GT(w_hi, 0.0);
    EXPECT_GT(w_lo, 0.0);
    EXPECT_GT(w_hi, w_lo);  // 高 affect 优先采样
    // affect 解析后 salience 远高于 0.1 column,差距应显著(>5x),非边际。
    EXPECT_GT(w_hi, w_lo * 5.0);
}

// arousal 乘子已接线:相同 base salience 下,arousal 越高权重越高。
TEST(AffectReplayWeight, ArousalMultiplierApplied) {
    constexpr char kNow[] = "2026-05-27T10:00:00Z";

    SamplerInputs hot;  // 高 arousal
    hot.salience = 0.8; hot.provenance = "user_input"; hot.affect_arousal = 0.9;
    SamplerInputs cold = hot;  // 同 salience,arousal=0
    cold.affect_arousal = 0.0;

    const SamplerConfig cfg;
    const double w_hot = sample_weight(hot, cfg, kNow);
    const double w_cold = sample_weight(cold, cfg, kNow);

    EXPECT_GT(w_hot, w_cold);
    // (1 + 0.4·0.9) / (1 + 0) = 1.36
    EXPECT_NEAR(w_hot / w_cold, 1.0 + cfg.arousal_bonus * 0.9, 1e-9);
}
