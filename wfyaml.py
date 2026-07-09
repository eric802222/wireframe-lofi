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

_THEME = {}          # 當前載入的 theme bindings（綁 name/role 的專案微調）；空 dict = wireframe 模式
_THEME_BASE = {}     # theme 的 base: 模式開關（chrome/link-marker/scrollbar）
_THEME_TOKENS = {}   # theme 的 tokens: 值層（Tier-1 design token，FE 可直接接手）
_THEME_PRESETS = {}  # tokens.preset: composite token（一組 property，被 apply: 組合，不渲染）
_THEME_COMPONENTS = {}  # components: 元件皮（Tier-2，base/variants/states + apply）
_THEME_FLATVALS = {}    # {"family.name": 已展開純值}（供 {ref} 的 var() fallback）


def _theme_active():
    return bool(_THEME or _THEME_BASE or _THEME_TOKENS or _THEME_COMPONENTS)


# bindings 綁「內建元件 role」→ selector（同一套詞彙換元件皮，不另發明語彙）。
_THEME_ELEMENT_SELECTORS = {
    'button':        '.wf-btn',
    'button-link':   'a.wf-btn.wf-link',    # 帶 to: 的按鈕（主要動作/導航）
    'input':         '.wf-input',
    'select':        '.wf-select',
    'status':        '.wf-tag',
    'status.muted':  '.wf-tag-muted',
    'status.strong': '.wf-tag-strong',
    'status.badge':  '.wf-badge',
    'box':           '.wf-box',
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
    'height', 'min-height', 'max-height', 'width', 'min-width', 'max-width',
    'display', 'align-items', 'justify-content', 'transition', 'cursor',
    'outline', 'outline-offset', 'fill',
}

_THEME_BASE_KEYS = {'chrome', 'link-marker', 'scrollbar'}
_THEME_CHROME = {
    'flat': '',
    'card': ('body{background:var(--wf-page-bg,#eef0f3);}'
             '.wf-root{background:var(--wf-surface,#ffffff);border:none;'
             'box-shadow:var(--wf-shadow-lg,0 4px 24px rgba(0,0,0,.10));}'),
}


def _slug(s):
    return re.sub(r'[^a-z0-9-]', '-', str(s).lower())


def _theme_var_name(family, name):
    """token 路徑 → CSS var 名。舊家族/名走既有 var（相容），其餘走 `--wf-<family>-<name>`。"""
    fam = _THEME_TOKEN_VARS.get(family)
    if fam and str(name) in fam:
        return fam[str(name)]
    return f'--wf-{_slug(family)}-{_slug(name)}'


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
            raise ValueError(f"theme 參照未定義 token {{{key}}}{hint}")
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
            decls.append(f'{_theme_var_name(family, name)}:{_resolve_value(_token_scalar(entry))}')
    css = [f':root{{{";".join(decls)}}}'] if decls else []
    # 全頁背景：定義了 page 背景 token（--wf-page-bg）就套到 body，與 chrome 模式解耦
    # （chrome: flat 也能有全頁底；chrome: card 另覆寫 root 為白卡浮於其上）。
    if any(d.startswith('--wf-page-bg:') for d in decls):
        css.append('body{background:var(--wf-page-bg);}')
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
    if sname == 'hover':
        return sel + ':hover'
    if sname == 'focus':
        return sel + ':focus'
    return f'{sel}[data-ui-state="{_slug(sname)}"]'


def _theme_components_css(components):
    """components: 元件皮 → CSS（base / variants / states，含 apply preset）。"""
    lines = []
    for cname, spec in components.items():
        if not isinstance(spec, dict):
            raise ValueError(f"theme.components.{cname} 必須是 dict（收到 {type(spec).__name__}）")
        sel = _THEME_COMPONENT_SELECTORS.get(cname) or f'.wf-role-{_slug(cname)}'
        base = {k: v for k, v in spec.items() if k not in ('variants', 'states')}
        if base:
            props = _expand_props(base, f'components.{cname}')
            if props:
                lines.append(f'{sel}{{{_props_str(props)}}}')
        for vname, vrules in (spec.get('variants') or {}).items():
            props = _expand_props(vrules, f'components.{cname}.variants.{vname}')
            lines.append(f'{sel}[data-variant="{_slug(vname)}"]{{{_props_str(props)}}}')
        for sname, srules in (spec.get('states') or {}).items():
            props = _expand_props(srules, f'components.{cname}.states.{sname}')
            lines.append(f'{_state_selector(sel, sname)}{{{_props_str(props)}}}')
    return '\n'.join(lines)


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
            use_enum = k in _THEME_BINDABLE and not (isinstance(v, str) and '{' in v)
            if use_enum:
                try:
                    css_prop, resolver = _THEME_BINDABLE[k]
                    decls.append(f'{css_prop}:{resolver(v)}')
                    continue
                except ValueError:
                    pass   # 非 enum 值 → 落到 raw property 路徑
            if k not in _CSS_PROP_ALLOW:
                sugg = _suggest_key(k, _CSS_PROP_ALLOW | set(_THEME_BINDABLE))
                hint = f"（是不是「{sugg}」？）" if sugg else ""
                raise ValueError(f"theme.bindings.{role}.{k}: 未知綁定屬性/CSS property{hint}")
            decls.append(f'{k}:{_resolve_value(v)}')
        r = esc_attr(role)
        # 優先序：語義身份（role/name）selector 三疊拉高 specificity，贏過元件皮。
        sel = _THEME_ELEMENT_SELECTORS.get(role) or \
            (f'.wf-role-{r}.wf-role-{r}.wf-role-{r}, '
             f'[data-name="{r}"][data-name="{r}"][data-name="{r}"]')
        lines.append(f'{sel}{{{";".join(decls)}}}')
    return '\n'.join(lines)


def _load_theme(path):
    """載入 theme YAML；驗證 tokens / preset / base / components / bindings（fail-fast）。"""
    global _THEME, _THEME_BASE, _THEME_TOKENS, _THEME_PRESETS, _THEME_COMPONENTS, _THEME_FLATVALS
    if not path:
        _THEME, _THEME_BASE, _THEME_TOKENS = {}, {}, {}
        _THEME_PRESETS, _THEME_COMPONENTS, _THEME_FLATVALS = {}, {}, {}
        return {}
    if not os.path.exists(path):
        raise ValueError(f"--mockup 找不到 theme 檔：{path}")
    data = yaml.safe_load(open(path, encoding='utf-8')) or {}
    unknown = set(data.keys()) - {'tokens', 'base', 'bindings', 'components'}
    if unknown:
        raise ValueError(f"theme 檔頂層 key 只允許 tokens/base/bindings/components（收到多餘: {sorted(unknown)}）")
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
    # 全部先編一次觸發驗證（property 白名單 / enum / ref）
    _theme_tokens_css(tokens)
    _theme_components_css(components)
    _theme_bindings_css(bindings)
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
              'progress', 'avatar']
TEXT_CLASS = {'text': 'wf-label', 'text.title': 'wf-h wf-h1', 'text.heading': 'wf-h wf-h2',
              'text.label': 'wf-label wf-fieldlabel', 'text.strong': 'wf-b', 'text.hint': 'wf-hint'}
_UI_STATES = {'selected', 'disabled', 'hover', 'focus', 'active'}   # 顯示態（→ data-ui-state；theme states 綁）

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
    if role == 'status.badge':
        return f'<label class="{cls("wf-badge")}"{A}>{inline(val)}</label>'
    if role in ('status', 'status.muted', 'status.strong'):
        lvl = {'status.muted': ' wf-tag-muted', 'status.strong': ' wf-tag-strong'}.get(role, '')
        return f'<span class="{cls("wf-tag" + lvl)}"{A}>{inline(val)}</span>'
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
        return f'<div class="{cls(f"wf-avatar wf-avatar-{size}")}"{A}>{esc(label)}</div>'
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
    if 'embed' in d:               # fail-fast：embed 應在 expand 階段展開完畢，走到這裡=結構走訪漏了
        raise ValueError(f"內部錯誤：embed 節點未展開（embed: {d.get('embed')!r}）——此節點藏在 expand 未走訪的結構裡，請回報")
    name = d.pop('name', None)
    if 'tone' in d:                # tone 已移除（2026-07-08）：色彩=保真度的函數
        raise ValueError(
            "tone 已移除：wireframe 全灰階。\n"
            "產品狀態色 → --mockup theme binding；評審聚焦 → spotlight/badge（標註面）；"
            "語義強調 → text.strong / status.strong")
    is_widget = 'widget' in d
    block_to = d.pop('to', None) if (is_container(d) or is_widget) else None
    spot = d.pop('spotlight', None)
    note = d.pop('note', None)
    span = d.pop('span', None)
    pin = d.pop('pin', None)          # 浮層：錨點(center/邊/角)
    modal = d.pop('modal', None)      # 浮層：擋後面(scrim + inert)
    layer = d.pop('layer', None)      # 浮層：z 帶(base/overlay/notify/top)
    ui_state = d.pop('ui-state', None)  # 顯示態（selected/disabled/hover/focus）→ data-ui-state（theme states 綁）
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
        if d.pop('grow', None):    # R2-2：leaf 也可 grow（等寬按鈕列等；與 track/container 同一語義）
            xcls.append('wf-grow')
        core = render_leaf(d, xcls, xattr)

    if block_to:
        core = f'<a href="{_href(block_to)}" class="wf-blocklink-a wf-link">{core}</a>'
    if story_badge or story_steps:    # SAC：貼紙 + flow 序號徽章（絕對定位疊在元素角落；story 的 to 掛徽章上）
        extra = ''
        if story_badge:
            extra += f'<span class="wf-story-badge">{inline(str(story_badge))}</span>'
        for st in (story_steps or []):
            lbl = esc(st['label'])
            if st.get('to'):
                extra += f'<a class="wf-story-step wf-story-step-pin" href="{_href(st["to"])}">{lbl}</a>'
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
        if isinstance(it, dict) and 'embed' in it:
            name = it['embed']
            params = it.get('with', {}) or {}
            as_ = it.get('as')
            path = _resolve(name, basedir)
            if path in stack:
                raise ValueError(f"模板循環引用：{' -> '.join(stack + (path,))}")
            comp = yaml.safe_load(open(path)) or {}
            if _DEBUG:
                _stamp(comp, str(name))            # component 節點來源 = 其 embed 名
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
                # 用 `col: content` 的 transparent 容器承載；`__embed_role` 讓 render_item 加 wf-role class
                out.append({**ann, '__embed_role': embed_role,
                            'col': content, 'gap': 'none', 'padding': 'none'})
            else:
                out.extend(content)
        elif isinstance(it, dict):
            nd = dict(it)
            for k in _child_list_keys(nd):
                nd[k] = expand(nd[k], basedir, ctx, stack)
            if isinstance(nd.get('widget'), dict) and isinstance(nd['widget'].get('body'), list):
                nd['widget'] = {**nd['widget'], 'body': expand(nd['widget']['body'], basedir, ctx, stack)}
            out.append(nd)
        else:
            out.append(it)
    return out


def _child_list_keys(nd):
    """節點的結構子清單 keys：方向 key / items + overlay 角色內容（dialog/toast/專案自定…）。
    expand / _fill_slots 都要走訪這些，否則藏在 overlay 角色裡的 embed / slot 靜默失效。"""
    keys = [k for k in ('items', 'row', 'col', 'grid') if isinstance(nd.get(k), list)]
    keys += [k for k in _overlay_tokens() if isinstance(nd.get(k), list)]
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
            if isinstance(nd.get('widget'), dict) and isinstance(nd['widget'].get('body'), list):
                nd['widget'] = {**nd['widget'], 'body': _fill_slots(nd['widget']['body'], slots)}
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
        layout = yaml.safe_load(open(_resolve(doc['extends'], basedir))) or {}
        if _DEBUG:
            _stamp(layout, str(doc['extends']))    # layout 節點來源 = 其引用名
        params = {**(doc.get('with') or {}), **(provider.get('with') or {})}
        body = _fill_slots(layout.get('body', []), provider.get('slots', {}) or {})
        body = _subst(body, params)
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
    if h:   # 有畫布高度：root 成 flex-col、body 撐滿該高 → spacer/justify 能把內容(如 footer)推到底
        o += f'{sel}{{min-height:{h}px;display:flex;flex-direction:column;}}{sel}>.wf-node{{flex:1 1 auto;min-height:0;}}'
    return o


def _compile_page(doc, provider, basedir, ctx=None, cur_label=None, all_labels=None, debug=False):
    content, w, h, notes = _render_page(doc, provider, basedir, ctx, cur_label, all_labels)
    # theme CSS 疊最後 → 覆蓋 base/clean/tokens；只在 --mockup 載了 theme 才有內容
    css = _hoist_imports(_BASE_CSS + CSS_EXTRA + (DEBUG_CSS if debug else '')
                         + _style_css() + _tokens_css() + _theme_css()
                         + _width_css('.wf-root', w, h, notes))
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


def bundle(files, debug=False, title='prototype', style=None, story=None):
    """把多個 .wf.yaml 併成單一可點擊 prototype.html（左 nav + :target 切頁 + 頁內 to: 錨點）。
    debug=True → 疊評審回饋層；story=<path> → 附加故事疊加版 section（📖 nav 分組）。"""
    global _PAGE_BASE, _DEBUG, _BUNDLE, _STYLE, _STORY
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
    if story:
        # SAC (b)：story nav 分組 = 綁定頁疊加版一頁；flow 跳轉連 bundle 內 clean 頁（錨點改寫沿用）
        sdata = _load_story(story)
        spath, sfrag = _resolve_story_page(sdata['page'], os.path.dirname(story) or '.')
        sbase = re.sub(r'\.(wf\.)?ya?ml$', '', os.path.basename(spath))
        sdoc = yaml.safe_load(open(spath).read()) or {}
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
        secs.append(f'<section class="wf-pg" id="{pid}"><div class="wf-root">{content}</div></section>')
        overrides.append(_width_css(f'#{pid} .wf-root', w, h, notes))
        navs.append(f'<div class="wf-navgrp"><b>📖 {esc(str(sdata["story"]))}</b>'
                    f'<a href="#{pid}" id="nav-{pid}">{esc(sbase)}（故事版）</a></div>')
    # nav 當前頁高亮（零 JS：:has(section:target) → 對應 nav 連結；無 target 則第一頁）
    if pids:
        sel = ','.join(f'body:has(#{p}:target) #nav-{p}' for p in pids)
        sel += f',body:not(:has(.wf-pg:target)) #nav-{pids[0]}'
        overrides.append(sel + '{background:#0f766e;color:#fff;font-weight:600;}')
    css = _hoist_imports(_BASE_CSS + CSS_EXTRA + BUNDLE_CSS + (DEBUG_CSS if debug else '')
                         + _style_css() + _tokens_css() + _theme_css() + ''.join(overrides))
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
    if debug or _STORY:
        _stamp(doc, base)          # 蓋來源+路徑：debug 定位 / story 路徑 target 比對
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
_GRAMMAR_KEYS = {'viewport', 'body', 'extends', 'with', 'slots', 'routes',
                 'content', 'placeholder'}
# 已知 container 屬性 keys（sibling 掛在容器 dict 上）
_CONTAINER_ATTRS = {'row', 'col', 'grid', 'items', 'box', 'gap', 'padding',
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
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, path, msg, hint=None):
        self.errors.append((path, msg, hint))

    def warn(self, path, msg, hint=None):
        self.warnings.append((path, msg, hint))

    def dump(self, file_label, out=sys.stderr):
        for level, items in (('error', self.errors), ('warn', self.warnings)):
            for path, msg, hint in items:
                head = f'\033[1;31m{level}\033[0m' if level == 'error' else f'\033[1;33m{level}\033[0m'
                print(f'{head}: {file_label}', file=out)
                print(f'  → path: {path or "<root>"}', file=out)
                print(f'  → {msg}', file=out)
                if hint:
                    for line in hint.split('\n'):
                        print(f'  hint: {line}', file=out)


def _walk_lint(node, path, diag):
    """遞迴 lint YAML 結構樹。只走結構節點，跳過 leaf value dict / with / as / meta 值。"""
    if isinstance(node, list):
        for i, item in enumerate(node):
            _walk_lint(item, f'{path}[{i}]', diag)
        return
    if not isinstance(node, dict):
        return

    keys = set(node.keys()) - {'__src', '__path'}

    # 判斷節點類型
    has_direction = keys & _DIRECTION_KEYS
    has_leaf_role = keys & set(LEAF_ROLES)
    is_widget = 'widget' in keys
    is_slot_marker = 'slot' in keys and len(keys - {'slot', 'name'}) == 0
    is_spacer = keys == {'spacer'}          # 與 render `_is_spacer` 同判定（恰一個 spacer key）
    is_embed = 'embed' in keys
    # overlay 角色 = 內建 sugar ∪ 專案 token（wf.tokens.yaml overlay: 自定角色，與 render _overlay_tokens 同源）
    has_overlay_sugar = keys & (_OVERLAY_SUGARS | set(_TOKENS.get('overlay') or {}))

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
            if v not in allowed:
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

    # 8. 未知 key typo 檢查（只對通用 container 節點；leaf / widget / overlay sugar 有各自 shape）
    if not is_widget and not has_overlay_sugar and not has_leaf_role and not is_slot_marker and not is_embed and not is_spacer:
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
    _RECURSE_INTO = _DIRECTION_KEYS | {'items', 'body'}   # 這些 value 是結構樹
    for k, v in node.items():
        if k in ('__src', '__path'):
            continue
        sub_path = f'{path}.{k}' if path else k
        if k in _RECURSE_INTO or k in _overlay_tokens():
            if isinstance(v, list):
                for i, item in enumerate(v):
                    _walk_lint(item, f'{sub_path}[{i}]', diag)
            elif isinstance(v, dict):
                _walk_lint(v, sub_path, diag)
        elif k == 'slots':
            # slots 的 key 是使用者定義的 slot 名（不是 vocab key）→ 只走各 slot 的內容
            if isinstance(v, dict):
                for slot_name, slot_content in v.items():
                    _walk_lint(slot_content, f'{sub_path}.{slot_name}', diag)
        elif k == 'routes':
            # routes 內每項是路由 dict，含 slots/body
            if isinstance(v, list):
                for i, r in enumerate(v):
                    _walk_lint(r, f'{sub_path}[{i}]', diag)
        # 其他 key（with/as/note/spotlight/button 等的 dict value）不遞迴 lint —— 屬 value 空間


def _lint_file(path):
    """對單一檔案跑 lint。回傳 (error_count, warning_count)。story 檔走 story schema 驗證。"""
    try:
        doc = yaml.safe_load(open(path, encoding='utf-8')) or {}
    except Exception as e:
        print(f'\033[1;31merror\033[0m: {path}', file=sys.stderr)
        print(f'  → YAML 解析失敗：{e}', file=sys.stderr)
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
    diag = _Diag()
    # 頂層 keys：允許 grammar keys；未知頂層 → warn
    top_keys = set(doc.keys()) if isinstance(doc, dict) else set()
    for k in top_keys:
        if k in _GRAMMAR_KEYS or k in _STRUCTURE_UNITS:
            continue
        sugg = _suggest_key(k, _GRAMMAR_KEYS)
        hint = f"是不是「{sugg}」？" if sugg else f"合法頂層 key：{sorted(_GRAMMAR_KEYS)}"
        diag.warn('<root>', f"未知頂層 key `{k}`", hint)
    # 走 body / slots / routes（slots 的 key 是使用者 slot 名，只走各值；routes 每項是路由 dict）
    basedir = os.path.dirname(path) or '.'
    _load_tokens(basedir)
    if isinstance(doc, dict):
        if 'body' in doc:
            _walk_lint(doc['body'], 'body', diag)
        if 'slots' in doc and isinstance(doc['slots'], dict):
            for slot_name, slot_content in doc['slots'].items():
                _walk_lint(slot_content, f'slots.{slot_name}', diag)
        if 'routes' in doc and isinstance(doc['routes'], list):
            for i, r in enumerate(doc['routes']):
                _walk_lint(r, f'routes[{i}]', diag)
    if diag.errors or diag.warnings:
        diag.dump(path)
    return len(diag.errors), len(diag.warnings)


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
            print("  viewport / body / extends / embed / with / slot / slots / as / routes / default / when / items")
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
        files = [a for a in sys.argv[2:] if not a.startswith('-')]
        if not files:
            print("usage: wfyaml.py lint <file.wf.yaml> [...]", file=sys.stderr)
            sys.exit(1)
        total_err, total_warn = 0, 0
        for f in files:
            e, w = _lint_file(f)
            total_err += e
            total_warn += w
        print(f"\n═══ 總計：{total_err} error / {total_warn} warning ═══", file=sys.stderr)
        sys.exit(2 if total_err else (1 if total_warn else 0))

    out_path = _argval('-o')
    style = _argval('--style')
    mockup_theme = _argval('--mockup')
    story_path = _argval('--story')
    skip = {'--debug', '--bundle', '--no-lint', '-o', out_path,
            '--style', style, '--mockup', mockup_theme, '--story', story_path}
    args = [a for a in sys.argv[1:] if a not in skip]
    if not args and not story_path:
        print("usage: wfyaml.py [--debug] [--bundle [-o out.html]] [--style <name>] [--mockup <theme.yaml>] [--story <x.story.yaml>] <file.wf.yaml> [...]", file=sys.stderr)
        print("       wfyaml.py --story <x.story.yaml>                 # SAC 單獨生成：底圖+故事疊加 → <id>.story.html", file=sys.stderr)
        print("       wfyaml.py list [--ring 0|1] [--basedir <dir>]   # introspection", file=sys.stderr)
        print("       wfyaml.py lint <file.wf.yaml> [...]              # P0.7 schema validation", file=sys.stderr)
        sys.exit(1)
    # --style sketch × --mockup 互斥（低保真美學 vs 高保真綁定，語義衝突）
    if style == 'sketch' and mockup_theme:
        print("[error] --style sketch 與 --mockup 互斥（低保真美學 vs 高保真綁定）", file=sys.stderr)
        sys.exit(1)
    # 有 --mockup <theme> → 載入 theme（fail-fast：檔案不存在或 schema 錯直接拋）
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
        open(out, 'w').write(bundle(args, debug=debug, style=style, story=story_path))
        extra = (' [style:' + style + ']' if style else '') + (f' [story:{os.path.basename(story_path)}]' if story_path else '')
        print(f"  bundled: {out} ({len(args)} 檔){extra}")
        return
    for path in args:
        src = open(path).read()
        basedir = os.path.dirname(path) or '.'
        stem = re.sub(r'\.(wf\.)?ya?ml$', '', path)
        base = os.path.basename(stem)
        suffix = '.debug.html' if debug else '.html'
        for rid, htmlout in compile_all(src, basedir, base, debug=debug, style=style):
            out = stem + (('.' + rid) if rid else '') + suffix
            open(out, 'w').write(htmlout)
            print(f"  compiled: {out}")


if __name__ == '__main__':
    main()
