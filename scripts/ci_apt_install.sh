#!/usr/bin/env bash
# CI 装 apt 依赖：先按 runner 默认的源装，失败就换到 Ubuntu 官方源再装一次。
#
# 为什么：GitHub 的 ubuntu-24.04 runner 把 apt 源写成 mirror+file:/etc/apt/apt-mirrors.txt，第一项是
# azure.archive.ubuntu.com。2026-11-11 这个域名在 runner 上解析失败了两个多小时（「Temporary failure resolving」），
# cpp-build-test 连续 5 次停在装依赖这一步，代码一次也没编译。apt 自带的重试只会反复问同一个解析不了的域名，
# 所以第二轮把源换成 archive.ubuntu.com / security.ubuntu.com（与 Azure 镜像独立的域名）。
#
# 用法：scripts/ci_apt_install.sh <包名>...
# 只在 CI runner 上用（会改 /etc/apt 的源，需要 sudo）。
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <package>..." >&2
  exit 2
fi

APT_OPTS=(-o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30)

install_once() {
  sudo apt-get "${APT_OPTS[@]}" update &&
    sudo apt-get "${APT_OPTS[@]}" install -y --no-install-recommends "$@"
}

if install_once "$@"; then
  exit 0
fi

echo "::warning::apt install failed with the runner's default sources; retrying with archive.ubuntu.com / security.ubuntu.com"

# 把 mirror+file:/etc/apt/apt-mirrors.txt（及任何 azure 镜像）替换成官方源。24.04 用 deb822 格式的
# /etc/apt/sources.list.d/ubuntu.sources；老格式的 /etc/apt/sources.list 也一并处理（文件不存在就跳过）。
for f in /etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list; do
  [ -f "$f" ] || continue
  sudo sed -i -E \
    -e 's#mirror\+file:/etc/apt/apt-mirrors\.txt#http://archive.ubuntu.com/ubuntu/#g' \
    -e 's#https?://azure\.archive\.ubuntu\.com/ubuntu/?#http://archive.ubuntu.com/ubuntu/#g' \
    "$f"
done
# security 套件走 security.ubuntu.com（官方源的约定），其余套件留在 archive.ubuntu.com。
if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then
  sudo python3 - /etc/apt/sources.list.d/ubuntu.sources <<'PY'
import re, sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
stanzas = re.split(r"\n\s*\n", text.strip())
out = []
for st in stanzas:
    if re.search(r"^Suites:.*-security", st, re.M):
        st = re.sub(r"^URIs:.*$", "URIs: http://security.ubuntu.com/ubuntu/", st, flags=re.M)
    out.append(st)
open(path, "w", encoding="utf-8").write("\n\n".join(out) + "\n")
PY
fi
sudo apt-get clean
install_once "$@"
