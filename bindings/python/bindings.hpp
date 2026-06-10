#pragma once
// Declarations for the per-domain binding registrars. PYBIND11_MODULE in
// module.cpp calls these strictly in order — the sequence preserves the
// registration order of the original monolithic module.cpp.

#include <pybind11/pybind11.h>

namespace starling::bindings {

void bind_01_core(pybind11::module_& m);
void bind_02_persistence(pybind11::module_& m);
void bind_03_evidence(pybind11::module_& m);
void bind_04_bus(pybind11::module_& m);
void bind_05_retrieval(pybind11::module_& m);
void bind_06_extractor(pybind11::module_& m);
void bind_07_cognizer(pybind11::module_& m);
void bind_08_tom(pybind11::module_& m);
void bind_09_brain_dynamics(pybind11::module_& m);
void bind_10_embedding(pybind11::module_& m);
void bind_11_neocortex(pybind11::module_& m);
void bind_12_prospective(pybind11::module_& m);

}  // namespace starling::bindings
