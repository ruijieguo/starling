#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace starling::crypto {

// P1 placeholder for the per-record encryption hook. M0.4+ will replace this
// with a real AES-256-GCM + KMS adapter; the call site in EngramStore stays
// the same. While this stub is in place, `key_ref` is NULL on every Engram
// row and `content_ciphertext` carries raw payload bytes.
class NullKms {
public:
    // Identity: returns the payload unchanged. The key_ref argument is ignored
    // in P1 (real KMS will use it to address the per-record DEK).
    static std::vector<std::uint8_t> encrypt(
        const std::vector<std::uint8_t>& payload,
        const std::string& /*key_ref*/) {
        return payload;
    }

    // Always nullopt — no key is generated; the engrams.key_ref column stays NULL.
    static std::optional<std::string> generate_key_ref() {
        return std::nullopt;
    }
};

}  // namespace starling::crypto
