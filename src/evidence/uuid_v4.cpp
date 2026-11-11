#include "starling/evidence/uuid_v4.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <random>
#include <string>
#include <string_view>

namespace starling::evidence {

// 原在 src/evidence/engram_store.cpp 的匿名命名空间里(engram id 用),抽出来给 events 行的身份共用(裁定 R118)。
// 输出与原实现逐字节相同:两个 64 位随机数按小端拆成 16 字节,第 6 字节写版本 4,第 8 字节写变体 10xx。
std::string generate_uuid_v4() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    constexpr std::size_t kByteCount = 16;
    constexpr std::size_t kWordBytes = 8;
    const std::uint64_t first_word = rng();
    const std::uint64_t second_word = rng();
    std::array<std::uint8_t, kByteCount> bytes{};
    for (std::size_t pos = 0; pos < kWordBytes; ++pos) {
        bytes.at(pos) = static_cast<std::uint8_t>((first_word >> (pos * 8U)) & 0xFFU);
        bytes.at(pos + kWordBytes) = static_cast<std::uint8_t>((second_word >> (pos * 8U)) & 0xFFU);
    }
    const unsigned version_byte = bytes.at(6);
    const unsigned variant_byte = bytes.at(8);
    bytes.at(6) = static_cast<std::uint8_t>((version_byte & 0x0FU) | 0x40U);   // version 4
    bytes.at(8) = static_cast<std::uint8_t>((variant_byte & 0x3FU) | 0x80U);   // variant 10xx

    constexpr std::string_view kHex = "0123456789abcdef";
    std::string out;
    out.reserve(36);
    for (std::size_t pos = 0; pos < kByteCount; ++pos) {
        if (pos == 4 || pos == 6 || pos == 8 || pos == 10) {
            out.push_back('-');
        }
        const unsigned value = bytes.at(pos);
        out.push_back(kHex.at(value >> 4U));
        out.push_back(kHex.at(value & 0x0FU));
    }
    return out;
}

}  // namespace starling::evidence
