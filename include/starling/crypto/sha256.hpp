#pragma once
#include <openssl/evp.h>

#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>

namespace starling::crypto {

// SHA-256 hex digest of `data`. 64-character lowercase hex output.
//
// Rigorous variant: checks every OpenSSL return value, throws on failure,
// and uses a lookup-table for hex formatting (no ostringstream / locale
// concerns). RAII over EVP_MD_CTX so a throw between alloc and free does
// not leak the context.
inline std::string sha256_hex(std::string_view data) {
    constexpr char kHexDigits[] = "0123456789abcdef";

    EVP_MD_CTX* const raw_ctx = EVP_MD_CTX_new();
    if (raw_ctx == nullptr) {
        throw std::runtime_error("sha256_hex: EVP_MD_CTX_new failed");
    }
    struct CtxGuard {
        EVP_MD_CTX* ctx;
        ~CtxGuard() { EVP_MD_CTX_free(ctx); }
    } guard{raw_ctx};

    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int digest_len = 0;
    if (EVP_DigestInit_ex(guard.ctx, EVP_sha256(), nullptr) != 1
        || EVP_DigestUpdate(guard.ctx, data.data(), data.size()) != 1
        || EVP_DigestFinal_ex(guard.ctx, digest, &digest_len) != 1) {
        throw std::runtime_error("sha256_hex: EVP_Digest call failed");
    }

    std::string out;
    out.resize(static_cast<std::size_t>(digest_len) * 2);
    for (unsigned int i = 0; i < digest_len; ++i) {
        const unsigned char byte = digest[i];
        out[static_cast<std::size_t>(i) * 2]     = kHexDigits[byte >> 4];
        out[static_cast<std::size_t>(i) * 2 + 1] = kHexDigits[byte & 0x0fU];
    }
    return out;
}

}  // namespace starling::crypto
