#pragma once
#include <stdexcept>
#include <string>

namespace starling::persistence { class SqliteAdapter; }

namespace starling::governance {

class RuntimeSupervisor;  // fwd

// 治理写拒绝。std::runtime_error 子类 → pybind register_exception → _core.WriteGateRejected。
class WriteGateRejected : public std::runtime_error {
 public:
  explicit WriteGateRejected(const std::string& what) : std::runtime_error(what) {}
};

// 前台写准入门(策略一处):adapter 无钩子 → 放行;钩子 reject → 抛 WriteGateRejected。
// 7 个核心写函数各首行调一次。
void require_write_admission(const persistence::SqliteAdapter& adapter);

// production Runtime 构造时调一次:把 adapter 的钩子接到 sup.check_write()。
void install_write_gate(persistence::SqliteAdapter& adapter, const RuntimeSupervisor& sup);

}  // namespace starling::governance
