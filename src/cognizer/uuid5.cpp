#include "starling/cognizer/uuid5.hpp"

#include <openssl/evp.h>

#include <array>
#include <cstdint>
#include <stdexcept>

namespace starling::cognizer {

namespace {

// Parse 36-char dashed UUID into 16 raw bytes.
std::array<std::uint8_t, 16> parse_uuid_str(std::string_view s) {
    if (s.size() != 36 || s[8] != '-' || s[13] != '-'
        || s[18] != '-' || s[23] != '-') {
        throw std::invalid_argument("UUID string must be 36 chars 8-4-4-4-12");
    }
    auto hex_val = [](char c) -> int {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        throw std::invalid_argument("invalid hex digit in UUID");
    };
    std::array<std::uint8_t, 16> out{};
    std::size_t out_i = 0;
    for (std::size_t i = 0; i < s.size(); ++i) {
        if (s[i] == '-') continue;
        const int high = hex_val(s[i]);
        ++i;
        const int low  = hex_val(s[i]);
        out[out_i++] = static_cast<std::uint8_t>((high << 4) | low);
    }
    return out;
}

std::string bytes_to_uuid_str(const std::uint8_t* bytes) {
    static constexpr char kHex[] = "0123456789abcdef";
    std::string out(36, '-');
    std::size_t j = 0;
    for (int i = 0; i < 16; ++i) {
        if (i == 4 || i == 6 || i == 8 || i == 10) { out[j++] = '-'; }
        out[j++] = kHex[(bytes[i] >> 4) & 0x0f];
        out[j++] = kHex[bytes[i] & 0x0f];
    }
    return out;
}

}  // namespace

std::string compute_uuid5(std::string_view namespace_uuid_str,
                           std::string_view name) {
    const auto ns_bytes = parse_uuid_str(namespace_uuid_str);

    EVP_MD_CTX* raw_ctx = EVP_MD_CTX_new();
    if (raw_ctx == nullptr) {
        throw std::runtime_error("compute_uuid5: EVP_MD_CTX_new failed");
    }
    struct CtxGuard {
        EVP_MD_CTX* ctx;
        ~CtxGuard() { EVP_MD_CTX_free(ctx); }
    } guard{raw_ctx};

    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int digest_len = 0;
    if (EVP_DigestInit_ex(guard.ctx, EVP_sha1(), nullptr) != 1
        || EVP_DigestUpdate(guard.ctx, ns_bytes.data(), ns_bytes.size()) != 1
        || EVP_DigestUpdate(guard.ctx, name.data(), name.size()) != 1
        || EVP_DigestFinal_ex(guard.ctx, digest, &digest_len) != 1) {
        throw std::runtime_error("compute_uuid5: EVP_Digest call failed");
    }

    // SHA-1 produces 20 bytes; take first 16, set version=5 + variant=10xx
    std::uint8_t out[16];
    for (int i = 0; i < 16; ++i) out[i] = digest[i];
    out[6] = static_cast<std::uint8_t>((out[6] & 0x0f) | 0x50);  // version 5
    out[8] = static_cast<std::uint8_t>((out[8] & 0x3f) | 0x80);  // variant 10xx

    return bytes_to_uuid_str(out);
}

}  // namespace starling::cognizer
