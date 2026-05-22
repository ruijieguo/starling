// Placeholder translation unit — replaced in M0.0 Task 6 (testing helper marker).
// Keeps starling_testing_marker linkable until the marker is implemented.
// A non-inline definition is required so the archive entry has at least one
// symbol; otherwise ranlib warns about empty translation units.
namespace starling::testing::detail {
extern const int testing_marker_placeholder;
const int testing_marker_placeholder = 0;
}  // namespace starling::testing::detail
