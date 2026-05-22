// Placeholder translation unit — replaced in M0.0 Task 4 (preflight 校验).
// Keeps starling_core linkable until preflight is implemented.
// A non-inline definition is required so the archive entry has at least one
// symbol; otherwise ranlib warns about empty translation units.
namespace starling::detail {
extern const int preflight_placeholder;
const int preflight_placeholder = 0;
}  // namespace starling::detail
