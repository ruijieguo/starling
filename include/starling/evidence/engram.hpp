#pragma once

#include "starling/schema/enums.hpp"

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace starling::evidence {

// Adapter / source identification. P1 has no segment_map, so chunk_index is
// the finest grain. P3 will add (segment_id, span_start, span_end).
struct SourceIdentity {
    std::string  adapter_name;     // "direct_api" if produced by a direct caller
    std::string  adapter_version;  // semver or commit hash
    std::string  source_item_id;   // adapter-stable id of the source record
    std::string  source_version;   // adapter-stable version of that record
    std::int32_t chunk_index = 0;  // 0 if the whole record is one chunk
};

// Producer-supplied input. Bus.append_evidence is the only consumer.
struct EngramInput {
    std::string                 tenant_id;
    SourceIdentity              source;
    schema::SourceKind          source_kind;
    schema::IngestMode          ingest_mode;
    schema::PrivacyClass        privacy_class;
    schema::EngramRetentionMode retention_mode;
    std::vector<std::string>    declared_transformations;  // empty == byte_preserving claim
    bool                        byte_preserving = false;   // producer claim; trusted in P1
    std::vector<std::uint8_t>   payload_bytes;             // verbatim payload (or metadata blob)
    std::optional<std::string>  redacted_content;          // for redacted_retain only
    std::string                 created_at_iso8601;        // caller-supplied; UTC ISO-8601
};

// Persistence-side row. The id, ingest_policy, content_hash, key_ref, and
// content_ciphertext fields are filled in by EngramStore::put.
struct Engram {
    std::string                 id;                 // UUID
    std::string                 tenant_id;
    SourceIdentity              source;
    schema::SourceKind          source_kind;
    schema::IngestPolicy        ingest_policy;
    schema::IngestMode          ingest_mode;
    schema::PrivacyClass        privacy_class;
    schema::EngramRetentionMode retention_mode;
    std::vector<std::string>    declared_transformations;
    bool                        byte_preserving = false;
    std::string                 content_hash;       // sha256 hex
    std::optional<std::string>  key_ref;            // null in P1 (no KMS yet)
    std::vector<std::uint8_t>   content_ciphertext; // raw bytes in P1 (null_kms)
    std::optional<std::string>  redacted_content;
    std::int64_t                refcount = 0;       // not touched in M0.3
    std::string                 created_at_iso8601;
    std::optional<std::string>  erased_at_iso8601;  // always null in M0.3
};

// Returned by Bus.append_evidence to producers. Statement.evidence will use
// this shape (M0.5).
struct EngramRef {
    std::string                 id;
    std::string                 content_hash;
    schema::EngramRetentionMode retention_mode;
};

// Canonical bytes for content_hash. The §3.7 invariant is that
// declared_transformations is part of the hash domain so that two pipelines
// that produced "same bytes" via different normalizations get different hashes.
//
// Format: "v1\x1f" + payload_bytes + "\x1f" + sorted_unique(transformations).join("\x1f")
std::string canonicalize_engram_payload(
    const std::vector<std::uint8_t>& payload_bytes,
    const std::vector<std::string>& declared_transformations);

std::string compute_engram_content_hash(
    const std::vector<std::uint8_t>& payload_bytes,
    const std::vector<std::string>& declared_transformations);

}  // namespace starling::evidence
