#!/usr/bin/env python3
"""
wireframe-yaml compiler (prototype v0.1)

把「語義化 YAML」編譯成低保真、零 JS 的 HTML wireframe。
設計脈絡見 DISCUSSION.md；核心取捨：

- 結構解析全交給 yaml.safe_load（免手刻 parser）；本檔只做「YAML 樹 → HTML」的分派。
- 葉子是語義 role（text.title / button / status…），非視覺標記；渲染用自帶的
  封印 CSS 與 icon 函式（fa_svg / lu_svg / ICONS）。
- 顏色封印（只 tone / severity 語義色）；尺寸走 Tailwind token、間距走語義 scale。

v0.1 涵蓋：canvas / body（獨立頁）、extends+slots（layout 合併）、include+with+as:placeholder、
row/col/grid（+box/justify/align/spacer/span/gap/padding/欄寬）、葉子詞彙全表、行內 markdown、
checkbox/radio task-list 語法、to/link、tone、name、Layer2 spotlight/note（基本）。
待補（見 README）：routes 多輸出、as:{stage,state} 元件變體、when: 節點過濾。
"""
import sys, os, re, html, gzip, json, base64, glob, yaml

# ---- 自含資產（封印 CSS + icon 圖庫），可整包帶走；無外部依賴 ----
# assets/ 為自帶的封印視覺（CSS + Font Awesome / Lucide 圖庫）；要更新視覺改 assets/wf.css 或重新打包圖庫。
_HERE = os.path.dirname(os.path.abspath(__file__))
_ASSETS = os.path.join(_HERE, 'assets')


def _load_css():
    try:
        return open(os.path.join(_ASSETS, 'wf.css'), encoding='utf-8').read()
    except Exception as e:  # pragma: no cover
        sys.stderr.write(f"[error] 讀不到 assets/wf.css：{e}\n")
        raise


_BASE_CSS = _load_css()

# ---- style（風格）：assets/styles/<name>/style.css；素材 url(name) 依實際副檔名內嵌 data-URI（可換 svg/png/jpg）----
_STYLE = None
_ASSET_MIME = {'.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
               '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp',
               '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.otf': 'font/otf'}


def _inline_asset(ref, base_dir):
    """ref = 相對名（可不帶副檔名）→ 找 base_dir/<name>.* 內嵌成 data-URI。抓 name、不鎖副檔名。"""
    if ref.startswith(('data:', 'http:', 'https:', '#', '/')):
        return None
    stem = os.path.splitext(ref)[0]
    cands = sorted(set(glob.glob(os.path.join(base_dir, ref)) + glob.glob(os.path.join(base_dir, stem + '.*'))))
    cands = [c for c in cands if os.path.splitext(c)[1].lower() in _ASSET_MIME]
    if not cands:
        sys.stderr.write(f"[warn] style 素材找不到：{ref}（於 {base_dir}）\n")
        return None
    f = cands[0]
    mime = _ASSET_MIME[os.path.splitext(f)[1].lower()]
    b64 = base64.b64encode(open(f, 'rb').read()).decode()
    return f'data:{mime};base64,{b64}'


def _style_css():
    """clean 為永遠載入的視覺基底；選定 style（非 clean）疊在其上覆寫。"""
    css = _load_style('clean')
    if _STYLE and _STYLE != 'clean':
        css += _load_style(_STYLE)
    return css


def _hoist_imports(css):
    """@import 必須位於樣式表最前（否則瀏覽器忽略）。把散落各處的 @import 全部提到最前。"""
    pat = r'''@import\s+(?:url\(|["'])[^;]+;'''
    imports = re.findall(pat, css)
    if not imports:
        return css
    return '\n'.join(imports) + '\n' + re.sub(pat, '', css)


def _load_style(name):
    """讀 styles/<name>/style.css，把相對 url(素材) 內嵌成 data-URI（輸出仍自含）。"""
    if not name:
        return ''
    d = os.path.join(_ASSETS, 'styles', name)
    css_path = os.path.join(d, 'style.css')
    if not os.path.exists(css_path):
        raise ValueError(f"找不到 style「{name}」：{css_path}")
    css = open(css_path, encoding='utf-8').read()
    return re.sub(r'url\(\s*([^)]+?)\s*\)',
                  lambda m: (f'url("{_inline_asset(m.group(1).strip(chr(39)+chr(34)), d)}")'
                             if _inline_asset(m.group(1).strip(chr(39) + chr(34)), d) else m.group(0)),
                  css)

# 內建幾何圖示（挑 Sarasa Mono 覆蓋得到的字元，避免 emoji tofu）
ICONS = {
    'list': '≡', 'pin': '⊙', 'document': '▤', 'reload': '↻', 'x': '✕',
    'check': '✓', 'clock': '◔', 'plus': '+', 'minus': '−',
    'caret-right': '▸', 'caret-bottom': '▾', 'caret-top': '▴', 'caret-left': '◂',
    'arrow-right': '→', 'trash': '⌦', 'pencil': '✎', 'warning': '⚠',
    'dollar': '$', 'lock-locked': '▣', 'lock-unlocked': '▢', 'star': '★',
    'ban': '⊘', 'magnifying-glass': '⌕', 'envelope-closed': '✉', 'cog': '⚙',
}

_fa_data, _fa_cache = None, {}
_lu_data, _lu_cache = None, {}


def _gz(name):
    try:
        with gzip.open(os.path.join(_ASSETS, name), 'rt', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def fa_svg(style, name):
    """Font Awesome：內嵌 <svg>（零 JS、離線）。讀自帶 assets/fa-icons.json.gz。"""
    global _fa_data
    if _fa_data is None:
        _fa_data = _gz('fa-icons.json.gz')
    key = (style, name)
    if key not in _fa_cache:
        entry = _fa_data.get(style, {}).get(name)
        if entry:
            w, h, path = entry
            _fa_cache[key] = (f'<svg class="wf-fa" viewBox="0 0 {w} {h}" '
                              f'xmlns="http://www.w3.org/2000/svg"><path d="{path}"/></svg>')
        else:
            _fa_cache[key] = f'<span class="wf-icon" title="fa:{style}:{name} (未找到)">◻</span>'
    return _fa_cache[key]


def lu_svg(name):
    """Lucide：stroke 線條風；讀自帶 assets/lucide-icons.json.gz。"""
    global _lu_data
    if _lu_data is None:
        _lu_data = _gz('lucide-icons.json.gz')
    if name not in _lu_cache:
        inner = _lu_data.get(name)
        if inner:
            _lu_cache[name] = ('<svg class="wf-lu" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                               'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
                               f'stroke-linejoin="round">{inner}</svg>')
        else:
            _lu_cache[name] = f'<span class="wf-icon" title="lu:{name} (未找到)">◻</span>'
    return _lu_cache[name]

# ---- 語義 scale / 對照表（集中一處 → 可 theme）----
GAP = {'none': '0', 'sm': 'var(--wf-space-sm)', 'md': 'var(--wf-space-md)', 'lg': 'var(--wf-space-lg)'}  # 語義間距 scale→CSS var(可 theme)；預設 md

# ---- 專案 semantic token（選配；wf.tokens.yaml）----
# 引用型 token：意圖名 → primitive 刻度。零設定=不載，全走內建 primitive。可攜地板：內建名恆效，
# token 只覆寫/加名，缺失優雅退回（未知名 → 內建預設 + lint warning）。詳見 DISCUSSION「semantic token」。
_TOKENS = {}


def _load_tokens(basedir):
    """探測專案 tokens（選配）。載入優先序：
    1. basedir/tokens/*.yaml（Phase 2a：多檔扁平化，各檔淺合併；同 key 後蓋前）
    2. basedir/wf.tokens.yaml（相容單檔）
    不存在則 _TOKENS 空、全用內建 primitive。
    """
    global _TOKENS
    _TOKENS = {}
    base = basedir or '.'
    tdir = os.path.join(base, 'tokens')
    if os.path.isdir(tdir):
        for fn in sorted(os.listdir(tdir)):
            if not (fn.endswith('.yaml') or fn.endswith('.yml')):
                continue
            try:
                data = yaml.safe_load(open(os.path.join(tdir, fn), encoding='utf-8')) or {}
                for k, v in data.items():
                    if isinstance(v, dict) and isinstance(_TOKENS.get(k), dict):
                        _TOKENS[k] = {**_TOKENS[k], **v}   # 淺合併同家族
                    else:
                        _TOKENS[k] = v
            except Exception as e:
                sys.stderr.write(f"[warn] 讀取 tokens/{fn} 失敗：{e}\n")
    # 相容單檔（若存在，疊加在目錄之上；同 key 後蓋前）
    p = os.path.join(base, 'wf.tokens.yaml')
    if os.path.exists(p):
        data = yaml.safe_load(open(p, encoding='utf-8')) or {}
        for k, v in data.items():
            if isinstance(v, dict) and isinstance(_TOKENS.get(k), dict):
                _TOKENS[k] = {**_TOKENS[k], **v}
            else:
                _TOKENS[k] = v


def _tokens_css():
    """引用型 token 編成 :root 別名（如 --wf-gap-section: var(--wf-space-lg)）。放 clean 之後 → 可引用 primitive。"""
    lines = []
    for name, prim in (_TOKENS.get('gap') or {}).items():
        lines.append(f'--wf-gap-{esc_attr(name)}:{GAP.get(str(prim), str(prim))};')
    return (':root{' + ''.join(lines) + '}') if lines else ''


def _gap(name):
    """gap/padding 值解析：內建 primitive 直用；專案 token → var 別名；未知 → 退回 md + warn。"""
    n = str(name)
    if n in GAP:
        return GAP[n]
    if n in (_TOKENS.get('gap') or {}):
        return f'var(--wf-gap-{n})'
    sys.stderr.write(f"[warn] 未知 gap/padding 值「{n}」→ 退回 md（可在 wf.tokens.yaml 定義為 semantic token）\n")
    return GAP['md']


def esc_attr(s):
    return re.sub(r'[^A-Za-z0-9_-]', '-', str(s))
JUSTIFY = {'between': 'space-between', 'end': 'flex-end', 'start': 'flex-start',
           'center': 'center', 'around': 'space-around'}
ALIGN = {'center': 'center', 'top': 'flex-start', 'bottom': 'flex-end',
         'baseline': 'baseline', 'stretch': 'stretch'}
CONTAINER_KEYS = {'row', 'col', 'grid', 'items', 'embed', 'include', 'slot'}
LEAF_ROLES = ['text.title', 'text.heading', 'text.label', 'text.strong', 'text.hint', 'text',
              'input', 'select', 'button', 'status.badge', 'status.muted', 'status.strong', 'status',
              'badge', 'alert', 'icon', 'divider', 'tabs', 'image', 'checkbox', 'radio', 'link',
              'progress', 'avatar']
TEXT_CLASS = {'text': 'wf-label', 'text.title': 'wf-h wf-h1', 'text.heading': 'wf-h wf-h2',
              'text.label': 'wf-label wf-fieldlabel', 'text.strong': 'wf-b', 'text.hint': 'wf-hint'}

_NOTES = []   # Layer2 note → 右側 gutter（供 render.sh 量測對齊（位置烤進 DOM））
_NCOUNT = 0
_PAGE_BASE = ''   # 目前頁面檔名 base，供 `to: "#stage.state"` 同頁路由連結解析
_DEBUG = False    # debug 模式：輸出 data-wf-src/data-wf-path 供評審回饋定位
_BUNDLE = False   # bundle 模式：連結改寫成單檔內錨點（#wf-pg-...）


def _stamp(node, src, path=''):
    """替每個 dict 節點蓋來源檔 `__src` 與檔內路徑 `__path`（scalar 於 render 時依位置算）。"""
    if isinstance(node, dict):
        node['__src'] = node.get('__src', src)
        node['__path'] = node.get('__path', path)
        for k, v in list(node.items()):
            if k in ('__src', '__path'):
                continue
            _stamp(v, src, (path + '.' + k) if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _stamp(v, src, f'{path}[{i}]')

# ---- 額外 CSS（基底 wf.css 沒有的：image 佔位 / spotlight / severity 別名 / 欄位標籤）----
CSS_EXTRA = r"""
.wf-image { display:flex; align-items:center; justify-content:center; min-height:64px;
  border:1px dashed #9ca3af; color:#9ca3af; border-radius:var(--wf-radius); font-size:.85em;
  background-image:linear-gradient(45deg,transparent 47%,#d1d5db 48%,#d1d5db 52%,transparent 53%),
                   linear-gradient(-45deg,transparent 47%,#d1d5db 48%,#d1d5db 52%,transparent 53%); }
.wf-fieldlabel { color:#6b7280; font-size:.9em; }
.wf-hyperlink { color:#2563eb; text-decoration:underline; text-underline-offset:2px; }
/* Layer2 spotlight（明顯是註記、非 UI；可剝離：.wf-clean 全部隱藏）*/
.wf-spot { position:relative; }
.wf-spot-focus  { background:rgba(253,224,71,.4); box-shadow:0 0 0 3px rgba(253,224,71,.4); border-radius:var(--wf-radius); }
.wf-spot-new::after { content:'NEW'; position:absolute; top:-8px; right:-8px; font-size:.6em; font-weight:700;
  background:#b45309; color:#fff; padding:1px 5px; border-radius:var(--wf-radius-pill); letter-spacing:.05em; }
.wf-spot-change { text-decoration:underline wavy #d97706; text-underline-offset:3px; }
.wf-spot-click  { outline:2px dashed #0d9488; outline-offset:3px; border-radius:var(--wf-radius); }
.wf-spotlabel { position:absolute; top:100%; left:0; margin-top:4px; white-space:nowrap;
  font-size:.7em; color:#0f766e; background:#f0fdfa; border:1px solid #99f6e4; border-radius:var(--wf-radius); padding:1px 6px; z-index:5; }
.wf-step { display:inline-flex; align-items:center; justify-content:center; width:16px; height:16px;
  margin-right:4px; font-size:.65em; font-weight:700; color:#fff; background:#0d9488; border-radius:var(--wf-radius-pill); vertical-align:middle; }
.wf-clean .wf-spot { background:none !important; box-shadow:none !important; outline:none !important; text-decoration:none !important; }
.wf-clean .wf-spot::after, .wf-clean .wf-spotlabel, .wf-clean .wf-step, .wf-clean .wf-gutter, .wf-clean .wf-ref { display:none !important; }
/* --- scroll 捲動：HTML 用瀏覽器原生捲軸（overflow:auto + 封頂，模擬真實）；PNG(wf-show-all) 全展開 + 手畫低保真示意 --- */
.wf-scroll { overflow-y:auto; }   /* HTML：內距純 md，原生捲軸自理，不預留 15px */
.wf-scroll-x { overflow-x:auto; }
/* PNG 才為 DOS bar 保留 gutter = 捲軸寬 15px + md 間距(.5rem)；!important 蓋過 inline padding shorthand */
.wf-show-all .wf-scroll { max-height:none !important; position:relative; padding-right:calc(15px + var(--wf-space-md)) !important; }
.wf-show-all .wf-scroll-x { overflow:visible; }
/* DOS 風捲軸示意（低保真）：▲ 上鈕 + ▒ dither 軌 + █ 方塊 thumb + ▼ 下鈕 */
.wf-sb { display:none; }
.wf-show-all .wf-sb { display:flex; flex-direction:column; position:absolute; top:0; right:0; bottom:0;
  width:15px; box-sizing:border-box; border:1px solid #6b7280; background:#e5e7eb;
  font:11px/12px 'Sarasa Mono TC','Courier New',monospace; color:#374151; text-align:center; }
.wf-sb-btn { height:14px; border:1px solid #6b7280; background:#d1d5db; }
.wf-sb-track { flex:1; position:relative;
  background-image:repeating-linear-gradient(45deg,#9ca3af 0 1px,transparent 1px 3px); }
.wf-sb-thumb { position:absolute; left:1px; right:1px; top:2px; height:40px; background:#6b7280; border:1px solid #374151; }
/* progress leaf：語義比例 fill bar；tone 走 Layer 1 顏色 */
.wf-progress { position:relative; display:block; height:.75rem; background:#e5e7eb;
  border-radius:var(--wf-radius-pill); overflow:hidden; min-width:4rem; }
.wf-progress-fill { position:absolute; top:0; left:0; bottom:0; background:#6b7280;
  border-radius:var(--wf-radius-pill); transition:width .2s ease; }
.wf-tone-danger  > .wf-progress-fill,
.wf-progress.wf-tone-danger  .wf-progress-fill { background:#dc2626; }
.wf-tone-warn    > .wf-progress-fill,
.wf-progress.wf-tone-warn    .wf-progress-fill { background:#f59e0b; }
.wf-tone-success > .wf-progress-fill,
.wf-progress.wf-tone-success .wf-progress-fill { background:#16a34a; }
.wf-tone-feature > .wf-progress-fill,
.wf-progress.wf-tone-feature .wf-progress-fill { background:#0d9488; }
.wf-tone-info    > .wf-progress-fill,
.wf-progress.wf-tone-info    .wf-progress-fill { background:#2563eb; }
.wf-progress-label { position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
  font-size:.7em; color:#111827; font-weight:600; }
/* avatar leaf：只 label(縮寫) + size(sm/md/lg)；圓形佔位，禁 src/bg（守視覺封印） */
.wf-avatar { display:inline-flex; align-items:center; justify-content:center;
  background:#e5e7eb; color:#374151; border:1px solid #9ca3af; border-radius:var(--wf-radius-pill);
  font-weight:600; text-transform:uppercase; }
.wf-avatar-sm { width:1.5rem; height:1.5rem; font-size:.65em; }
.wf-avatar-md { width:2.25rem; height:2.25rem; font-size:.8em; }
.wf-avatar-lg { width:3rem; height:3rem; font-size:1em; }
"""


# ---- --debug 評審回饋層（獨立模式；注入 JS+localStorage。一般輸出不含此，維持零 <script>）----
# reviewer 點元素→寫建議→localStorage 暫存→匯出 [id] role "內容" → 建議，貼回給 LLM 一次改 YAML。
DEBUG_CSS = r"""
.wf-annotate [data-wf-path]{cursor:pointer;}
.wf-annotate [data-wf-path]:hover{outline:2px solid #6366f1 !important;outline-offset:1px;}
.wf-dbg-has{outline:2px solid #ef4444 !important;outline-offset:1px;}
#wf-dbg{position:fixed;top:8px;right:8px;z-index:99999;background:#111827;color:#fff;
  padding:6px 10px;border-radius:var(--wf-radius);font:12px/1.4 sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.3);}
#wf-dbg button{margin-left:6px;font:inherit;cursor:pointer;border:0;border-radius:var(--wf-radius);padding:2px 8px;}
#wf-dbg-pop{position:absolute;z-index:100000;background:#fff;border:1px solid #6366f1;border-radius:var(--wf-radius);
  padding:8px;box-shadow:0 6px 20px rgba(0,0,0,.25);font:12px/1.4 sans-serif;color:#111;}
#wf-dbg-pop .h{font-weight:700;color:#6366f1;margin-bottom:4px;}
#wf-dbg-pop textarea{display:block;width:260px;height:60px;margin:4px 0;font:12px sans-serif;}
#wf-dbg-pop button{margin-right:6px;cursor:pointer;}
#wf-dbg-export{position:fixed;inset:8% 15%;z-index:100001;background:#fff;border:1px solid #333;
  border-radius:var(--wf-radius);padding:14px;box-shadow:0 10px 40px rgba(0,0,0,.35);font:13px sans-serif;color:#111;}
#wf-dbg-export textarea{display:block;width:100%;height:62vh;font:12px monospace;margin:8px 0;}
#wf-dbg-export button{cursor:pointer;padding:4px 12px;margin-right:8px;}
"""

DEBUG_JS = r"""
(function(){
  var KEY='wfdbg:'+location.pathname.split('/').pop();
  var store=JSON.parse(localStorage.getItem(KEY)||'{}');   // key = src|path
  function role(el){return ((''+el.className).match(/wf-[a-z0-9-]+/g)||[]).join(' ');}
  function snap(el){return (el.textContent||'').replace(/\s+/g,' ').trim().slice(0,48);}
  function keyOf(el){return (el.getAttribute('data-wf-src')||'')+'|'+(el.getAttribute('data-wf-path')||'');}
  function mark(){document.querySelectorAll('[data-wf-path]').forEach(function(el){el.classList.toggle('wf-dbg-has',!!store[keyOf(el)]);});}
  mark();
  var pop=null;
  function close(){if(pop){pop.remove();pop=null;}}
  function open(el){
    close();var k=keyOf(el),src=el.getAttribute('data-wf-src')||'',path=el.getAttribute('data-wf-path')||'',r=el.getBoundingClientRect();
    pop=document.createElement('div');pop.id='wf-dbg-pop';
    pop.style.top=(scrollY+r.bottom+4)+'px';pop.style.left=(scrollX+r.left)+'px';
    pop.innerHTML='<div class="h">'+src+' → '+path+'</div>';
    var ta=document.createElement('textarea');ta.value=(store[k]&&store[k].note)||'';ta.placeholder='修改建議…';
    var s=document.createElement('button');s.textContent='存';
    var d=document.createElement('button');d.textContent='刪';
    pop.appendChild(ta);pop.appendChild(s);pop.appendChild(d);document.body.appendChild(pop);ta.focus();
    s.onclick=function(){var v=ta.value.trim();
      if(v)store[k]={src:src,path:path,role:role(el),text:snap(el),note:v};else delete store[k];
      localStorage.setItem(KEY,JSON.stringify(store));mark();close();};
    d.onclick=function(){delete store[k];localStorage.setItem(KEY,JSON.stringify(store));mark();close();};
  }
  var ann=false;   // false=瀏覽(點擊可跳轉走動線)、true=註記(點擊開建議框)
  document.addEventListener('click',function(e){
    if(e.target.closest('#wf-dbg')||e.target.closest('#wf-dbg-pop')||e.target.closest('#wf-dbg-export'))return;
    if(!ann){close();return;}                    // 瀏覽模式：放行（連結照常導覽）
    var el=e.target.closest('[data-wf-path]');
    if(el){e.preventDefault();e.stopPropagation();open(el);}else close();
  },true);
  var bar=document.createElement('div');bar.id='wf-dbg';
  bar.innerHTML='<b>DEBUG</b><button id="wf-dbg-mode">模式:瀏覽</button><button id="wf-dbg-exp">匯出</button><button id="wf-dbg-clr">清除</button>';
  document.body.appendChild(bar);
  var mbtn=document.getElementById('wf-dbg-mode');
  mbtn.onclick=function(){ann=!ann;mbtn.textContent='模式:'+(ann?'註記':'瀏覽');document.body.classList.toggle('wf-annotate',ann);if(!ann)close();};
  document.getElementById('wf-dbg-clr').onclick=function(){if(confirm('清除本頁所有註記?')){store={};localStorage.removeItem(KEY);mark();}};
  document.getElementById('wf-dbg-exp').onclick=function(){
    var byFile={};Object.keys(store).forEach(function(k){var s=store[k];(byFile[s.src]=byFile[s.src]||[]).push(s);});
    var L=['# debug 註記（貼給 LLM 改 YAML）'];
    Object.keys(byFile).sort().forEach(function(f){
      L.push('','## '+f+'.wf.yaml');
      byFile[f].forEach(function(s){L.push('- ['+s.path+'] '+s.role+' "'+s.text+'" → '+s.note);});
    });
    if(L.length===1)L.push('(無註記)');
    var ov=document.createElement('div');ov.id='wf-dbg-export';
    var ta=document.createElement('textarea');ta.readOnly=true;ta.value=L.join('\n');
    var cp=document.createElement('button');cp.textContent='複製';cp.onclick=function(){ta.select();try{document.execCommand('copy');cp.textContent='已複製✓';}catch(e){}};
    var cl=document.createElement('button');cl.textContent='關閉';cl.onclick=function(){ov.remove();};
    ov.appendChild(ta);ov.appendChild(cp);ov.appendChild(cl);document.body.appendChild(ov);ta.select();
  };
})();
"""


def esc(s):
    return html.escape(str(s if s is not None else ''))


def _track(tok):
    """grid 欄寬 token → CSS track。寬度=關係：正道是 grow(填滿) / fit(依內容) / N%(比例)；
    絕對量值 w-N 是逃生門（破壞低保真，僅必要時用）。grow 與節點屬性 grow: true 同一心智模型。"""
    t = str(tok).strip()
    if t in ('grow', 'flex-1', 'fill', 'w-full'):   # grow=正名主詞；其餘為相容別名
        return '1fr'
    if t in ('fit', 'w-auto', 'auto'):              # fit=依內容正名
        return 'auto'
    m = re.match(r'[wh]-(\d+)$', t)             # Tailwind spacing：w-24/h-64 → rem
    if m:
        return f'{int(m.group(1)) * 0.25:g}rem'
    m = re.match(r'w-(\d+)/(\d+)$', t)          # 分數 → fr 比例
    if m:
        return f'{int(m.group(1))}fr'
    if re.match(r'\d+px$', t) or t.endswith('rem') or t.endswith('%'):
        return t
    if t.isdigit():
        return f'{t}fr'
    return t


def inline(s):
    """text 值內的行內 markdown：**粗** / *斜* / ~~刪除線~~ / [字](目標)。扁平、每葉子獨立。
    連結目標語義化：帶 `to:` 前綴 = wireframe 動線（依單頁/bundle/debug 輸出改寫）；否則 = 外部真連結原樣輸出。"""
    s = esc(s)

    def _a(m):
        txt, tgt = m.group(1), m.group(2)
        href = _href(tgt[3:]) if tgt.startswith('to:') else tgt   # to:→動線解析；否則外部字面（已於上方 esc）
        return f'<a class="wf-hyperlink" href="{href}">{txt}</a>'

    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _a, s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'~~(.+?)~~', r'<del>\1</del>', s)
    s = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', s)
    return s


def _icon(val):
    if isinstance(val, dict):
        st, name = val.get('set', 'fa'), val.get('name', '')
        return lu_svg(name) if st == 'lu' else fa_svg('fas', name)
    name = str(val)
    if name in ICONS:
        return f'<span class="wf-icon">{ICONS[name]}</span>'
    return fa_svg('fas', name)


def _slug(s):
    return re.sub(r'[^A-Za-z0-9]+', '-', str(s)).strip('-')


def _pgid(page, frag=''):
    return 'wf-pg-' + _slug(page) + (('-' + _slug(frag)) if frag else '')


def _href(target):
    # 純 wireframe 動線解析器：只收「已宣告為動線」的目標（block `to:` / inline `to:` 前綴）。
    # 外部/真連結由 link: 與無前綴 inline 走字面輸出，永不流經此處 → 不需在這裡嗅探 URL 長相。
    t = str(target)
    page, _, frag = t.partition('#')
    page = re.sub(r'\.html$', '', page)
    if _BUNDLE:                             # 單檔 bundle：連結 → 頁內錨點
        return '#' + _pgid(page or _PAGE_BASE, frag)
    if _DEBUG:                              # debug：連結指向 .debug.html（在 debug 頁間走動線）
        page = page or _PAGE_BASE
        return esc(f'{page}.{frag}.debug.html' if frag else f'{page}.debug.html')
    if t.endswith('.html'):
        return esc(t)
    if frag:
        return esc(f'{(page or _PAGE_BASE)}.{frag}.html')
    return esc(t + '.html')


def _attrs(d):
    return ''.join(f' {k}="{esc(v)}"' for k, v in d.items())


def _dbg_attrs(src, path):
    """debug 模式才輸出來源定位屬性（一般輸出保持乾淨）。"""
    if not _DEBUG or path is None:
        return {}
    a = {'data-wf-path': path}
    if src:
        a['data-wf-src'] = src
    return a


# --------------------------------------------------------------------------
# 葉子渲染（語義 role → HTML；用自帶 wf-class）
# --------------------------------------------------------------------------
def render_string(s, xattr=None):
    """裸字串葉子：role 前綴(`text.strong: x`) → 該葉子；checkbox/radio task-list；否則 text（行內 markdown）。"""
    A = _attrs(xattr or {})
    m = re.match(r'^([\w.]+):\s*(.*)$', s, re.S)
    if m and m.group(1) in LEAF_ROLES:
        return render_leaf({m.group(1): m.group(2)}, [], dict(xattr or {}))
    m = re.match(r'^\[([ xX])\]\s*(.*)$', s)
    if m:
        box = '☑' if m.group(1).lower() == 'x' else '☐'
        return f'<span class="wf-label"{A}><span class="wf-check">{box}</span> {inline(m.group(2))}</span>'
    m = re.match(r'^\(([ xXoO])\)\s*(.*)$', s)
    if m:
        dot = '◉' if m.group(1).lower() in ('x', 'o') else '○'
        return f'<span class="wf-label"{A}><span class="wf-radio">{dot}</span> {inline(m.group(2))}</span>'
    return f'<span class="wf-label"{A}>{inline(s)}</span>'


def render_leaf(d, xcls, xattr):
    role = next((r for r in LEAF_ROLES if r in d), None)
    val = d.get(role)
    cls = lambda base: ' '.join([base] + xcls)
    A = _attrs(xattr)

    if role in TEXT_CLASS:
        return f'<div class="{cls(TEXT_CLASS[role])}"{A}>{inline(val)}</div>'
    if role == 'input':
        ph = val.get('placeholder', '') if isinstance(val, dict) else val
        v = val.get('value') if isinstance(val, dict) else None
        inner = esc(v) if v else (esc(ph) or '&nbsp;&nbsp;')
        return f'<span class="{cls("wf-input")}"{A}>{inner}</span>'
    if role == 'select':
        txt = val.get('text', '') if isinstance(val, dict) else val
        return f'<span class="{cls("wf-select")}"{A}>{inline(txt)}</span>'
    if role == 'button':
        if isinstance(val, dict):
            txt, to, ic = val.get('text', ''), val.get('to'), val.get('icon')
            inner = (_icon(ic) + ' ' if ic else '') + inline(txt)
        else:
            txt, to, inner = val, None, inline(val)
        if to:
            return f'<a href="{_href(to)}" class="{cls("wf-btn wf-link")}"{A}>{inner}</a>'
        return f'<button class="{cls("wf-btn")}"{A}>{inner}</button>'
    if role in ('status', 'status.muted', 'status.strong', 'status.badge'):
        # status.badge = 舊 badge 合併進 status 家族（方角變體），wf-badge class 保留視覺
        lvl = {'status.muted': ' wf-tag-muted', 'status.strong': ' wf-tag-strong',
               'status.badge': ' wf-badge'}.get(role, '')
        if role == 'status.badge':
            return f'<label class="{cls("wf-badge")}"{A}>{inline(val)}</label>'
        return f'<span class="{cls("wf-tag" + lvl)}"{A}>{inline(val)}</span>'
    if role == 'badge':
        sys.stderr.write("[warn] badge: 已合併進 status 家族改名 status.badge:（deprecated，過渡期支援）\n")
        return f'<label class="{cls("wf-badge")}"{A}>{inline(val)}</label>'
    if role == 'alert':
        return f'<span class="{cls("wf-warn")}"{A}><span class="wf-icon">⚠</span> {inline(val)}</span>'
    if role == 'icon':
        return f'<span class="{cls("")}"{A}>{_icon(val)}</span>'
    if role == 'divider':
        return f'<hr class="{cls("wf-hr")}"{A}/>'
    if role == 'link':
        txt = val.get('text', '') if isinstance(val, dict) else val
        to = val.get('to', '#') if isinstance(val, dict) else '#'
        return f'<a class="{cls("wf-hyperlink")}" href="{esc(to)}"{A}>{inline(txt)}</a>'
    if role in ('checkbox', 'radio'):
        label = val.get('label', '') if isinstance(val, dict) else val
        checked = val.get('checked') if isinstance(val, dict) else False
        if role == 'checkbox':
            mark, mcls = ('☑' if checked else '☐'), 'wf-check'
        else:
            mark, mcls = ('◉' if checked else '○'), 'wf-radio'
        return f'<span class="{cls("")}"{A}><span class="{mcls}">{mark}</span> {inline(label)}</span>'
    if role == 'image':
        label = val.get('label', '') if isinstance(val, dict) else (val or '圖片')
        style = []
        if isinstance(val, dict):
            if val.get('w'):
                style.append(f'width:{_track(val["w"])}')
            if val.get('h'):
                style.append(f'height:{_track(val["h"])}')
            if val.get('ratio'):
                a, _, b = str(val['ratio']).partition('/')
                if b:
                    style.append(f'aspect-ratio:{a}/{b}')
        st = f' style="{";".join(style)}"' if style else ''
        return f'<div class="{cls("wf-image")}"{st}{A}>▧ {esc(label)}</div>'
    if role == 'tabs':
        items = val.get('items', []) if isinstance(val, dict) else (val or [])
        active = val.get('active') if isinstance(val, dict) else None
        out = ''
        for i, t in enumerate(items):
            is_a = (t == active) or (active is None and i == 0)
            out += f'<div class="wf-tab{" wf-tab-active" if is_a else ""}">{inline(t)}</div>'
        return f'<div class="{cls("wf-tabs flex flex-row")}"{A}>{out}</div>'
    if role == 'progress':
        # value 0-1 語義比例；label 走 inline markdown
        # 注意：tone/name 應寫在節點層（跟 progress key 同層 sibling），而非 value 內。
        if isinstance(val, dict):
            v = val.get('value', 0)
            label = val.get('label', '')
            # 相容 & 提醒：若 tone/name 誤寫在 value 內，警告並忽略（走節點層是 canonical）
            if 'tone' in val or 'name' in val:
                sys.stderr.write(f"[warn] progress: tone/name 應寫在節點層（跟 progress key 同層），非 value 內。當前值忽略。\n")
        else:
            v = val
            label = ''
        try:
            pct = max(0.0, min(1.0, float(v))) * 100
        except (TypeError, ValueError):
            sys.stderr.write(f"[warn] progress.value 需為 0-1 數字（收到 {v!r}）→ 退回 0\n")
            pct = 0
        lbl_html = f'<span class="wf-progress-label">{inline(label)}</span>' if label else ''
        return f'<div class="{cls("wf-progress")}"{A}><div class="wf-progress-fill" style="width:{pct:.1f}%"></div>{lbl_html}</div>'
    if role == 'avatar':
        # 只接 label(字母縮寫) + size(sm/md/lg)；禁 src/bg（守北極星② 視覺封印）
        if isinstance(val, dict):
            if 'src' in val or 'bg' in val:
                sys.stderr.write(f"[warn] avatar 禁 src/bg（違反視覺封印）→ 忽略\n")
            label = val.get('label', '')
            size = val.get('size', 'md')
        else:
            label = str(val or '')
            size = 'md'
        if size not in ('sm', 'md', 'lg'):
            sys.stderr.write(f"[warn] avatar.size 只接 sm/md/lg（收到 {size!r}）→ 退回 md\n")
            size = 'md'
        return f'<div class="{cls(f"wf-avatar wf-avatar-{size}")}"{A}>{esc(label)}</div>'
    return f'<span class="wf-label">{esc(d)}</span>'


# --------------------------------------------------------------------------
# 容器渲染（row / col / grid + box + 對齊 + 間距）
# --------------------------------------------------------------------------
def _items_of(d, direction):
    """回傳 (itemkey, items)：itemkey 供組出子節點的來源路徑（col[i] vs items[i]）。

    canonical form（DISCUSSION 2026-07-03 Phase 1a）：
    - grid：值是欄寬 tracks，items 走 `items:` 是允許的（不衝突）
    - row/col 直接接 list：`row: [ ... ]` items 短寫；同時給 `items:` = 雙重宣告 → error
    - row/col 接 str（justify 短寫，如 `row: between`）：items 走 `items:` 是允許的
    - row/col 值為 dict：dict-form 明拒（P0） → error
    - 無方向 key（box 隱式 col）：`items:` 是允許的
    """
    if direction == 'grid':
        return 'items', (d.get('items', []) or [])
    v = d.get(direction)
    if isinstance(v, list):
        if 'items' in d:
            raise ValueError(
                f"{direction}: [ ... ] 與 items: 同時存在（雙重宣告衝突）。\n"
                f"list 短寫已承載 items；請移除多餘的 items: key。"
            )
        return direction, v
    if isinstance(v, dict):
        raise ValueError(
            f"{direction}: 不接受 dict 形式（收到 keys={list(v)}）。\n"
            f"container 屬性一律 sibling — 方向 key `{direction}:` 只承載 items 短寫或 justify 短寫。\n"
            f"請改寫成：\n"
            f"  {direction}: [ item1, item2, ... ]     # items 短寫\n"
            f"  gap: sm                                 # 屬性放 sibling\n"
            f"  align: center"
        )
    return 'items', (d.get('items', []) or [])


def render_container(d, xcls, xattr, src=None, base=''):
    direction = 'grid' if 'grid' in d else 'row' if 'row' in d else 'col'
    itemkey, items = _items_of(d, direction)
    boxed = bool(d.get('box'))     # box 只畫框；標題請用 text.title / text.heading（語義化）
    csrc = src                     # 子節點來源路徑基準（scalar 依 base+itemkey+索引算）
    base = base or ''
    cpath = lambda i: (f'{base}.{itemkey}[{i}]' if base else f'{itemkey}[{i}]')

    cls = ['wf-node'] + xcls
    style = []
    style.append('gap:' + _gap(d.get('gap', 'md')))   # 預設 md；semantic token 走 _gap 解析
    pad = d.get('padding')                     # box 內距走 scale，預設 md；非 box 不寫則無
    if pad is not None:
        style.append('padding:' + _gap(pad))
    elif boxed:
        style.append('padding:' + GAP['md'])

    if direction == 'grid':
        cls += ['grid', 'items-start']
        g = d.get('grid')
        if isinstance(g, list):
            style.append('grid-template-columns:' + ' '.join(_track(x) for x in g))
        elif isinstance(g, int):
            style.append(f'grid-template-columns:repeat({g},minmax(0,1fr))')
        else:
            style.append('grid-template-columns:repeat(3,minmax(0,1fr))')
        body = ''.join(render_item(it, csrc, cpath(i)) for i, it in enumerate(items))
    elif direction == 'row':
        cls += ['flex', 'flex-row']
        style.append('align-items:' + ALIGN.get(d.get('align', 'center'), 'center'))
        j = d.get('row') if isinstance(d.get('row'), str) else d.get('justify')
        if j in JUSTIFY:
            style.append('justify-content:' + JUSTIFY[j])
        body = ''.join('<span class="wf-spacer"></span>' if _is_spacer(it)
                       else render_item(it, csrc, cpath(i)) for i, it in enumerate(items))
    else:
        cls += ['flex', 'flex-col']
        if d.get('align') in ALIGN:
            style.append('align-items:' + ALIGN[d['align']])
        if d.get('justify') in JUSTIFY:          # col 主軸=垂直：end 置底 / between 上下撐開…（需容器有高度）
            style.append('justify-content:' + JUSTIFY[d['justify']])
        body = ''.join(render_item(it, csrc, cpath(i)) for i, it in enumerate(items))

    if boxed:
        cls.append('wf-box')
    if d.get('grow'):              # 結構原語：吃掉父容器主軸剩餘空間（如主體區撐滿→footer 自然置底）
        style.append('flex:1 1 auto')
        style.append('min-height:0')
        if direction == 'grid':    # grid 撐滿時讓列分佈填滿（預設 items-start 由 align: 覆寫）
            style.append('align-content:stretch')
    if d.get('scroll'):            # 垂直捲：封頂高度 + overflow（HTML 真捲、PNG 展開+示意）
        cls.append('wf-scroll')
        sv = d['scroll']
        style.append('max-height:' + (_track(sv) if sv is not True else '16rem'))
    if d.get('scroll-x'):          # 水平捲
        cls.append('wf-scroll-x')
    if isinstance(d.get('span'), int):
        style.append(f'grid-column:span {d["span"]}')
    if d.get('scroll'):
        style.append('padding-right:%s' % GAP['md'])   # HTML 右 gutter = md；PNG 由 .wf-show-all 覆寫成 15px+md
        body += ('<div class="wf-sb" aria-hidden="true"><div class="wf-sb-btn">▲</div>'
                 '<div class="wf-sb-track"><div class="wf-sb-thumb"></div></div>'
                 '<div class="wf-sb-btn">▼</div></div>')
    st = f' style="{";".join(style)}"' if style else ''
    return f'<div class="{" ".join(cls)}"{st}{_attrs(xattr)}>{body}</div>'


def render_widget(d, xcls, xattr, src=None, path=None):
    """示意複雜元件（table/chart/rich editor…的代表物）。屬 leaf 家族的巢狀 dict-form
    （同 button/image：屬性掛在 widget 底下，與節點 metadata name/tone 分層）。自我聲明保真度：
    宣告能力(can) 與/或 示意內部排版(body，複用 row/col/grid/leaf 與 to: 動線)，
    但自帶「示意」標記 → 內部一律讀作代表性、非規格，實作內部歸元件庫。
    讀成一句話：`is`（是什麼）+ `can`（能做什麼）。純量簡寫 `widget: 工單表格` = `{is: 工單表格}`。"""
    w = d['widget']
    if not isinstance(w, dict):
        w = {} if w is True else {'is': w}
    ident = w.get('is', '元件')
    can = w.get('can') or []
    body = w.get('body')
    bpath = (f'{path}.widget.body' if path else 'widget.body')

    head = (f'<div class="wf-widget-head"><span class="wf-widget-label">{esc(ident)}</span>'
            f'<span class="wf-widget-tag">◫ 示意</span></div>')
    can_html = ''
    if can:
        chips = ''.join(f'<span class="wf-tag wf-tag-muted">{esc(c)}</span>' for c in can)
        can_html = f'<div class="wf-widget-caps">{chips}</div>'
    if body is None:
        body_html = ''
    elif isinstance(body, dict):
        body_html = render_container(body, [], {}, src, bpath)
    elif isinstance(body, list):
        body_html = ''.join(render_item(it, src, f'{bpath}[{i}]') for i, it in enumerate(body))
    else:
        body_html = render_item(body, src, bpath)
    foot = '<div class="wf-widget-foot">實作依設計／元件庫</div>'

    cls = ['wf-node', 'wf-widget'] + xcls
    return f'<div class="{" ".join(cls)}"{_attrs(xattr)}>{head}{can_html}{body_html}{foot}</div>'


def _ckeys(it):
    """內容鍵（排除 __src/__path 蓋章）→ 供結構判斷不受蓋章干擾。"""
    return set(it) - {'__src', '__path'}


def _is_spacer(it):
    return it == 'spacer' or (isinstance(it, dict) and _ckeys(it) == {'spacer'})


def is_container(d):
    return any(k in d for k in CONTAINER_KEYS)


# --------------------------------------------------------------------------
# item 分派 + 共用包裝（name / tone / severity / to / spotlight / note / span）
# --------------------------------------------------------------------------
_LAYER_Z = {'base': 1, 'overlay': 10, 'notify': 20, 'top': 30}   # 封閉語意 z-scale（帶→z-index，封 renderer）

# 組合型 semantic token：意圖名 → 組合 pin/modal/layer 原語。內建預設 = 可攜地板；
# 專案可在 wf.tokens.yaml 的 `overlay:` 覆寫/加名。node 上顯式 pin/modal/layer 可覆寫 token 預設。
_OVERLAY_DEFAULTS = {
    'dialog':  {'pin': 'center', 'modal': True, 'layer': 'overlay'},
    'drawer':  {'pin': 'right', 'modal': True, 'layer': 'overlay'},   # 側邊預設右；要左用 `pin: left` 覆寫
    'sheet':   {'pin': 'bottom', 'modal': True, 'layer': 'overlay'},
    'toast':   {'pin': 'bottom-right', 'layer': 'notify'},
    'loading': {'pin': 'center', 'modal': True, 'layer': 'top'},
}


def _overlay_tokens():
    return {**_OVERLAY_DEFAULTS, **(_TOKENS.get('overlay') or {})}


def render_item(it, src=None, path=None):
    global _NCOUNT
    if _is_spacer(it):
        return '<span class="wf-spacer"></span>'
    if isinstance(it, str):
        return _wrap({}, render_string(it, _dbg_attrs(src, path)))
    if not isinstance(it, dict):
        return f'<span class="wf-label">{esc(it)}</span>'

    d = dict(it)
    esrc = d.pop('__src', None) or src        # dict 自帶來源路徑優先（跨 component/slot），否則用父算的
    epath = d.pop('__path', None)
    epath = epath if epath is not None else path

    _ov = _overlay_tokens()                   # 組合型 semantic token 展開：dialog/drawer/toast… → pin+modal+layer
    _role = next((k for k in _ckeys(d) if k in _ov), None)
    if _role:
        content = d.pop(_role)
        for k, v in _ov[_role].items():
            d.setdefault(k, v)                # token 給預設；node 顯式 pin/modal/layer 可覆寫
        d.setdefault('box', True)
        if isinstance(content, list):
            d.setdefault('col', content)
        elif content not in (None, True):
            d.setdefault('col', [content])
    name = d.pop('name', None)
    tone = d.pop('tone', None) or d.pop('severity', None)
    is_widget = 'widget' in d
    block_to = d.pop('to', None) if (is_container(d) or is_widget) else None
    spot = d.pop('spotlight', None)
    note = d.pop('note', None)
    span = d.pop('span', None)
    pin = d.pop('pin', None)          # 浮層：錨點(center/邊/角)
    modal = d.pop('modal', None)      # 浮層：擋後面(scrim + inert)
    layer = d.pop('layer', None)      # 浮層：z 帶(base/overlay/notify/top)

    xcls, xattr = [], {}
    if _role:                          # 語義 token 展開後保留角色指紋：可區分/針對 styling、產物語義可讀（drawer ≠ 一般 box）
        xcls.append('wf-role-' + esc_attr(_role))
        xattr['data-wf-role'] = _role
    if tone:
        xcls.append('wf-tone-' + str(tone))
    if name:
        xattr['data-name'] = name
    xattr.update(_dbg_attrs(esrc, epath))
    if isinstance(span, int):
        xattr['style'] = f'grid-column:span {span}'

    if is_widget:
        core = render_widget(d, xcls, xattr, esrc, epath)
    elif is_container(d):
        d.setdefault('span', span) if isinstance(span, int) else None
        core = render_container(d, xcls, xattr, esrc, epath)
    else:
        core = render_leaf(d, xcls, xattr)

    if block_to:
        core = f'<a href="{_href(block_to)}" class="wf-blocklink-a wf-link">{core}</a>'
    if pin or modal:                  # 浮層：抽離流排、錨定所在容器、依 z 帶疊放
        pos = re.sub(r'[^a-z-]', '', str(pin).lower()) if pin else 'center'
        z = _LAYER_Z.get(str(layer), _LAYER_Z['overlay'])
        lcls = 'wf-layer wf-pin-' + pos + (' wf-modal' if modal else '')
        core = f'<div class="{lcls}" style="z-index:{z}">{core}</div>'
    core = _wrap({'spotlight': spot, 'note': note}, core)
    return core


def _wrap(layer2, core):
    """套 Layer2：spotlight overlay + note 標記（收進 gutter）。"""
    global _NCOUNT
    spot, note = layer2.get('spotlight'), layer2.get('note')
    if spot:
        if isinstance(spot, dict):
            kind, text, step = spot.get('kind', 'focus'), spot.get('text'), spot.get('step')
        else:
            kind, text, step = str(spot), None, None
        extra = (f'<span class="wf-step">{esc(step)}</span>' if step is not None else '') + \
                (f'<span class="wf-spotlabel">{esc(text)}</span>' if text else '')
        core = f'<span class="wf-spot wf-spot-{esc(kind)}">{extra}{core}</span>'
    if note:
        ref = note.get('ref') if isinstance(note, dict) else None
        text = note.get('text') if isinstance(note, dict) else note
        if ref is not None:
            core += f'<sup class="wf-ref" data-ref="{esc(ref)}">[{esc(ref)}]</sup>'
            _NOTES.append({'anchor': 'ref-' + str(ref), 'num': str(ref), 'text': text})
        else:
            global _NCOUNT
            _NCOUNT += 1
            _NOTES.append({'anchor': 'auto-%d' % _NCOUNT, 'num': None, 'text': text})
    return core


def build_gutter():
    if not _NOTES:
        return ''
    items = ''
    for n in _NOTES:
        badge = f'<span class="wf-mnote-num">[{esc(n["num"])}]</span> ' if n['num'] else ''
        items += f'<div class="wf-mnote" data-anchor="{n["anchor"]}">{badge}{inline(n["text"])}</div>'
    return f'<div class="wf-gutter">{items}</div>'


# --------------------------------------------------------------------------
# 模板：extends + slots / include + with + as:placeholder（資料結構合併，非字串替換）
# --------------------------------------------------------------------------
def _resolve(name, basedir):
    exts = [''] if name.endswith(('.yaml', '.yml')) else ['.wf.yaml', '.yaml', '.yml']
    dirs = [basedir] + [os.path.join(basedir, s) for s in ('components', 'layouts', 'partials')]
    for d in dirs:
        for e in exts:
            c = os.path.join(d, name + e)
            if os.path.exists(c):
                return c
    raise ValueError(f"找不到模板：{name}（找過 {basedir} 與 components/layouts/partials）")


def _subst(node, params):
    """{{x}} 只對葉子字串做侷限替換。"""
    if isinstance(node, str):
        return re.sub(r'\{\{\s*([\w-]+)\s*\}\}', lambda m: str(params.get(m.group(1), m.group(0))), node)
    if isinstance(node, list):
        return [_subst(x, params) for x in node]
    if isinstance(node, dict):
        return {k: _subst(v, params) for k, v in node.items()}
    return node


def _auto_stub(name):
    return [{'box': True, 'items': [{'text.hint': f'▧ {os.path.basename(name)}（略）'}]}]


def _match(when, ctx):
    """when 是否命中當前路由 context ctx。多 key = AND、值為 list = OR、無 when = 恆真。"""
    if not when:
        return True
    for dim in ('stage', 'state'):
        if dim in when:
            want = when[dim]
            allowed = want if isinstance(want, list) else [want]
            if ctx.get(dim) not in allowed:
                return False
    return True


def expand(items, basedir, ctx, stack=()):
    """一次 pass：when: 過濾（依 ctx）+ include 展開（as 決定變體/繼承 ctx）。ctx = {stage, state}。"""
    out = []
    for it in items:
        if isinstance(it, dict) and 'when' in it:      # 節點級 when：不命中當前路由 → 整塊移除
            if not _match(it['when'], ctx):
                continue
            it = {k: v for k, v in it.items() if k != 'when'}
        if isinstance(it, dict) and ('embed' in it or 'include' in it):
            if 'include' in it and 'embed' not in it:
                import sys as _sys
                print(f'  warn: include: 已改名為 embed:（deprecated，過渡期支援）—— {it["include"]!r}', file=_sys.stderr)
                it = {**it, 'embed': it['include']}
            name = it['embed']
            params = it.get('with', {}) or {}
            as_ = it.get('as')
            path = _resolve(name, basedir)
            if path in stack:
                raise ValueError(f"模板循環引用：{' -> '.join(stack + (path,))}")
            comp = yaml.safe_load(open(path)) or {}
            if _DEBUG:
                _stamp(comp, str(name))            # component 節點來源 = 其 include 名
            cdir = os.path.dirname(path) or '.'
            if as_ == 'placeholder':                    # 降階佔位（ctx 無意義）
                content, child_ctx = (comp.get('placeholder') or _auto_stub(name)), ctx
            else:
                content = comp if isinstance(comp, list) else (comp.get('content') or comp.get('body') or [])
                # as:{stage,state} → pin 該變體；省略 → 繼承當前頁面路由 ctx
                child_ctx = as_ if isinstance(as_, dict) else ctx
            content = _subst(content, params)
            content = expand(content, cdir, child_ctx, stack + (path,))
            ann = {k: it[k] for k in ('note', 'spotlight', 'name', 'tone', 'to') if k in it}
            if ann:                      # include 帶標註 → 包一層 col 承載（否則標註會被丟掉）
                for pk in ('__src', '__path'):
                    if pk in it:
                        ann[pk] = it[pk]
                out.append({**ann, 'col': content})
            else:
                out.extend(content)
        elif isinstance(it, dict):
            nd = dict(it)
            for k in ('items', 'row', 'col', 'grid'):
                if isinstance(nd.get(k), list):
                    nd[k] = expand(nd[k], basedir, ctx, stack)
            out.append(nd)
        else:
            out.append(it)
    return out


def _fill_slots(items, slots):
    out = []
    for it in items:
        if isinstance(it, dict) and (set(it) - {'__src', '__path'}) == {'slot'}:
            out.extend(slots.get(it['slot'], []))
        elif isinstance(it, dict):
            nd = dict(it)
            for k in ('items', 'row', 'col', 'grid'):
                if isinstance(nd.get(k), list):
                    nd[k] = _fill_slots(nd[k], slots)
            out.append(nd)
        else:
            out.append(it)
    return out


def resolve_body(doc, provider, basedir, ctx):
    """回傳 (body_items, canvas)。slots/body 來自 provider（無路由=doc；有路由=該路由項）。
    extends/with/canvas 屬 doc 級（各路由共用）。ctx = 當前路由 {stage, state}，供 when: 過濾與元件繼承。"""
    canvas = doc.get('canvas')
    if 'extends' in doc:
        layout = yaml.safe_load(open(_resolve(doc['extends'], basedir))) or {}
        if _DEBUG:
            _stamp(layout, str(doc['extends']))    # layout 節點來源 = 其引用名
        params = {**(doc.get('with') or {}), **(provider.get('with') or {})}
        body = _fill_slots(layout.get('body', []), provider.get('slots', {}) or {})
        body = _subst(body, params)
        canvas = canvas or layout.get('canvas')
    else:
        body = provider.get('body', [])
    body = expand(body, basedir, ctx)
    return body, canvas


# --------------------------------------------------------------------------
# 組頁
# --------------------------------------------------------------------------
def _canvas_wh(c):
    if c is None:
        return None, None
    s = str(c)
    if 'x' in s:
        a, _, b = s.partition('x')
        return (int(a) if a else None), (int(b) if b else None)
    return (int(s) if s.isdigit() else None), None


def _route_entry(r):
    """路由項 → (rid, provider, label, ctx)。rid 供檔名(空=default)、label 供 stagebar、ctx 供 when 過濾/元件繼承。"""
    if 'default' in r:
        return '', {k: v for k, v in r.items() if k != 'default'}, 'default', {}
    w = r.get('when', {}) or {}
    parts = [str(w[k]) for k in ('stage', 'state') if w.get(k)]
    rid = '.'.join(parts)
    ctx = {k: w[k] for k in ('stage', 'state') if w.get(k)}
    return rid, {k: v for k, v in r.items() if k != 'when'}, (rid or 'default'), ctx


def _stagebar(labels, current):
    """頂部路由列：列出所有路由、標當前 → 單張圖也能自我說明是哪條路由。"""
    if not labels or len(labels) < 2:
        return ''
    dots = ''.join(f'<span class="wf-stage-dot{" wf-stage-cur" if l == current else ""}">{esc(l)}</span>'
                   for l in labels)
    return f'<div class="wf-stagebar"><span class="wf-stage-label">ROUTE</span>{dots}</div>'


def _render_page(doc, provider, basedir, ctx=None, cur_label=None, all_labels=None):
    """渲染一頁的 .wf-root 內容（不含 <html>/head）→ (content, w, h, has_notes)。"""
    global _NOTES, _NCOUNT
    _NOTES, _NCOUNT = [], 0
    body, canvas = resolve_body(doc, provider, basedir, ctx or {})
    w, h = _canvas_wh(canvas)
    inner = render_container({'col': body}, [], {}, _PAGE_BASE, '')   # 頂層 flex-col（避免 inline span 並排）
    bar = _stagebar(all_labels, cur_label) if all_labels else ''
    return bar + inner + build_gutter(), w, h, bool(_NOTES)


def _width_css(sel, w, h, has_notes):
    """畫布寬高覆蓋（可指定選擇器 → bundle 各 section 各自套）。"""
    main_w, o = w or 780, ''
    if has_notes:
        g, gap = 240, 24
        o += (f'{sel}{{width:{main_w + g + gap}px;position:relative;}}'
              f'{sel}>.wf-node{{width:{main_w}px;}}{sel} .wf-gutter{{width:{g}px;}}')
    elif w:
        o += f'{sel}{{width:{w}px;}}'
    if h:   # 有畫布高度：root 成 flex-col、body 撐滿該高 → spacer/justify 能把內容(如 footer)推到底
        o += f'{sel}{{min-height:{h}px;display:flex;flex-direction:column;}}{sel}>.wf-node{{flex:1 1 auto;min-height:0;}}'
    return o


def _compile_page(doc, provider, basedir, ctx=None, cur_label=None, all_labels=None, debug=False):
    content, w, h, notes = _render_page(doc, provider, basedir, ctx, cur_label, all_labels)
    css = _hoist_imports(_BASE_CSS + CSS_EXTRA + (DEBUG_CSS if debug else '')
                         + _style_css() + _tokens_css() + _width_css('.wf-root', w, h, notes))
    page_attr = f' data-wf-page="{esc(_PAGE_BASE)}"' if debug else ''
    head = (f'<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{css}</style>'
            f'</head><body><div class="wf-root"{page_attr}>')
    tail = ('<script>' + DEBUG_JS + '</script>' if debug else '') + '</body></html>'
    return head + content + '</div>' + tail


BUNDLE_CSS = r"""
body.wf-bundle{display:flex;margin:0;align-items:flex-start;font-family:var(--wf-font,'Sarasa Mono TC','Courier New',monospace);}
#wf-nav{position:sticky;top:0;flex:0 0 190px;max-height:100vh;overflow:auto;padding:12px;
  border-right:1px solid #e5e7eb;font:12px/1.5 sans-serif;background:#fafafa;}
#wf-nav .wf-navgrp{margin-bottom:6px;}
#wf-nav b{display:block;color:#6b7280;margin:8px 0 2px;font-size:11px;letter-spacing:.03em;}
#wf-nav a{display:block;padding:2px 8px;color:#0f766e;text-decoration:none;border-radius:var(--wf-radius);}
#wf-nav a:hover{background:#f0fdfa;}
#wf-main{flex:1;padding:24px;overflow:auto;}
.wf-pg{display:none;}
.wf-pg:target{display:block;}
body:not(:has(.wf-pg:target)) .wf-pg:first-of-type{display:block;}  /* 無 target 才顯第一頁；有 target(含第一頁) 只顯 target */
"""


def bundle(files, debug=False, title='prototype', style=None):
    """把多個 .wf.yaml 併成單一可點擊 prototype.html（左 nav + :target 切頁 + 頁內 to: 錨點）。
    debug=True → 疊評審回饋層（模式切換 + 跨頁匯出，單檔共用一份 localStorage）。"""
    global _PAGE_BASE, _DEBUG, _BUNDLE, _STYLE
    _DEBUG, _BUNDLE, _STYLE = debug, True, style
    _load_tokens(os.path.dirname(files[0]) if files else '.')   # 專案 semantic token（探首檔所在夾）
    secs, navs, overrides, pids = [], [], [], []
    for f in files:
        src = open(f).read()
        basedir = os.path.dirname(f) or '.'
        base = re.sub(r'\.(wf\.)?ya?ml$', '', os.path.basename(f))
        _PAGE_BASE = base
        doc = yaml.safe_load(src) or {}
        if debug:
            _stamp(doc, base)
        routes = doc.get('routes')
        entries = ([('', doc, base, None)] if not routes
                   else [_route_entry(r) for r in routes])
        labels = [e[2] for e in entries] if routes else None
        navitems = []
        for rid, prov, label, ctx in entries:
            content, w, h, notes = _render_page(doc, prov, basedir, ctx,
                                                 (label if routes else None), labels)
            pid = _pgid(base, rid)
            pids.append(pid)
            secs.append(f'<section class="wf-pg" id="{pid}"><div class="wf-root">{content}</div></section>')
            overrides.append(_width_css(f'#{pid} .wf-root', w, h, notes))
            navitems.append(f'<a href="#{pid}" id="nav-{pid}">{esc(label if routes else base)}</a>')
        navs.append(f'<div class="wf-navgrp"><b>{esc(base)}</b>{"".join(navitems)}</div>')
    # nav 當前頁高亮（零 JS：:has(section:target) → 對應 nav 連結；無 target 則第一頁）
    if pids:
        sel = ','.join(f'body:has(#{p}:target) #nav-{p}' for p in pids)
        sel += f',body:not(:has(.wf-pg:target)) #nav-{pids[0]}'
        overrides.append(sel + '{background:#0f766e;color:#fff;font-weight:600;}')
    css = _hoist_imports(_BASE_CSS + CSS_EXTRA + BUNDLE_CSS + (DEBUG_CSS if debug else '')
                         + _style_css() + _tokens_css() + ''.join(overrides))
    tail = ('<script>' + DEBUG_JS + '</script>' if debug else '') + '</body></html>'
    return (f'<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{esc(title)}</title>'
            f'<style>{css}</style></head><body class="wf-bundle">'
            f'<nav id="wf-nav">{"".join(navs)}</nav><div id="wf-main">{"".join(secs)}</div>{tail}')


def compile_all(src, basedir='.', base='', debug=False, style=None):
    """回傳 [(rid, html), ...]。無 routes → [('', html)]；有 routes → 每路由一份可定址輸出。
    debug=True → 注入 --debug 評審回饋層（JS+localStorage）；否則維持零 <script>。"""
    global _PAGE_BASE, _DEBUG, _STYLE
    _PAGE_BASE, _DEBUG, _STYLE = base, debug, style
    _load_tokens(basedir)              # 探測選配的 wf.tokens.yaml（專案 semantic token）
    doc = yaml.safe_load(src) or {}
    if debug:
        _stamp(doc, base)          # 頁面節點蓋來源(base)+路徑，供 debug 定位
    routes = doc.get('routes')
    if not routes:
        return [('', _compile_page(doc, doc, basedir, debug=debug))]
    entries = [_route_entry(r) for r in routes]
    labels = [e[2] for e in entries]
    return [(rid, _compile_page(doc, prov, basedir, ctx, label, labels, debug=debug))
            for rid, prov, label, ctx in entries]


def compile_yaml(src, basedir='.', base='', debug=False, style=None):
    """向後相容：回傳第一份（無路由時即唯一份）。"""
    return compile_all(src, basedir, base, debug, style)[0][1]


def _argval(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv) else None


def main():
    debug = '--debug' in sys.argv
    do_bundle = '--bundle' in sys.argv
    # 檢查 list 子命令前，先定義（inline，短小）
    def _list_vocab(basedir, ring=None):
        """列 Ring 0（結構原語）+ Ring 1（專案 semantic token）。給 AI/作者一眼看完詞彙。"""
        want_r0 = ring in (None, '0')
        want_r1 = ring in (None, '1')
        if want_r0:
            print("═══ Ring 0：結構原語（恆定，AI 必背）═══")
            print("\n[Grammar 關鍵字]")
            print("  canvas / body / extends / embed / with / slot / slots / as / routes / default / when / items")
            print("\n[結構單元類型]")
            print("  page / layout / component / widget")
            print("\n[Container]")
            print("  row / col / grid / box / widget")
            print("  Overlay 家族 sugar: dialog / drawer / sheet / toast / loading")
            print("\n[Leaf 元件]")
            print("  文字：text / text.title / text.heading / text.label / text.strong / text.hint")
            print("  表單：input / select / button / checkbox / radio")
            print("  狀態：status / status.muted / status.strong / status.badge / alert")
            print("  其他：icon / divider / image / tabs / link / progress / avatar")
            print("\n[Widget 屬性]")
            print("  is / can")
            print("\n[空間屬性]")
            print("  justify / align / gap / padding / span / grow / scroll / scroll-x / spacer")
            print("  寬度 token：grow / fit / w-N/M / <N>% / w-N（逃生門）")
            print("\n[動線/連結]")
            print("  to / link")
            print("\n[浮層原語]")
            print("  pin / modal / layer")
            print("\n[產品面 tone] (Layer 1)")
            print("  feature / info / success / warn / danger / muted")
            print("\n[標註面] (Layer 2)")
            print("  note / spotlight")
            print("\n[Meta（隱形）]")
            print("  name / canvas")
        if want_r1:
            _load_tokens(basedir)
            print("\n═══ Ring 1：專案 semantic token（opt-in，讀 tokens/*.yaml + wf.tokens.yaml）═══")
            if not _TOKENS:
                print(f"  （{basedir} 下未找到 tokens/ 目錄或 wf.tokens.yaml）")
            else:
                for family, entries in _TOKENS.items():
                    print(f"\n[{family}]")
                    if isinstance(entries, dict):
                        for name, val in entries.items():
                            print(f"  {family}.{name}  →  {val}")
                    else:
                        print(f"  {entries}")

    # ---- list 子命令：introspection（Ring 0 原語 + Ring 1 專案 token）----
    if len(sys.argv) >= 2 and sys.argv[1] == 'list':
        list_ring = _argval('--ring')     # None / '0' / '1'
        basedir = _argval('--basedir') or '.'
        _list_vocab(basedir, ring=list_ring)
        return

    out_path = _argval('-o')
    style = _argval('--style')
    skip = {'--debug', '--bundle', '-o', out_path, '--style', style}
    args = [a for a in sys.argv[1:] if a not in skip]
    if not args:
        print("usage: wfyaml.py [--debug] [--bundle [-o out.html]] [--style <name>] <file.wf.yaml> [...]", file=sys.stderr)
        print("       wfyaml.py list [--ring 0|1] [--basedir <dir>]   # introspection：列 Ring 0 原語 + Ring 1 專案 token", file=sys.stderr)
        sys.exit(1)
    if do_bundle:
        out = out_path or os.path.join(os.path.dirname(args[0]) or '.',
                                       'prototype' + ('.debug' if debug else '') + '.html')
        open(out, 'w').write(bundle(args, debug=debug, style=style))
        print(f"  bundled: {out} ({len(args)} 檔){' [style:' + style + ']' if style else ''}")
        return
    for path in args:
        src = open(path).read()
        basedir = os.path.dirname(path) or '.'
        stem = re.sub(r'\.(wf\.)?ya?ml$', '', path)
        base = os.path.basename(stem)
        suffix = '.debug.html' if debug else '.html'   # debug 版另存，不覆蓋乾淨產物
        for rid, htmlout in compile_all(src, basedir, base, debug=debug, style=style):
            out = stem + (('.' + rid) if rid else '') + suffix
            open(out, 'w').write(htmlout)
            print(f"  compiled: {out}")


if __name__ == '__main__':
    main()
