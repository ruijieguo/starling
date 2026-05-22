#pragma once

namespace starling::testing {

// True iff the testing-only translation unit is linked into the current binary.
// Defined in a separate target (starling_testing_marker) that prod profiles MUST NOT
// link. preflight reads this at startup and refuses to enter READY when:
//   - profile == "prod" AND testing_marker_loaded() == true
//
// CI grep (defense-in-depth #1) further bans `starling::testing` references in prod
// entrypoints — see scripts/ci_static_scan.py.
bool testing_marker_loaded() noexcept;

}  // namespace starling::testing
