#include "starling/retrieval/pattern_completor.hpp"

namespace starling::retrieval {

CompletionResult PatternCompletor::complete(persistence::Connection& /*conn*/,
                                            const PatternCompletionParams& /*params*/) {
    (void)seeds_;  // used in Task 2+
    return CompletionResult{};  // Task 2+ 填充
}

}  // namespace starling::retrieval
