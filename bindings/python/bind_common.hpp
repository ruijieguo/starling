#pragma once
// Shared helpers for the split _core binding translation units
// (bind_NN_<domain>.cpp). Everything here was hoisted from the head of the
// original monolithic bindings/python/module.cpp.

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <string>

#include "starling/schema/canonicalize.hpp"

namespace py = pybind11;

namespace starling::bindings {

inline constexpr std::array<const char*, 6> kRefClassNames{
    "CognizerRef", "EntityRef", "StatementRef",
    "EngramRef", "PersonaRef", "KnowledgeFrontierRef",
};

inline bool is_known_ref_class(const std::string& name) {
    for (const char* known : kRefClassNames) {
        if (name == known) {
            return true;
        }
    }
    return false;
}

// Dispatch a Python value to the C++ canonicalize_object. Mirrors the type
// ladder in python/starling/schema/value.py — bool BEFORE int (PyBool is a
// PyLong subclass), then int → float → str → datetime → Ref → error.
inline py::tuple canonicalize_object_cpp(py::object value) {
    using starling::schema::canonicalize_object;
    using starling::schema::CanonicalInput;
    using starling::schema::CanonicalRefInput;

    CanonicalInput input;

    if (py::isinstance<py::bool_>(value)) {
        input = value.cast<bool>();
    } else if (py::isinstance<py::int_>(value)) {
        input = value.cast<std::int64_t>();
    } else if (py::isinstance<py::float_>(value)) {
        input = value.cast<double>();
    } else if (py::isinstance<py::str>(value)) {
        input = value.cast<std::string>();
    } else {
        // datetime?
        py::object datetime_mod = py::module_::import("datetime");
        py::object datetime_cls = datetime_mod.attr("datetime");
        py::object timezone_cls = datetime_mod.attr("timezone");
        if (py::isinstance(value, datetime_cls)) {
            if (value.attr("tzinfo").is_none()) {
                throw py::value_error(
                    "schema_invalid: naive datetime not canonicalizable");
            }
            py::object utc = value.attr("astimezone")(timezone_cls.attr("utc"));
            // Use timestamp() (returns float seconds since epoch); truncate to
            // integer seconds to match Python's strftime("%Y-%m-%dT%H:%M:%SZ"),
            // which formats whole-second resolution and drops sub-second.
            const double ts = utc.attr("timestamp")().cast<double>();
            const auto secs = static_cast<std::int64_t>(ts);
            input = std::chrono::sys_seconds{std::chrono::seconds{secs}};
        } else {
            // Ref?  Detected by class name + uuid.UUID-typed `id` attribute.
            const std::string class_name =
                py::str(py::type::of(value).attr("__name__")).cast<std::string>();
            if (!is_known_ref_class(class_name)) {
                throw py::value_error(
                    std::string("schema_invalid: unsupported type ") + class_name);
            }
            py::object uuid_mod = py::module_::import("uuid");
            py::object uuid_cls = uuid_mod.attr("UUID");
            py::object id_attr = value.attr("id");
            if (!py::isinstance(id_attr, uuid_cls)) {
                throw py::value_error(
                    "schema_invalid: Ref.id must be a uuid.UUID");
            }
            py::bytes raw = id_attr.attr("bytes").cast<py::bytes>();
            const std::string raw_str = raw.cast<std::string>();
            if (raw_str.size() != 16) {
                throw py::value_error(
                    "schema_invalid: UUID.bytes must be 16 bytes");
            }
            CanonicalRefInput ref{};
            ref.class_name = class_name;
            std::memcpy(ref.uuid_bytes.data(), raw_str.data(), 16);
            input = ref;
        }
    }

    auto result = canonicalize_object(input);
    return py::make_tuple(result.canonical, result.sha256_hex);
}

}  // namespace starling::bindings
