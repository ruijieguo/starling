// bind_15_world — 世界注册表与快照（W1/W2）。注册表在 Python 侧以 dict 表示，
// 格式与 worlds.json 逐字一致；转换经 Python json 模块，C++ 是唯一的序列化实现。
// 设计：docs/superpowers/specs/2026-10-25-world-scene-management-design.md
//
// 约定：
//  - 所有函数都是纯函数式的：入参 dict 不被修改，更新后的注册表作为新 dict 返回。
//    delete / create / set_active / take_snapshot 只改内存里的注册表（外加世界目录
//    或快照文件），不落盘 worlds.json；调用方（WorldManager）必须随后
//    world_save_registry。
//  - WorldStoreError 带稳定的 code（见 world_store.hpp）。save_registry /
//    ensure_registry 遇到的 I/O 失败（filesystem_error、runtime_error）没有专门的
//    code，原样传播，这里不伪装成 WorldStoreError。调用方（routes/worlds.py 的
//    _run）把它们统一兜成 JSON 500 internal_error，异常文本只进服务端日志。

#include "bind_common.hpp"

#include <pybind11/stl.h>

#include "starling/governance/world_store.hpp"

namespace starling::bindings {

namespace {

namespace gov = starling::governance;

py::object to_py(const std::string& text) {
    return py::module_::import("json").attr("loads")(text);
}

std::string from_py(const py::object& obj) {
    return py::module_::import("json").attr("dumps")(obj, py::arg("ensure_ascii") = false)
        .cast<std::string>();
}

// 需要持有 GIL（经由 Python json 模块）。解析失败抛 registry_corrupt，
// retention < 2 抛 invalid_retention，规则与 load_registry 相同。
gov::Registry reg_in(const py::dict& reg) { return gov::registry_from_json(from_py(reg)); }
py::object reg_out(const gov::Registry& reg) { return to_py(gov::registry_to_json(reg)); }

}  // namespace

// NOLINTNEXTLINE(readability-identifier-length) — `m` matches all sibling bind_NN units
void bind_15_world(pybind11::module_& m) {
    using namespace pybind11::literals;

    // 与 bind_07/bind_14 同一写法；what() 形如 "world_exists: sim-1"。
    py::register_exception<gov::WorldStoreError>(m, "WorldStoreError", PyExc_RuntimeError);

    // 取异常文本冒号前的部分，即 WorldStoreError 的 code。
    m.def("world_store_error_code", [](const py::object& exc) {
        const auto text = py::str(exc).cast<std::string>();
        const auto pos = text.find(':');
        return pos == std::string::npos ? text : text.substr(0, pos);
    }, py::arg("exc"));

    m.def("world_is_valid_name", &gov::is_valid_world_name, py::arg("name"));

    m.def("world_ensure_registry",
          // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
          [](const std::string& reg_path, const std::string& db_path, const std::string& tenant) {
              return reg_out(gov::ensure_registry(reg_path, db_path, tenant));
          }, py::arg("registry_path"), py::arg("default_db_path"), py::arg("default_tenant"));

    m.def("world_load_registry",
          [](const std::string& reg_path) { return reg_out(gov::load_registry(reg_path)); },
          py::arg("registry_path"));

    m.def("world_save_registry",
          [](const std::string& reg_path, const py::dict& reg) {
              gov::save_registry(reg_path, reg_in(reg));
          }, py::arg("registry_path"), py::arg("registry"));

    m.def("world_create",
          // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
          [](const py::dict& reg, const std::string& reg_dir, const std::string& name,
             const std::string& label, const std::string& now_iso) {
              auto registry = reg_in(reg);
              const auto world = gov::create_world(registry, reg_dir, name, label, now_iso);
              return py::dict("registry"_a = reg_out(registry),
                              "world"_a = to_py(gov::world_entry_to_json(world)));
          }, py::arg("registry"), py::arg("registry_dir"), py::arg("name"),
          py::arg("label"), py::arg("now_iso"));

    // 只摘内存注册项并删世界目录，不落盘 worlds.json：调用方必须随后保存返回值。
    m.def("world_delete",
          [](const py::dict& reg, const std::string& reg_dir, const std::string& name) {
              auto registry = reg_in(reg);
              {
                  // 递归删目录可能很大，不占着 GIL。
                  const py::gil_scoped_release release;
                  gov::delete_world(registry, reg_dir, name);
              }
              return reg_out(registry);
          }, py::arg("registry"), py::arg("registry_dir"), py::arg("name"));

    m.def("world_set_active",
          [](const py::dict& reg, const std::string& name) {
              auto registry = reg_in(reg);
              gov::set_active(registry, name);
              return reg_out(registry);
          }, py::arg("registry"), py::arg("name"));

    // 只读打开，busy_timeout 最长 5 秒，所以释放 GIL。键名见 WorldStats。
    // 库文件存在但读不出时抛 snapshot_failed；只有文件不存在才是全 0。
    m.def("world_stats",
          [](const std::string& db_path, const std::string& tenant) {
              gov::WorldStats stats;
              {
                  const py::gil_scoped_release release;
                  stats = gov::world_stats(db_path, tenant);
              }
              return py::dict("db_bytes"_a = stats.db_bytes, "live_bytes"_a = stats.live_bytes,
                              "statements"_a = stats.statements, "engrams"_a = stats.engrams,
                              "world_time"_a = stats.world_time);
          }, py::arg("db_path"), py::arg("tenant"));

    // 租户不变式（spec §2.1）：只读扫一遍库，有别的租户的行抛 world_tenant_mismatch。
    // 2.6GB 的生产库约 90ms，释放 GIL。库文件不存在时直接通过。
    m.def("world_verify_tenant",
          // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
          [](const std::string& db_path, const std::string& tenant) {
              const py::gil_scoped_release release;
              gov::verify_world_tenant(db_path, tenant);
          }, py::arg("db_path"), py::arg("tenant"));

    // 快照会 VACUUM 整库，可能要几秒，期间释放 GIL。
    // take_snapshot 先清扫上次崩溃的残留、写快照文件、插入条目，最后才执行保留策略。
    // 保留策略失败（清理旧快照时路径无法解析、删不掉或越界）由 C++ 吞掉：成功的快照
    // 一定返回条目，注册表与磁盘仍一致，只是暂时多出几份旧快照，下次快照或保留策略
    // 会重试。因此抛出异常只表示快照本身没拍成（磁盘不足、库损坏、kind 非法、
    // vector_backend 不是 sqlite 等），此时磁盘上没有新文件，传入的 dict 也未被改动。
    // vector_backend 由调用方按当前配置传入；拒绝与否由 C++ 判（snapshot_unsupported_backend）。
    m.def("world_take_snapshot",
          // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
          [](const py::dict& reg, const std::string& world, const std::string& kind,
             const std::string& reason, const std::string& note,
             const std::string& vector_backend) {
              auto registry = reg_in(reg);
              gov::SnapshotOptions opts;
              opts.kind = kind;
              opts.reason = reason;
              opts.note = note;
              opts.vector_backend = vector_backend;
              gov::SnapshotEntry snap;
              {
                  const py::gil_scoped_release release;
                  snap = gov::take_snapshot(registry, world, opts);
              }
              return py::dict("registry"_a = reg_out(registry),
                              "snapshot"_a = to_py(gov::snapshot_entry_to_json(snap)));
          }, py::arg("registry"), py::arg("world"), py::arg("kind") = "manual",
          py::arg("reason") = "manual", py::arg("note") = "",
          py::kw_only(), py::arg("vector_backend") = "sqlite");

    // 只删一份快照的文件，注册表不动（不返回新注册表）。给 take_snapshot 成功、
    // world_save_registry 却失败时做补偿：新文件没登记，不删就是列不出来的孤儿。
    m.def("world_discard_snapshot_file",
          // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
          [](const py::dict& reg, const std::string& world, const std::string& snapshot_id) {
              const auto registry = reg_in(reg);
              gov::discard_snapshot_file(registry, world, snapshot_id);
          }, py::arg("registry"), py::arg("world"), py::arg("snapshot_id"));

    m.def("world_delete_snapshot",
          [](const py::dict& reg, const std::string& world, const std::string& snapshot_id) {
              auto registry = reg_in(reg);
              gov::delete_snapshot(registry, world, snapshot_id);
              return reg_out(registry);
          }, py::arg("registry"), py::arg("world"), py::arg("snapshot_id"));

    // ---- 回滚与归档（W3） ----
    // 回滚不改注册表，所以不返回新注册表。registry_dir 是注册表文件所在目录（与 world_create /
    // world_delete 同一参数），世界 home 与归档目录只从它推出。C++ 的连接探测（world_in_use）只是
    // 纵深防御，看得见哪些连接取决于日志模式（见 world_store.hpp rollback_world）；进程内的安全
    // 由调用方保证（WorldManager 的租约、旧 Runtime 弱引用、遗留 Runtime 登记）。
    // 同一世界的回滚已串行化（WorldManager 全程持管理锁）。复制快照 + integrity_check 可能要
    // 几秒，释放 GIL。C++ 的测试钩子（free_space、before_replace）不暴露。
    // 回滚预检：world_rollback 第 1–4 步的只读检查（同顺序、同错误码），什么都不动。活动世界
    // 回滚在停引擎之前先调它，拒掉不存在的快照、缺失的快照文件、不支持的后端、磁盘不足。
    // 通过不代表 world_rollback 一定成功（它自己再查一遍）。磁盘守卫会 statvfs，释放 GIL。
    m.def("world_check_rollback",
          // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
          [](const py::dict& reg, const std::string& reg_dir, const std::string& world,
             const std::string& snapshot_id, const std::string& vector_backend) {
              const auto registry = reg_in(reg);
              gov::RollbackOptions opts;
              opts.vector_backend = vector_backend;
              const py::gil_scoped_release release;
              gov::check_rollback(registry, reg_dir, world, snapshot_id, opts);
          }, py::arg("registry"), py::arg("registry_dir"), py::arg("world"),
          py::arg("snapshot_id"), py::kw_only(), py::arg("vector_backend") = "sqlite");

    m.def("world_rollback",
          // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
          [](const py::dict& reg, const std::string& reg_dir, const std::string& world,
             const std::string& snapshot_id, const std::string& vector_backend) {
              const auto registry = reg_in(reg);
              gov::RollbackOptions opts;
              opts.vector_backend = vector_backend;
              gov::RollbackResult result;
              {
                  const py::gil_scoped_release release;
                  result = gov::rollback_world(registry, reg_dir, world, snapshot_id, opts);
              }
              return py::dict("archive_path"_a = result.archive_path,
                              "restored_bytes"_a = result.restored_bytes);
          }, py::arg("registry"), py::arg("registry_dir"), py::arg("world"),
          py::arg("snapshot_id"), py::kw_only(), py::arg("vector_backend") = "sqlite");

    m.def("world_list_archives",
          // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
          [](const py::dict& reg, const std::string& reg_dir, const std::string& world) {
              const auto registry = reg_in(reg);
              std::vector<gov::ArchiveEntry> listed;
              {
                  const py::gil_scoped_release release;
                  listed = gov::list_rollback_archives(registry, reg_dir, world);
              }
              py::list out;
              for (const auto& item : listed) {
                  out.append(py::dict("name"_a = item.name, "size_bytes"_a = item.size_bytes));
              }
              return out;
          }, py::arg("registry"), py::arg("registry_dir"), py::arg("world"));

    // 归档是整份旧库，删除可能较慢，释放 GIL。返回删掉的文件数。
    m.def("world_purge_archives",
          // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
          [](const py::dict& reg, const std::string& reg_dir, const std::string& world) {
              const auto registry = reg_in(reg);
              const py::gil_scoped_release release;
              return gov::purge_rollback_archives(registry, reg_dir, world);
          }, py::arg("registry"), py::arg("registry_dir"), py::arg("world"));
}

}  // namespace starling::bindings
