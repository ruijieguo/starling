#include <gtest/gtest.h>

#include "starling/extractor/fake_llm_adapter.hpp"

namespace starling::extractor {

TEST(FakeLLMAdapter, ReturnsCannedResponse) {
    FakeLLMAdapter a;
    a.set_response("hash-1", LLMResponse{
        .raw_xml = "[]", .ok = true, .error = ""});
    LLMResponse r = a.extract("ignored prompt", "hash-1");
    EXPECT_TRUE(r.ok);
    EXPECT_EQ(r.raw_xml, "[]");
}

TEST(FakeLLMAdapter, MissingHashIsTransientError) {
    FakeLLMAdapter a;
    LLMResponse r = a.extract("prompt", "unknown-hash");
    EXPECT_FALSE(r.ok);
    EXPECT_EQ(r.error, "fake_adapter_no_response_for_hash");
}

TEST(FakeLLMAdapter, OverwriteResponse) {
    FakeLLMAdapter a;
    a.set_response("h", LLMResponse{.raw_xml = "v1", .ok = true});
    a.set_response("h", LLMResponse{.raw_xml = "v2", .ok = true});
    EXPECT_EQ(a.extract("p", "h").raw_xml, "v2");
}

TEST(FakeLLMAdapter, FailureResponse) {
    FakeLLMAdapter a;
    a.set_response("h", LLMResponse{
        .raw_xml = "", .ok = false, .error = "rate_limited"});
    LLMResponse r = a.extract("p", "h");
    EXPECT_FALSE(r.ok);
    EXPECT_EQ(r.error, "rate_limited");
}

}  // namespace starling::extractor
