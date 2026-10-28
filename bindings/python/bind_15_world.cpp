// bind_15_world — 世界注册表、快照与自动快照（W1–W4）。注册表在 Python 侧以 dict 表示，
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

py::object text_or_none(const std::string& text) {
    return text.empty() ? py::object(py::none()) : py::object(py::str(text));
}

// 单份快照的 dict（world_take_snapshot / world_take_auto_snapshot 返回的那份）。W4 的三个字段
// 总是在，缺省为 None，调用方不必区分新旧条目：sessions_complete（int | None）、session_id
// （str | None）、content_mark（str | None，只给内部与测试用，HTTP 白名单不外露）。
// 注册表 dict 里的条目不补这些键：注册表逐字往返（见文件头）。
py::object snap_out(const gov::SnapshotEntry& snap) {
    auto out = to_py(gov::snapshot_entry_to_json(snap)).cast<py::dict>();
    for (const char* key : {"sessions_complete", "session_id", "content_mark"}) {
        out.attr("setdefault")(key, py::none());
    }
    return out;
}

[[noreturn]] void invalid_auto(const std::string& detail) {
    throw gov::WorldStoreError("invalid_auto_snapshot", detail);
}

// 绑定层只做类型归一：Python 的 int（bool 不算）→ int64，放不下 int64 的按越界报。
// 取值范围（interval_hours 0–8760、limit 1–1000）由 C++ 校验。类型不对与越界同一个码
// invalid_auto_snapshot，路由只映射一个 400。
std::int64_t int64_in(const py::handle& value, const std::string& field) {
    if (!py::isinstance<py::int_>(value) || py::isinstance<py::bool_>(value)) {
        invalid_auto(field + " must be an integer");
    }
    int overflow = 0;
    const auto number = PyLong_AsLongLongAndOverflow(value.ptr(), &overflow);
    if (overflow != 0) { invalid_auto(field + " is out of range"); }
    if (PyErr_Occurred() != nullptr) { throw py::error_already_set(); }
    return static_cast<std::int64_t>(number);
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
gov::AutoSnapshotConfig auto_config_in(const py::handle& on_session, const py::handle& hours) {
    if (!py::isinstance<py::bool_>(on_session)) { invalid_auto("on_session must be a bool"); }
    return gov::AutoSnapshotConfig{.on_session = on_session.cast<bool>(),
                                   .interval_hours = int64_in(hours, "interval_hours"),};
}

// {"on_session": bool, "interval_hours": int}，两个键都要有，多余的键忽略（与注册表的解析一致）。
gov::AutoSnapshotConfig auto_config_from_dict(const py::handle& obj) {
    if (!py::isinstance<py::dict>(obj)) {
        invalid_auto("auto_snapshot must be a dict {on_session, interval_hours}");
    }
    const auto config = py::reinterpret_borrow<py::dict>(obj);
    if (!config.contains("on_session") || !config.contains("interval_hours")) {
        invalid_auto("auto_snapshot needs both on_session and interval_hours");
    }
    return auto_config_in(config.attr("get")("on_session"), config.attr("get")("interval_hours"));
}

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

    // auto_snapshot：None 时用新世界的默认值（按会话开、按时间关，C++ create_world 的默认参数）；
    // 否则是 {"on_session": bool, "interval_hours": int}，形状或类型不对、越界都抛
    // invalid_auto_snapshot，此时什么都没建。
    m.def("world_create",
          // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
          [](const py::dict& reg, const std::string& reg_dir, const std::string& name,
             const std::string& label, const std::string& now_iso, const py::object& auto_snapshot) {
              auto registry = reg_in(reg);
              const auto world =
                  auto_snapshot.is_none()
                      ? gov::create_world(registry, reg_dir, name, label, now_iso)
                      : gov::create_world(registry, reg_dir, name, label, now_iso,
                                          auto_config_from_dict(auto_snapshot));
              return py::dict("registry"_a = reg_out(registry),
                              "world"_a = to_py(gov::world_entry_to_json(world)));
          }, py::arg("registry"), py::arg("registry_dir"), py::arg("name"),
          py::arg("label"), py::arg("now_iso"), py::arg("auto_snapshot") = py::none());

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
              return py::dict("registry"_a = reg_out(registry), "snapshot"_a = snap_out(snap));
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

    // ---- 自动快照与会话清单（W4） ----
    // 三个函数都释放 GIL（参数先在持 GIL 时转换好）。只改内存里的注册表，调用方保存。

    // 改一个世界的自动快照配置，返回新注册表。world_not_found；类型不对或 interval_hours 不在
    // 0–8760 抛 invalid_auto_snapshot。两种情况入参 dict 都不变。
    m.def("world_set_auto_snapshot",
          // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
          [](const py::dict& reg, const std::string& world, const py::object& on_session,
             const py::object& interval_hours) {
              auto registry = reg_in(reg);
              const auto config = auto_config_in(on_session, interval_hours);
              {
                  const py::gil_scoped_release release;
                  gov::set_auto_snapshot(registry, world, config);
              }
              return reg_out(registry);
          }, py::arg("registry"), py::arg("world"), py::arg("on_session"),
          py::arg("interval_hours"));

    // 按触发判断要不要拍一份自动快照（规则全在 C++ take_auto_snapshot）。trigger 是 "session" |
    // "interval"；now_iso 是调用方的时钟，必须是 YYYY-MM-DDTHH:MM:SSZ（快照 id 前缀与 created_at
    // 都取它；带小数秒等形状不对抛 invalid_auto_snapshot）；session_id 只给 "session" 触发。
    // 返回 {"registry", "snapshot", "skipped", "refused"}：拍了时 snapshot 是条目（同 world_take_snapshot
    // 的形状）、skipped 与 refused 为 None；没拍时 snapshot 为 None、skipped 是原因（disabled |
    // known_session | unchanged | not_due | empty | unsupported_backend），registry 与入参内容相同。
    // 修剪卡住而拒绝拍时 refused 是原因（"retention cannot prune ..."），snapshot 与 skipped 为 None，
    // registry 是部分修剪后的注册表（已删文件的条目已摘掉）：调用方必须保存它，并计为失败
    // （码 snapshot_failed）。拍了时快照文件已落盘，调用方存注册表失败要 world_discard_snapshot_file
    // 补偿（同 world_take_snapshot）。
    m.def("world_take_auto_snapshot",
          // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
          [](const py::dict& reg, const std::string& world, const std::string& trigger,
             const std::string& now_iso, const std::string& session_id,
             const std::string& vector_backend) {
              auto registry = reg_in(reg);
              const gov::AutoTrigger auto_trigger{
                  .kind = trigger, .session_id = session_id, .now_iso = now_iso,};
              gov::SnapshotOptions base;
              base.vector_backend = vector_backend;
              gov::AutoSnapshotResult result;
              {
                  const py::gil_scoped_release release;
                  result = gov::take_auto_snapshot(registry, world, auto_trigger, base);
              }
              py::object snapshot = py::none();
              if (result.taken.has_value()) { snapshot = snap_out(*result.taken); }
              return py::dict("registry"_a = reg_out(registry), "snapshot"_a = snapshot,
                              "skipped"_a = text_or_none(result.skipped),
                              "refused"_a = text_or_none(result.refused));
          }, py::arg("registry"), py::arg("world"), py::arg("trigger"), py::arg("now_iso"),
          py::arg("session_id") = "", py::kw_only(), py::arg("vector_backend") = "sqlite");

    // 会话清单（设计稿 §7），只读打开该世界的库。返回 {"total", "null_observed", "truncated",
    // "sessions": [{session_id, units, speakers, first_at, last_at, anchor}]}；first_at / last_at
    // 没有时间时为 None，anchor 为 {"snapshot_id", "created_at"} 或 None。limit 不是整数或不在
    // 1–1000 抛 invalid_auto_snapshot，世界不存在抛 world_not_found，库读不出抛 snapshot_failed。
    m.def("world_list_sessions",
          [](const py::dict& reg, const std::string& world, const py::object& limit) {
              const auto registry = reg_in(reg);
              const auto max_rows = int64_in(limit, "limit");
              gov::SessionList listed;
              {
                  const py::gil_scoped_release release;
                  listed = gov::list_sessions(registry, world, max_rows);
              }
              py::list sessions;
              for (const auto& row : listed.rows) {
                  py::object anchor = py::none();
                  if (!row.anchor_snapshot_id.empty()) {
                      anchor = py::dict("snapshot_id"_a = row.anchor_snapshot_id,
                                        "created_at"_a = row.anchor_created_at);
                  }
                  sessions.append(py::dict("session_id"_a = row.session_id, "units"_a = row.units,
                                           "speakers"_a = row.speakers,
                                           "first_at"_a = text_or_none(row.first_at),
                                           "last_at"_a = text_or_none(row.last_at),
                                           "anchor"_a = anchor));
              }
              return py::dict("total"_a = listed.total, "null_observed"_a = listed.null_observed,
                              "truncated"_a = listed.truncated, "sessions"_a = sessions);
          }, py::arg("registry"), py::arg("world"), py::arg("limit") = 200);

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
