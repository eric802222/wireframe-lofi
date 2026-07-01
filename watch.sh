#!/bin/bash
# 監看 .wf.yaml 變動 → 自動重渲（微調時即時看結果）。
# Usage:
#   ./watch.sh [render 旗標...] [資料夾或檔案]     省略路徑則看 examples/
#   例：./watch.sh 20_Areas/…/yaml            （一般渲染）
#       ./watch.sh --bundle --debug 某夾       （邊改邊看單檔評審原型）
# 每秒輪詢整棵樹的 *.wf.yaml mtime；因含 include/layout，任一檔變動即重渲「頂層頁」
# （改 component/layout 也會連帶更新用它的頁面）。Ctrl-C 停止。零依賴（find + mtime，相容 macOS bash）。
DIR="$(cd "$(dirname "$0")" && pwd)"

FLAGS=""
while [ "$#" -gt 0 ] && [ "${1#--}" != "$1" ]; do FLAGS="$FLAGS $1"; shift; done
TARGET="${1:-$DIR/examples}"
if [ -d "$TARGET" ]; then FOLDER="$TARGET"; else FOLDER="$(dirname "$TARGET")"; fi

find_all() { find "$FOLDER" -name '*.wf.yaml' "$@"; }   # 整棵樹（含 components/ layouts/）

rebuild() {   # 頂層頁重渲（component/layout 靠被 include 帶進來，非直接渲染）
  if [ -d "$TARGET" ]; then "$DIR/render.sh" $FLAGS "$TARGET"/*.wf.yaml
  else "$DIR/render.sh" $FLAGS "$TARGET"; fi
}

MARKER="$(mktemp)"
trap 'rm -f "$MARKER"; echo; echo "停止監看。"; exit 0' INT TERM

echo "▶ 初次渲染 $TARGET ..."
rebuild
touch "$MARKER"
echo "👀 watching $TARGET — 改任一 .wf.yaml 即自動重渲（Ctrl-C 停止）"

while true; do
  sleep 1
  changed="$(find_all -newer "$MARKER")"
  [ -z "$changed" ] && continue
  touch "$MARKER"
  printf '↻ %s → rebuild\n' "$(echo "$changed" | xargs -n1 basename 2>/dev/null | paste -sd' ' -)"
  rebuild || echo "  [warn] 渲染失敗，繼續監看"
done
