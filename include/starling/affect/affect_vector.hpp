// include/starling/affect/affect_vector.hpp
#pragma once
#include <string_view>

namespace starling::affect {

struct AffectVector {
    float valence = 0.f;    // -1..+1
    float arousal = 0.f;    //  0..1
    float dominance = 0.f;  // -1..+1
    float novelty = 0.f;    //  0..1
    float stakes = 0.f;     //  0..1
};

// salience 公式 (对拍 python/starling/schema/affect.py)：
// (0.4+0.6|valence|)·(0.4+0.6·arousal)·(0.3+0.7·novelty)·(0.3+0.7·stakes)·(0.6+0.4·surprise_decay)
double salience(const AffectVector&, double surprise_decay = 1.0);

// 解析 affect_json (keys: valence/arousal/dominance/novelty/stakes;缺/非法默认 0)。
AffectVector parse_affect_json(std::string_view json);

}  // namespace starling::affect
