#!/bin/bash
# Usage: ./render.sh [file.wf.yaml ...]   （省略則跑 examples/*.wf.yaml）
#
# 每個 .wf.yaml → .html（自帶 CSS、零 <script>）+ .png（JS 停用截圖）
#                + .clean.png（剝離 Layer2 標註的乾淨 UI 版）
# 畫布尺寸：YAML 內 canvas: 1100x / 1200x900 / x800
# Layer2 邊註（note）對齊靠瀏覽器量測後烤進 DOM（零 JS 產物）。
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
DEBUG=0; BUNDLE=0
while :; do case "$1" in
  --debug) DEBUG=1; shift;;   # 出 .debug.html（可點擊註記+匯出）
  --bundle) BUNDLE=1; shift;; # 併成單檔 prototype.html（左 nav + 走動線）；可疊 --debug
  *) break;; esac; done
if [ "$#" -eq 0 ]; then set -- "$DIR"/examples/*.wf.yaml; fi

PY=""
for cand in "${WFYAML_PY:-}" python3 /usr/bin/python3 /opt/homebrew/bin/python3 python; do
  [ -n "$cand" ] || continue
  loc="$(command -v "$cand" 2>/dev/null)" || continue
  if "$loc" -c "import playwright, yaml" 2>/dev/null; then PY="$loc"; break; fi
done
if [ -z "$PY" ]; then
  echo "  [error] 找不到裝了 playwright + pyyaml 的 python。pip3 install playwright pyyaml && python3 -m playwright install chromium；或設 WFYAML_PY=<路徑>" >&2
  exit 1
fi

# bundle / debug：都在瀏覽器跑、不需截圖 → 直接用 compiler 產出後結束
if [ "$BUNDLE" = 1 ]; then
  FLAGS="--bundle"; [ "$DEBUG" = 1 ] && FLAGS="$FLAGS --debug"
  "$PY" "$DIR/wfyaml.py" $FLAGS "$@"
  if [ "$DEBUG" = 1 ]; then
    echo "  → 開 prototype.debug.html：左 nav 切頁走動線；切「模式:註記」點元素寫建議→「匯出」貼給我"
  else
    echo "  → 開 prototype.html：左 nav 切頁、點連結走動線（零 JS 可點原型）"
  fi
  exit 0
fi
if [ "$DEBUG" = 1 ]; then
  "$PY" "$DIR/wfyaml.py" --debug "$@"
  echo "  → 用瀏覽器開 .debug.html：點元素寫建議，右上「匯出」複製後貼給我改 YAML"
  exit 0
fi

"$PY" - "$DIR" "$@" <<'PYEOF'
import sys, os, glob
SKILL_DIR = sys.argv[1]
sys.path.insert(0, SKILL_DIR)
import wfyaml
from playwright.sync_api import sync_playwright

PAD = 24
files = []
for a in sys.argv[2:]:
    if a.lower().endswith(('.html', '.png')):
        a = a.rsplit('.', 1)[0]
        a = a + '.wf.yaml' if os.path.exists(a + '.wf.yaml') else a + '.yaml'
    g = sorted(glob.glob(a))
    files.extend(g if g else ([a] if os.path.exists(a) else []))

# 量測 note 對齊：把 note 對到 [^N] 標記高度、遇疊往下推，位置烤進 DOM。
ALIGN = r"""() => {
  const gutter = document.querySelector('.wf-gutter'); if (!gutter) return;
  const root = document.querySelector('.wf-root');
  const gTop = gutter.getBoundingClientRect().top, BIG = 1e9;
  const items = [...gutter.children].map(note => {
    const key = note.getAttribute('data-anchor'); let el = null;
    if (key && key.indexOf('ref-') === 0) el = document.querySelector('.wf-ref[data-ref="' + key.slice(4) + '"]');
    const want = el ? (el.getBoundingClientRect().top - gTop) : BIG;
    return { note, want };
  });
  items.sort((a, b) => a.want - b.want);
  let cursor = 0, maxB = 0; const GAP = 8;
  for (const it of items) {
    it.note.style.position = 'absolute'; it.note.style.left = '0'; it.note.style.right = '0';
    const top = Math.max(it.want === BIG ? cursor : it.want, cursor);
    it.note.style.top = top + 'px'; cursor = top + it.note.offsetHeight + GAP; maxB = top + it.note.offsetHeight;
  }
  if (root.offsetHeight < maxB) root.style.minHeight = maxB + 'px';
}"""

import re as _re2
def make_svg(html_text, w, h):
    """把 show-all 的 HTML 包進 <foreignObject> → 向量 SVG（瀏覽器渲染完美；不支援 foreignObject 的 viewer 會空白）。"""
    style = _re2.search(r'<style>(.*?)</style>', html_text, _re2.S).group(1)
    body = _re2.search(r'<body[^>]*>(.*)</body>', html_text, _re2.S).group(1)
    # 瀏覽器序列化的 HTML → XHTML 良構：void 元素自閉、&nbsp; 轉合法實體（foreignObject 走 XML parser）
    body = _re2.sub(r'<(hr|br|img|input|meta|link|col|source|wbr|area|base|embed)\b([^>]*?)/?>',
                    r'<\1\2/>', body)
    body = body.replace('&nbsp;', '&#160;')
    W, H = int(w) + PAD * 2, int(h) + PAD * 2
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<foreignObject x="0" y="0" width="{W}" height="{H}">'
            f'<div xmlns="http://www.w3.org/1999/xhtml" style="padding:{PAD}px;background:#fff;'
            f"font-family:'Sarasa Mono TC','Courier New',monospace;\">"
            f'<style><![CDATA[{style}]]></style>{body}</div></foreignObject></svg>')


def shoot(page, png):
    box = page.locator('.wf-root').bounding_box()
    need = int(box['y'] + box['height'] + PAD + 8)
    if need > page.viewport_size['height']:
        page.set_viewport_size({'width': page.viewport_size['width'], 'height': need})
        box = page.locator('.wf-root').bounding_box()
    page.screenshot(path=png, clip={'x': max(0, box['x'] - PAD), 'y': max(0, box['y'] - PAD),
                                    'width': box['width'] + PAD * 2, 'height': box['height'] + PAD * 2})
    return int(box['width']), int(box['height'])

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(java_script_enabled=True, viewport={'width': 1920, 'height': 700})
    page = ctx.new_page()
    import re as _re
    for f in files:
        src = open(f).read()
        basedir = os.path.dirname(f) or '.'
        stem = _re.sub(r'\.(wf\.)?ya?ml$', '', f)
        base = os.path.basename(stem)
        for rid, htmlout in wfyaml.compile_all(src, basedir, base):   # 每路由各一份
            s2 = stem + (('.' + rid) if rid else '')
            html_path = s2 + '.html'
            open(html_path, 'w').write(htmlout)
            page.goto('file://' + os.path.abspath(html_path), wait_until='load')
            page.wait_for_timeout(200)
            page.evaluate(ALIGN)
            open(html_path, 'w').write(page.content())   # 位置烤進 DOM，產物零 <script>（存出=互動真捲版）
            # PNG 模式：scroll 區塊全展開 + 畫捲軸示意（只影響截圖，不寫回 .html）
            page.evaluate("() => document.querySelector('.wf-root').classList.add('wf-show-all')")
            page.wait_for_timeout(50)
            w, h = shoot(page, s2 + '.png')              # 標註版（含 Layer2）
            open(s2 + '.svg', 'w').write(make_svg(page.content(), w, h))  # 向量版（同 show-all）
            page.evaluate("() => document.querySelector('.wf-root').classList.add('wf-clean')")
            shoot(page, s2 + '.clean.png')               # 乾淨 UI 版（剝離 Layer2）
            print(f"  rendered: {os.path.basename(s2)}.png (+.svg +.clean.png) {w}x{h}")
    browser.close()

# 自動產畫面互動流程圖（每個被渲染的資料夾一張；需 graphviz dot、且 ≥2 畫面）
import shutil, subprocess
if shutil.which('dot'):
    for d in sorted({os.path.dirname(os.path.abspath(f)) or '.' for f in files}):
        subprocess.run([sys.executable, os.path.join(SKILL_DIR, 'flowmap.py'), d], check=False)
PYEOF
