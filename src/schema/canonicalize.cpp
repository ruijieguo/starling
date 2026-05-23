// canonicalize_object v1 — C++ mirror of python/starling/schema/value.py.
//
// Byte-for-byte parity with the Python implementation is required. See
// tests/python/test_canonicalize_parity.py.
//
// Platform note: NFC + lowercase + whitespace folding uses macOS Core
// Foundation. The linux build will need ICU; not addressed in M0.1.

#include "starling/schema/canonicalize.hpp"
#include "starling/crypto/sha256.hpp"

#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <format>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>

#if defined(__APPLE__)
#include <CoreFoundation/CoreFoundation.h>
#else
#error "M0.1 currently macOS-only — linux build needs an ICU NFC/lowercase shim"
#endif

namespace starling::schema {

namespace {

// Python's `\s+` matches [ \t\n\r\f\v]. Match the same set explicitly so we
// never depend on locale-sensitive std::isspace.
bool is_python_whitespace(char32_t c) {
    return c == U' ' || c == U'\t' || c == U'\n'
        || c == U'\r' || c == U'\f' || c == U'\v';
}

// NFC-normalize, lowercase, strip leading/trailing whitespace, fold runs of
// whitespace to a single ASCII space. Mirrors:
//   nfc = unicodedata.normalize("NFC", value)
//   trimmed = nfc.strip()
//   folded = re.sub(r"\s+", " ", trimmed)
//   return folded.lower()
std::string canonicalize_string(const std::string& input) {
#if defined(__APPLE__)
    // Build a mutable CFString from UTF-8.
    CFStringRef base = CFStringCreateWithBytes(
        kCFAllocatorDefault,
        reinterpret_cast<const UInt8*>(input.data()),
        static_cast<CFIndex>(input.size()),
        kCFStringEncodingUTF8,
        /*isExternalRepresentation=*/false);
    if (base == nullptr) {
        throw std::invalid_argument("schema_invalid: invalid UTF-8 string");
    }
    CFMutableStringRef mut = CFStringCreateMutableCopy(
        kCFAllocatorDefault, /*maxLength=*/0, base);
    CFRelease(base);
    if (mut == nullptr) {
        throw std::runtime_error("schema_invalid: CFStringCreateMutableCopy failed");
    }
    // NFC, then lowercase. CFStringLowercase uses no locale (NULL) — matches
    // Python's str.lower() for ASCII; full Unicode locale-insensitive.
    CFStringNormalize(mut, kCFStringNormalizationFormC);
    CFStringLowercase(mut, /*locale=*/nullptr);

    // Re-encode to UTF-8 so we can iterate codepoints with simple bytes (NFC
    // already applied — no further reordering will occur).
    CFIndex len = CFStringGetLength(mut);
    CFIndex utf8_max = CFStringGetMaximumSizeForEncoding(len, kCFStringEncodingUTF8) + 1;
    std::vector<char> buf(static_cast<std::size_t>(utf8_max));
    CFIndex used = 0;
    if (!CFStringGetCString(mut, buf.data(), utf8_max, kCFStringEncodingUTF8)) {
        CFRelease(mut);
        throw std::runtime_error("schema_invalid: CFStringGetCString failed");
    }
    used = static_cast<CFIndex>(std::strlen(buf.data()));
    CFRelease(mut);

    const std::string lower(buf.data(), static_cast<std::size_t>(used));

    // Strip + fold whitespace. We only need to identify the ASCII whitespace
    // set, which is single-byte in UTF-8 and never appears inside a multibyte
    // sequence's continuation bytes (continuation bytes have the high bit set,
    // outside our whitespace set). So byte iteration is safe.
    std::string out;
    out.reserve(lower.size());
    std::size_t i = 0;
    const std::size_t n = lower.size();

    // Skip leading whitespace.
    while (i < n && is_python_whitespace(static_cast<char32_t>(static_cast<unsigned char>(lower[i])))) {
        ++i;
    }
    bool in_ws_run = false;
    while (i < n) {
        const unsigned char b = static_cast<unsigned char>(lower[i]);
        if (is_python_whitespace(static_cast<char32_t>(b))) {
            in_ws_run = true;
            ++i;
            continue;
        }
        if (in_ws_run) {
            out.push_back(' ');
            in_ws_run = false;
        }
        out.push_back(static_cast<char>(b));
        ++i;
    }
    // Trailing whitespace run (in_ws_run true) is dropped — equivalent to strip().
    return out;
#endif
}

std::string canonicalize_double(double v) {
    if (std::isnan(v) || std::isinf(v)) {
        throw std::invalid_argument("schema_invalid: NaN/Inf not canonicalizable");
    }
    // Collapse -0.0 → 0.0 BEFORE formatting; std::format("{:.6f}", -0.0)
    // produces "-0.000000" on Apple Clang.
    if (v == 0.0) {
        v = 0.0;
    }
    return std::format("{:.6f}", v);
}

std::string canonicalize_int(std::int64_t v) {
    // std::format default for integers: decimal, no grouping, '-' on negatives,
    // no '+'. Matches Python str(int).
    return std::format("{}", v);
}

std::string canonicalize_datetime(std::chrono::sys_seconds t) {
    // {:%FT%TZ} → "YYYY-MM-DDTHH:MM:SSZ".
    return std::format("{:%FT%TZ}", t);
}

std::string canonicalize_ref(const CanonicalRefInput& ref) {
    std::string out;
    out.reserve(ref.class_name.size() + 1 + 32);
    out.append(ref.class_name);
    out.push_back(':');
    for (std::size_t i = 0; i < ref.uuid_bytes.size(); ++i) {
        const std::uint8_t byte = ref.uuid_bytes[i];
        out.push_back(kHexDigits[byte >> 4]);
        out.push_back(kHexDigits[byte & 0x0fU]);
    }
    return out;
}

}  // namespace

CanonicalResult canonicalize_object(const CanonicalInput& v) {
    std::string canonical = std::visit([](const auto& x) -> std::string {
        using T = std::decay_t<decltype(x)>;
        if constexpr (std::is_same_v<T, bool>) {
            return x ? std::string("true") : std::string("false");
        } else if constexpr (std::is_same_v<T, std::int64_t>) {
            return canonicalize_int(x);
        } else if constexpr (std::is_same_v<T, double>) {
            return canonicalize_double(x);
        } else if constexpr (std::is_same_v<T, std::string>) {
            return canonicalize_string(x);
        } else if constexpr (std::is_same_v<T, std::chrono::sys_seconds>) {
            return canonicalize_datetime(x);
        } else if constexpr (std::is_same_v<T, CanonicalRefInput>) {
            return canonicalize_ref(x);
        } else {
            static_assert(sizeof(T) == 0, "unhandled CanonicalInput alternative");
        }
    }, v);

    return CanonicalResult{
        .canonical = canonical,
        .sha256_hex = starling::crypto::sha256_hex(canonical),
    };
}

}  // namespace starling::schema
