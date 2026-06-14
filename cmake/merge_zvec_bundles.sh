#!/bin/bash
# P3.b1 phase 5: zvec 产物合并脚本(ExternalProject post-build 调用)。
#
# zvec 不导出 C++ target,30+ 静态库散在 4+ 目录(含 arrow ExternalProject 深层
# 内部路径)。本脚本用 find 收集(不写死深层路径,zvec/arrow 升级脚本不变)+ macOS
# libtool -static 合并为两个稳定 bundle:
#   libzvec_plugins.a — core_knn/metric/plugin 等需 static 注册到 Factory 的插件,
#                       starling 端 -force_load(否则未引用的注册 .o 被丢弃)。
#   libzvec_main.a    — zvec + arrow + rocksdb + protobuf + 全部依赖,普通链接。
# 关键:force_load 只针对 plugins —— force_load 整个 bundle 会强拉 thrift SSL
# socket(arrow/parquet 依赖,zvec 不用)暴露 OpenSSL 未定义符号。
#
# 用法: merge_zvec_bundles.sh <zvec_build_dir> <out_dir>
set -euo pipefail
BUILD_DIR="$1"
OUT="$2"
mkdir -p "$OUT"
cd "$BUILD_DIR"

# plugins:binding force_load 的 core_*(diskann/rabitq 在 macOS 不产出,跳过)。
plugins=()
for p in libcore_knn_flat libcore_knn_flat_sparse libcore_knn_hnsw \
         libcore_knn_hnsw_sparse libcore_knn_ivf libcore_knn_vamana \
         libcore_knn_cluster libcore_plugin libcore_metric \
         libcore_mix_reducer libcore_quantizer libcore_utility; do
    f=$(find . -name "${p}.a" -not -path '*.dir/*' | head -1)
    [ -n "$f" ] && plugins+=("$f")
done
if [ "${#plugins[@]}" -eq 0 ]; then
    echo "merge_zvec_bundles: ERROR no core plugin .a found in $BUILD_DIR" >&2
    exit 1
fi
libtool -static -o "$OUT/libzvec_plugins.a" "${plugins[@]}"

# main = 全部 .a - plugins - diskann/rabitq(macOS 跳过) - ExternalProject 内部重复版。
_all=$(mktemp)
_plg=$(mktemp)
find . -name '*.a' \
    | grep -viE 'CMakeFiles|\.dir/|libtesting|re2_ep-prefix|utf8proc_ep-prefix|zlib_ep-build|ARROW\.BUILD-build/release|libcore_knn_diskann|libcore_knn_hnsw_rabitq' \
    > "$_all"
printf '%s\n' "${plugins[@]}" > "$_plg"
grep -vFf "$_plg" "$_all" | xargs libtool -static -o "$OUT/libzvec_main.a"
rm -f "$_all" "$_plg"

echo "merge_zvec_bundles: wrote $OUT/libzvec_plugins.a + $OUT/libzvec_main.a"
