#pragma once

#include <charconv>
#include <optional>
#include <string>
#include <string_view>
#include <system_error>

namespace starling::vector::detail {

inline constexpr std::string_view kZvecPkPrefix = "starling:v1:";

inline std::string encode_zvec_primary_key(std::string_view tenant_id,
                                           std::string_view stmt_id) {
    return std::string(kZvecPkPrefix) + std::to_string(tenant_id.size()) + ":" +
           std::to_string(stmt_id.size()) + ":" + std::string(tenant_id) +
           std::string(stmt_id);
}

inline std::optional<std::string> decode_zvec_statement_id(
        std::string_view pk, std::string_view expected_tenant) {
    if (!pk.starts_with(kZvecPkPrefix)) return std::string(pk);

    const auto parse_size = [](std::string_view text) -> std::optional<std::size_t> {
        if (text.empty()) return std::nullopt;
        std::size_t value = 0;
        const auto [ptr, ec] = std::from_chars(
            text.data(), text.data() + text.size(), value);
        if (ec != std::errc{} || ptr != text.data() + text.size())
            return std::nullopt;
        return value;
    };

    const auto tenant_len_begin = kZvecPkPrefix.size();
    const auto tenant_len_end = pk.find(':', tenant_len_begin);
    if (tenant_len_end == std::string_view::npos) return std::nullopt;
    const auto stmt_len_end = pk.find(':', tenant_len_end + 1);
    if (stmt_len_end == std::string_view::npos) return std::nullopt;
    const auto tenant_size = parse_size(
        pk.substr(tenant_len_begin, tenant_len_end - tenant_len_begin));
    const auto stmt_size = parse_size(
        pk.substr(tenant_len_end + 1, stmt_len_end - tenant_len_end - 1));
    if (!tenant_size || !stmt_size) return std::nullopt;

    const auto tenant_begin = stmt_len_end + 1;
    const auto remaining = pk.size() - tenant_begin;
    if (*tenant_size > remaining || *stmt_size != remaining - *tenant_size)
        return std::nullopt;
    if (pk.substr(tenant_begin, *tenant_size) != expected_tenant)
        return std::nullopt;
    return std::string(pk.substr(tenant_begin + *tenant_size, *stmt_size));
}

}  // namespace starling::vector::detail
