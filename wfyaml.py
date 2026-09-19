#!/usr/bin/env python3
"""
wireframe-lofi compiler

把「語義化 YAML」編譯成低保真、零 JS 的 HTML wireframe。設計脈絡見 DISCUSSION.md。

三環架構（見 TOOL-SUGGESTIONS.md P5）：
- Ring 0 結構原語（恆定）：`wfyaml.py list --ring 0` 一次看完
- Ring 1 專案 semantic token（opt-in）：tokens/*.yaml 或 wf.tokens.yaml
- Ring 2 輸出旗標（不進 YAML）：--style clean|sketch / --mockup <theme> / --bundle / --debug

核心取捨：
- 結構解析全交給 yaml.safe_load（免手刻 parser）；本檔只做「YAML 樹 → HTML」的分派
- 葉子是語義 role（text.title / button / status…），非視覺標記
- 顏色封印（wireframe 全灰階；色彩=保真度的函數：產品色走 --mockup theme、聚焦走標註面）；尺寸走 Tailwind token；間距走語義 scale
- Fail-Fast：靜默失敗禁止；未知值/typo 一律 error（POC 階段無 deprecated 相容包袱）

子命令：
- `wfyaml.py <file>` 編譯成 .html
- `wfyaml.py --bundle <files>` 併成 prototype.html
- `wfyaml.py --debug <file>` 出評審模式
- `wfyaml.py list [--ring 0|1] [--basedir <dir>]` introspection
- `wfyaml.py lint <files>` schema validation + fail-fast diagnostics
"""
import sys, os, re, html, gzip, json, base64, glob, yaml
import xml.etree.ElementTree as ET


class AuthorError(ValueError):
    """作者輸入錯誤；保留來源，不把非預期程式例外偽裝成語法問題。"""
    def __init__(self, message, source=None, path=None):
        super().__init__(message)
        self.source, self.path = source, path


def _yaml_load(src, source='<input>'):
    try:
        return yaml.safe_load(src) or {}
    except yaml.YAMLError as e:
        mark = getattr(e, 'problem_mark', None)
        location = f'line {mark.line + 1}, column {mark.column + 1}' if mark else '<root>'
        problem = getattr(e, 'problem', None) or str(e)
        hint = '\n文字含 [ ] , : # 時，請為整個值加引號（尤其 flow sequence）。'
        raise AuthorError(f'YAML 解析失敗：{problem}{hint}', source, location) from e


def _read_yaml(path):
    try:
        with open(path, encoding='utf-8') as f:
            return _yaml_load(f.read(), path)
    except OSError as e:
        raise AuthorError(f'讀不到檔案：{e.strerror}', path, '<root>') from e


def cli_entry(run):
    """CLI 與截圖入口共用的簡潔作者錯誤輸出；程式錯誤保留 traceback。"""
    trace = '--traceback' in sys.argv or os.environ.get('WF_TRACEBACK') == '1'
    if '--traceback' in sys.argv:
        sys.argv.remove('--traceback')
    try:
        return run()
    except (ValueError, yaml.YAMLError) as e:
        if trace:
            raise
        source, path = getattr(e, 'source', None), getattr(e, 'path', None)
        print(f'error: {source or "<input>"} → {path or "<root>"}', file=sys.stderr)
        for line in str(e).splitlines():
            if line.strip():
                print(f'  {line}', file=sys.stderr)
        print('  （用 --traceback 或 WF_TRACEBACK=1 看完整 traceback）', file=sys.stderr)
        sys.exit(1)

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
            raise ValueError(f"icon: fa:{style}:{name} 未找到（請確認 name 存在於 assets/fa-icons.json.gz）")
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
            raise ValueError(f"icon: lu:{name} 未找到（請確認 name 存在於 assets/lucide-icons.json.gz）")
    return _lu_cache[name]

# ---- 語義 scale / 對照表（集中一處 → 可 theme）----
GAP = {'none': '0', 'sm': 'var(--wf-space-sm)', 'md': 'var(--wf-space-md)',
       'lg': 'var(--wf-space-lg)', 'xl': 'var(--wf-space-xl)'}  # 語義間距 scale→CSS var(可 theme)；預設 md


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


# ─────────────────────────────────────────────────────────────────────────
# P7 Theme-as-binding-YAML（DISCUSSION 2026-07-03）
# ─────────────────────────────────────────────────────────────────────────
# 四層架構的 Theme 層：綁物理到 component role 名（用 Primitive 值）。
# 只在 `--mockup <theme.yaml>` 時載入；wireframe 模式忽略（fidelity mode = 結構性防漂移）。

# 綁定屬性 → CSS 屬性映射（MVP 支援集）；unknown key = error（禁靜默）
# bindings 的語義名一律解析成 var(--wf-*, <內建 fallback>)——工具只認名字，值歸 theme `tokens:`。
# 內建 fallback = 可攜地板（沒定義 token 也能渲染）；細顆粒調值在 theme tokens，不改工具。
def _enum_var(prop, table):
    def resolve(v):
        if str(v) not in table:
            raise ValueError(f"theme.{prop}: 未知值 {v!r}（合法：{'/'.join(table)}）")
        return table[str(v)]
    return resolve


_theme_radius = _enum_var('radius', {
    'none': '0',
    'sm':   'var(--wf-radius-sm,3px)',
    'md':   'var(--wf-radius-md,6px)',
    'lg':   'var(--wf-radius-lg,12px)',
    'pill': 'var(--wf-radius-pill,9999px)',
    'full': 'var(--wf-radius-pill,9999px)',
})

_THEME_BINDABLE = {
    'padding':       ('padding',       lambda v: _gap(v)),
    'margin':        ('margin',        lambda v: _gap(v)),
    'gap':           ('gap',           lambda v: _gap(v)),
    'radius':        ('border-radius', _theme_radius),
    'shadow':        ('box-shadow',    _enum_var('shadow', {
                          'none': 'none',
                          'sm':   'var(--wf-shadow-sm,0 1px 2px rgba(0,0,0,.06))',
                          'md':   'var(--wf-shadow-md,0 2px 6px rgba(0,0,0,.10))',
                          'lg':   'var(--wf-shadow-lg,0 6px 20px rgba(0,0,0,.14))',
                      })),
    'border':        ('border',        _enum_var('border', {
                          'none':    'none',
                          'subtle':  '1px solid var(--wf-line-subtle,rgba(0,0,0,.08))',
                          'default': '1px solid var(--wf-line,#d1d5db)',
                          'strong':  '2px solid var(--wf-line-strong,#6b7280)',
                          'brand':   '1.5px solid var(--wf-brand,#0d9488)',
                      })),
    'background':    ('background',    _enum_var('background', {
                          'inverse':      'var(--wf-inverse,#ffffff)',
                          'surface':      'var(--wf-surface,#ffffff)',
                          'surface-alt':  'var(--wf-surface-alt,#f9fafb)',
                          'surface-sunk': 'var(--wf-surface-sunk,#f3f4f6)',
                          'ink':          'var(--wf-ink,#111827)',
                          'brand':        'var(--wf-brand,#0d9488)',   # 色彩=保真度的函數：產品色只住 theme
                          'brand-soft':   'var(--wf-brand-soft,#f0fdfa)',
                      })),
    'text':          ('color',         _enum_var('text', {
                          'ink':     'var(--wf-ink,#111827)',
                          'soft':    'var(--wf-ink-soft,#6b7280)',
                          'inverse': 'var(--wf-inverse,#ffffff)',
                          'brand':   'var(--wf-brand,#0d9488)',
                      })),
}

_THEME_ASSETS = {}
_THEME_ASSET_WARNINGS = []
_THEME_WARNINGS = []        # theme 本身的診斷（綁不到的目標等），與素材警示分開累積

_THEME = {}          # 當前載入的 theme bindings（綁 name/role 的專案微調）；空 dict = wireframe 模式
_THEME_BASE = {}     # theme 的 base: 模式開關（chrome/link-marker/scrollbar）
_THEME_TOKENS = {}   # theme 的 tokens: 值層（Tier-1 design token，FE 可直接接手）
_THEME_PRESETS = {}  # tokens.preset: composite token（一組 property，被 apply: 組合，不渲染）
_THEME_COMPONENTS = {}  # components: 元件皮（Tier-2，base/variants/states + apply）
_THEME_FLATVALS = {}    # {"family.name": 已展開純值}（供 {ref} 的 var() fallback）
_KIT_COMPONENTS = {}    # 專案型別詞彙；render/lint 共用同一份 schema
_KIT_PATH = None
_KIT_EXPLICIT = False
_STRICT_KIT = False


def _theme_active():
    return bool(_THEME or _THEME_BASE or _THEME_TOKENS or _THEME_COMPONENTS)


def _load_kit(path=None, explicit=False):
    """Load a deliberately non-programmable component kit."""
    global _KIT_COMPONENTS, _KIT_PATH, _KIT_EXPLICIT
    _KIT_COMPONENTS, _KIT_PATH, _KIT_EXPLICIT = {}, path, explicit
    if not path:
        return {}
    if not os.path.isfile(path):
        raise AuthorError(f'找不到 kit：{path}', path, '<root>')
    data = _read_yaml(path)
    if not isinstance(data, dict) or set(data) != {'components'} or not isinstance(data['components'], dict):
        raise AuthorError('kit 頂層只能是 components: dict', path, '<root>')
    allowed = {'of', 'props', 'states', 'content'}
    canvas_allowed = {'of', 'base', 'item', 'node', 'link', 'edge', 'states'}
    for name, spec in data['components'].items():
        here = f'components.{name}'
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name):
            raise AuthorError('kit 型別名只接小寫 kebab-case', path, here)
        if name in LEAF_ROLES or name in CONTAINER_KEYS or name in _OVERLAY_SUGARS:
            raise AuthorError(f'kit 型別 `{name}` 與內建詞彙衝突', path, here)
        if not isinstance(spec, dict):
            raise AuthorError('kit 元件定義必須是 dict', path, here)
        is_canvas = spec.get('of') == 'canvas'
        legal = canvas_allowed if is_canvas else allowed
        unknown = set(spec) - legal
        if unknown:
            raise AuthorError(f'kit 元件不接受 {sorted(unknown)}；只允許 {sorted(legal)}', path, here)
        of, content = spec.get('of'), spec.get('content')
        if not is_canvas and bool(of) == (content is not None):
            raise AuthorError('元件必須二選一：of（leaf 特化）或 content（純組合）', path, here)
        if of and of not in LEAF_ROLES and of != 'canvas':
            raise AuthorError(f'of 只能指向既有 leaf（收到 `{of}`）', path, f'{here}.of')
        if content is not None and not isinstance(content, list):
            raise AuthorError('content 必須是 list', path, f'{here}.content')
        props = spec.get('props', [])
        if not isinstance(props, list) or any(not isinstance(x, str) or not re.fullmatch(r'[a-zA-Z][\w-]*', x) for x in props) or len(props) != len(set(props)):
            raise AuthorError('props 必須是不重複的名稱 list', path, f'{here}.props')
        states = spec.get('states', [])
        if not isinstance(states, list) or any(not isinstance(x, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', x) for x in states) or len(states) != len(set(states)):
            raise AuthorError('states 必須是不重複的小寫名稱 list', path, f'{here}.states')
        if is_canvas:
            if 'node' in spec:                      # nodes/edges 為正名（React Flow / 圖論通用）
                spec['item'] = spec.pop('node')
            if 'edge' in spec:
                spec['link'] = spec.pop('edge')
            base, item, link = spec.get('base'), spec.get('item'), spec.get('link')
            if not isinstance(base, dict) or set(base) - {'asset', 'grid', 'blank', 'anchors', 'ratio'}:
                raise AuthorError('canvas.base 必須是 {asset|grid|blank, anchors?, ratio?}', path, f'{here}.base')
            base_kinds = [k for k in ('asset', 'grid', 'blank') if base.get(k)]
            if len(base_kinds) != 1 or ('asset' in base and (not isinstance(base['asset'], str) or not base['asset'])):
                raise AuthorError('canvas.base 必須恰選一種非空底：asset / grid:true / blank:true', path, f'{here}.base')
            if 'grid' in base and base['grid'] is not True or 'blank' in base and base['blank'] is not True:
                raise AuthorError('canvas.base 的 grid / blank 只接 true', path, f'{here}.base')
            anchors = base.get('anchors', {})
            if not isinstance(anchors, dict):
                raise AuthorError('canvas.base.anchors 必須是 id → [x,y] dict', path, f'{here}.base.anchors')
            for anchor, point in anchors.items():
                if not isinstance(anchor, str) or not anchor:
                    raise AuthorError('canvas anchor 名必須是非空字串', path, f'{here}.base.anchors')
                _canvas_point(point, path, f'{here}.base.anchors.{anchor}')
            ratio = base.get('ratio')
            if ratio is not None:
                match = re.fullmatch(r'(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)', str(ratio))
                if not match or float(match.group(1)) <= 0 or float(match.group(2)) <= 0:
                    raise AuthorError('canvas.base.ratio 必須是大於零的 N/N（例如 4/3）', path, f'{here}.base.ratio')
            if not isinstance(item, dict) or set(item) != {'use'} or not isinstance(item.get('use'), str):
                raise AuthorError('canvas.item 必須是 {use: kit-type}', path, f'{here}.item')
            if link is not None and (not isinstance(link, dict) or set(link) - {'shape', 'arrow'} or
                                     link.get('shape') not in ('straight', 'smooth') or
                                     ('arrow' in link and link['arrow'] is not True)):
                raise AuthorError('canvas.link 只接 {shape: straight|smooth, arrow?: true}', path, f'{here}.link')
    _KIT_COMPONENTS = data['components']
    for name, spec in _KIT_COMPONENTS.items():
        if spec.get('of') == 'canvas':
            used = spec['item']['use']
            target = _KIT_COMPONENTS.get(used)
            if not target:
                raise AuthorError(f'canvas item.use `{used}` 未在 kit 宣告', path, f'components.{name}.item.use')
            if target.get('of') == 'canvas':
                raise AuthorError('canvas item.use 不可再指向 canvas', path, f'components.{name}.item.use')
    _kit_css()  # fail fast on CSS properties and token references
    # Validate composition structure once; parameter placeholders are deliberately allowed.
    check = _Diag(path, allow_parameters=True)
    for name, spec in _KIT_COMPONENTS.items():
        if 'content' in spec:
            _walk_lint(spec['content'], f'components.{name}.content', check, os.path.dirname(path) or '.')
    if check.errors:
        _src, at, message, _hint = check.errors[0]
        raise AuthorError(message, path, at)
    return _KIT_COMPONENTS


def _canvas_point(point, source=None, path=None):
    if (not isinstance(point, list) or len(point) != 2 or
            any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1 for v in point)):
        raise AuthorError('canvas 座標必須是 0–1 的 [x, y]', source, path)
    return [float(point[0]), float(point[1])]


def _ensure_kit(basedir):
    if _KIT_EXPLICIT:
        return
    candidate = os.path.join(basedir, 'kit', 'components.yaml')
    if os.path.isfile(candidate):
        _load_kit(candidate)
    elif _KIT_PATH:
        _load_kit(None)


def _kit_css():
    """A kit declares vocabulary only. All visual CSS belongs to the theme."""
    return ''


# bindings 綁「內建元件 role」→ selector（同一套詞彙換元件皮，不另發明語彙）。
_THEME_ELEMENT_SELECTORS = {
    # 文字家族：語義角色依用途命名（Material 3 的 type scale 同一哲學），theme 綁得到才有契約可言
    'text':          '.wf-label:not(.wf-fieldlabel)',
    'text.title':    '.wf-h1',
    'text.heading':  '.wf-h2',
    'text.label':    '.wf-fieldlabel',
    'text.strong':   '.wf-b',
    'text.hint':     '.wf-hint',
    'button':        '.wf-btn',
    'button-link':   ':is(a,label.wf-radio-link).wf-btn.wf-link',    # 帶 to: 的按鈕（主要動作/導航）
    'input':         '.wf-input',
    'select':        '.wf-select',
    'status':        '.wf-tag',
    'status.muted':  '.wf-tag-muted',
    'status.strong': '.wf-tag-strong',
    'status.badge':  '.wf-badge',
    'box':           '.wf-box',
    # Leaf / composite parts: themes keep the same role vocabulary as YAML.
    # checkbox/radio bind the drawn control, never the accompanying label.
    'checkbox':      '.wf-check-control',
    'radio':         '.wf-radio-control',
    'progress':      '.wf-progress',
    'progress.fill': '.wf-progress-fill',
    'avatar':        '.wf-avatar',
    'avatars':       '.wf-avatars',
    'icon':          '.wf-icon',
    'image':         '.wf-image',
    'divider':       '.wf-hr',
    'widget':        '.wf-widget',
    'tab':           '.wf-tab',
    'tab.active':    '.wf-tab-active',
    'link':          '.wf-hyperlink',
}

# components: 元件名 → base selector。內建元件走既有 wf-* class；
# 未列者（= 專案 component / embed 名）預設 `.wf-role-<name>`（embed 展開時已蓋此指紋）。
_THEME_COMPONENT_SELECTORS = {
    **_THEME_ELEMENT_SELECTORS,
    'card':  '.wf-box',
    'alert': '.wf-warn',
    'tabs':  '.wf-tabs',
}

# 舊版固定 token 家族 → 既有 CSS var 名（保住 wf.css / clean 皮讀得到；向後相容）。
# 新增家族/名字則自動走 `--wf-<family>-<name>`（開放命名）。
_THEME_TOKEN_VARS = {
    'font':   {'body': '--wf-font', 'size': '--wf-font-size',
               'h1': '--wf-h1', 'h2': '--wf-h2', 'h3': '--wf-h3'},
    'space':  {'sm': '--wf-space-sm', 'md': '--wf-space-md',
               'lg': '--wf-space-lg', 'xl': '--wf-space-xl'},
    'radius': {'default': '--wf-radius', 'sm': '--wf-radius-sm', 'md': '--wf-radius-md',
               'lg': '--wf-radius-lg', 'pill': '--wf-radius-pill'},
    'shadow': {'sm': '--wf-shadow-sm', 'md': '--wf-shadow-md', 'lg': '--wf-shadow-lg'},
    'color':  {'brand': '--wf-brand', 'brand-soft': '--wf-brand-soft',
               'surface': '--wf-surface', 'surface-alt': '--wf-surface-alt',
               'surface-sunk': '--wf-surface-sunk',
               'ink': '--wf-ink', 'ink-soft': '--wf-ink-soft', 'inverse': '--wf-inverse',
               'line-subtle': '--wf-line-subtle', 'line': '--wf-line',
               'line-strong': '--wf-line-strong', 'page': '--wf-page-bg'},
    'page':   {'pad': '--wf-page-pad'},
}

# CSS property 白名單（components / preset / raw binding 用）——未知 property fail-fast。
_CSS_PROP_ALLOW = {
    'background', 'background-color', 'background-image', 'color',
    'border', 'border-top', 'border-right', 'border-bottom', 'border-left',
    'border-color', 'border-width', 'border-style', 'border-radius',
    'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
    'gap', 'box-shadow', 'opacity', 'font', 'font-family', 'font-size', 'font-weight',
    'line-height', 'letter-spacing', 'text-transform', 'text-decoration', 'text-align',
    'font-style',   # 線框用斜體標次要文字；mockup 階段那層 lo-fi 語意沒有意義，theme 要收得回來
    'height', 'min-height', 'max-height', 'width', 'min-width', 'max-width',
    'display', 'align-items', 'justify-content', 'transition', 'cursor',
    'outline', 'outline-offset', 'fill', 'stroke', 'stroke-width', 'stroke-dasharray',
}

_THEME_BASE_KEYS = {'chrome', 'link-marker', 'scrollbar'}
_THEME_CHROME = {
    'flat': '',
    'card': ('body{background:var(--wf-page-bg,#eef0f3);}'
             '.wf-root{background:var(--wf-surface,#ffffff);border:none;'
             'box-shadow:var(--wf-shadow-lg,0 4px 24px rgba(0,0,0,.10));}'),
}


def _theme_slug(s):
    return re.sub(r'[^a-z0-9-]', '-', str(s).lower())


# DTCG 複合型別（gradient / typography）：wfexport 已經在輸出 DTCG，這兩個是同一批規格裡
# 還沒補的部分。命名哲學抄 Material 3：type scale 依用途命名、每個 scale 是一組
# family + size + weight + line-height + letter-spacing 的 token。
_TYPOGRAPHY_SUBS = {'fontFamily': 'font-family', 'fontSize': 'font-size', 'fontWeight': 'font-weight',
                    'lineHeight': 'line-height', 'letterSpacing': 'letter-spacing'}


def _typography_vars(name, value, where):
    """typography 複合值 → 一組 CSS var（每個子值一條，Material 3 的 --md-sys-typescale-<role>-<prop>）。"""
    if not isinstance(value, dict):
        raise ValueError(f'{where} 需要 dict（子值：{sorted(_TYPOGRAPHY_SUBS)}）')
    unknown = set(value) - set(_TYPOGRAPHY_SUBS)
    if unknown:
        raise ValueError(f'{where} 未知子值 {sorted(unknown)}（DTCG typography：{sorted(_TYPOGRAPHY_SUBS)}）')
    return {f'--wf-typography-{_theme_slug(name)}-{css}': str(value[sub])
            for sub, css in _TYPOGRAPHY_SUBS.items() if sub in value}


def _gradient_value(entry, name, where):
    """gradient 複合值 → 單一 CSS 漸層字串。

    DTCG 的 gradient 是一組 {color, position}，本身沒有定義方向（見 DTCG issue #101）。
    theme 裡 `angle` 寫在 token 的同層（預設 180deg，由上而下）；匯出 DTCG 時它進
    $extensions（規格外的資料只能放那裡），匯入時再還原回同層——兩邊是同一個值。
    漸層只住 theme：畫面 YAML 永遠不准寫，跟「產品色只住 theme」是同一條原則。"""
    stops = entry.get('$value') if isinstance(entry, dict) else entry
    if not isinstance(stops, list) or not stops:
        raise ValueError(f'{where} 需要一組色停 list（DTCG gradient：[{{color, position}}, ...]）')
    angle = str(entry.get('angle', '180deg')) if isinstance(entry, dict) else '180deg'
    parts = []
    for i, stop in enumerate(stops):
        if not isinstance(stop, dict) or 'color' not in stop:
            raise ValueError(f'{where}[{i}] 需要 {{color, position}}')
        pos = stop.get('position')
        if pos is None:
            parts.append(str(stop['color']))
        else:
            pct = f'{float(pos) * 100:g}%' if isinstance(pos, (int, float)) and 0 <= float(pos) <= 1 else str(pos)
            parts.append(f"{stop['color']} {pct}")
    return f"linear-gradient({angle}, {', '.join(parts)})"


def _theme_var_name(family, name):
    """token 路徑 → CSS var 名。舊家族/名走既有 var（相容），其餘走 `--wf-<family>-<name>`。"""
    fam = _THEME_TOKEN_VARS.get(family)
    if fam and str(name) in fam:
        return fam[str(name)]
    return f'--wf-{_theme_slug(family)}-{_theme_slug(name)}'


def _token_scalar(entry):
    """token 值：scalar 直用；dict 需 `$value`（DTCG）；其餘（composite 無 $value）報錯。"""
    if isinstance(entry, dict):
        if '$value' in entry:
            return str(entry['$value'])
        raise ValueError(f"theme token 值為 dict 但缺 $value（收到 keys={sorted(entry)}）；"
                         f"一組 property 請放 tokens.preset")
    return str(entry)


def _flatten_tokens(tokens):
    """建 {"family.name": 純值}；展開巢狀 {ref}（含循環偵測）。preset 家族不進此表。"""
    raw = {}
    for family, entries in tokens.items():
        if family == 'preset':
            continue
        if not isinstance(entries, dict):
            raise ValueError(f"theme.tokens.{family} 必須是 dict（收到 {type(entries).__name__}）")
        for name, entry in entries.items():
            if family == 'typography':
                continue          # 一組子值不是單一值，靠 bindings/components 的 typography: 展開
            if family == 'gradient':
                raw[f'{family}.{name}'] = _gradient_value(entry, name, f'theme.tokens.gradient.{name}')
                continue
            raw[f'{family}.{name}'] = _token_scalar(entry)
    resolved = {}

    def resolve(key, stack):
        if key in resolved:
            return resolved[key]
        if key not in raw:
            sugg = _suggest_key(key, set(raw))
            hint = f"（是不是「{sugg}」？）" if sugg else ""
            raise ValueError(f"theme token 參照 {{{key}}} 未定義{hint}")
        if key in stack:
            raise ValueError(f"theme token 參照循環：{' → '.join(list(stack) + [key])}")
        out = re.sub(r'\{([^}]+)\}', lambda m: resolve(m.group(1).strip(), stack + (key,)), raw[key])
        resolved[key] = out
        return out

    for k in raw:
        resolve(k, ())
    return resolved


def _resolve_value(val):
    """把值裡的 {family.name} 換成 var(--wf-…, 純值 fallback)；其餘原樣透傳。"""
    def sub(m):
        key = m.group(1).strip()
        fb = _THEME_FLATVALS.get(key)
        if fb is None:
            sugg = _suggest_key(key, set(_THEME_FLATVALS))
            hint = f"（是不是「{sugg}」？）" if sugg else ""
            family = key.partition('.')[0]
            available = sorted(k.partition('.')[2] for k in _THEME_FLATVALS if k.startswith(family + '.'))
            choices = f"；{family} 可用：{available}" if available else ''
            raise ValueError(f"theme 參照未定義 token {{{key}}}{hint}{choices}")
        fam, _, nm = key.partition('.')
        return f'var({_theme_var_name(fam, nm)}, {fb})'
    out = re.sub(r'\{([^}]+)\}', sub, str(val))
    if re.search(r'[;{}]', out):
        raise ValueError(f"theme 值含非法字元或未解析 ref（收到 {val!r}）")
    return out


def _expand_props(rules, where=''):
    """dict（可含 apply: [preset…]）→ 展開後的 {prop: 解析值}。優先序：preset < 明寫。"""
    if not isinstance(rules, dict):
        raise ValueError(f"theme {where} 必須是 dict（收到 {type(rules).__name__}）")
    merged = {}
    for pname in (rules.get('apply') or []):
        preset = _THEME_PRESETS.get(pname)
        if preset is None:
            sugg = _suggest_key(pname, set(_THEME_PRESETS))
            hint = f"（是不是「{sugg}」？）" if sugg else ""
            raise ValueError(f"theme {where} apply 未定義 preset `{pname}`{hint}")
        merged.update(preset)
    for k, v in rules.items():
        if k == 'apply':
            continue
        merged[k] = v
    final = {}
    for p, v in merged.items():
        if p not in _CSS_PROP_ALLOW:
            sugg = _suggest_key(p, _CSS_PROP_ALLOW)
            hint = f"（是不是「{sugg}」？）" if sugg else f"合法：{sorted(_CSS_PROP_ALLOW)}"
            raise ValueError(f"theme {where} 未知 CSS property `{p}` {hint}")
        final[p] = _resolve_value(v)
    return final


# 結構性/列舉型關鍵字不是「設計值」：它們沒有級距可言，逼它們走 token 只會產生假 token。
# 有大小、有色彩的字面值仍然一律擋下（那才是 tokens: 要管的事）。
_THEME_STRUCTURAL_VALUES = {'0', 'none', 'transparent', 'inherit', 'currentColor', 'auto',
                            'normal', 'italic'}


def _require_token_value(value, where):
    """Reject design literals outside tokens while allowing zero-like structure."""
    text = str(value).strip()
    refs = re.findall(r'\{[^}]+\}', text)
    rest = re.sub(r'\{[^}]+\}', '', text)
    if text in _THEME_STRUCTURAL_VALUES:
        return
    if re.search(r'#[0-9a-fA-F]{3,8}\b|(?<![\w.])[-+]?(?:[1-9]\d*|0?\.\d+)(?:px|rem|em|vh|vw|%|s|ms|deg)?\b', rest):
        raise ValueError(f'theme {where} 不接受字面設計值 `{value}`；請先在 tokens: 定義級距，再用 {{family.name}} 引用')
    if not refs:
        raise ValueError(f'theme {where} 必須使用 token 參照（收到 `{value}`）')


def _require_token_rules(rules, where):
    if not isinstance(rules, dict):
        raise ValueError(f'theme {where} 必須是 dict')
    for key, value in rules.items():
        if key == 'apply':
            continue
        _require_token_value(value, f'{where}.{key}')


def _props_str(props):
    return ';'.join(f'{p}:{v}' for p, v in props.items())


def _theme_tokens_css(tokens):
    """theme `tokens:` → `:root{--wf-*:值}`（preset 不進 :root）。"""
    if not tokens:
        return ''
    decls = []
    for family, entries in tokens.items():
        if family == 'preset':
            continue
        for name, entry in entries.items():
            where = f'theme.tokens.{family}.{name}'
            if family == 'typography':
                value = entry.get('$value', entry) if isinstance(entry, dict) else entry
                for var, val in _typography_vars(name, value, where).items():
                    decls.append(f'{var}:{_resolve_value(val)}')
            elif family == 'gradient':
                decls.append(f'{_theme_var_name(family, name)}:{_resolve_value(_gradient_value(entry, name, where))}')
            else:
                decls.append(f'{_theme_var_name(family, name)}:{_resolve_value(_token_scalar(entry))}')
    css = [f':root{{{";".join(decls)}}}'] if decls else []
    # 全頁背景：定義了 page 背景 token（--wf-page-bg）就套到 .wf-root（= viewport / app 視窗本體，
    # 非 body 外圍留白），與 chrome 模式解耦。chrome: flat → root 顯示此底、面板浮其上；
    # chrome: card 之後另覆寫 root 為白卡（base 在 tokens 之後輸出，故 card 勝出）。
    if any(d.startswith('--wf-page-bg:') for d in decls):
        css.append('.wf-root{background:var(--wf-page-bg);}')
    if 'font' in tokens:
        # 標註面維持 wireframe 字體（meta 非產品，不受 theme）——機制守衛，非樣式
        css.append(".wf-gutter,.wf-mnote,.wf-spotlabel,.wf-step"
                   "{font-family:'Sarasa Mono TC','SarasaMono','Courier New',monospace;}")
    return '\n'.join(css)


def _theme_base_css(base):
    """base: 模式開關 → CSS。值類設定不在這裡（歸 tokens:）。"""
    if not base:
        return ''
    css = []
    chrome = base.get('chrome')
    if chrome is not None:
        if chrome not in _THEME_CHROME:
            raise ValueError(f"theme.base.chrome 只接 {sorted(_THEME_CHROME)}（收到 {chrome!r}）")
        css.append(_THEME_CHROME[chrome])
    marker = base.get('link-marker')
    if marker is not None:
        if marker not in ('show', 'hide'):
            raise ValueError(f"theme.base.link-marker 只接 show/hide（收到 {marker!r}）")
        if marker == 'hide':   # 動線 ↗ 是線框註記，產品不長這樣（連結仍可點）
            css.append('.wf-link::after,.wf-blocklink-a::after,.wf-btn.wf-link::after{content:none;}')
    sb = base.get('scrollbar')
    if sb is not None:
        if sb not in ('show', 'hide'):
            raise ValueError(f"theme.base.scrollbar 只接 show/hide（收到 {sb!r}）")
        if sb == 'hide':   # DOS 捲軸是線框示意，產品用原生捲動（HTML 真捲不受影響）
            css.append('.wf-show-all .wf-sb{display:none !important;}'
                       '.wf-show-all .wf-scroll{padding-right:var(--wf-space-md) !important;}')
    return '\n'.join(css)


def _state_selector(sel, sname):
    """狀態 selector：hover/focus 走真 pseudo（.html 互動可見）；其餘走 [data-ui-state]。"""
    if sname in ('hover', 'focus'):
        pseudo = ':focus-within' if sname == 'focus' else ':hover'
        return f'{sel}:is({pseudo},[data-ui-state="{sname}"])'
    return f'{sel}[data-ui-state="{_theme_slug(sname)}"]'


def _theme_components_css(components):
    """components: 元件皮 → CSS（base / variants / states，含 apply preset）。"""
    lines = []
    for cname, spec in components.items():
        if not isinstance(spec, dict):
            raise ValueError(f"theme.components.{cname} 必須是 dict（收到 {type(spec).__name__}）")
        if _KIT_COMPONENTS and cname not in _KIT_COMPONENTS and cname not in _THEME_COMPONENT_SELECTORS:
            raise ValueError(f'theme.components.{cname} 未在 kit 宣告；可用型別：{sorted(_KIT_COMPONENTS)}')
        sel = _THEME_COMPONENT_SELECTORS.get(cname) or f'.wf-role-{_theme_slug(cname)}'
        kit_spec = _KIT_COMPONENTS.get(cname) or {}
        if kit_spec.get('of') == 'canvas':
            special = {'base', 'link'} | {f'item.state.{s}' for s in kit_spec.get('states', [])}
            unknown_special = {k for k in spec if k.startswith('item.') and k not in special}
            if unknown_special:
                raise ValueError(f'theme.components.{cname} 未知 canvas 規則 {sorted(unknown_special)}（合法：{sorted(special)}）')
            base_rules = spec.get('base', {})
            if not isinstance(base_rules, dict):
                raise ValueError(f'theme.components.{cname}.base 必須是 dict')
            if base_rules:
                _require_token_rules(base_rules, f'components.{cname}.base')
                lines.append(f'{sel} .wf-canvas-base{{{_props_str(_expand_props(base_rules, f"components.{cname}.base"))}}}')
            link_rules = spec.get('link', {})
            if not isinstance(link_rules, dict) or set(link_rules) - {'stroke', 'stroke-width', 'dash'}:
                raise ValueError(f'theme.components.{cname}.link 只接 stroke/stroke-width/dash')
            if link_rules and kit_spec.get('link') is None:
                raise ValueError(f'theme.components.{cname}.link 無效：kit 未宣告 canvas link')
            link_props = {k: v for k, v in link_rules.items() if k != 'dash'}
            if link_props:
                _require_token_rules(link_props, f'components.{cname}.link')
                lines.append(f'{sel} .wf-canvas-link{{{_props_str(_expand_props(link_props, f"components.{cname}.link"))}}}')
            if link_rules.get('dash') is not None:
                if link_rules['dash'] is not True:
                    raise ValueError(f'theme.components.{cname}.link.dash 只接 true；虛線節奏定義在 tokens.stroke.dash')
                if 'stroke.dash' not in _THEME_FLATVALS:
                    raise ValueError(f'theme.components.{cname}.link.dash 需要先定義 tokens.stroke.dash')
                lines.append(f'{sel} .wf-canvas-link{{stroke-dasharray:{_resolve_value("{stroke.dash}")}}}')
            for key, rules in spec.items():
                if not key.startswith('item.'):
                    continue
                if not isinstance(rules, dict):
                    raise ValueError(f'theme.components.{cname}.{key} 必須是 dict')
                _require_token_rules(rules, f'components.{cname}.{key}')
                props = _expand_props(rules, f'components.{cname}.{key}')
                state = key[len('item.state.'):]
                target = f'{sel} .wf-canvas-item[data-kit-state="{_theme_slug(state)}"]'
                lines.append(f'{target}{{{_props_str(props)}}}')
            spec = {k: v for k, v in spec.items() if k not in special}
        state_flat = {k[6:]: v for k, v in spec.items() if k.startswith('state.')}
        base = {k: v for k, v in spec.items() if k not in ('variants', 'states') and not k.startswith('state.')}
        if base:
            _require_token_rules(base, f'components.{cname}')
            props = _expand_props(base, f'components.{cname}')
            if props:
                lines.append(f'{sel}{{{_props_str(props)}}}')
        for vname, vrules in (spec.get('variants') or {}).items():
            if cname in _KIT_COMPONENTS:
                raise ValueError(f'theme.components.{cname}.variants 尚未由 kit 宣告／實作')
            _require_token_rules(vrules, f'components.{cname}.variants.{vname}')
            props = _expand_props(vrules, f'components.{cname}.variants.{vname}')
            lines.append(f'{sel}[data-variant="{_theme_slug(vname)}"]{{{_props_str(props)}}}')
        for sname, srules in (spec.get('states') or {}).items():
            allowed = (_KIT_COMPONENTS.get(cname) or {}).get('states', [])
            if cname in _KIT_COMPONENTS and sname not in allowed:
                raise ValueError(f'theme.components.{cname}.states.{sname} 未在 kit states 宣告（合法：{allowed}）')
            _require_token_rules(srules, f'components.{cname}.states.{sname}')
            props = _expand_props(srules, f'components.{cname}.states.{sname}')
            lines.append(f'{_state_selector(sel, sname)}{{{_props_str(props)}}}')
        for sname, srules in state_flat.items():
            allowed = (_KIT_COMPONENTS.get(cname) or {}).get('states', [])
            if cname in _KIT_COMPONENTS and sname not in allowed:
                raise ValueError(f'theme.components.{cname}.state.{sname} 未在 kit states 宣告（合法：{allowed}）')
            _require_token_rules(srules, f'components.{cname}.state.{sname}')
            props = _expand_props(srules, f'components.{cname}.state.{sname}')
            lines.append(f'{sel}[data-kit-state="{_theme_slug(sname)}"]{{{_props_str(props)}}}')
    return '\n'.join(lines)


def _typography_decls(value, where):
    """typography: <token 名> → 一組宣告。只展開該 token 真的有宣告的子值。"""
    ref = str(value).strip('{}')
    if '.' in ref:
        family, name = ref.split('.', 1)
        if family != 'typography':
            # 只取最後一段會讓 {color.ink} 默默被當成 typography.ink 用——錯的家族要報錯
            raise ValueError(f'{where}: 需要 typography 家族的 token（收到 {value!r}）')
    else:
        name = ref
    keys = (_THEME_TOKENS.get('typography') or {})
    if name not in keys:
        raise ValueError(f'{where}: 未定義的 typography token {value!r}（可用：{sorted(keys)}）')
    entry = keys[name]
    sub = entry.get('$value', entry) if isinstance(entry, dict) else entry
    return [f'{css}:var(--wf-typography-{_theme_slug(name)}-{css})'
            for s_name, css in _TYPOGRAPHY_SUBS.items() if isinstance(sub, dict) and s_name in sub]


def _theme_bindings_css(bindings):
    """bindings: 綁 name:/role 的專案微調。相容舊 enum（surface/subtle/md…），並吃 {ref} / raw property。"""
    lines = []
    for role, rules in bindings.items():
        decls = []
        merged = {}
        for pname in (rules.get('apply') or []):          # bindings 也支援 apply preset
            preset = _THEME_PRESETS.get(pname)
            if preset is None:
                sugg = _suggest_key(pname, set(_THEME_PRESETS))
                hint = f"（是不是「{sugg}」？）" if sugg else ""
                raise ValueError(f"theme.bindings.{role} apply 未定義 preset `{pname}`{hint}")
            merged.update(preset)
        merged.update({k: v for k, v in rules.items() if k != 'apply'})
        for k, v in merged.items():
            if k in ('image', 'icon', 'fit'):
                continue
            if k == 'typography':        # 複合值：一個 token 展開成多條宣告，不是單一 property
                decls.extend(_typography_decls(v, f'bindings.{role}.typography'))
                continue
            use_enum = k in _THEME_BINDABLE and not (isinstance(v, str) and '{' in v)
            if k in ('padding', 'margin', 'gap') and str(v) not in GAP and str(v) not in (_TOKENS.get('gap') or {}):
                use_enum = False
            if use_enum:
                try:
                    css_prop, resolver = _THEME_BINDABLE[k]
                    decls.append(f'{css_prop}:{resolver(v)}')
                    continue
                except ValueError:
                    pass   # 非 enum 值 → 落到 raw property 路徑
            css_prop = _THEME_BINDABLE[k][0] if k in _THEME_BINDABLE else k
            if css_prop not in _CSS_PROP_ALLOW:
                sugg = _suggest_key(k, _CSS_PROP_ALLOW | set(_THEME_BINDABLE))
                hint = f"（是不是「{sugg}」？）" if sugg else ""
                raise ValueError(f"theme.bindings.{role}.{k}: 未知綁定屬性/CSS property{hint}")
            _require_token_value(v, f'bindings.{role}.{k}')
            decls.append(f'{css_prop}:{_resolve_value(v)}')
        r = esc_attr(role)
        named = json.dumps(str(role), ensure_ascii=False).replace('<', r'\3c ')
        # 優先序：語義身份（role/name）selector 三疊拉高 specificity，贏過元件皮。
        sel = _THEME_ELEMENT_SELECTORS.get(role)
        if sel is None:
            _warn_unbindable_target(role)
            sel = (f'.wf-role-{r}.wf-role-{r}.wf-role-{r}, '
                   f'[data-name={named}][data-name={named}][data-name={named}]')
        lines.append(f'{sel}{{{";".join(decls)}}}')
    return '\n'.join(lines)


def _warn_unbindable_target(role):
    """bindings 的 fallback selector 是給 kit 元件角色與畫面 `name:` 用的正當路徑，
    但打錯字或綁一個還沒有選擇器的 DSL 角色時，它會編出對不到任何元素的死 CSS 而靜默通過。
    這裡只在「確定綁不到」的兩種情況出聲，name: 因為可能定義在本次範圍外的畫面，一律放行。"""
    # 契約：kit 必須先於 theme 載入，否則 kit 元件角色會被誤判成綁不到。
    # CLI 兩條路徑（render / lint）都是這個順序；當作程式庫呼叫時也要維持。
    if role in _KIT_COMPONENTS:
        return
    bindable = sorted(_THEME_ELEMENT_SELECTORS)
    if role in LEAF_ROLES or role in TEXT_CLASS:
        msg = (f'bindings.{role} 是 DSL 葉子角色，但目前沒有對應的 theme 選擇器，'
               f'這條綁定不會生效（`wfyaml.py list` 可看可綁的角色）')
    else:
        sugg = _suggest_key(str(role), set(bindable))
        if not sugg:
            return          # 看起來是畫面的 name:，放行
        msg = (f'bindings.{role} 不是已知的綁定目標，是不是「{sugg}」？'
               f'（若這是畫面的 name:，可忽略這則警示）')
    if msg not in _THEME_WARNINGS:
        _THEME_WARNINGS.append(msg)


def _safe_asset_svg(raw, recolor=False):
    """Shape-only SVG: no scripts, event handlers, external references or embedded HTML."""
    root = ET.fromstring(raw)
    tags = {'svg', 'g', 'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'title', 'desc'}
    attrs = {'viewBox', 'width', 'height', 'd', 'x', 'y', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry',
             'points', 'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'fill-rule',
             'clip-rule', 'opacity', 'fill-opacity', 'stroke-opacity', 'transform', 'preserveAspectRatio'}
    def clean(el):
        el.tag = el.tag.split('}')[-1]
        for key, value in list(el.attrib.items()):
            if key not in attrs or 'url(' in value.lower():
                del el.attrib[key]
            elif recolor and key in ('fill', 'stroke') and value != 'none':
                el.set(key, 'currentColor')
        for child in list(el):
            if child.tag.split('}')[-1] not in tags:
                el.remove(child)
            else:
                clean(child)
    if root.tag.split('}')[-1] != 'svg':
        raise ValueError('不是 SVG')
    clean(root)
    if 'viewBox' not in root.attrib:
        w, h = root.get('width', ''), root.get('height', '')
        if re.fullmatch(r'[0-9.]+', w) and re.fullmatch(r'[0-9.]+', h):
            root.set('viewBox', f'0 0 {w} {h}')
    root.set('xmlns', 'http://www.w3.org/2000/svg')
    if recolor:
        root.set('fill', root.get('fill', 'currentColor'))
        root.set('class', 'wf-asset-icon')
        root.set('width', '1em'); root.set('height', '1em')
    return ET.tostring(root, encoding='unicode')


def _load_theme_assets(assets, theme_path):
    if not isinstance(assets, dict):
        raise AuthorError('theme.assets 必須是 dict', theme_path, 'assets')
    types = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
             '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml'}
    total = 0
    for name, relative in assets.items():
        if not isinstance(name, str) or not isinstance(relative, str) or os.path.isabs(relative) or re.match(r'^[a-zA-Z]+:', relative):
            raise AuthorError('素材須為邏輯名 → 相對 theme 的本機檔案', theme_path, f'assets.{name}')
        mime = types.get(os.path.splitext(relative)[1].lower())
        if not mime:
            raise AuthorError('素材只接 PNG/JPEG/GIF/WebP/SVG', theme_path, f'assets.{name}')
        entry = {'mime': mime, 'uri': None, 'icon': None}
        _THEME_ASSETS[name] = entry
        try:
            with open(os.path.join(os.path.dirname(theme_path), relative), 'rb') as handle:
                raw = handle.read()
            if len(raw) > 300 * 1024:
                _THEME_ASSET_WARNINGS.append(f'素材 {name} 超過 300KB（{len(raw)} bytes）')
            if mime == 'image/svg+xml':
                entry['icon'] = _safe_asset_svg(raw, True)
                raw = _safe_asset_svg(raw).encode('utf-8')
            entry['uri'] = f'data:{mime};base64,' + base64.b64encode(raw).decode('ascii')
            total += len(entry['uri'])
        except (OSError, ET.ParseError, ValueError) as e:
            _THEME_ASSET_WARNINGS.append(f'素材 {name} 無法讀取 {relative}：{e}；使用佔位')
    if total > 5 * 1024 * 1024:
        _THEME_ASSET_WARNINGS.append(f'素材內嵌總量超過 5MB（{total} bytes；重複使用會增加產物大小）')


def _warn_asset_output(output):
    size = sum(len(x) for x in re.findall(r'data:image/[^"\s]+', output))
    if size > 5 * 1024 * 1024:
        print(f'warning: 產物素材內嵌總量超過 5MB（{size} bytes）', file=sys.stderr)


def _bound_asset(node, kind):
    # Assets bind only stable node names; role and label never select files.
    rules = _THEME.get(node.get('data-name'), {})
    asset = _THEME_ASSETS.get(rules.get(kind), {})
    return asset, rules.get('fit', 'contain')


def _load_theme(path):
    """載入 theme YAML；驗證 tokens / preset / base / components / bindings（fail-fast）。"""
    global _THEME, _THEME_BASE, _THEME_TOKENS, _THEME_PRESETS, _THEME_COMPONENTS, _THEME_FLATVALS, _THEME_ASSETS, _THEME_ASSET_WARNINGS, _THEME_WARNINGS
    _THEME_ASSETS, _THEME_ASSET_WARNINGS, _THEME_WARNINGS = {}, [], []
    if not path:
        _THEME, _THEME_BASE, _THEME_TOKENS = {}, {}, {}
        _THEME_PRESETS, _THEME_COMPONENTS, _THEME_FLATVALS = {}, {}, {}
        return {}
    if not os.path.exists(path):
        raise ValueError(f"--mockup 找不到 theme 檔：{path}")
    data = _read_yaml(path)
    if not isinstance(data, dict):
        raise AuthorError('theme 頂層必須是 dict', path, '<root>')
    unknown = set(data.keys()) - {'tokens', 'base', 'bindings', 'components', 'assets'}
    if unknown:
        raise ValueError(f"theme 檔頂層 key 只允許 tokens/base/bindings/components/assets（收到多餘: {sorted(unknown)}）")
    _load_theme_assets(data.get('assets', {}), path)
    tokens = data.get('tokens') or {}
    if not isinstance(tokens, dict):
        raise ValueError(f"theme.tokens 必須是 dict（收到 {type(tokens).__name__}）")
    base = data.get('base') or {}
    if not isinstance(base, dict):
        raise ValueError(f"theme.base 必須是 dict（收到 {type(base).__name__}）")
    unk_base = set(base) - set(_THEME_BASE_KEYS)
    if unk_base:
        raise ValueError(f"theme.base 未知 key {sorted(unk_base)}（合法：{sorted(_THEME_BASE_KEYS)}；"
                         f"值類設定歸 tokens:）")
    bindings = data.get('bindings') or {}
    if not isinstance(bindings, dict):
        raise ValueError(f"theme.bindings 必須是 dict（收到 {type(bindings).__name__}）")
    for role, rules in bindings.items():
        if not isinstance(rules, dict):
            raise AuthorError(f'theme.bindings.{role} 必須是 dict', path, f'bindings.{role}')
        for kind in ('image', 'icon'):
            if kind in rules and (not isinstance(rules[kind], str) or rules[kind] not in _THEME_ASSETS):
                raise AuthorError(f'未定義素材 {rules[kind]!r}', path, f'bindings.{role}.{kind}')
            if kind == 'icon' and kind in rules and _THEME_ASSETS[rules[kind]]['mime'] != 'image/svg+xml':
                raise AuthorError('icon 素材必須是 SVG', path, f'bindings.{role}.icon')
        if 'fit' in rules and rules['fit'] not in ('cover', 'contain'):
            raise AuthorError('fit 只接受 cover/contain', path, f'bindings.{role}.fit')
        radius = rules.get('radius')
        if radius is not None and '{' not in str(radius) and str(radius) not in ('none', 'sm', 'md', 'lg', 'pill', 'full'):
            raise AuthorError(
                f'bindings.{role}.radius 收語義名，不接受 {radius!r}。\n'
                f'請在 tokens.radius.lg 定義 {radius!r}，並使用 bindings.{role}.radius: lg；'
                '原始 CSS 屬性使用 border-radius。', path, f'bindings.{role}.radius')
    components = data.get('components') or {}
    if not isinstance(components, dict):
        raise ValueError(f"theme.components 必須是 dict（收到 {type(components).__name__}）")

    # 值層先展開（fail-fast：未定義 ref / 循環在此炸）
    _THEME_FLATVALS = _flatten_tokens(tokens)
    presets = (tokens.get('preset') or {})
    if not isinstance(presets, dict):
        raise ValueError(f"theme.tokens.preset 必須是 dict（收到 {type(presets).__name__}）")
    # preset 不可 apply 另一個 preset（一層攤平）
    for pn, pr in presets.items():
        if isinstance(pr, dict) and 'apply' in pr:
            raise ValueError(f"theme.tokens.preset.{pn} 不可 apply 另一個 preset（一層攤平；共用值請用 {{token.ref}}）")
    _THEME_PRESETS = presets
    for pn, pr in presets.items():        # 驗證 preset 內 property + ref
        _expand_props(pr, f'tokens.preset.{pn}')
    _THEME, _THEME_BASE, _THEME_TOKENS, _THEME_COMPONENTS = bindings, base, tokens, components
    for cname, spec in _KIT_COMPONENTS.items():
        asset_name = spec.get('base', {}).get('asset') if spec.get('of') == 'canvas' else None
        if asset_name and asset_name not in _THEME_ASSETS:
            raise AuthorError(f'canvas `{cname}` 使用未定義素材 {asset_name!r}', path,
                              f'components.{cname}.base.asset')
    # 全部先編一次觸發驗證（property 白名單 / enum / ref）
    _theme_tokens_css(tokens)
    _theme_components_css(components)
    _theme_bindings_css(bindings)
    for warning in _THEME_ASSET_WARNINGS + _THEME_WARNINGS:
        print(f'warning: {path} → {warning}', file=sys.stderr)
    return bindings


def _theme_css():
    """把當前 theme（tokens + base + components + bindings）編成 CSS。
    工具不硬編任何 mockup 長相（theme 是資料，可跨平台翻譯；style 解耦原則）。
    輸出順序即 specificity：tokens(:root) → base → components → bindings（最後最高）。"""
    if not _theme_active():
        return ''
    lines = [_theme_tokens_css(_THEME_TOKENS), _theme_base_css(_THEME_BASE),
             _theme_components_css(_THEME_COMPONENTS), _theme_bindings_css(_THEME)]
    return '\n'.join(x for x in lines if x)


# ─────────────────────────────────────────────────────────────────────────
# SAC Story-as-Code（DISCUSSION 2026-07-03，四輪 review 定稿）
# ─────────────────────────────────────────────────────────────────────────
# 故事綁定層：底圖單一事實來源，故事以外部 .story.yaml 疊加（標註 + 情境變體）。
# 三系統分工：routes=產品狀態、story=情境資料+標註、theme=視覺綁定。

_STORY = None    # 當前載入的 story dict；None = 無故事疊加

_STORY_TOP_KEYS = {'story', 'actor', 'intent', 'page', 'bindings', 'flow'}
_STORY_BINDING_KEYS = {'target', 'spotlight', 'note', 'badge', 'set'}   # 標註類頂層白名單
_STORY_SET_KEYS = {'text', 'to'}                                        # 變體類白名單（防滑坡）
_STORY_FLOW_KEYS = {'step', 'target', 'to', 'desc'}


def _load_story(path):
    """載入 + 驗證 story 檔（fail-fast：白名單 / 必填 / step 規則）。回傳 story dict。"""
    if not os.path.exists(path):
        raise ValueError(f"--story 找不到故事檔：{path}")
    data = yaml.safe_load(open(path, encoding='utf-8')) or {}
    unknown = set(data) - _STORY_TOP_KEYS
    if unknown:
        raise ValueError(f"story 檔頂層 key 白名單：{sorted(_STORY_TOP_KEYS)}（收到多餘 keys: {sorted(unknown)}）")
    for req in ('story', 'page'):
        if req not in data:
            raise ValueError(f"story 檔缺必填欄位 `{req}:`")
    for i, b in enumerate(data.get('bindings') or []):
        unk = set(b) - _STORY_BINDING_KEYS
        if unk:
            sugg = _suggest_key(sorted(unk)[0], _STORY_BINDING_KEYS)
            hint = f"（是不是「{sugg}」？）" if sugg else ""
            raise ValueError(f"bindings[{i}]: 未知 key {sorted(unk)} {hint}白名單：{sorted(_STORY_BINDING_KEYS)}")
        if 'target' not in b:
            raise ValueError(f"bindings[{i}] 缺必填 `target:`")
        s = b.get('set') or {}
        unk2 = set(s) - _STORY_SET_KEYS
        if unk2:
            raise ValueError(f"bindings[{i}].set: 未知 key {sorted(unk2)}（白名單只有 {sorted(_STORY_SET_KEYS)}；"
                             f"狀態變體歸 routes/when 系統）")
    # flow 驗證 + step 編號（選填：未寫 = 上一整數步 +1；字串 step 後未編號 → error；重複 → error）
    last_int, seen = 0, set()
    for i, f in enumerate(data.get('flow') or []):
        if not isinstance(f, dict):
            raise ValueError(f"flow[{i}] 必須是 dict（收到 {type(f).__name__}）")
        unk = set(f) - _STORY_FLOW_KEYS
        if unk:
            raise ValueError(f"flow[{i}]: 未知 key {sorted(unk)}（白名單：{sorted(_STORY_FLOW_KEYS)}）")
        if 'desc' not in f:
            raise ValueError(f"flow[{i}] 缺必填 `desc:`（敘事主體）")
        st = f.get('step')
        if st is None:
            if last_int is None:
                raise ValueError(f"flow[{i}]: 字串 step 之後的項目必須明寫 step")
            st = last_int + 1
        last_int = st if isinstance(st, int) else None
        if str(st) in seen:
            raise ValueError(f"flow[{i}]: step 重複（{st}）")
        seen.add(str(st))
        f['_step'] = st
    return data


def _resolve_story_page(pageref, story_dir):
    """解析 story 的 page 引用 → (檔案路徑, fragment ctx)。搜尋：story 同目錄 → 父目錄 → pages/。
    無 fragment → 綁 default 路由（回傳 ctx None）。"""
    frag = None
    if '#' in str(pageref):
        pageref, _, frag = str(pageref).partition('#')
    parent = os.path.dirname(story_dir) or '.'
    dirs = [story_dir, parent, os.path.join(parent, 'pages')]
    for d in dirs:
        for ext in ('.wf.yaml', '.yaml', '.yml'):
            c = os.path.join(d, pageref + ext)
            if os.path.exists(c):
                return c, frag
    raise ValueError(f"story.page 找不到底圖：{pageref}（找過 {dirs}）")


def _story_target_match(node, target):
    """target 消歧：含 `[` = YAML 路徑（比對 __path 蓋章）；否則 = name 錨點。"""
    if '[' in target:
        return node.get('__path') == target
    return node.get('name') == target


def _apply_story(items, story):
    """把 story 的 bindings（標註+變體）與 flow 序號注入 expand 後的樹。
    fail-fast：任一 target 0 命中 → error。命中多個 = 全疊（統一規則）。"""
    bindings = story.get('bindings') or []
    flow = story.get('flow') or []
    hits = {b['target']: 0 for b in bindings}
    fhits = {f['target']: 0 for f in flow if f.get('target')}

    def inject_binding(node, b):
        if 'spotlight' in b:
            node['spotlight'] = b['spotlight']
        if 'note' in b:
            node['note'] = b['note']
        if 'badge' in b:
            node['__story_badge'] = b['badge']
        s = b.get('set') or {}
        if 'text' in s:
            role = next((r for r in LEAF_ROLES if r in node), None)
            if not role:
                raise ValueError(
                    f"set.text 只對 leaf 有效（target `{b['target']}` 命中 container：keys={sorted(_ckeys(node))}）")
            val = node[role]
            if isinstance(val, dict):
                for k in ('text', 'placeholder', 'label'):
                    if k in val:
                        val[k] = s['text']
                        break
                else:
                    val['text'] = s['text']
            else:
                node[role] = s['text']
        if 'to' in s:
            role = next((r for r in LEAF_ROLES if r in node), None)
            if role and role not in ('button', 'link'):
                raise ValueError(
                    f"set.to 只支援 container / widget / button / link（target `{b['target']}` 是 {role}）")
            if role in ('button', 'link') and isinstance(node[role], dict):
                node[role]['to'] = s['to']
            elif role in ('button', 'link'):
                node[role] = {'text': node[role], 'to': s['to']}
            else:
                node['to'] = s['to']

    def visit(node):
        if isinstance(node, list):
            for x in node:
                visit(x)
            return
        if not isinstance(node, dict):
            return
        for b in bindings:
            if _story_target_match(node, b['target']):
                hits[b['target']] += 1
                inject_binding(node, b)
        for f in flow:
            t = f.get('target')
            if t and _story_target_match(node, t):
                fhits[t] += 1
                node.setdefault('__story_steps', []).append({'label': str(f['_step']), 'to': f.get('to')})
        for k, v in list(node.items()):
            if isinstance(k, str) and k.startswith('__'):
                continue
            visit(v)

    visit(items)
    miss = sorted([t for t, c in hits.items() if c == 0] + [t for t, c in fhits.items() if c == 0])
    if miss:
        raise ValueError(f"story target 解析不到節點：{miss}\n"
                         f"（name 錨點需底圖節點掛 `name: <target>`；路徑需含 `[` 且與 debug 蓋章一致）")
    return items


def _story_header_html():
    """story banner（📖 id｜actor｜intent）+ flow desc 清單。無 story → 空字串。"""
    if not _STORY:
        return ''
    s = _STORY
    parts = [esc(str(s['story']))]
    if s.get('actor'):
        parts.append(esc(str(s['actor'])))
    if s.get('intent'):
        parts.append(esc(str(s['intent'])))
    out = f'<div class="wf-story-banner">📖 {" ｜ ".join(parts)}</div>'
    if s.get('flow'):
        lis = ''.join(
            f'<div class="wf-story-flowitem"><span class="wf-story-step">{esc(str(f["_step"]))}</span>'
            f'<span>{inline(f["desc"])}</span></div>'
            for f in s['flow'])
        out += f'<div class="wf-story-flowlist">{lis}</div>'
    return out


def _gap(name):
    """gap/padding 值解析：內建 primitive 直用；專案 token → var 別名；未知 → error（fail-fast）。"""
    n = str(name)
    if n in GAP:
        return GAP[n]
    if n in (_TOKENS.get('gap') or {}):
        return f'var(--wf-gap-{n})'
    raise ValueError(f"未知 gap/padding 值「{n}」（合法：{sorted(GAP)}；或在 tokens/*.yaml 定義為 semantic token）")


def esc_attr(s):
    return re.sub(r'[^A-Za-z0-9_-]', '-', str(s))
JUSTIFY = {'between': 'space-between', 'end': 'flex-end', 'start': 'flex-start',
           'center': 'center', 'around': 'space-around'}
ALIGN = {'center': 'center', 'top': 'flex-start', 'bottom': 'flex-end',
         'start': 'flex-start', 'end': 'flex-end',   # col 交錯軸 = 水平；start/end 是 CSS Flex 標準
         'baseline': 'baseline', 'stretch': 'stretch'}
SCROLL_SCALE = {'sm': '8rem', 'md': '16rem', 'lg': '32rem', 'xl': '48rem'}  # P0.5 純語義級距
CONTAINER_KEYS = {'row', 'col', 'grid', 'items', 'embed', 'slot'}
LEAF_ROLES = ['text.title', 'text.heading', 'text.label', 'text.strong', 'text.hint', 'text',
              'input', 'select', 'button', 'status.badge', 'status.muted', 'status.strong', 'status',
              'alert', 'icon', 'divider', 'tabs', 'image', 'checkbox', 'radio', 'link',
              'progress', 'avatar', 'avatars', 'map']
TEXT_CLASS = {'text': 'wf-label', 'text.title': 'wf-h wf-h1', 'text.heading': 'wf-h wf-h2',
              'text.label': 'wf-label wf-fieldlabel', 'text.strong': 'wf-b', 'text.hint': 'wf-hint'}
_UI_STATES = {'selected', 'disabled', 'hover', 'focus', 'active'}   # 顯示態（→ data-ui-state；theme states 綁）

_NOTES = []   # Layer2 note → 右側 gutter（供 render.sh 量測對齊（位置烤進 DOM））
_NCOUNT = 0
_PAGE_BASE = ''   # 目前頁面檔名 base，供 `to: "#stage.state"` 同頁路由連結解析
_DEBUG = False    # debug 模式：輸出 data-wf-src/data-wf-path 供評審回饋定位
_RADIO_NAV = False
_LINK_SERIAL = 0
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

# ---- 額外 CSS（基底 wf.css 沒有的：image 佔位 / spotlight / 欄位標籤 / progress / avatar）----
CSS_EXTRA = r"""
.wf-image { display:flex; align-items:center; justify-content:center; min-height:64px;
  border:1px dashed #9ca3af; color:#9ca3af; border-radius:var(--wf-radius); font-size:.85em;
  background-image:linear-gradient(45deg,transparent 47%,#d1d5db 48%,#d1d5db 52%,transparent 53%),
                   linear-gradient(-45deg,transparent 47%,#d1d5db 48%,#d1d5db 52%,transparent 53%); }
.wf-fieldlabel { color:#6b7280; font-size:.9em; }
.wf-hyperlink { color:#2563eb; text-decoration:underline; text-underline-offset:2px; }
/* collapsible：通用可收合區塊（原生 details/summary；零 JS 可展開）。視覺細節走 --mockup theme */
.wf-collapsible > .wf-summary { cursor:pointer; list-style:revert; user-select:none; }
.wf-collapsible > .wf-node { margin-top:var(--wf-space-sm,.4rem); }
/* 通用顯示態：disabled 去互動（其餘態長相由 theme components states 決定） */
[data-ui-state="disabled"] { opacity:.5; cursor:default; pointer-events:none; }
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
.wf-scroll > * { flex-shrink:0; }
.wf-placeholder { color:#6b7280; border-bottom:1px dashed currentColor; }
.wf-avatars { display:flex; align-items:center; padding-left:var(--wf-space-sm); }
.wf-avatars > .wf-avatar { margin-left:calc(-1 * var(--wf-space-sm)); flex-shrink:0; outline:2px solid #fff; }
/* checkbox/radio are deliberately drawn HTML controls, rather than glyphs or native inputs.
   Theme bindings target only .wf-*-control; label text remains ordinary document text. */
.wf-choice { display:inline-flex; align-items:center; gap:.45em; }
.wf-choice-control { box-sizing:border-box; width:1.55em; height:1.55em; flex:0 0 1.55em;
  display:inline-flex; align-items:center; justify-content:center; color:#374151;
  background:#fff; border:2px solid #374151; line-height:1; }
.wf-check-control { border-radius:calc(var(--wf-radius,6px) * .6); }
.wf-radio-control { border-radius:50%; }
.wf-choice-input { position:absolute; opacity:0; width:0; height:0; }
.wf-choice-box { display:inline-flex; cursor:pointer; }
.wf-choice-label { cursor:pointer; }
.wf-choice-input:checked ~ .wf-choice-box > .wf-choice-control::after,
.wf-choice-control.wf-choice-checked::after { content:'✓'; font-size:1.18em; font-weight:800; line-height:1; }
.wf-choice-input:focus-visible ~ .wf-choice-box > .wf-choice-control { outline:2px solid currentColor; outline-offset:2px; }
.wf-radio-control.wf-choice-checked::after { content:''; width:.7em; height:.7em; border-radius:50%; background:currentColor; }
.wf-map { border:1px dashed #9ca3af; min-height:8rem; padding:var(--wf-space-md);
  display:flex; flex-wrap:wrap; align-content:center; justify-content:center; gap:var(--wf-space-md);
  background:repeating-linear-gradient(0deg,transparent,transparent 23px,#e5e7eb 24px),
             repeating-linear-gradient(90deg,transparent,transparent 23px,#e5e7eb 24px); }
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
/* progress leaf：語義比例 fill bar（全灰階——色彩=保真度的函數，產品色走 --mockup theme） */
.wf-progress { position:relative; display:block; height:.75rem; background:#e5e7eb;
  border-radius:var(--wf-radius-pill); overflow:hidden; min-width:4rem; }
.wf-progress-fill { position:absolute; top:0; left:0; bottom:0; background:#6b7280;
  border-radius:var(--wf-radius-pill); transition:width .2s ease; }
.wf-progress-label { position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
  font-size:.7em; color:#111827; font-weight:600; }
.wf-asset-image { position:relative; padding:0 !important; overflow:hidden; background-image:none !important; }
.wf-asset-image::before,.wf-asset-image::after { display:none !important; }
.wf-asset-image img { position:absolute; inset:0; width:100%; height:100%; }
.wf-avatar img { width:100%; height:100%; border-radius:inherit; }
.wf-asset-icon { vertical-align:middle; }
.wf-canvas { position:relative; overflow:hidden; min-height:8rem; }
.wf-canvas-base { position:absolute; inset:0; }
.wf-canvas-base-img { width:100%; height:100%; object-fit:cover; }
.wf-canvas-base-grid { background:repeating-linear-gradient(0deg,transparent,transparent 23px,#e5e7eb 24px),
  repeating-linear-gradient(90deg,transparent,transparent 23px,#e5e7eb 24px); }
.wf-canvas-placeholder { display:flex; align-items:center; justify-content:center;
  color:#6b7280; border:1px dashed #9ca3af; background:#f3f4f6; }
.wf-canvas-link-layer { position:absolute; inset:0; width:100%; height:100%; overflow:visible; pointer-events:none; }
.wf-canvas-link { fill:none; stroke:#6b7280; stroke-width:4; vector-effect:non-scaling-stroke; }
.wf-canvas-link-arrow { fill:context-stroke; stroke:none; }
.wf-canvas-item { position:absolute; z-index:2; transform:translate(-50%,-50%); }
/* avatar leaf：只 label(縮寫) + size(sm/md/lg)；圓形佔位，禁 src/bg（守視覺封印） */
.wf-avatar { display:inline-flex; align-items:center; justify-content:center;
  background:#e5e7eb; color:#374151; border:1px solid #9ca3af; border-radius:var(--wf-radius-pill);
  font-weight:600; text-transform:uppercase; }
.wf-avatar-sm { width:1.5rem; height:1.5rem; font-size:.65em; }
.wf-avatar-md { width:2.25rem; height:2.25rem; font-size:.8em; }
.wf-avatar-lg { width:3rem; height:3rem; font-size:1em; }
/* ── SAC Story-as-Code overlay（標註面；story 版專屬，紫色系明顯非 UI） ── */
.wf-story-anchor { position:relative; }
.wf-story-badge { position:absolute; top:-9px; right:-6px; z-index:6; white-space:nowrap;
  background:#b45309; color:#fff; font-size:.65em; padding:1px 7px;
  border-radius:var(--wf-radius-pill); box-shadow:0 1px 2px rgba(0,0,0,.25); }
.wf-story-step { display:inline-flex; align-items:center; justify-content:center;
  min-width:18px; height:18px; padding:0 4px; font-size:.7em; font-weight:700;
  color:#fff; background:#7c3aed; border-radius:var(--wf-radius-pill); text-decoration:none; }
a.wf-story-step:hover { background:#5b21b6; }
.wf-story-step-pin { position:absolute; top:-9px; left:-9px; z-index:6; }
.wf-story-step-pin + .wf-story-step-pin { left:12px; }   /* 同 anchor 多序號排開 */
.wf-story-banner { background:#f5f3ff; border:1px solid #ddd6fe; color:#5b21b6;
  padding:6px 10px; border-radius:var(--wf-radius); font-size:.85em; font-weight:600; margin-bottom:4px; }
.wf-story-flowlist { border:1px dashed #c4b5fd; border-radius:var(--wf-radius);
  padding:8px 10px; margin-bottom:8px; display:flex; flex-direction:column; gap:5px; }
.wf-story-flowitem { font-size:.8em; color:#4c1d95; display:flex; gap:8px; align-items:center; }
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
@media(max-width:860px){
  body.wf-debug{padding-bottom:calc(var(--wf-dbg-bar-clearance,74px) + env(safe-area-inset-bottom));}
  body.wf-debug #wf-main{padding-bottom:calc(var(--wf-dbg-bar-clearance,74px) + env(safe-area-inset-bottom));}
  #wf-dbg{top:auto;bottom:calc(10px + var(--wf-dbg-lift,0px) + env(safe-area-inset-bottom));
    left:10px;right:auto;max-width:calc(100% - 20px);display:flex;flex-wrap:wrap;align-items:center;gap:4px;font-size:11px;}
  #wf-dbg button{margin:0;min-height:40px;min-width:56px;}
  #wf-dbg-pop{position:fixed;left:8px;right:8px;top:auto;
    bottom:calc(var(--wf-dbg-bar-clearance,74px) + var(--wf-dbg-lift,0px) + env(safe-area-inset-bottom));
    max-height:calc(var(--wf-dbg-vh,100dvh) * .46);overflow:auto;overflow-wrap:anywhere;}
  #wf-dbg-pop textarea{width:100%;box-sizing:border-box;min-height:70px;font-size:16px;}
  #wf-dbg-pop button{min-height:40px;min-width:56px;}
  #wf-dbg-export{inset:auto 4%;top:calc(var(--wf-dbg-vtop,0px) + 8px + env(safe-area-inset-top));
    bottom:calc(var(--wf-dbg-lift,0px) + 8px + env(safe-area-inset-bottom));
    display:flex;flex-direction:column;overflow:auto;}
  #wf-dbg-export textarea{height:auto;min-height:0;flex:1;font-size:16px;}
  #wf-dbg-export button{min-height:40px;min-width:56px;}
  body:has(#wf-dbg-export) #wf-dbg{visibility:hidden;}
}

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
  var pop=null,anchor=null;
  var narrow=window.matchMedia('(max-width:860px)');
  function position(){
    var vv=window.visualViewport,root=document.documentElement;
    root.style.setProperty('--wf-dbg-vh',(vv?vv.height:innerHeight)+'px');
    root.style.setProperty('--wf-dbg-vtop',(vv?vv.offsetTop:0)+'px');
    root.style.setProperty('--wf-dbg-lift',Math.max(0,innerHeight-(vv?vv.height+vv.offsetTop:innerHeight))+'px');
    root.style.setProperty('--wf-dbg-bar-clearance',(bar.offsetHeight+26)+'px');
    if(pop){
      if(narrow.matches){pop.style.removeProperty('top');pop.style.removeProperty('left');}
      else if(anchor){var r=anchor.getBoundingClientRect();
        pop.style.top=(scrollY+r.bottom+4)+'px';pop.style.left=(scrollX+r.left)+'px';}
    }
  }
  function close(){if(pop){pop.remove();pop=null;}anchor=null;}
  function open(el){
    close();var k=keyOf(el),src=el.getAttribute('data-wf-src')||'',path=el.getAttribute('data-wf-path')||'';
    pop=document.createElement('div');pop.id='wf-dbg-pop';anchor=el;
    pop.innerHTML='<div class="h">'+src+' → '+path+'</div>';
    var ta=document.createElement('textarea');ta.value=(store[k]&&store[k].note)||'';ta.placeholder='修改建議…';
    var s=document.createElement('button');s.textContent='存';
    var d=document.createElement('button');d.textContent='刪';
    pop.appendChild(ta);pop.appendChild(s);pop.appendChild(d);document.body.appendChild(pop);position();ta.focus();
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
  document.body.appendChild(bar);document.body.classList.add('wf-debug');
  window.addEventListener('resize',position);
  if(window.visualViewport){visualViewport.addEventListener('resize',position);visualViewport.addEventListener('scroll',position);}
  position();
  var mbtn=document.getElementById('wf-dbg-mode');
  mbtn.onclick=function(){ann=!ann;mbtn.textContent='模式:'+(ann?'註記':'瀏覽');document.body.classList.toggle('wf-annotate',ann);if(!ann)close();};
  document.getElementById('wf-dbg-clr').onclick=function(){if(confirm('清除本頁所有註記?')){store={};localStorage.removeItem(KEY);mark();}};
  document.getElementById('wf-dbg-exp').onclick=function(){
    close();var previous=document.getElementById('wf-dbg-export');if(previous)previous.remove();
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
    var actions=document.createElement('div');actions.appendChild(cp);actions.appendChild(cl);
    ov.appendChild(ta);ov.appendChild(actions);document.body.appendChild(ov);position();ta.select();
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
        if m.group(2) is None:
            return _placeholder_match(m.group(3), m.group(0))
        txt, tgt = m.group(1), m.group(2)
        if tgt.startswith('to:'):
            return _wire_link(tgt[3:], txt, "wf-hyperlink")
        return f'<a class="wf-hyperlink" href="{tgt}">{txt}</a>'

    s = _INLINE_BRACKETS.sub(_a, s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'~~(.+?)~~', r'<del>\1</del>', s)
    s = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', s)
    return s


# 一次分類連結與未定值；連結整段先吃掉，避免將 href 中的方括號標成未定值。
_INLINE_BRACKETS = re.compile(r'\[([^\[\]\n]+)\]\(([^)\n]+)\)|(?<!\\)\[([^\[\]\n]+)\](?!\()')


def _placeholder_match(label, original):
    if label.strip().lower() in ('', 'x'):
        return original
    return f'<span class="wf-placeholder" title="未定值">{original}</span>'


def _placeholder_html(value):
    return _INLINE_BRACKETS.sub(
        lambda m: m.group(0) if m.group(2) is not None else _placeholder_match(m.group(3), m.group(0)),
        esc(value))


def _placeholder_count(value):
    if not isinstance(value, str):
        return 0
    return sum(1 for m in _INLINE_BRACKETS.finditer(value)
               if m.group(2) is None and m.group(3).strip().lower() not in ('', 'x'))


def _icon(val):
    if isinstance(val, dict):
        st, name = val.get('set', 'fa'), val.get('name', '')
        return lu_svg(name) if st == 'lu' else fa_svg('fas', name)
    name = str(val)
    if name in ICONS:
        return f'<span class="wf-icon">{ICONS[name]}</span>'
    # 先試 FA，失敗轉試 Lucide；兩者皆無 → 錯誤（禁靜默）
    try:
        return fa_svg('fas', name)
    except ValueError:
        try:
            return lu_svg(name)
        except ValueError:
            raise ValueError(f"icon: `{name}` 在 FA / Lucide 都找不到（請確認 canonical 名稱）")


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


def _wire_link(target, inner, classes='', attrs='', page_id=None, nav=False, checked=False):
    """Wireframe links share the same output mode, including story and inline links.

    Each radio label owns a focusable native control, so Space/arrow keys work
    without JavaScript. Duplicate destinations share values, never input IDs.
    """
    global _LINK_SERIAL
    href = '#' + page_id if page_id else _href(target)
    if not (_BUNDLE and _RADIO_NAV):
        return f'<a href="{href}" class="{classes}"{attrs}>{inner}</a>'
    pid = page_id or href[1:]
    _LINK_SERIAL += 1
    rid = 'r-' + pid if nav else f'wf-r-link-{_LINK_SERIAL}'
    control = (f'<input class="wf-r" type="radio" name="wfpg" id="{rid}" '
               f'value="{pid}" aria-controls="{pid}"' + (' checked' if checked else '') + '>')
    return f'<label for="{rid}" class="{classes} wf-radio-link"{attrs}>{control}{inner}</label>'


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
        return _choice_html('checkbox', m.group(1).lower() == 'x', m.group(2), A)
    m = re.match(r'^\(([ xXoO])\)\s*(.*)$', s)
    if m:
        return _choice_html('radio', m.group(1).lower() in ('x', 'o'), m.group(2), A)
    return f'<span class="wf-label"{A}>{inline(s)}</span>'


_REVEAL_RULES = []        # 純 CSS 連動：(控制項 id, 要顯示的 name)
_REVEAL_SEQ = [0]


def _choice_html(kind, checked, label, attrs='', extra_class='', reveals=None, group=None):
    """真的 checkbox / radio：勾選是瀏覽器原生行為，零 JS。

    可主題化的視覺控制項仍是 span（外觀不變），真正的 <input> 藏在其後、
    由 :checked 驅動樣式 —— 與 bundle 的 radio 導覽同一套機制。
    `reveals` 指向某個 `name:`，勾了才顯示該節點（純 CSS `:has()`）。
    """
    role = 'checkbox' if kind == 'checkbox' else 'radio'
    short = 'check' if kind == 'checkbox' else 'radio'
    _REVEAL_SEQ[0] += 1
    cid = f'wf-c{_REVEAL_SEQ[0]}'
    if reveals:
        _REVEAL_RULES.append((cid, str(reveals)))
    name_attr = f' name="{html.escape(str(group), quote=True)}"' if group and kind == 'radio' else ''
    checked_attr = ' checked' if checked else ''
    box = f'<input class="wf-choice-input" id="{cid}" type="{role}"{name_attr}{checked_attr}>'
    control = f'<span class="wf-{short}-control wf-choice-control" aria-hidden="true"></span>'
    return (f'<span class="wf-choice wf-{short} {extra_class}"{attrs}>{box}'
            f'<label class="wf-choice-box" for="{cid}">{control}</label>'
            f'<label class="wf-choice-label" for="{cid}">{inline(label)}</label></span>')


def _reveal_css():
    """勾選連動的 CSS：未勾時隱藏對應 name 的節點。"""
    if not _REVEAL_RULES:
        return ''
    rules = [f'.wf-root:has(#{cid}:not(:checked)) [data-name="{html.escape(name, quote=True)}"]'
             '{display:none;}' for cid, name in _REVEAL_RULES]
    return '\n'.join(rules)


def render_leaf(d, xcls, xattr):
    role = next((r for r in LEAF_ROLES if r in d), None)
    val = d.get(role)
    cls = lambda base: ' '.join([base] + xcls)
    A = _attrs(xattr)

    if role in TEXT_CLASS:
        return f'<div class="{cls(TEXT_CLASS[role])}"{A}>{inline(val)}</div>'
    if role == 'input':
        # 真的 <input>：打字是瀏覽器原生行為，零 JS。value / placeholder 走屬性。
        ph = val.get('placeholder', '') if isinstance(val, dict) else val
        v = val.get('value') if isinstance(val, dict) else None
        attrs = f' value="{html.escape(str(v), quote=True)}"' if v else ''
        if ph:
            attrs += f' placeholder="{html.escape(str(ph), quote=True)}"'
        return f'<input class="{cls("wf-input")}" type="text"{attrs}{A}>'
    if role == 'select':
        # 真的 <select>：選單可展開。未宣告 options 時只放目前值一項。
        if isinstance(val, dict):
            txt, options = val.get('text', ''), val.get('options') or []
        else:
            txt, options = val, []
        items = ([txt] + [o for o in options if o != txt]) if txt else list(options)
        opts = ''.join(f'<option>{html.escape(str(o))}</option>' for o in items) or '<option></option>'
        return f'<select class="{cls("wf-select")}"{A}>{opts}</select>'
    if role == 'button':
        if isinstance(val, dict):
            txt, to, ic = val.get('text', ''), val.get('to', d.get('to')), val.get('icon')
            inner = (_icon(ic) + ' ' if ic else '') + inline(txt)
        else:
            txt, to, inner = val, d.get('to'), inline(val)
        if to:
            return _wire_link(to, inner, cls("wf-btn wf-link"), A)
        return f'<button class="{cls("wf-btn")}"{A}>{inner}</button>'
    if role == 'status.badge':
        return f'<label class="{cls("wf-badge")}"{A}>{inline(val)}</label>'
    if role in ('status', 'status.muted', 'status.strong'):
        lvl = {'status.muted': ' wf-tag-muted', 'status.strong': ' wf-tag-strong'}.get(role, '')
        return f'<span class="{cls("wf-tag" + lvl)}"{A}>{inline(val)}</span>'
    if role == 'alert':
        return f'<span class="{cls("wf-warn")}"{A}><span class="wf-icon">⚠</span> {inline(val)}</span>'
    if role == 'icon':
        asset, _fit = _bound_asset(xattr, 'icon')
        return f'<span class="{cls("")}"{A}>{asset.get("icon") or _icon(val)}</span>'
    if role == 'divider':
        return f'<hr class="{cls("wf-hr")}"{A}/>'
    if role == 'link':
        txt = val.get('text', '') if isinstance(val, dict) else val
        to = val.get('to', '#') if isinstance(val, dict) else '#'
        return f'<a class="{cls("wf-hyperlink")}" href="{esc(to)}"{A}>{inline(txt)}</a>'
    if role in ('checkbox', 'radio'):
        if isinstance(val, dict):
            unknown = {k for k in val if not str(k).startswith('__')} - {'label', 'checked', 'reveals', 'group'}
            if unknown:
                raise ValueError(f'{role} 只接 label/checked/reveals/group（收到多餘 {sorted(unknown)}）')
            label, checked = val.get('label', ''), val.get('checked')
            reveals, group = val.get('reveals'), val.get('group')
        else:
            label, checked, reveals, group = val, False, None, None
        return _choice_html(role, checked, label, A, ' '.join(xcls), reveals, group)
    if role == 'image':
        if isinstance(val, dict) and ('src' in val or 'bg' in val):
            raise ValueError('image 禁 src/bg；素材路徑只可放 theme.assets')
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
        asset, fit = _bound_asset(xattr, 'image')
        if asset.get('uri'):
            return f'<div class="{cls("wf-image wf-asset-image")}"{st}{A}><img src="{asset["uri"]}" alt="{esc(label)}" style="object-fit:{fit}"></div>'
        return f'<div class="{cls("wf-image")}"{st}{A}>▧ {_placeholder_html(label)}</div>'
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
        # name 必須寫節點層（跟 progress key 同層 sibling），非 value 內。
        if isinstance(val, dict):
            if 'name' in val:
                raise ValueError("progress: name 必須寫在節點層（跟 progress key 同層 sibling），非 value 內")
            v = val.get('value', 0)
            label = val.get('label', '')
        else:
            v = val
            label = ''
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"progress.value 需為 0-1 數字（收到 {v!r}）")
        if not (0.0 <= f <= 1.0):
            raise ValueError(f"progress.value 需在 0-1 範圍（收到 {f}）")
        pct = f * 100
        lbl_html = f'<span class="wf-progress-label">{inline(label)}</span>' if label else ''
        return f'<div class="{cls("wf-progress")}"{A}><div class="wf-progress-fill" style="width:{pct:.1f}%"></div>{lbl_html}</div>'
    if role == 'avatar':
        # 只接 label(字母縮寫) + size(sm/md/lg)；禁 src/bg（守北極星② 視覺封印）
        if isinstance(val, dict):
            if 'src' in val or 'bg' in val:
                raise ValueError("avatar 禁 src/bg（違反視覺封印；只接 label + size）")
            label = val.get('label', '')
            size = val.get('size', 'md')
        else:
            label = str(val or '')
            size = 'md'
        if size not in ('sm', 'md', 'lg'):
            raise ValueError(f"avatar.size 只接 sm/md/lg（收到 {size!r}）")
        asset, fit = _bound_asset(xattr, 'image')
        inner = (f'<img src="{asset["uri"]}" alt="{esc(label)}" style="object-fit:{fit}">' if asset.get('uri') else _placeholder_html(label))
        return f'<div class="{cls(f"wf-avatar wf-avatar-{size}")}"{A}>{inner}</div>'
    if role == 'avatars':
        if not isinstance(val, dict) or not isinstance(val.get('items'), list):
            raise ValueError('avatars 需為 {items: [...], max: 3}；items 必須是 list')
        maximum = val.get('max', 3)
        if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1:
            raise ValueError('avatars.max 需為正整數（不含 +N 溢出標記）')
        items = val['items']
        # 全部成員都驗證，避免超過 max 的錯誤輸入被隱藏。
        rendered = [render_leaf({'avatar': item}, [], {}) for item in items]
        overflow = len(items) - maximum
        rest = render_leaf({'avatar': f'+{overflow}'}, [], {}) if overflow > 0 else ''
        return f'<div class="{cls("wf-avatars")}"{A}>{"".join(rendered[:maximum])}{rest}</div>'
    if role == 'map':
        w = {'is': '地圖', 'can': ['pan', 'zoom', 'markers']}
        if isinstance(val, dict):
            if _ckeys(val) - {'label', 'markers', 'can'}:
                raise ValueError('map 只接受 label / markers / can（示意，非真實地圖服務）')
            markers = val.get('markers', [])
            if not isinstance(markers, list) or any(not isinstance(x, str) for x in markers):
                raise ValueError('map.markers 必須是文字標記 list')
            w['is'] = val.get('label', '地圖')
            w['can'] = val.get('can', w['can'])
        else:
            w['is'], markers = val or '地圖', []
        if not isinstance(w['can'], list) or any(not isinstance(x, str) for x in w['can']):
            raise ValueError('map.can 必須是文字能力 list')
        w['body'] = [{'row': [{'text': '⊙ ' + m} for m in markers], 'name': '地圖標記'}]
        return render_widget({'widget': w}, xcls + ['wf-map'], xattr)
    # 走到這裡 = 節點沒任何已知 leaf role → 明確錯誤而非靜默 fallback
    keys = list(d.keys()) if isinstance(d, dict) else [type(d).__name__]
    raise ValueError(f"leaf 節點沒有已知 role key（收到 keys={keys}；合法：{sorted(LEAF_ROLES)}）")


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
    if 'items' in d and d['items'] is not None and not isinstance(d['items'], list):
        raise ValueError('items 必須是 list')
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
            f"{direction}: 不接受 dict 形式（收到 keys={[k for k in v if not str(k).startswith('__')]}）。\n"
            f"container 屬性一律 sibling — 方向 key `{direction}:` 只承載 items 短寫或 justify 短寫。\n"
            f"請改寫成：\n"
            f"  {direction}: [ item1, item2, ... ]     # items 短寫\n"
            f"  gap: sm                                 # 屬性放 sibling\n"
            f"  align: center"
        )
    return 'items', (d.get('items', []) or [])


def render_container(d, xcls, xattr, src=None, base=''):
    try:
        return _render_container(d, xcls, xattr, src, base)
    except ValueError as e:
        if isinstance(e, AuthorError) and e.source:
            raise
        raise AuthorError(str(e), d.get('__src', src), d.get('__path', base)) from e


def _render_container(d, xcls, xattr, src=None, base=''):
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
    # scroll（垂直）：true = 高度由父容器/grow 決定；sm/md/lg/xl = 語義級距上限
    if d.get('scroll'):
        cls.append('wf-scroll')
        sv = d['scroll']
        if sv is not True:
            if not (isinstance(sv, str) and sv in SCROLL_SCALE):
                raise ValueError(f"scroll: 只接 true 或 sm/md/lg/xl（收到 {sv!r}）")
            style.append('max-height:' + SCROLL_SCALE[sv])
        style.append('padding-right:' + GAP['md'])   # HTML 右 gutter = md；PNG 由 .wf-show-all 覆寫成 15px+md
        body += ('<div class="wf-sb" aria-hidden="true"><div class="wf-sb-btn">▲</div>'
                 '<div class="wf-sb-track"><div class="wf-sb-thumb"></div></div>'
                 '<div class="wf-sb-btn">▼</div></div>')
    # scroll-x（水平）：對稱處理
    if d.get('scroll-x'):
        cls.append('wf-scroll-x')
        svx = d['scroll-x']
        if svx is not True:
            if not (isinstance(svx, str) and svx in SCROLL_SCALE):
                raise ValueError(f"scroll-x: 只接 true 或 sm/md/lg/xl（收到 {svx!r}）")
            style.append('max-width:' + SCROLL_SCALE[svx])
    if isinstance(d.get('span'), int):
        style.append(f'grid-column:span {d["span"]}')
    st = f' style="{";".join(style)}"' if style else ''
    # collapsible：通用可收合區塊（原生 <details>/<summary>，零 JS 可展開；非 nav 專屬）。
    # `collapsible: <摘要文字>` 或 `collapsible: true` + `summary:`；`expanded: true` → open。
    if 'collapsible' in d:
        cv = d.get('collapsible')
        summ = d.get('summary') if d.get('summary') is not None else (cv if isinstance(cv, str) else '')
        openattr = ' open' if d.get('expanded') else ''
        inner = f'<div class="{" ".join(cls)}"{st}>{body}</div>'
        return (f'<details class="wf-collapsible"{openattr}{_attrs(xattr)}>'
                f'<summary class="wf-summary">{inline(summ)}</summary>{inner}</details>')
    return f'<div class="{" ".join(cls)}"{st}{_attrs(xattr)}>{body}</div>'


def render_widget(d, xcls, xattr, src=None, path=None):
    """示意複雜元件（table/chart/rich editor…的代表物）。屬 leaf 家族的巢狀 dict-form
    （同 button/image：屬性掛在 widget 底下，與節點 metadata name 分層）。自我聲明保真度：
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


def _canvas_link_path(points, shape):
    if not points:
        return ''
    scaled = [(x * 1000, y * 1000) for x, y in points]
    out = [f'M {scaled[0][0]:g} {scaled[0][1]:g}']
    for x2, y2 in scaled[1:]:
        x1, y1 = scaled[len(out) - 1]
        if shape == 'smooth':
            mid = (x1 + x2) / 2
            out.append(f'C {mid:g} {y1:g} {mid:g} {y2:g} {x2:g} {y2:g}')
        else:
            out.append(f'L {x2:g} {y2:g}')
    return ' '.join(out)


def render_canvas(canvas, xcls, xattr, src=None, path=None):
    """Canvas positions HTML kit components; only optional relationship links use SVG geometry."""
    base_spec = canvas['base']
    ratio = base_spec.get('ratio')
    root_attrs = dict(xattr)
    if ratio:
        root_attrs['style'] = ';'.join(x for x in (root_attrs.get('style'), f'aspect-ratio:{ratio}') if x)
    if base_spec.get('asset'):
        asset = _THEME_ASSETS.get(base_spec['asset'], {})
        if asset.get('uri'):
            base = f'<img class="wf-canvas-base wf-canvas-base-img" src="{asset["uri"]}" alt="">'
        else:
            base = f'<div class="wf-canvas-base wf-canvas-placeholder">▧ {esc(base_spec["asset"])}</div>'
    elif base_spec.get('grid'):
        base = '<div class="wf-canvas-base wf-canvas-base-grid"></div>'
    else:
        base = '<div class="wf-canvas-base wf-canvas-blank"></div>'
    points = canvas.get('link_points') or []
    link_spec = canvas.get('link_spec') or {}
    link_d = _canvas_link_path(points, link_spec.get('shape', 'straight'))
    arrow = ''
    marker_end = ''
    if link_spec.get('arrow') and len(points) > 1:
        arrow_id = 'wf-canvas-arrow-' + esc_attr(f'{src or "page"}-{path or "root"}')
        arrow = (f'<defs><marker id="{arrow_id}" viewBox="0 0 10 10" refX="9" refY="5" '
                 'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
                 '<path class="wf-canvas-link-arrow" d="M 0 0 L 10 5 L 0 10 z"></path></marker></defs>')
        marker_end = f' marker-end="url(#{arrow_id})"'
    link = (f'<svg class="wf-canvas-link-layer" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true">'
            f'{arrow}<path class="wf-canvas-link" d="{link_d}"{marker_end}></path></svg>') if len(points) > 1 else ''
    items = []
    for item in canvas['items']:
        mx, my = item['at']
        state = item['props'].get('state') if isinstance(item['props'], dict) else None
        attrs = {'style': f'left:{mx * 100:g}%;top:{my * 100:g}%'}
        if state:
            attrs['data-kit-state'] = state
        inner = render_item(item['node'], item.get('__src') or src, item.get('__path') or path)
        items.append(f'<div class="wf-canvas-item"{_attrs(attrs)}>{inner}</div>')
    cls = ['wf-node', 'wf-canvas'] + xcls
    return f'<div class="{" ".join(cls)}"{_attrs(root_attrs)}>{base}{link}{"".join(items)}</div>'


def _ckeys(it):
    """內容鍵（排除 __ 開頭的內部 metadata 蓋章）→ 供結構判斷不受干擾。"""
    return {k for k in it if not (isinstance(k, str) and k.startswith('__'))}


def _is_spacer(it):
    return it == 'spacer' or (isinstance(it, dict) and _ckeys(it) == {'spacer'})


def is_container(d):
    return any(k in d for k in CONTAINER_KEYS)


# --------------------------------------------------------------------------
# item 分派 + 共用包裝（name / to / spotlight / note / span / pin / modal / layer）
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
    try:
        return _render_item(it, src, path)
    except ValueError as e:
        if isinstance(e, AuthorError) and e.source:
            raise
        source = it.get('__src', src) if isinstance(it, dict) else src
        location = it.get('__path', path) if isinstance(it, dict) else path
        raise AuthorError(str(e), source, location) from e


def _render_item(it, src=None, path=None):
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
    embed_role = d.pop('__embed_role', None)  # P7 theme 綁定：embed 展開時蓋 component 名為 wf-role
    kit_role = d.pop('__kit_role', None)
    kit_state = d.pop('__kit_state', None)
    canvas = d.pop('__canvas', None)
    story_badge = d.pop('__story_badge', None)   # SAC：故事貼紙 / flow 序號徽章
    story_steps = d.pop('__story_steps', None)

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
    # section：帶語義的一段（SDUI 的 ViewLayout → Section → Component 中間層）。
    # 只是有名字的容器，不新增視覺能力；collapsed 時走既有的 details/summary（零 JS）。
    if 'section' in d:
        label = d.pop('section')
        body = d.pop('body', None)
        if not isinstance(body, list):
            raise ValueError(f'section `{label}` 需要 body: list')
        if d.pop('collapsed', False):
            d.setdefault('collapsible', label)
        d.setdefault('col', body)
        d.setdefault('name', label)
        d['__section'] = label

    if 'embed' in d:               # fail-fast：embed 應在 expand 階段展開完畢，走到這裡=結構走訪漏了
        raise ValueError(f"內部錯誤：embed 節點未展開（embed: {d.get('embed')!r}）——此節點藏在 expand 未走訪的結構裡，請回報")
    section_label = d.pop('__section', None)
    name = d.pop('name', None)
    if 'tone' in d:                # tone 已移除（2026-07-08）：色彩=保真度的函數
        raise ValueError(
            "tone 已移除：wireframe 全灰階。\n"
            "產品狀態色 → --mockup theme binding；評審聚焦 → spotlight/badge（標註面）；"
            "語義強調 → text.strong / status.strong")
    is_widget = 'widget' in d
    block_to = d.pop('to', None) if (is_container(d) or is_widget or canvas is not None) else None
    spot = d.pop('spotlight', None)
    note = d.pop('note', None)
    span = d.pop('span', None)
    # 截斷是規格不是樣式：「這段最多兩行」PM 講得出來、RD 需要知道、AI 照著做得出來。
    # 只開「幾行」與「要不要換行」，不開 overflow / text-overflow / white-space。
    max_lines = d.pop('max-lines', None)
    wrap = d.pop('wrap', None)
    if max_lines is not None:
        if not isinstance(max_lines, int) or isinstance(max_lines, bool) or max_lines < 1:
            raise ValueError(f'max-lines 需要 >= 1 的整數（收到 {max_lines!r}）')
    if wrap is not None and not isinstance(wrap, bool):
        raise ValueError(f'wrap 只接 true/false（收到 {wrap!r}）')
    if max_lines is not None and wrap is False:
        # 「最多兩行」與「不准換行」語義互斥。靜默吃掉一邊，正是 theme binding
        # 警示（#48）在抓的同一種錯：規格寫了，工具默默不做。
        raise ValueError('max-lines 與 wrap: false 互斥（一個要多行截斷、一個要單行不換行），請擇一')
    pin = d.pop('pin', None)          # 浮層：錨點(center/邊/角)
    modal = d.pop('modal', None)      # 浮層：擋後面(scrim + inert)
    layer = d.pop('layer', None)      # 浮層：z 帶(base/overlay/notify/top)
    ui_state = d.pop('ui-state', None)  # 顯示態（selected/disabled/hover/focus）→ data-ui-state（theme states 綁）
    if isinstance(ui_state, str) and ('{{' in ui_state or ui_state == ''):
        ui_state = None                 # 未解析的 {{參數}}/空值 = 未指定（component 參數化顯示態）
    if ui_state is not None and ui_state not in _UI_STATES:
        raise ValueError(f"ui-state 只接 {sorted(_UI_STATES)}（收到 {ui_state!r}）")

    xcls, xattr = [], {}
    if ui_state:
        xattr['data-ui-state'] = ui_state
    if _role:                          # 語義 token 展開後保留角色指紋：可區分/針對 styling、產物語義可讀（drawer ≠ 一般 box）
        xcls.append('wf-role-' + esc_attr(_role))
        xattr['data-wf-role'] = _role
    if embed_role:                     # P7 embed 指紋：component 名 → wf-role class（theme 可綁）
        xcls.append('wf-role-' + esc_attr(embed_role))
        xattr.setdefault('data-wf-role', embed_role)
    if kit_role:
        xcls.append('wf-role-' + esc_attr(kit_role))
        xattr['data-wf-role'] = kit_role
        if kit_state:
            xattr['data-kit-state'] = kit_state
    if name:
        xattr['data-name'] = name
    if section_label:                  # 段落語義：theme 可綁、debug 定位更好讀
        xattr['data-section'] = section_label
        xcls.append('wf-section')
    xattr.update(_dbg_attrs(esrc, epath))
    styles = []
    if isinstance(span, int):
        styles.append(f'grid-column:span {span}')
    if max_lines is not None or wrap is False:
        # 截斷是「這段文字」的規格，容器上沒有語義。而且 wf-clamp 帶 display:-webkit-box，
        # 套在容器上會直接蓋掉 flex 排版——版面壞掉卻不報錯，比不支援還糟。
        container = next((k for k in ('row', 'col', 'grid', 'items', 'section') if k in d), None)
        if container:
            raise ValueError(f'max-lines / wrap 只能用在文字節點，不能放在 `{container}` 容器上'
                             f'（要截斷容器裡的某段文字，請掛在那個文字節點上）')
    if max_lines is not None:
        xcls.append('wf-clamp')
        styles.append(f'--wf-max-lines:{max_lines}')
    elif wrap is False:
        xcls.append('wf-nowrap')
    if styles:
        xattr['style'] = ';'.join(styles)

    if canvas is not None:
        core = render_canvas(canvas, xcls, xattr, esrc, epath)
    elif is_widget:
        core = render_widget(d, xcls, xattr, esrc, epath)
    elif is_container(d):
        d.setdefault('span', span) if isinstance(span, int) else None
        core = render_container(d, xcls, xattr, esrc, epath)
    else:
        if d.pop('grow', None):    # R2-2：leaf 也可 grow（等寬按鈕列等；與 track/container 同一語義）
            xcls.append('wf-grow')
        core = render_leaf(d, xcls, xattr)

    if block_to:
        # Grid span belongs on the direct child link in either navigation mode.
        sp = f' style="grid-column:span {span}"' if isinstance(span, int) else ''
        core = _wire_link(block_to, core, "wf-blocklink-a wf-link", sp)
    if story_badge or story_steps:    # SAC：貼紙 + flow 序號徽章（絕對定位疊在元素角落；story 的 to 掛徽章上）
        extra = ''
        if story_badge:
            extra += f'<span class="wf-story-badge">{inline(str(story_badge))}</span>'
        for st in (story_steps or []):
            lbl = esc(st['label'])
            if st.get('to'):
                extra += _wire_link(st["to"], lbl, "wf-story-step wf-story-step-pin")
            else:
                extra += f'<span class="wf-story-step wf-story-step-pin">{lbl}</span>'
        disp = 'block' if (is_widget or is_container(d)) else 'inline-block'
        core = f'<span class="wf-story-anchor" style="display:{disp}">{core}{extra}</span>'
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
            # ref 錨點包 wrapper（同 wf-story-anchor 前例）：sup 絕對定位、不進 flow——
            # 否則在 grid 容器裡 sup 會自己佔一格，把後面的 cell 全推位
            core = (f'<span class="wf-refwrap">{core}'
                    f'<sup class="wf-ref" data-ref="{esc(ref)}">[{esc(ref)}]</sup></span>')
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
# 模板：extends + slots / embed + with + as:placeholder（資料結構合併，非字串替換）
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


def _kit_use(it):
    """Return (type, spec) for one kit invocation, rejecting ambiguous nodes."""
    hits = [k for k in _ckeys(it) if k in _KIT_COMPONENTS]
    if len(hits) > 1:
        raise ValueError(f'一個節點只能使用一個 kit 型別（收到 {sorted(hits)}）')
    return (hits[0], _KIT_COMPONENTS[hits[0]]) if hits else (None, None)


def _kit_params(name, spec, raw):
    if spec.get('of') == 'canvas':
        if not isinstance(raw, dict):
            raise ValueError(f'kit canvas `{name}` 需要 {{items: [...]}}')
        clean = {k: v for k, v in raw.items() if k not in ('__src', '__path')}
        # nodes / edges 是正名（與 React Flow、D3、圖論一致）；items / link 為相容別名
        if 'nodes' in clean:
            clean['items'] = clean.pop('nodes')
        if 'edges' in clean:
            clean['link'] = clean.pop('edges')
        unknown = set(clean) - {'items', 'link'}
        if unknown or not isinstance(clean.get('items'), list):
            raise ValueError(f'kit canvas `{name}` 只接 nodes: list 與 edges: list（多餘：{sorted(unknown)}）')
        anchors = spec['base'].get('anchors') or {}
        item_name = spec['item']['use']
        item_spec = _KIT_COMPONENTS[item_name]
        items = []
        for i, original in enumerate(clean['items']):
            if not isinstance(original, dict):
                raise ValueError(f'kit canvas `{name}` items[{i}] 必須是 dict')
            item = {k: v for k, v in original.items() if k not in ('__src', '__path')}
            item_id = item.pop('id', None)
            if item_id is not None and (isinstance(item_id, bool) or not isinstance(item_id, (str, int, float))):
                raise ValueError(f'kit canvas `{name}` items[{i}].id 必須是字串或數字')
            anchor_key = item_id or next((v for k, v in item.items()
                                          if k not in ('at', 'state', 'to') and isinstance(v, str) and v in anchors), None)
            point = item.pop('at', anchors.get(anchor_key))
            if point is None:
                raise ValueError(f'kit canvas `{name}` items[{i}] 缺 at，kit anchors 也找不到對應值')
            try:
                point = _canvas_point(point)
            except AuthorError as e:
                raise ValueError(f'kit canvas `{name}` items[{i}].at：{e}') from e
            target = item.pop('to', None)
            state = item.get('state')
            if state is not None and state not in (spec.get('states') or []):
                raise ValueError(f'kit canvas `{name}` items[{i}].state `{state}` 不合法（合法：{spec.get("states") or []}）')
            item_props = _kit_params(item_name, item_spec, item)
            identities = {item_id} if item_id is not None else set()
            if isinstance(item_props, dict):
                identities.update(v for k, v in item_props.items() if k != 'state' and isinstance(v, (str, int, float)))
            items.append({'id': item_id, 'at': point, 'to': target, 'props': item_props,
                          'identities': identities, '__src': original.get('__src'), '__path': original.get('__path')})
        link_refs = clean.get('link')
        if link_refs is not None:
            if spec.get('link') is None:
                raise ValueError(f'kit canvas `{name}` 未宣告 link，畫面不可提供 link')
            if not isinstance(link_refs, list) or len(link_refs) < 2:
                raise ValueError(f'kit canvas `{name}` link 必須是至少兩個 item 識別值的 list')
            link_items = []
            for ref in link_refs:
                if isinstance(ref, bool) or not isinstance(ref, (str, int, float)):
                    raise ValueError(f'kit canvas `{name}` link 識別值必須是字串或數字（收到 {ref!r}）')
                matches = [item for item in items if ref in item['identities']]
                if len(matches) != 1:
                    raise ValueError(f'kit canvas `{name}` link 值 {ref!r} 必須恰好對應一個 item（找到 {len(matches)} 個）')
                link_items.append(matches[0])
        else:
            link_items = []
        return {'items': items, 'link_items': link_items}
    props = spec.get('props') or []
    if isinstance(raw, dict):
        raw = {k: v for k, v in raw.items() if k not in ('__src', '__path')}
    if spec.get('of') and not props:
        # Leaf specializations inherit the leaf's own closed value shape.
        if isinstance(raw, dict):
            state = raw.get('state')
            if state is not None and state not in (spec.get('states') or []):
                raise ValueError(f'kit 型別 `{name}` state `{state}` 不合法（合法：{spec.get("states") or []}）')
        return dict(raw) if isinstance(raw, dict) else raw
    if not isinstance(raw, dict):
        raise ValueError(f'kit 型別 `{name}` 需要 props dict（合法：{props}）')
    state = raw.get('state')
    allowed_states = spec.get('states') or []
    if state is not None and state not in allowed_states:
        raise ValueError(f'kit 型別 `{name}` state `{state}` 不合法（合法：{allowed_states}）')
    unknown = set(raw) - set(props) - {'state'}
    missing = set(props) - set(raw)
    if unknown or missing:
        parts = []
        if unknown: parts.append(f'未知 props {sorted(unknown)}')
        if missing: parts.append(f'缺少 props {sorted(missing)}')
        raise ValueError(f'kit 型別 `{name}`：' + '；'.join(parts) + f'（合法：{props}）')
    return dict(raw)


def _expand_kit_node(it, basedir, ctx, stack):
    name, spec = _kit_use(it)
    if not name:
        return None
    marker = f'kit:{name}'
    if marker in stack:
        raise ValueError(f'kit 元件循環引用：{" -> ".join(stack + (marker,))}')
    params = _kit_params(name, spec, it[name])
    if spec.get('of') == 'canvas':
        ann_keys = {'name', 'to', 'note', 'spotlight', 'span', 'grow', 'pin', 'modal', 'layer', 'ui-state',
                'max-lines', 'wrap'}
        unknown = _ckeys(it) - {name} - ann_keys
        if unknown:
            raise ValueError(f'kit 型別 `{name}` 不接受 sibling {sorted(unknown)}')
        ann = {k: it[k] for k in ann_keys if k in it}
        for internal in ('__src', '__path'):
            if internal in it:
                ann[internal] = it[internal]
        item_name = spec['item']['use']
        items = []
        for item in params['items']:
            node = {item_name: item['props']}
            if item['to'] is not None:
                node['to'] = item['to']
            if item.get('__src'):
                node['__src'] = item['__src']
            if item.get('__path'):
                node['__path'] = item['__path']
            expanded = _expand_kit_node(node, basedir, ctx, stack + (marker,))
            items.append({**item, 'node': expanded[0]})
        point_by_identity = {id(original): rendered['at'] for original, rendered in zip(params['items'], items)}
        canvas = {'base': spec['base'], 'items': items, 'link_spec': spec.get('link'),
                  'link_points': [point_by_identity[id(item)] for item in params['link_items']]}
        return [{**ann, '__kit_role': name, '__canvas': canvas}]
    kit_state = params.pop('state', None) if isinstance(params, dict) else None
    ann_keys = {'name', 'to', 'note', 'spotlight', 'span', 'grow', 'pin', 'modal', 'layer', 'ui-state',
                'max-lines', 'wrap'}
    unknown = _ckeys(it) - {name} - ann_keys
    if unknown:
        raise ValueError(f'kit 型別 `{name}` 不接受 sibling {sorted(unknown)}')
    ann = {k: it[k] for k in ann_keys if k in it}
    for internal in ('__src', '__path'):
        if internal in it: ann[internal] = it[internal]
    if spec.get('of'):
        value = params
        return [{**ann, '__kit_role': name, '__kit_state': kit_state, spec['of']: value}]
    content = expand(_subst(spec['content'], params), basedir, ctx, stack + (marker,))
    return [{**ann, '__kit_role': name, '__kit_state': kit_state, 'col': content, 'gap': 'none'}]


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
    """一次 pass：when: 過濾（依 ctx）+ embed 展開（as 決定變體/繼承 ctx）。ctx = {stage, state}。"""
    out = []
    for it in items:
        if isinstance(it, dict) and 'when' in it:      # 節點級 when：不命中當前路由 → 整塊移除
            if not _match(it['when'], ctx):
                continue
            it = {k: v for k, v in it.items() if k != 'when'}
        kit_nodes = _expand_kit_node(it, basedir, ctx, stack) if isinstance(it, dict) else None
        if kit_nodes is not None:
            out.extend(kit_nodes)
        elif isinstance(it, dict) and 'embed' in it:
            name = it['embed']
            params = it.get('with', {}) or {}
            as_ = it.get('as')
            try:
                path = _resolve(name, basedir)
            except ValueError as e:
                raise AuthorError(str(e), it.get('__src'), it.get('__path')) from e
            if path in stack:
                raise ValueError(f"模板循環引用：{' -> '.join(stack + (path,))}")
            comp = _read_yaml(path)
            _stamp(comp, str(name) if _DEBUG else path)
            cdir = os.path.dirname(path) or '.'
            if as_ == 'placeholder':                    # 降階佔位（ctx 無意義）
                content, child_ctx = (comp.get('placeholder') or _auto_stub(name)), ctx
            else:
                content = comp if isinstance(comp, list) else (comp.get('content') or comp.get('body') or [])
                # as:{stage,state} → pin 該變體；省略 → 繼承當前頁面路由 ctx
                child_ctx = as_ if isinstance(as_, dict) else ctx
            content = _subst(content, params)
            content = expand(content, cdir, child_ctx, stack + (path,))
            ann = {k: it[k] for k in ('note', 'spotlight', 'name', 'to', 'ui-state') if k in it}
            # P7 theme 綁定：embed 的 component 名帶為 wf-role 指紋（讓 theme 可 target）
            # basename 從 `components/tx-item` 或 `layouts/mobile` 取 `tx-item` / `mobile`
            embed_role = os.path.basename(str(name))
            if ann or _theme_active():
                for pk in ('__src', '__path'):
                    if pk in it:
                        ann[pk] = it[pk]
                # 用 `col: content` 的 transparent 容器承載；`__embed_role` 讓 render_item 加 wf-role class。
                # 不寫死 padding（col 預設本就無內距）→ theme components.<role> 的 padding 才能生效
                # （inline style 會蓋過 class；padding 交給 theme，gap 仍歸零避免多項間距）。
                out.append({**ann, '__embed_role': embed_role,
                            'col': content, 'gap': 'none'})
            else:
                out.extend(content)
        elif isinstance(it, dict):
            nd = dict(it)
            for k in _child_list_keys(nd):
                nd[k] = expand(nd[k], basedir, ctx, stack)
            if isinstance(nd.get('widget'), dict) and 'body' in nd['widget']:
                wb = nd['widget']['body']
                if isinstance(wb, list):
                    wb = expand(wb, basedir, ctx, stack)
                elif isinstance(wb, dict):
                    wb = expand([wb], basedir, ctx, stack)[0]
                nd['widget'] = {**nd['widget'], 'body': wb}
            out.append(nd)
        else:
            out.append(it)
    return out


def _child_list_keys(nd):
    """節點的結構子清單 keys：方向 key / items + overlay 角色內容（dialog/toast/專案自定…）。
    expand / _fill_slots 都要走訪這些，否則藏在 overlay 角色裡的 embed / slot 靜默失效。"""
    # grid 的 list 是欄寬 tracks，不是子節點。
    keys = [k for k in ('items', 'row', 'col') if isinstance(nd.get(k), list)]
    keys += [k for k in _overlay_tokens() if isinstance(nd.get(k), list)]
    if 'section' in nd and isinstance(nd.get('body'), list):   # section 的 body 也是結構子清單
        keys.append('body')
    return keys


def _fill_slots(items, slots):
    out = []
    for it in items:
        if isinstance(it, dict) and (set(it) - {'__src', '__path'}) == {'slot'}:
            out.extend(slots.get(it['slot'], []))
        elif isinstance(it, dict):
            nd = dict(it)
            for k in _child_list_keys(nd):
                nd[k] = _fill_slots(nd[k], slots)
            if isinstance(nd.get('widget'), dict) and 'body' in nd['widget']:
                wb = nd['widget']['body']
                if isinstance(wb, list):
                    wb = _fill_slots(wb, slots)
                elif isinstance(wb, dict):
                    wb = _fill_slots([wb], slots)[0]
                nd['widget'] = {**nd['widget'], 'body': wb}
            out.append(nd)
        else:
            out.append(it)
    return out


def _viewport_of(node):
    return node.get('viewport')


def resolve_body(doc, provider, basedir, ctx):
    """回傳 (body_items, viewport)。slots/body 來自 provider（無路由=doc；有路由=該路由項）。
    extends/with/viewport 屬 doc 級（各路由共用）。ctx = 當前路由 {stage, state}，供 when: 過濾與元件繼承。"""
    viewport = _viewport_of(doc)
    if 'extends' in doc:
        try:
            lpath = _resolve(doc['extends'], basedir)
        except ValueError as e:
            raise AuthorError(str(e), doc.get('__src'), 'extends') from e
        layout = _read_yaml(lpath)
        _stamp(layout, str(doc['extends']) if _DEBUG else lpath)
        params = {**(doc.get('with') or {}), **(provider.get('with') or {})}
        # layout 的 embed 相對 layout；頁面 slots 的 embed 相對頁面。
        lbody = expand(_subst(layout.get('body', []), params), os.path.dirname(lpath) or '.', ctx)
        slots = {k: expand(_subst(v, params), basedir, ctx)
                 for k, v in (provider.get('slots', {}) or {}).items()}
        body = _fill_slots(lbody, slots)
        viewport = viewport or _viewport_of(layout)
    else:
        body = provider.get('body', [])
        body = expand(body, basedir, ctx)
    if _STORY:                          # SAC：story 注入在 expand 之後（name 錨點需 embed 展開後才存在）
        body = _apply_story(body, _STORY)
    return body, viewport


# --------------------------------------------------------------------------
# 組頁
# --------------------------------------------------------------------------
def _viewport_wh(c):
    """解析 viewport 尺寸字串：'390x844' / '1100x' / 'x800' / '390' → (w, h)。"""
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
    body, viewport = resolve_body(doc, provider, basedir, ctx or {})
    w, h = _viewport_wh(viewport)
    inner = render_container({'col': body}, [], {}, _PAGE_BASE, '')   # 頂層 flex-col（避免 inline span 並排）
    bar = _stagebar(all_labels, cur_label) if all_labels else ''
    return _story_header_html() + bar + inner + build_gutter(), w, h, bool(_NOTES)


def _width_css(sel, w, h, has_notes):
    """畫布寬高覆蓋（可指定選擇器 → bundle 各 section 各自套）。"""
    main_w, o = w or 780, ''
    if has_notes:
        # gutter 站在畫布外側（note 是標註面 meta，不屬 viewport 內容）：root 維持 viewport 寬，
        # 便利貼掛在 root 右外緣、body 預留空間（截圖 clip 由 render.sh 取 root∪gutter 聯集）
        g, gap = 240, 24
        o += (f'{sel}{{width:{main_w}px;position:relative;}}'
              f'{sel} .wf-gutter{{left:calc(100% + {gap}px);right:auto;width:{g}px;}}'
              f'body{{padding-right:{g + gap}px;}}')
    elif w:
        o += f'{sel}{{width:{w}px;}}'
    if h:
        o += (f'{sel}{{height:{h}px;min-height:{h}px;display:flex;flex-direction:column;}}'
              f'{sel}>.wf-node{{flex:1 1 auto;min-height:0;}}'
              f'{sel}>.wf-node>.wf-node,{sel}>.wf-node>.wf-hr{{flex-shrink:0;}}'
              f'{sel}>.wf-node>.wf-scroll{{flex-shrink:1;}}'
              f'{sel}.wf-show-all{{height:auto;}}'
              f'{sel}.wf-show-all .wf-scroll{{flex-shrink:0;overflow:visible;}}')
    return o


def _compile_page(doc, provider, basedir, ctx=None, cur_label=None, all_labels=None, debug=False):
    _REVEAL_RULES.clear()
    content, w, h, notes = _render_page(doc, provider, basedir, ctx, cur_label, all_labels)
    # theme CSS 疊最後 → 覆蓋 base/clean/tokens；只在 --mockup 載了 theme 才有內容
    css = _hoist_imports(_BASE_CSS + CSS_EXTRA + (DEBUG_CSS if debug else '')
                         + _style_css() + _tokens_css() + _theme_css()
                         + _width_css('.wf-root', w, h, notes) + _reveal_css())
    # debug：root 也帶 data-wf-src/path → viewport 本身可被點選標記（畫布級建議：背景/尺寸/整體）
    page_attr = (f' data-wf-page="{esc(_PAGE_BASE)}" data-wf-src="{esc(_PAGE_BASE)}"'
                 f' data-wf-path="viewport"') if debug else ''
    head = (f'<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>{css}</style>'
            f'</head><body><div class="wf-root"{page_attr}>')
    tail = ('<script>' + DEBUG_JS + '</script>' if debug else '') + '</body></html>'
    result = head + content + '</div>' + tail
    _warn_asset_output(result)
    return result


BUNDLE_CSS = r"""
body.wf-bundle{display:flex;margin:0;align-items:flex-start;font-family:var(--wf-font,'Sarasa Mono TC','Courier New',monospace);}
#wf-nav{position:sticky;top:0;flex:0 0 190px;max-height:100vh;overflow:auto;padding:12px;
  border-right:1px solid #e5e7eb;font:12px/1.5 sans-serif;background:#fafafa;}
#wf-nav .wf-navgrp{margin-bottom:6px;}
#wf-nav b{display:block;color:#6b7280;margin:8px 0 2px;font-size:11px;letter-spacing:.03em;}
#wf-nav :is(a,label){display:block;padding:2px 8px;color:#0f766e;text-decoration:none;border-radius:var(--wf-radius);}
#wf-nav :is(a,label):hover{background:#f0fdfa;}
#wf-main{flex:1;min-width:0;padding:24px;overflow:auto;}
.wf-pg{display:none;}
body:not(.wf-radio-nav) .wf-pg:target{display:block;}
body:not(.wf-radio-nav):not(:has(.wf-pg:target)) .wf-pg:first-of-type{display:block;}
/* Keep native radios focusable while hiding their visual boxes. */
.wf-r{position:absolute;width:1px;height:1px;padding:0;margin:0;overflow:hidden;
  clip-path:inset(50%);white-space:nowrap;border:0;}
.wf-radio-link{cursor:pointer;}
.wf-radio-link:has(> .wf-r:focus-visible){outline:2px solid #0f766e;outline-offset:2px;}
@media(max-width:860px){
  body.wf-bundle{flex-direction:column;padding:0;}
  #wf-nav{width:100%;flex:0 0 auto;display:flex;gap:12px;max-height:none;
    overflow-x:auto;border-right:0;border-bottom:1px solid #e5e7eb;z-index:10;}
  #wf-nav .wf-navgroup,#wf-nav .wf-navgrp{flex:0 0 auto;margin-bottom:0;}
  #wf-nav .wf-navgroup{display:flex;gap:12px;align-items:center;}
  #wf-nav h2{font-size:12px;margin:0;white-space:nowrap;}
  #wf-nav .wf-navgrp{display:flex;gap:4px;align-items:center;}
  #wf-nav b{margin:0 4px 0 0;white-space:nowrap;}
  #wf-nav :is(a,label){white-space:nowrap;padding:6px 8px;}
  #wf-main{width:100%;padding:12px;}
}
"""


def bundle(files, debug=False, title='prototype', style=None, story=None, standalone=False):
    """把多個 .wf.yaml 併成單一可點擊 prototype.html（左 nav + :target 切頁 + 頁內 to: 錨點）。
    standalone=True → radio/label 切頁，不改 URL；debug=True → 疊評審回饋層。
    story=<path> → 附加故事疊加版 section（📖 nav 分組）。"""
    global _PAGE_BASE, _DEBUG, _BUNDLE, _STYLE, _STORY, _RADIO_NAV, _LINK_SERIAL
    _DEBUG, _BUNDLE, _STYLE = debug, True, style
    _RADIO_NAV, _LINK_SERIAL = standalone, 0
    if files:
        _ensure_kit(os.path.dirname(files[0]) or '.')
    _load_tokens(os.path.dirname(files[0]) if files else '.')   # 專案 semantic token（探首檔所在夾）
    secs, navs, overrides, pids = [], [], [], []
    nav_groups = {}
    for f in files:
        src = open(f).read()
        basedir = os.path.dirname(f) or '.'
        base = re.sub(r'\.(wf\.)?ya?ml$', '', os.path.basename(f))
        _PAGE_BASE = base
        doc = _yaml_load(src, f)
        _stamp(doc, base if debug else f)
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
            root_attr = f' data-wf-src="{esc(base)}" data-wf-path="viewport"' if debug else ''
            secs.append(f'<section class="wf-pg" id="{pid}"><div class="wf-root"{root_attr}>{content}</div></section>')
            overrides.append(_width_css(f'#{pid} .wf-root', w, h, notes))
            navitems.append(_wire_link('', esc(label if routes else doc.get("title", base)),
                                       attrs=f' id="nav-{pid}"', page_id=pid, nav=True,
                                       checked=len(pids) == 1))
        entry = f'<div class="wf-navgrp"><b>{esc(doc.get("title", base))}</b>{"".join(navitems)}</div>'
        nav_groups.setdefault(doc.get('group') or '', []).append(entry)
    # 群組按首次出現，組內維持輸入順序。未指定 meta 時保留原本 nav 結構。
    for group, entries in nav_groups.items():
        if group:
            navs.append(f'<div class="wf-navgroup"><h2>{esc(group)}</h2>{"".join(entries)}</div>')
        else:
            navs.extend(entries)
    if story:
        # SAC (b)：story nav 分組 = 綁定頁疊加版一頁；flow 跳轉連 bundle 內 clean 頁（錨點改寫沿用）
        sdata = _load_story(story)
        spath, sfrag = _resolve_story_page(sdata['page'], os.path.dirname(story) or '.')
        sbase = re.sub(r'\.(wf\.)?ya?ml$', '', os.path.basename(spath))
        sdoc = _read_yaml(spath)
        _stamp(sdoc, sbase)                       # story 路徑 target 比對需要蓋章
        _PAGE_BASE = sbase
        sid = _slug(sdata['story'])
        sroutes = sdoc.get('routes')
        sprov, sctx = sdoc, None
        if sroutes:
            sentries = [_route_entry(r) for r in sroutes]
            want = sfrag or ''
            hit = next((e for e in sentries if (e[0] == want) or (not want and e[3] is None)), sentries[0])
            _, sprov, _, sctx = hit
        _STORY = sdata
        try:
            content, w, h, notes = _render_page(sdoc, sprov, os.path.dirname(spath) or '.', sctx)
        finally:
            _STORY = None
        pid = f'wf-pg-story-{sid}'
        pids.append(pid)
        root_attr = f' data-wf-src="{esc(sbase)}" data-wf-path="viewport"' if debug else ''
        secs.append(f'<section class="wf-pg" id="{pid}"><div class="wf-root"{root_attr}>{content}</div></section>')
        overrides.append(_width_css(f'#{pid} .wf-root', w, h, notes))
        navs.append(f'<div class="wf-navgrp"><b>📖 {esc(str(sdata["story"]))}</b>'
                    + _wire_link('', esc(sbase) + '（故事版）', attrs=f' id="nav-{pid}"',
                                 page_id=pid, nav=True, checked=len(pids) == 1) + '</div>')
    # nav 當前頁高亮（零 JS：:has(section:target) → 對應 nav 連結；無 target 則第一頁）
    if pids:
        if standalone:
            for p in pids:
                overrides.append(f'body:has(.wf-r[value="{p}"]:checked) #{p}' + '{display:block;}')
            sel = ','.join(f'body:has(.wf-r[value="{p}"]:checked) #nav-{p}' for p in pids)
        else:
            sel = ','.join(f'body:has(#{p}:target) #nav-{p}' for p in pids)
            sel += f',body:not(:has(.wf-pg:target)) #nav-{pids[0]}'
        overrides.append(sel + '{background:#0f766e;color:#fff;font-weight:600;}')
    css = _hoist_imports(_BASE_CSS + CSS_EXTRA + BUNDLE_CSS + (DEBUG_CSS if debug else '')
                         + _style_css() + _tokens_css() + _theme_css() + ''.join(overrides) + _reveal_css())
    tail = ('<script>' + DEBUG_JS + '</script>' if debug else '') + '</body></html>'
    result = (f'<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)}</title>'
            f'<style>{css}</style></head><body class="wf-bundle{" wf-radio-nav" if standalone else ""}">'
            f'<nav id="wf-nav">{"".join(navs)}</nav><div id="wf-main">{"".join(secs)}</div>{tail}')
    _warn_asset_output(result)
    return result


def compile_all(src, basedir='.', base='', debug=False, style=None, source_name=None):
    """回傳 [(rid, html), ...]。無 routes → [('', html)]；有 routes → 每路由一份可定址輸出。
    debug=True → 注入 --debug 評審回饋層（JS+localStorage）；否則維持零 <script>。"""
    global _PAGE_BASE, _DEBUG, _STYLE, _BUNDLE
    _PAGE_BASE, _DEBUG, _STYLE = base, debug, style
    _BUNDLE = False
    _ensure_kit(basedir)
    _load_tokens(basedir)              # 探測選配的 wf.tokens.yaml（專案 semantic token）
    source = source_name or (os.path.join(basedir, base + '.wf.yaml') if base else '<input>')
    doc = _yaml_load(src, source)
    if not isinstance(doc, dict):
        raise AuthorError('頁面頂層必須是 dict', source, '<root>')
    _stamp(doc, base if debug or _STORY else source)
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


# --------------------------------------------------------------------------
# P0.7 Schema Validation & Fail-Fast — lint 子命令實作
# --------------------------------------------------------------------------
# 合法值集（DISCUSSION 定案；scroll/gap/padding/align/justify/pin/layer/spotlight.kind）
_ENUMS = {
    'gap': {'none', 'sm', 'md', 'lg', 'xl'},
    'padding': {'none', 'sm', 'md', 'lg', 'xl'},
    'align': {'top', 'bottom', 'start', 'end', 'center', 'baseline', 'stretch'},
    'justify': {'start', 'end', 'center', 'between', 'around'},
    'scroll':   {True} | set(SCROLL_SCALE),
    'scroll-x': {True} | set(SCROLL_SCALE),
    'pin': {'center', 'left', 'right', 'top', 'bottom',
            'top-left', 'top-right', 'bottom-left', 'bottom-right',
            'top-center', 'bottom-center', 'left-center', 'right-center'},
    'layer': {'base', 'overlay', 'notify', 'top'},
    'ui-state': _UI_STATES,
}
# 已知頂層 grammar keys（未知 → warn typo）
# body: 主要內容區；content/placeholder: component 檔頂層（完整/降階佔位）
_GRAMMAR_KEYS = {'viewport', 'title', 'group', 'body', 'extends', 'with', 'slots', 'routes',
                 'content', 'placeholder'}
# 已知 container 屬性 keys（sibling 掛在容器 dict 上）
_CONTAINER_ATTRS = {'row', 'col', 'grid', 'items', 'section', 'collapsed', 'box', 'gap', 'padding',
                    'justify', 'align', 'span', 'grow', 'scroll', 'scroll-x',
                    'name', 'to', 'note', 'spotlight', 'pin', 'modal', 'layer',
                    'embed', 'with', 'slot', 'as', 'when', 'ui-state',
                    'collapsible', 'expanded', 'summary'}
_DIRECTION_KEYS = {'row', 'col', 'grid'}
_STRUCTURE_UNITS = {'page', 'layout', 'component', 'widget'}
_OVERLAY_SUGARS = {'dialog', 'drawer', 'sheet', 'toast', 'loading'}


def _levenshtein(a, b):
    """簡短 Levenshtein 距離；供未知 key 建議 typo 修正。"""
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _suggest_key(unknown, known_set, max_dist=2):
    cands = sorted(((_levenshtein(unknown, k), k) for k in known_set), key=lambda x: x[0])
    return cands[0][1] if cands and cands[0][0] <= max_dist else None


class _Diag:
    def __init__(self, source=None, shared=None, allow_parameters=False):
        self.source = source
        self.allow_parameters = allow_parameters
        self.errors = shared.errors if shared else []
        self.warnings = shared.warnings if shared else []
        self.placeholders = shared.placeholders if shared else {}

    def error(self, path, msg, hint=None):
        self.errors.append((self.source, path, msg, hint))

    def warn(self, path, msg, hint=None):
        self.warnings.append((self.source, path, msg, hint))

    def dump(self, file_label, out=None):
        out = out or sys.stderr
        for level, items in (('error', self.errors), ('warn', self.warnings)):
            for source, path, msg, hint in items:
                head = f'\033[1;31m{level}\033[0m' if level == 'error' else f'\033[1;33m{level}\033[0m'
                print(f'{head}: {source or file_label}', file=out)
                print(f'  → path: {path or "<root>"}', file=out)
                first, *rest = msg.splitlines()
                print(f'  → {first}', file=out)
                for line in rest:
                    print(f'    {line}', file=out)
                if hint:
                    for line in hint.split('\n'):
                        print(f'  hint: {line}', file=out)


def _walk_lint(node, path, diag, basedir='.', stack=()):
    """遞迴 lint YAML 結構樹。只走結構節點，跳過 leaf value dict / with / as / meta 值。"""
    if isinstance(node, list):
        for i, item in enumerate(node):
            _walk_lint(item, f'{path}[{i}]', diag, basedir, stack)
        return
    if isinstance(node, str):
        if diag.allow_parameters and _has_parameter(node):
            return
        try:
            render_string(node)
        except ValueError as e:
            diag.error(path, str(e))
        return
    if not isinstance(node, dict):
        return

    keys = set(node.keys()) - {'__src', '__path'}
    kit_hits = keys & set(_KIT_COMPONENTS)
    if len(kit_hits) > 1:
        diag.error(path, f'一個節點只能使用一個 kit 型別（收到 {sorted(kit_hits)}）')
        return
    if kit_hits:
        name = next(iter(kit_hits))
        try:
            spec = _KIT_COMPONENTS[name]
            params = _kit_params(name, spec, node[name])
            if spec.get('of') and spec.get('of') != 'canvas':
                value = dict(params) if isinstance(params, dict) else params
                if isinstance(value, dict): value.pop('state', None)
                render_leaf({spec['of']: value}, [], {})
            allowed = {name, 'name', 'to', 'note', 'spotlight', 'span', 'grow', 'pin', 'modal', 'layer', 'ui-state',
                       'max-lines', 'wrap'}
            extra = keys - allowed
            if extra:
                raise ValueError(f'kit 型別 `{name}` 不接受 sibling {sorted(extra)}')
        except ValueError as e:
            diag.error(path, str(e))
        return

    # 判斷節點類型
    has_direction = keys & _DIRECTION_KEYS
    has_leaf_role = keys & set(LEAF_ROLES)
    is_widget = 'widget' in keys
    is_slot_marker = 'slot' in keys and len(keys - {'slot', 'name'}) == 0
    is_spacer = keys == {'spacer'}          # 與 render `_is_spacer` 同判定（恰一個 spacer key）
    is_embed = 'embed' in keys
    # overlay 角色 = 內建 sugar ∪ 專案 token（wf.tokens.yaml overlay: 自定角色，與 render _overlay_tokens 同源）
    has_overlay_sugar = keys & (_OVERLAY_SUGARS | set(_TOKENS.get('overlay') or {}))
    if _STRICT_KIT and not diag.allow_parameters:
        if has_leaf_role or is_widget:
            diag.error(path, 'strict-kit：畫面 leaf/widget 必須包成 kit 型別')
        if node.get('box'):
            diag.error(path, 'strict-kit：不允許裸露 box；請抽成 kit 組合元件')
    for key, expected in (('with', dict), ('slots', dict)):
        if key in node and not isinstance(node[key], expected):
            diag.error(f'{path}.{key}', f'{key} 必須是 {expected.__name__}')

    # 共用 render 的 items 判定；grid list 是 tracks，與 items 並存合法。
    if has_direction or 'items' in keys:
        direction = 'grid' if 'grid' in keys else 'row' if 'row' in keys else 'col'
        try:
            _items_of(node, direction)
        except ValueError as e:
            diag.error(path, str(e))

    if is_embed:
        if not isinstance(node.get('embed'), str):
            diag.error(path + '.embed', 'embed 必須是模板路徑字串')
        else:
            _lint_reference(node['embed'], basedir, diag, path + '.embed', stack, node.get('with'))

    # 葉子與未知 role 沿用 render 的驗證（包含 avatar / progress / icon）。
    is_route_context = 'when' in keys and keys <= {'when', 'with', 'default'}
    if not (has_direction or keys & {'items', 'body', 'slots', 'default'} or is_route_context or is_widget or is_embed or has_overlay_sugar or is_slot_marker or is_spacer):
        if not (diag.allow_parameters and _has_parameter({k: node[k] for k in has_leaf_role})):
            try:
                render_leaf(node, [], {})
            except ValueError as e:
                if _KIT_COMPONENTS and not has_leaf_role:
                    candidates = keys - _CONTAINER_ATTRS - _GRAMMAR_KEYS
                    diag.error(path, f'kit 未定義型別 {sorted(candidates)}；此 kit 可用：{sorted(_KIT_COMPONENTS)}')
                else:
                    diag.error(path, str(e))

    # 3. container 恰一個 direction key
    if len(has_direction) > 1:
        diag.error(path, f"container 恰能有一個方向 key（收到 {sorted(has_direction)}）",
                   "row / col / grid 三者互斥，請只留一個")

    # 4. leaf 恰一個 role key
    if len(has_leaf_role) > 1:
        diag.error(path, f"leaf 節點只能有一個 role key（收到 {sorted(has_leaf_role)}）",
                   "一個節點只承載一個 leaf role；分開成多個 items")

    # 5. container 屬性混掛 leaf
    if has_leaf_role and has_direction:
        diag.warn(path, "同時存在 leaf role 與 container direction key",
                  "leaf 節點不掛 row/col/grid；請拆成父容器 + 子 leaf")

    # 6. scale 值域檢查（sibling 屬性）
    for key, allowed in _ENUMS.items():
        if key in node:
            v = node[key]
            if diag.allow_parameters and _has_parameter(v):
                continue
            if not isinstance(v, (str, int, float, bool, type(None))) or v not in allowed:
                proj = (_TOKENS.get(key) or {})
                if str(v) in proj:
                    continue
                sugg = _suggest_key(str(v), {str(x) for x in allowed})
                hint = f"合法值：{sorted(str(x) for x in allowed)}"
                if sugg and sugg != str(v):
                    hint = f"是不是「{sugg}」？\n" + hint
                diag.error(f'{path}.{key}', f"未知 {key} 值 `{v}`", hint)

    # 6b. tone 已移除（2026-07-08 定案：色彩=保真度的函數）
    if 'tone' in node:
        diag.error(f'{path}.tone', "tone 已移除：wireframe 全灰階",
                   "產品狀態色 → --mockup theme binding；評審聚焦 → spotlight/badge（標註面）；\n"
                   "語義強調 → text.strong / status.strong")

    # 7. spotlight.kind 檢查（scalar 或 dict）
    if 'spotlight' in node:
        sp = node['spotlight']
        kind = sp.get('kind') if isinstance(sp, dict) else sp
        if kind and kind not in ('focus', 'new', 'change', 'click'):
            diag.error(f'{path}.spotlight', f"未知 spotlight.kind `{kind}`",
                       "合法值：focus / new / change / click")

    # 8. 未知 key typo 檢查。葉子節點也要查：leaf 的「值」有各自 shape，但掛在它旁邊的
    #    sibling 屬性（grow / pin / name / to …）沒有人管，打錯字會靜默消失在產出裡。
    #    widget / overlay sugar / slot / embed / spacer 的 key 集合由各自路徑驗證，跳過。
    if not is_widget and not has_overlay_sugar and not is_slot_marker and not is_embed and not is_spacer:
        known = _CONTAINER_ATTRS | _GRAMMAR_KEYS | set(LEAF_ROLES) | _OVERLAY_SUGARS | {'widget', 'is', 'can'}
        for k in keys:
            if k in known or k in ('placeholder', 'content', 'default'):
                continue
            if k == 'spacer':   # spacer 混掛其他 key → render 不會當 spacer（_is_spacer 要求恰一 key）
                diag.warn(f'{path}.{k}', "spacer 不與其他 key 同節點（會失去 spacer 語義）",
                          "推擠用獨立 item `- spacer`；區塊自己填滿改用 `grow: true`")
                continue
            sugg = _suggest_key(k, known)
            hint = f"是不是「{sugg}」？" if sugg else "未在已知詞彙集（見 `wfyaml.py list --ring 0`）"
            diag.warn(f'{path}.{k}', f"未知 key `{k}`", hint)

    # 9. 遞迴子節點：只走結構性 key，跳過 leaf value / meta / 參數
    # 結構性 key：direction values (list) / items / body / overlay 角色內容 / slots values / routes items
    _RECURSE_INTO = {'row', 'col', 'items', 'body'}   # grid list 不是結構樹
    for k, v in node.items():
        if k in ('__src', '__path'):
            continue
        sub_path = f'{path}.{k}' if path else k
        if k in _RECURSE_INTO or k in _overlay_tokens():
            if isinstance(v, list):
                for i, item in enumerate(v):
                    _walk_lint(item, f'{sub_path}[{i}]', diag, basedir, stack)
            elif isinstance(v, dict):
                _walk_lint(v, sub_path, diag, basedir, stack)
        elif k == 'widget' and isinstance(v, dict) and 'body' in v:
            _walk_lint(v['body'], f'{sub_path}.body', diag, basedir, stack)
        elif k == 'slots':
            # slots 的 key 是使用者定義的 slot 名（不是 vocab key）→ 只走各 slot 的內容
            if isinstance(v, dict):
                for slot_name, slot_content in v.items():
                    _walk_lint(slot_content, f'{sub_path}.{slot_name}', diag, basedir, stack)
        elif k == 'routes':
            # routes 內每項是路由 dict，含 slots/body
            if isinstance(v, list):
                for i, r in enumerate(v):
                    _walk_lint(r, f'{sub_path}[{i}]', diag, basedir, stack)
        # 其他 key（with/as/note/spotlight/button 等的 dict value）不遞迴 lint —— 屬 value 空間


def _lint_file(path):
    """對單一檔案跑 lint。回傳 (error_count, warning_count)。story 檔走 story schema 驗證。"""
    _ensure_kit(os.path.dirname(path) or '.')
    try:
        doc = _read_yaml(path)
    except AuthorError as e:
        diag = _Diag(path)
        diag.error(e.path or '<root>', str(e))
        diag.dump(path)
        return 1, 0
    if isinstance(doc, dict) and 'story' in doc:
        # SAC story 檔：schema + page 存在性（target 命中驗證在 render 時 fail-fast）
        try:
            sdata = _load_story(path)
            _resolve_story_page(sdata['page'], os.path.dirname(path) or '.')
            return 0, 0
        except ValueError as e:
            print(f'\033[1;31merror\033[0m: {path}', file=sys.stderr)
            print(f'  → {e}', file=sys.stderr)
            return 1, 0
    template = (isinstance(doc, list) or (isinstance(doc, dict) and bool(set(doc) & {'content', 'placeholder'}))
                or bool(set(os.path.normpath(path).split(os.sep)) & {'components', 'layouts', 'partials'}))
    diag = _Diag(path, allow_parameters=template)
    _lint_document(doc, path, diag, (os.path.realpath(path),))
    if diag.errors or diag.warnings:
        diag.dump(path)
    for source, count in diag.placeholders.items():
        if count:
            print(f'info: {source} → {count} 個未定值（按來源出現次數，不影響 exit code）', file=sys.stderr)
    return len(diag.errors), len(diag.warnings)


def _has_parameter(value):
    if isinstance(value, str):
        return '{{' in value
    if isinstance(value, list):
        return any(_has_parameter(x) for x in value)
    if isinstance(value, dict):
        return any(_has_parameter(x) for x in value.values())
    return False


def _lint_reference(name, basedir, diag, path, stack, params=None):
    global _TOKENS
    try:
        target = _resolve(name, basedir)
    except ValueError as e:
        diag.error(path, str(e), '檢查檔名或 components/ layouts/ partials/ 相對路徑')
        return
    canonical = os.path.realpath(target)
    if canonical in stack:
        diag.error(path, '模板循環引用：' + ' -> '.join(stack + (canonical,)))
        return
    previous_tokens = _TOKENS
    child = _Diag(target, diag)
    try:
        doc = _read_yaml(target)
        bindings = params if isinstance(params, dict) else {}
        _lint_document(_subst(doc, bindings), target, child, stack + (canonical,), load_tokens=False)
        diag.placeholders[target] = _declared_placeholders(doc)
    except AuthorError as e:
        child.error(e.path or '<root>', str(e))
    finally:
        _TOKENS = previous_tokens


def _declared_placeholders(node):
    """來源文字的出現次數，不計 metadata、URL、when 或重複展開的引用。"""
    if isinstance(node, str):
        return _placeholder_count(node)
    if isinstance(node, list):
        return sum(_declared_placeholders(x) for x in node)
    if not isinstance(node, dict):
        return 0
    count = 0
    fields = {'text', 'label', 'placeholder', 'value'}
    for role in LEAF_ROLES:
        if role not in node or role in ('icon', 'divider'):
            continue
        value = node[role]
        if isinstance(value, str):
            count += _placeholder_count(value)
        elif isinstance(value, dict):
            count += sum(_placeholder_count(value.get(k)) for k in fields)
            if role in ('tabs', 'avatars') and isinstance(value.get('items', []), list):
                for item in value.get('items', []):
                    count += _placeholder_count(item.get('label') if isinstance(item, dict) else item)
            if role == 'map' and isinstance(value.get('markers', []), list):
                count += sum(_placeholder_count(x) for x in value.get('markers', []))
    for key in ('body', 'content', 'placeholder', 'routes', 'items', 'row', 'col', *_overlay_tokens()):
        if key in node:
            count += _declared_placeholders(node[key])
    if isinstance(node.get('slots'), dict):
        for value in node['slots'].values():
            count += _declared_placeholders(value)
    widget = node.get('widget')
    if isinstance(widget, dict):
        count += _placeholder_count(widget.get('is')) + _declared_placeholders(widget.get('body'))
    elif isinstance(widget, str):
        count += _placeholder_count(widget)
    if isinstance(node.get('with'), dict):
        count += sum(_placeholder_count(v) for v in node['with'].values())
    return count


def _structure_occurrences(node, source, path='<root>', out=None):
    """Collect content-agnostic container shapes for cross-page extraction hints."""
    out = out if out is not None else {}
    if isinstance(node, list):
        for i, child in enumerate(node):
            _structure_occurrences(child, source, f'{path}[{i}]', out)
        return out
    if not isinstance(node, dict):
        return out
    keys = _ckeys(node)
    if keys & set(_KIT_COMPONENTS):
        return out
    direction = next((x for x in ('row', 'col', 'grid') if x in keys), None)
    if direction or node.get('box'):
        child_key = direction if direction in ('row', 'col') and isinstance(node.get(direction), list) else 'items'
        children = node.get(child_key) if isinstance(node.get(child_key), list) else []
        child_roles = []
        for child in children:
            if isinstance(child, dict):
                role = next((r for r in LEAF_ROLES if r in child), None)
                nested = next((d for d in ('row', 'col', 'grid') if d in child), None)
                child_roles.append(role or nested or ('box' if child.get('box') else 'node'))
            else:
                child_roles.append('text')
        signature = json.dumps([direction or 'col', bool(node.get('box')), child_roles], ensure_ascii=False)
        if node.get('box') or len(children) >= 2:
            out.setdefault(signature, []).append((source, path))
    for key in ('body', 'content', 'items', 'row', 'col'):
        if key in node:
            _structure_occurrences(node[key], source, f'{path}.{key}', out)
    return out


def _duplicate_structure_info(files):
    found = {}
    for source in files:
        try:
            _structure_occurrences(_read_yaml(source), source, '<root>', found)
        except ValueError:
            continue
    for occurrences in found.values():
        pages = sorted({src for src, _ in occurrences})
        if len(pages) >= 3:
            sample = ', '.join(f'{os.path.basename(src)}:{path}' for src, path in occurrences[:3])
            print(f'info: 重複結構出現在 {len(pages)} 個畫面（{sample}）— 這看起來是一個元件，考慮抽進 kit', file=sys.stderr)


def _lint_document(doc, path, diag, stack, load_tokens=True):
    basedir = os.path.dirname(path) or '.'
    if load_tokens:
        _load_tokens(basedir)
    if isinstance(doc, list):
        _walk_lint(doc, '<root>', diag, os.path.dirname(path) or '.', stack)
        diag.placeholders[path] = _declared_placeholders(doc)
        return
    if not isinstance(doc, dict):
        diag.error('<root>', '頂層必須是 dict（component 亦可使用 list）')
        return
    for key, expected in (('with', dict), ('slots', dict), ('routes', list)):
        if key in doc and not isinstance(doc[key], expected):
            diag.error(key, f'{key} 必須是 {expected.__name__}')
    # 頂層 keys：允許 grammar keys；未知頂層 → warn
    top_keys = set(doc.keys()) if isinstance(doc, dict) else set()
    for k in top_keys:
        if k in _GRAMMAR_KEYS or k in _STRUCTURE_UNITS:
            continue
        sugg = _suggest_key(k, _GRAMMAR_KEYS)
        hint = f"是不是「{sugg}」？" if sugg else f"合法頂層 key：{sorted(_GRAMMAR_KEYS)}"
        diag.warn('<root>', f"未知頂層 key `{k}`", hint)
    # 走 body / slots / routes（slots 的 key 是使用者 slot 名，只走各值；routes 每項是路由 dict）
    for key in ('title', 'group'):
        if key in doc and not isinstance(doc[key], str):
            diag.error(key, f'{key} metadata 必須是字串')
    if 'viewport' in doc:
        try:
            _viewport_wh(doc['viewport'])
        except ValueError as e:
            diag.error('viewport', str(e), '使用 390x844 / 1100x / x800')
    if 'extends' in doc:
        if isinstance(doc['extends'], str):
            common = doc.get('with') if isinstance(doc.get('with'), dict) else {}
            providers = doc.get('routes') if isinstance(doc.get('routes'), list) and doc['routes'] else [doc]
            for provider in providers:
                extra = provider.get('with') if isinstance(provider, dict) and isinstance(provider.get('with'), dict) else {}
                _lint_reference(doc['extends'], basedir, diag, 'extends', stack, {**common, **extra})
        else:
            diag.error('extends', 'extends 必須是模板路徑字串')
    if isinstance(doc, dict):
        for key in ('body', 'content', 'placeholder'):
            if key in doc:
                if not isinstance(doc[key], list):
                    diag.error(key, f'{key} 必須是 list')
                else:
                    _walk_lint(doc[key], key, diag, basedir, stack)
        if 'slots' in doc and isinstance(doc['slots'], dict):
            for slot_name, slot_content in doc['slots'].items():
                if not isinstance(slot_content, list):
                    diag.error(f'slots.{slot_name}', 'slot 內容必須是 list')
                else:
                    _walk_lint(slot_content, f'slots.{slot_name}', diag, basedir, stack)
        if 'routes' in doc and isinstance(doc['routes'], list):
            for i, r in enumerate(doc['routes']):
                if not isinstance(r, dict):
                    diag.error(f'routes[{i}]', 'route 必須是 dict')
                else:
                    _walk_lint(r, f'routes[{i}]', diag, basedir, stack)
    diag.placeholders[path] = _declared_placeholders(doc)


def main():
    global _STRICT_KIT
    debug = '--debug' in sys.argv
    standalone = '--bundle-standalone' in sys.argv
    do_bundle = '--bundle' in sys.argv or standalone
    # 檢查 list 子命令前，先定義（inline，短小）
    def _list_vocab(basedir, ring=None):
        """列 Ring 0（結構原語）+ Ring 1（專案 semantic token）。給 AI/作者一眼看完詞彙。"""
        want_r0 = ring in (None, '0')
        want_r1 = ring in (None, '1')
        if want_r0:
            print("═══ Ring 0：結構原語（恆定，AI 必背）═══")
            print("\n[Grammar 關鍵字]")
            print("  viewport / title / group / body / extends / embed / with / slot / slots / as / routes / default / when / items")
            print("\n[結構單元類型]")
            print("  page / layout / component / widget")
            print("\n[Container]")
            print("  row / col / grid / box / widget")
            print("  Overlay 家族 sugar: dialog / drawer / sheet / toast / loading")
            print("\n[Leaf 元件]")
            print("  文字：text / text.title / text.heading / text.label / text.strong / text.hint")
            print("  表單：input / select / button / checkbox / radio")
            print("  狀態：status / status.muted / status.strong / status.badge / alert")
            print("  其他：icon / divider / image / tabs / link / progress / avatar / avatars / map")
            print("\n[Widget 屬性]")
            print("  is / can")
            print("\n[空間屬性]")
            print("  justify / align / gap / padding / span / grow / scroll / scroll-x / spacer")
            print("  寬度 token：grow / fit / w-N/M / <N>% / w-N（逃生門）")
            print("\n[動線/連結]")
            print("  to / link")
            print("\n[浮層原語]")
            print("  pin / modal / layer")
            print("\n[標註面] (Layer 2)")
            print("  note / spotlight")
            print("\n[Meta（隱形）]")
            print("  name / viewport")
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

    # ---- lint 子命令：P0.7 Schema Validation + Fail-Fast ----
    if len(sys.argv) >= 2 and sys.argv[1] == 'lint':
        kit_path = _argval('--kit')
        _STRICT_KIT = '--strict-kit' in sys.argv
        if kit_path:
            _load_kit(kit_path, explicit=True)
        theme = _argval('--mockup')
        files = [a for a in sys.argv[2:] if not a.startswith('-') and a not in (theme, kit_path)]
        if not kit_path and files:
            _ensure_kit(os.path.dirname(files[0]) or '.')
        if _STRICT_KIT and not _KIT_COMPONENTS:
            raise ValueError('--strict-kit 需要 --kit <file> 或專案 kit/components.yaml')
        if '--mockup' in sys.argv and not theme:
            raise ValueError('--mockup 需要 theme 檔')
        if theme:
            _load_theme(theme)
        if not files:
            print("usage: wfyaml.py lint [--kit <kit.yaml> [--strict-kit]] [--mockup <theme.yaml>] <file.wf.yaml> [...]", file=sys.stderr)
            sys.exit(1)
        total_err, total_warn = 0, len(_THEME_ASSET_WARNINGS) + len(_THEME_WARNINGS)
        for f in files:
            e, w = _lint_file(f)
            total_err += e
            total_warn += w
        _duplicate_structure_info(files)
        print(f"\n═══ 總計：{total_err} error / {total_warn} warning ═══", file=sys.stderr)
        sys.exit(2 if total_err else (1 if total_warn else 0))

    out_path = _argval('-o')
    style = _argval('--style')
    mockup_theme = _argval('--mockup')
    kit_path = _argval('--kit')
    _STRICT_KIT = '--strict-kit' in sys.argv
    story_path = _argval('--story')
    skip = {'--debug', '--bundle', '--bundle-standalone', '--no-lint', '--strict-kit', '-o', out_path,
            '--style', style, '--mockup', mockup_theme, '--kit', kit_path, '--story', story_path}
    args = [a for a in sys.argv[1:] if a not in skip]
    if not args and not story_path:
        print("usage: wfyaml.py [--debug] [--bundle|--bundle-standalone [-o out.html]] [--kit <kit.yaml> [--strict-kit]] [--style <name>] [--mockup <theme.yaml>] [--story <x.story.yaml>] <file.wf.yaml> [...]", file=sys.stderr)
        print("       wfyaml.py --story <x.story.yaml>                 # SAC 單獨生成：底圖+故事疊加 → <id>.story.html", file=sys.stderr)
        print("       wfyaml.py list [--ring 0|1] [--basedir <dir>]   # introspection", file=sys.stderr)
        print("       wfyaml.py lint [--kit <kit.yaml> [--strict-kit]] <file.wf.yaml> [...] # schema validation", file=sys.stderr)
        sys.exit(1)
    # --style sketch × --mockup 互斥（低保真美學 vs 高保真綁定，語義衝突）
    if style == 'sketch' and mockup_theme:
        print("[error] --style sketch 與 --mockup 互斥（低保真美學 vs 高保真綁定）", file=sys.stderr)
        sys.exit(1)
    if kit_path:
        _load_kit(kit_path, explicit=True)
    elif args:
        _ensure_kit(os.path.dirname(args[0]) or '.')
    if _STRICT_KIT and not _KIT_COMPONENTS:
        raise ValueError('--strict-kit 需要 --kit <file> 或專案 kit/components.yaml')
    # 有 --mockup <theme> → 載入 theme（kit 必須先載入，theme 不得自行新增型別）
    if mockup_theme:
        _load_theme(mockup_theme)

    # ---- SAC (a) 單獨生成模式：--story 無 --bundle ----
    if story_path and not do_bundle:
        if args:
            print("[error] --story 單獨生成模式不需頁面參數（story 檔已宣告 page:）；"
                  "要渲進 bundle 請加 --bundle", file=sys.stderr)
            sys.exit(1)
        global _STORY
        sdata = _load_story(story_path)
        sdir = os.path.dirname(story_path) or '.'
        spath, sfrag = _resolve_story_page(sdata['page'], sdir)
        if '--no-lint' not in sys.argv:
            e, _w = _lint_file(spath)          # 底圖照樣過 lint gate
            if e:
                print(f"\n═══ lint 阻斷 story render：底圖 {spath} 共 {e} error ═══", file=sys.stderr)
                sys.exit(2)
        src = open(spath).read()
        sbase = re.sub(r'\.(wf\.)?ya?ml$', '', os.path.basename(spath))
        _STORY = sdata
        try:
            results = compile_all(src, os.path.dirname(spath) or '.', sbase, debug=debug, style=style)
        finally:
            _STORY = None
        # 有 routes 時取 fragment 指定的路由；無 fragment 取第一份（default）
        want = (sfrag or '')
        html_out = next((h for rid, h in results if rid == want), results[0][1])
        out = os.path.join(sdir, f'{_slug(sdata["story"])}.story.html')
        open(out, 'w').write(html_out)
        print(f"  story: {out}（底圖 {os.path.basename(spath)} + 故事疊加）")
        return
    # ---- render 前 lint gate（--no-lint 可略過；errors 早失敗、warnings 印但續）----
    skip_lint = '--no-lint' in sys.argv
    if not skip_lint:
        total_err = 0
        for f in args:
            e, _w = _lint_file(f)
            total_err += e
        if total_err:
            print(f"\n═══ lint 阻斷 render：共 {total_err} error（用 --no-lint 略過）═══", file=sys.stderr)
            sys.exit(2)
    if do_bundle:
        out = out_path or os.path.join(os.path.dirname(args[0]) or '.',
                                       'prototype' + ('.debug' if debug else '') + '.html')
        open(out, 'w').write(bundle(args, debug=debug, style=style, story=story_path, standalone=standalone))
        extra = (' [style:' + style + ']' if style else '') + (f' [story:{os.path.basename(story_path)}]' if story_path else '')
        print(f"  bundled: {out} ({len(args)} 檔){extra}")
        return
    for path in args:
        src = open(path).read()
        basedir = os.path.dirname(path) or '.'
        stem = re.sub(r'\.(wf\.)?ya?ml$', '', path)
        base = os.path.basename(stem)
        suffix = '.debug.html' if debug else '.html'
        for rid, htmlout in compile_all(src, basedir, base, debug=debug, style=style, source_name=path):
            out = stem + (('.' + rid) if rid else '') + suffix
            open(out, 'w').write(htmlout)
            print(f"  compiled: {out}")


def console():
    """console_scripts 進入點：沿用 cli_entry 的作者錯誤格式（不噴 traceback）。"""
    return cli_entry(main)


if __name__ == '__main__':
    cli_entry(main)
