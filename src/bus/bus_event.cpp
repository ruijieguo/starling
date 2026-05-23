#include "starling/bus/bus_event.hpp"

#include <openssl/evp.h>
#include <iomanip>
#include <sstream>

namespace starling::bus {

namespace {
constexpr char kSep = '\x1f';

std::string sha256_hex(std::string_view data) {
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int digest_len = 0;
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_sha256(), nullptr);
    EVP_DigestUpdate(ctx, data.data(), data.size());
    EVP_DigestFinal_ex(ctx, digest, &digest_len);
    EVP_MD_CTX_free(ctx);
    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    for (unsigned int i = 0; i < digest_len; ++i) {
        oss << std::setw(2) << static_cast<int>(digest[i]);
    }
    return oss.str();
}
}  // namespace

std::string compute_idempotency_key(
        std::string_view event_type,
        std::string_view aggregate_id,
        std::string_view canonical_key,
        std::string_view causation_root,
        std::string_view window_bucket) {
    std::string buf;
    buf.reserve(event_type.size() + aggregate_id.size() + canonical_key.size()
                + causation_root.size() + window_bucket.size() + 4);
    buf.append(event_type);    buf.push_back(kSep);
    buf.append(aggregate_id);  buf.push_back(kSep);
    buf.append(canonical_key); buf.push_back(kSep);
    buf.append(causation_root);buf.push_back(kSep);
    buf.append(window_bucket);
    return sha256_hex(buf);
}

std::string compute_window_bucket(
        std::string_view event_type,
        std::chrono::system_clock::time_point now) {
    if (event_type == "pipeline_run.started") {
        const auto sec = std::chrono::duration_cast<std::chrono::seconds>(
            now.time_since_epoch()).count();
        return std::to_string(sec / 60);
    }
    return "";
}

}  // namespace starling::bus
