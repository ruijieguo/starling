// Placeholder translation unit — replaced in M0.0 Task 3 (RuntimeHealth 状态机).
// Keeps starling_core linkable until RuntimeHealth is implemented.
// A non-inline definition is required so the archive entry has at least one
// symbol; otherwise ranlib warns about empty translation units.
namespace starling::detail {
extern const int runtime_health_placeholder;
const int runtime_health_placeholder = 0;
}  // namespace starling::detail
