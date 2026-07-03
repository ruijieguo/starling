#include "starling/governance/write_gate.hpp"
#include "starling/governance/runtime_supervisor.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::governance {

void require_write_admission(const persistence::SqliteAdapter& adapter) {
  if (!adapter.write_admitted()) {
    throw WriteGateRejected("write rejected: runtime not accepting writes");
  }
}

void install_write_gate(persistence::SqliteAdapter& adapter, const RuntimeSupervisor& sup) {
  // 引用捕获:production 下 adapter 与 sup 同由 Runtime 持有,sup 生命周期不短于
  // adapter 的写调用(sup 本身也持 adapter 的 has_index 引用,互引用,Runtime 共管)。
  adapter.set_write_admit([&sup]() { return sup.check_write() == WriteGateDecision::kAccept; });
}

}  // namespace starling::governance
