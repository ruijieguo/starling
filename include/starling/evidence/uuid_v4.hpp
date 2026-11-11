#pragma once
// UUID v4(RFC 4122 的版本位与变体位),36 个字符的 8-4-4-4-12 小写十六进制。engram 的 id(EngramStore::put)与
// events 行的身份 incarnation(迁移 0040,memoryops::remember_event_begin)共用这一个生成器。
//
// 随机源:每个线程一个 std::mt19937_64,首次使用时用 std::random_device 播种(32 位种子)。同一线程连续取到的值
// 重复的概率可以忽略;两个不同线程(或进程)取到同一个值,要两个生成器的种子相同、且取到序列里同一个位置。例外:进程
// fork 之后不 exec,子进程继承父进程的生成器状态,父子两边接下来取到的序列相同(服务进程不 fork)。不用作密钥或令牌。
#include <string>

namespace starling::evidence {

[[nodiscard]] std::string generate_uuid_v4();

}  // namespace starling::evidence
