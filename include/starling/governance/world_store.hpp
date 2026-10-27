#pragma once

// world_store.hpp — 世界注册表（W1）与快照（W2）的唯一权威实现。
//
// 设计稿：docs/superpowers/specs/2026-10-25-world-scene-management-design.md
//   §3 世界注册表、§4 快照。
//
// 一个世界 = 一个 SQLite 文件 + 一个租户 id。注册表 worlds.json 是世界路径的
// 唯一来源：任何 API 都不接受客户端传入文件路径。绑定层（Python / HTTP）只做
// 转发；注册、校验、保留策略与快照语义全部在这里。

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <map>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace starling::governance {

class WorldStoreError : public std::runtime_error {
public:
    WorldStoreError(std::string code, const std::string& detail);
    [[nodiscard]] const std::string& code() const noexcept;
private:
    std::string code_;
};
// code 取值：invalid_world_name | world_exists | world_not_found | world_protected
//           | registry_corrupt | invalid_retention | snapshot_not_found
//           | insufficient_disk | snapshot_failed | invalid_snapshot_kind
//           | world_tenant_mismatch（verify_world_tenant：库里有别的租户的行）
//           | snapshot_unsupported_backend（take_snapshot / rollback_world：vector_backend 不是 sqlite）
//           | snapshot_corrupt（rollback_world：快照文件缺失、打不开或 integrity_check 不过）
//           | world_in_use（rollback_world：别的连接开着要被替换的库，见第 8 步）

struct SnapshotEntry {
    std::string id;           // 20261025T011200Z-a1b2
    std::string path;         // 绝对路径
    std::string kind;         // "auto" | "manual"
    std::string reason;       // manual 时 "manual"
    std::string note;
    std::string created_at;   // ISO-8601 UTC 秒精度
    std::string world_time;   // 快照覆盖到的世界时刻水位，可为空
    std::int64_t size_bytes = 0;
};

struct WorldEntry {
    std::string name;
    std::string tenant;
    std::string db_path;      // 绝对路径
    std::string snapshot_dir; // 绝对路径
    std::string label;
    std::string created_at;
};

struct Registry {
    int version = 1;
    std::string default_world = "default";
    std::string active = "default";
    int snapshot_retention = 5;
    std::map<std::string, WorldEntry> worlds;                       // 按 name 排序
    std::map<std::string, std::vector<SnapshotEntry>> snapshots;    // world name → 列表
};

[[nodiscard]] bool is_valid_world_name(std::string_view name);
// load 与 save 用同一套校验（registry_corrupt / invalid_retention）：
//   - default / active 已登记，snapshot_retention >= 2；
//   - 除 default 外每个世界名都满足 is_valid_world_name；
//   - 每个 db_path / snapshot_dir 都是绝对路径；
//   - 非 default 世界的 db_path 与 snapshot_dir 在字面上位于 <registry_dir>/worlds/<name>/ 之下，
//     default 世界的 snapshot_dir 同样位于 <registry_dir>/worlds/<default>/ 之下（它的库保持原地，
//     db_path 不受此限）；registry_dir 取注册表文件所在目录；
//   - 每份快照的 kind 是 manual / auto，path 在字面上位于所属世界的 snapshot_dir 之下；
//   - snapshots 的每个键都是已登记的世界。
[[nodiscard]] Registry load_registry(const std::filesystem::path& registry_path);
void save_registry(const std::filesystem::path& registry_path, const Registry& reg);
// 注册表文件不存在时，创建只含 default 世界的注册表并保存。
// 注册表已存在时，原样返回，不修改 default 的路径。
[[nodiscard]] Registry ensure_registry(const std::filesystem::path& registry_path,
                                       const std::filesystem::path& default_db_path,
                                       const std::string& default_tenant);
// 新世界目录为 <registry_dir>/worlds/<name>/，库文件为 world.db，快照目录为 snapshots/。
// 只创建目录和注册项，不创建库文件，库文件留到首次激活时由 SqliteAdapter 建。
// tenant 固定为 name（新建世界不是分叉，没有来源租户）。
WorldEntry create_world(Registry& reg, const std::filesystem::path& registry_dir,
                        const std::string& name, const std::string& label,
                        std::string_view now_iso);
// 拒绝删除 default 和当前活动世界，抛 world_protected。
// 删除注册项、对应的快照列表，并删除 <registry_dir>/worlds/<name>/ 整个目录。
// 只删 registry_dir 之下的路径（防止注册表被篡改后删到外部目录）：<registry_dir>/worlds
// 本身解析后（例如它是指向外部的符号链接）不在 registry_dir 之下时抛 snapshot_failed，
// 什么都不删，注册项保留。
void delete_world(Registry& reg, const std::filesystem::path& registry_dir,
                  const std::string& name);
void set_active(Registry& reg, const std::string& name);

// ---- JSON 文本（绑定层的序列化入口，格式与 worlds.json 逐字一致） -------------
//
// 绑定层把注册表在 Python dict 与 Registry 之间转换时只走这四个函数，序列化
// 因此只有 C++ 一份实现。
[[nodiscard]] std::string registry_to_json(const Registry& reg);
// 解析并校验（与 load_registry 同一套检查）：JSON 语法错误、字段缺失或类型不符、
// 默认/活动世界未登记抛 registry_corrupt，snapshot_retention < 2 抛 invalid_retention。
[[nodiscard]] Registry registry_from_json(const std::string& text);
// 单个世界/快照的 JSON，与注册表里对应条目逐字一致（世界条目不含 name，name 是注册表的键）。
[[nodiscard]] std::string world_entry_to_json(const WorldEntry& entry);
[[nodiscard]] std::string snapshot_entry_to_json(const SnapshotEntry& entry);

// ---- 世界统计与快照（W2） --------------------------------------------------

struct WorldStats {
    std::int64_t db_bytes = 0;        // 主文件 + -wal 的字节数；文件不存在时为 0
    std::int64_t live_bytes = 0;      // (page_count - freelist_count) * page_size
    std::int64_t statements = 0;      // WHERE tenant_id = tenant
    std::int64_t engrams = 0;         // WHERE tenant_id = tenant
    std::string world_time;           // 见 snapshot_world_time
};
// 只读打开 db_path（mode=ro）。库文件不存在时返回全 0 的统计，不抛异常。
// 表不存在时（库是空的、未迁移），对应计数为 0。
[[nodiscard]] WorldStats world_stats(const std::string& db_path, const std::string& tenant);

// 租户不变式（spec §2.1）：一个世界库里只允许有该世界自己的租户。只读打开 db_path，
// 逐个检查带 tenant_id 列的表，发现 tenant_id 非空且不等于 tenant 的行就抛
// world_tenant_mismatch（detail 点名第一张违规的表）。库文件不存在（新世界，首次激活）
// 时直接通过。库读不出时抛 snapshot_failed（与 world_stats 同一约定）。
void verify_world_tenant(const std::string& db_path, const std::string& tenant);

// 世界时刻水位：source_unit_meta 存在且有非空 observed_at 时取 MAX(observed_at)，
// 否则取 engrams 的 MAX(created_at)，都没有则为空字符串。只读，按 tenant 过滤。
[[nodiscard]] std::string snapshot_world_time(const std::string& db_path,
                                              const std::string& tenant);

struct SnapshotOptions {
    std::string kind = "manual";      // "manual" | "auto"
    std::string reason = "manual";
    std::string note;
    // 向量后端。只有 "sqlite" 的向量在库文件里，其余（zvec）快照会缺向量，拒绝。
    std::string vector_backend = "sqlite";
    // 测试注入用：返回可用字节数。为空时用 std::filesystem::space(dir).available。
    std::function<std::int64_t(const std::filesystem::path&)> free_space;
};

// 1. 取世界；不存在抛 world_not_found。kind 非法抛 invalid_snapshot_kind，
//    vector_backend 不是 "sqlite" 抛 snapshot_unsupported_backend，保留份数非法抛
//    invalid_retention，三者都在任何文件 I/O 之前。
// 1b. 清扫 snapshot_dir 里上次崩溃留下的残留：名字形如快照 id 的 <id>.db.partial，
//    以及没有任何注册项引用的 <id>.db（改名之后、调用方存注册表之前崩溃的产物，没有
//    元数据，列不出来）。只认快照 id 形状的文件名，别的文件一概不碰；每个删除都经
//    remove_within（不出 snapshot_dir）。清扫失败只记日志，不影响本次快照。
//    调用方必须按世界串行化快照（WorldManager 的管理锁），否则会把并发快照刚改好名、
//    还没登记的文件当成残留。
// 2. 只读打开 db_path，计算 live_bytes；free_space(snapshot_dir) < 3 * live_bytes 时
//    抛 insufficient_disk（不写任何文件）。恰好 3 倍放行。
// 3. id = compact_now() + "-" + 4 位随机十六进制；与该世界已有的 id 重复时重新生成。
// 4. 删掉残留的 <id>.db.partial，再用只读连接执行 VACUUM INTO ?（绑定参数）写到 partial。
// 5. 关闭连接，再用只读连接打开 partial，PRAGMA integrity_check 必须为 "ok"，
//    否则删掉 partial 并抛 snapshot_failed。
// 6. fs::rename(partial, <id>.db)，填 size_bytes、world_time、created_at。
// 7. 插到 reg.snapshots[world] 的开头（最新在前），然后调用 apply_retention。
//    成功的快照一定返回它的条目：修剪失败（旧快照路径无法解析或删不掉）在这里
//    被吞掉，不外抛。列表与磁盘仍一致（每个旧快照先删文件再摘注册项），只是
//    暂时多出几份，下一次 take_snapshot 或显式 apply_retention 会重试。
// 8. 不负责 save_registry，由调用方保存。
// opts.kind 不是 "manual" / "auto" 时在写任何文件之前抛 invalid_snapshot_kind
// （保留策略只认 "auto"，拼错会悄悄丢掉回滚锚点保护）。
// fs::space 返回「未知」（uintmax_t(-1)，FUSE / 网络文件系统）时跳过磁盘守卫。
// 任何 SQLite 错误都转成 snapshot_failed，并保证不留下 partial 文件。
SnapshotEntry take_snapshot(Registry& reg, const std::string& world,
                            const SnapshotOptions& opts);

// 按保留份数 N 修剪 reg.snapshots[world]，并删除对应的文件，返回被删除的 id 列表。
// 规则（spec §4.4）：
//   - 总数 <= N：不删。
//   - 超出部分从最旧的开始删，优先删 auto；auto 删完还超出时才删 manual，从最旧的开始。
//   - 但列表里有 auto 时，至少保留最新的 1 份 auto（回滚锚点）。
// 逐个「先删文件、再摘注册项」。路径解析后越出 snapshot_dir（被篡改的注册项、指向外部
// 的符号链接）时抛 snapshot_failed 并保留该注册项：文件没删，摘掉注册项就再也清不掉它。
std::vector<std::string> apply_retention(Registry& reg, const std::string& world);

// 删除一份快照（注册项 + 文件）。不存在时抛 snapshot_not_found。文件已经不在了也照删
// 注册项。只删 snapshot_dir 之下的文件：越界时抛 snapshot_failed，注册项保留。
void delete_snapshot(Registry& reg, const std::string& world, const std::string& snapshot_id);

// 只删一份快照的文件，不动注册表（reg 是 const）。给 take_snapshot 成功、调用方却没能
// 存下注册表时做补偿：新文件没有登记，不删就成了列不出来的孤儿。不存在抛
// world_not_found / snapshot_not_found，越出 snapshot_dir 抛 snapshot_failed。
void discard_snapshot_file(const Registry& reg, const std::string& world,
                           const std::string& snapshot_id);

// ---- 回滚与归档（W3） ------------------------------------------------------
//
// 设计稿 §5.1 语义 A（丢掉后续）。世界 home = <registry_dir>/worlds/<name>（与 create_world /
// delete_world 同一推导；snapshot_dir 不参与），归档目录为 <世界 home>/archive。回滚不写注册表。
// registry_dir 取注册表文件所在目录。
//
// 归档操作（回滚建硬链接、列出、清理）之前都先 fail closed，此时什么都还没建、没删：
//   a. <registry_dir>/worlds 解析符号链接后仍在 registry_dir 之下，否则 registry_corrupt
//      （与 load_registry 同一检查）；
//   b. 世界 home 解析符号链接后严格在 <registry_dir>/worlds 之下，否则 snapshot_failed（与
//      delete_world 拒删指向外部的世界目录同一边界）；
//   c. archive/ 解析符号链接后严格在世界 home 之下，否则 snapshot_failed。
// 回滚只在 a、b 通过之后才 create_directories(archive)，所以世界目录之外什么都不会被建出来。

struct RollbackOptions {
    // 向量后端。只有 "sqlite" 的向量在库文件里，其余（zvec）恢复不出完整的世界，拒绝（spec §12）。
    std::string vector_backend = "sqlite";
    // 测试注入用：返回可用字节数。为空时用 std::filesystem::space(dir).available。
    std::function<std::int64_t(const std::filesystem::path&)> free_space;
    // 测试注入用：归档名建好之后、原子替换之前（第 10 步与第 11 步之间）调用，参数是 partial
    // 的路径。抛异常或删掉 partial 即可模拟「替换失败」。为空时不调用。
    std::function<void(const std::filesystem::path& staged)> before_replace;
};

struct RollbackResult {
    std::string archive_path;   // 被替换的库现在的位置；库原本不存在时为空
    std::int64_t restored_bytes = 0;
};

// 把世界 world 的库替换成快照 snapshot_id 的内容（spec §5.1 语义 A）。
// 别的连接：读过这个库并且还开着的连接（同进程或别的进程，读者、闲置的写者都算）C++ 检测得到，
// 第 8 步拒绝（world_in_use）。只打开了、从没读过的连接不持锁，C++ 看不见它；调用方必须保证
// 这类连接不存在（Python 侧：打开该库的每条路径都在引擎租约之内，回滚等租约归零）。
// 不变式：库路径上任何时刻都是一份完整的库（替换前是旧库，替换后是新库），从不为空。
// 归档用硬链接建出来，替换是 rename(partial, 库) 一步原子完成。
// 顺序：
//   1. 取世界（world_not_found）与快照（snapshot_not_found）。opts.vector_backend 不是
//      "sqlite" 抛 snapshot_unsupported_backend。都在任何文件 I/O 之前。
//   1a. 世界 home 的 a、b 两项检查（见上）。
//   1b. 清扫库所在目录里上次回滚崩溃留下的 partial：名字严格为
//      `.<库文件名>.rollback-<16 位小写 hex>.partial` 的普通文件（跳过符号链接），每个删除都经
//      remove_within。再摘掉 archive 里与库是同一个文件（fs::equivalent）的归档名：上次回滚死在
//      第 9 步之后、第 11 步之前时留下的现役库第二个名字（删掉它只少一个名字）。清扫失败只记
//      日志，不影响本次回滚。调用方必须按世界串行化回滚。
//   2. 快照路径解析符号链接后必须严格在该世界 snapshot_dir 之下（snapshot_failed）。
//   3. 快照文件缺失或不是普通文件 → snapshot_corrupt。
//   4. free_space(库所在目录) < 2 × 快照文件大小 → insufficient_disk。
//   5. 把快照复制到库所在目录的 `.<库文件名>.rollback-<16 hex>.partial`。
//   6. 只读打开 partial，PRAGMA integrity_check 必须为 "ok"；打不开、不是 SQLite 同样算
//      （snapshot_corrupt）。校验的是要装上去的那份字节，不是快照文件。
//   7. verify_world_tenant(partial, 世界租户)（world_tenant_mismatch）。
//   8. 库路径存在但不是普通文件（例如符号链接）→ snapshot_failed。库旁边的 `-wal` 或
//      `-journal` 存在且非空（或不是普通文件）→ snapshot_failed（还有未合并的写入、写连接或
//      热日志）；库不存在时同样检查，否则残留的 WAL / 热日志会被 SQLite 重放到恢复出来的库上。
//      库存在时：前 16 字节必须是 "SQLite format 3\0"，否则 snapshot_failed（default 世界的
//      db_path 不受布局约束）；partial 沿用库的权限位；最后紧挨着第 9 步探测别的连接：新开一条
//      读写连接（不 CREATE），busy_timeout 0，`PRAGMA locking_mode=EXCLUSIVE; BEGIN EXCLUSIVE`
//      拿不到锁（SQLITE_BUSY / SQLITE_LOCKED）→ world_in_use，其他探测失败 → snapshot_failed。
//      探测排在 -wal / -journal 检查之后，不会把残留的 WAL 或热日志重放进旧库。
//   9. 库存在时再做一遍 a、b，然后 create_directories(<世界 home>/archive)（c：解析符号链接后
//      必须仍在世界 home 之下），用 create_hard_link 给库建归档名
//      `<archive>/<库文件名>.pre-rollback-<compact_now>-<4 hex>`（名字被占用就重抽）。建不了
//      （EXDEV、文件系统不支持硬链接、权限）→ snapshot_failed，什么都没变。
//   10. 删掉库旁边的空 `-wal` / `-journal` 和 `-shm`（只读读者会留下 32 KB 的 `-shm` 与
//      0 字节的 `-wal`）。
//   11. rename(partial, 库路径)，原子替换。旧 inode 只剩归档名这一个名字。
// 第 1–9 步任何失败：目标库原样不动，partial 删掉。
// 第 10–11 步失败：库路径上仍是旧库，摘掉归档名（经 remove_within），删掉 partial，抛
// snapshot_failed。归档名摘不掉时它是现役库的第二个名字：记 stderr，错误信息写明不能用写
// 连接打开它（清理它只删一个名字，无害）。
// 不改注册表。所有非 WorldStoreError 的异常都转成 snapshot_failed。
RollbackResult rollback_world(const Registry& reg, const std::filesystem::path& registry_dir,
                              const std::string& world, const std::string& snapshot_id,
                              const RollbackOptions& opts);

struct ArchiveEntry {
    std::string name;            // 文件名，例如 "world.db.pre-rollback-20261026T120000Z-ab12"
    std::int64_t size_bytes = 0;
};

// 列出 <世界 home>/archive 下文件名形如 "*.pre-rollback-<YYYYMMDDTHHMMSSZ>-<4 hex>" 的
// 普通文件（跳过符号链接），按名字降序（最新在前）。目录不存在时返回空。与现役库是同一个文件
// （fs::equivalent）的条目不是归档，跳过（不计个数、不计字节、不清理）。
// 不存在的世界抛 world_not_found；a、b、c 检查（见上）不通过、或读不出时抛 registry_corrupt /
// snapshot_failed。
[[nodiscard]] std::vector<ArchiveEntry> list_rollback_archives(
    const Registry& reg, const std::filesystem::path& registry_dir, const std::string& world);

// 删除 list_rollback_archives 列出的全部文件，每个都经 remove_within(archive 目录, 文件)。
// 返回删除的个数。确认越界的文件不删，抛 snapshot_failed。
std::size_t purge_rollback_archives(const Registry& reg, const std::filesystem::path& registry_dir,
                                    const std::string& world);

}  // namespace starling::governance
