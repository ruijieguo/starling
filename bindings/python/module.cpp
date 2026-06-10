#include <pybind11/pybind11.h>

#include "starling/version.hpp"

#include "bindings.hpp"

PYBIND11_MODULE(_core, m) {
    m.doc() = "Starling Memory C++ core bindings";
    m.attr("__version__") = STARLING_VERSION_STRING;

    // Registration order is load-bearing: pybind11 requires base classes to
    // be registered before derived classes, and several segments reference
    // types registered by earlier ones. Each bind_NN covers a contiguous
    // chunk of the original monolithic module.cpp, invoked in the original
    // order.
    starling::bindings::bind_01_core(m);
    starling::bindings::bind_02_persistence(m);
    starling::bindings::bind_03_evidence(m);
    starling::bindings::bind_04_bus(m);
    starling::bindings::bind_05_retrieval(m);
    starling::bindings::bind_06_extractor(m);
    starling::bindings::bind_07_cognizer(m);
    starling::bindings::bind_08_tom(m);
    starling::bindings::bind_09_brain_dynamics(m);
    starling::bindings::bind_10_embedding(m);
    starling::bindings::bind_11_neocortex(m);
    starling::bindings::bind_12_prospective(m);
}
