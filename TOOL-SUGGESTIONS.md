# wireframe-lofi 工具支援建議

從實作 `examples/expense-app/`（一份記帳 app 的 5 頁 wireframe）過程中發現的 bug、限制與 DX 缺口。按痛感排序。

> **本文已對照 `DISCUSSION.md` 校準**：區分「真 bug」vs「設計未涵蓋的新需求」vs「與現有 TODO 對齊」；優先貼北極星②（語義優先、排版原語只此一形）。

---

## P0 — Bug #1：`_items_of` 不讀 dict-form `row:` / `col:` 的 items

**現象**
```yaml
- row:
    gap: sm
    align: center
    items: [ { icon: home }, { text: 首頁 } ]
```
渲染後 `row` **完全空的**，`items` 被靜默丟棄。所有嵌套帶屬性的 row/col 都中招（tx-item component、app bar、預算列、分類排行、帳戶列表…）。

**Root cause** — `wfyaml.py:419-426`
```python
def _items_of(d, direction):
    if direction == 'grid':
        return 'items', (d.get('items', []) or [])
    v = d.get(direction)
    if isinstance(v, list):
        return direction, v
    return 'items', (d.get('items', []) or [])   # ← v 是 dict 時直接落到這，內部 items 拿不到
```

當 `v` 是 dict（表示「row 本身帶屬性」），內部 `v['items']` 沒被撿起來，反而去外層 `d.get('items')` 拿到空。

**建議修法**
```python
def _items_of(d, direction):
    if direction == 'grid':
        return 'items', (d.get('items', []) or [])
    v = d.get(direction)
    if isinstance(v, list):
        return direction, v
    if isinstance(v, dict) and isinstance(v.get('items'), list):
        return f'{direction}.items', v['items']   # __path 反映真實層級
    return 'items', (d.get('items', []) or [])
```

同時 `expand()` / `_fill_slots()` 遞迴要多認 `row: dict` 這條路徑，否則 include / slot 展開會跳過裡層。

**推薦修法（貼北極星②的做法）**：**明拒 dict-form + loader warning**。DISCUSSION 決議排版原語只有兩種寫法（line 21, 24）：
- `row: <str>`（`between` / `end` / `start` / `center` / `around`）
- `row: [ ... ]`（items 簡寫）
- items / gap / align / justify **一律當外層 sibling key**

支援 dict-form 會製造第三種寫法，違背「排版詞彙兩層 + 語義單一」設計。所以：

```python
def _items_of(d, direction):
    if direction == 'grid':
        return 'items', (d.get('items', []) or [])
    v = d.get(direction)
    if isinstance(v, list):
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
```

錯誤訊息要**教育為何是 sibling form**，不只叫人改寫（貼 P0.7 actionable diagnostics 原則）。

**影響範圍**：修完救所有嵌套 row/col 場景（tx-item、app bar、預算列、分類排行、帳戶列表…），是本 skill 最痛的一個。

---

## P0.5 — 設計缺口：`scroll` × `grow` 組合 & `scroll: h-*` 非語義漏水

**兩個相關問題**：
1. **組合缺口**：mobile 外殼要「main 區填滿 canvas 剩餘 + 可捲」，`scroll: true` × `grow: true` 目前沒定義（`scroll: true` 被鎖 16rem）。
2. **非語義漏水**：目前實務只能寫 `scroll: h-160`（40rem），`h-160` 是 Tailwind **像素 token**（640px），違反北極星②「不寫尺寸細節」——讀者要反查才知道是多高，也違反 DISCUSSION line 26 對「Tailwind 只用於 layout/尺寸/欄寬」的邊界（尺寸有語義，但 scroll 高度不是欄寬那種尺寸）。

**現象**
```yaml
- col:
    - slot: main
  grow: true
  scroll: true       # ← 期望：撐滿父容器剩餘高度 + 可捲
                     # ← 實際：16rem 保底，內容被切
```

**Root cause** — `wfyaml.py:479-482`
```python
if d.get('scroll'):
    cls.append('wf-scroll')
    sv = d['scroll']
    style.append('max-height:' + (_track(sv) if sv is not True else '16rem'))
```

**建議：`scroll:` / `scroll-x:` 純語義寫法（新設計）**

移除 `scroll: h-*` 像素 token 支援，改成純語義；`scroll-x:` 對稱處理：

| 寫法 | 語義 | 實作 |
|------|------|------|
| `scroll: true` | 「這區塊垂直可捲」，高度由父容器 / `grow: true` 決定 | `overflow-y: auto`，無 max-height |
| `scroll: sm` / `md` / `lg` / `xl` | 語義級距，可 theme（跟 `gap:` / `padding:` 家族對齊） | `max-height: var(--wf-scroll-sm/md/lg/xl)`；預設可設 `8rem / 16rem / 32rem / 48rem` |
| `scroll-x: true` | 「這區塊水平可捲」，寬度由父容器決定 | `overflow-x: auto`，無 max-width |
| `scroll-x: sm` / `md` / `lg` / `xl` | 對稱的水平 scale | `max-width: var(--wf-scroll-x-*)`（或共用同一 scale） |

**為什麼是 t-shirt scale 而非精確值**：
- 跟 DISCUSSION line 27 的間距語義 scale 對稱：「間距是設計節奏核心，語義=一張對照表，換 theme 一字不動」
- 捲動區高度也是「節奏」型的決策（多高才算合理閱讀量），不是「像素等於多少」的規格
- 換 canvas / theme 不用改 YAML

**組合語義自然成立**（不需要新關鍵字）：
```yaml
- col:
    - slot: main
  grow: true         # 「這區塊長大吃掉剩餘」
  scroll: true       # 「這區塊可捲」
```
兩個原語各自獨立，讀者一句一句讀就懂——不需要 `scroll: fill` 之類的聯集寫法。

**實作**
```python
_SCROLL_SCALE = {'sm': '12rem', 'md': '24rem', 'lg': '40rem'}   # 或抽 :root var

if d.get('scroll'):
    cls.append('wf-scroll')
    sv = d['scroll']
    if sv is True:
        style.append('overflow-y:auto')          # 高度由 grow / 父容器決定
    elif sv in _SCROLL_SCALE:
        style.append('max-height:' + _SCROLL_SCALE[sv])
    else:
        raise ValueError(f"scroll: 只接受 true 或 sm/md/lg（收到 {sv!r}）。")
```

**遷移**：現有 `scroll: h-*` / `scroll: <px>` 產生 warning，指向新寫法。

**繞開方式**（目前用的）：`scroll: h-160`，等修好後改成 `scroll: true`（配 `grow: true`）。

---

## P0.6 — 命名討論定調（`grow` vs `fill`、canonical form）

### `grow: true` 保留（不改成 `fill:`）

原本考慮改名 `fill: true` 求「更語義」，但討論後**保留 `grow`**：

- **方向已限縮在 row/col**：讀者從父容器 direction 已知主軸，不需要在名字裡再標「main」
- **`grow` 是 CSS/UI 界通用詞**（`flex-grow: 1`），既有 mental model 命中，讀者不需重新學
- **`grow` 動詞感精準**：flex 的行為是「動態長大吃剩餘」，`fill` 過於靜態；`fill` 也有 fill area / fill color 等歧義
- **`spacer` vs `grow` 分工清楚**：`spacer` = 塞一個空推擠鄰居；`grow` = 區塊自己填滿

### Canonical container form：**維持 sibling form，明拒 dict-form**（P0 立場不變）

原本考慮改 canonical 成 dict-form（因為對 AST → code 天然對齊），討論後**維持 sibling form**：

**trade-off 表**

| 面向 | Sibling form（現行） | Dict form |
|------|-------------------|-----------|
| 讀者「gap 屬於誰」 | 隱式（gap 是這個 dict 的 sibling） | 顯式（gap 在 row: 內部） |
| AST 對齊 | Loader 收攏 `(gap, align, items) ← 從同一 dict` | 天然對齊 |
| YAML 縮排 | 淺一階 | 深一階 |
| 短寫（無屬性） | `row: [a, b]` ✅ | `row: [a, b]` ✅（雙形式並存風險） |
| 北極星② 排版單一 | ✅ 只此一形 | ❌ 若並存 |

**決定 sibling form 的理由**：

1. **北極星② 排版單一勝過對齊**：DISCUSSION line 21/24 已定案「排版原語兩層」，改 canonical 會製造第三種寫法，違反核心設計；為 AST → code 的**未來需求**破**現在的一致性**不划算。

2. **AST → code 不會被 sibling form 卡住**：codegen 只是把「dict 裡的 gap/align/justify 和 row/col/items 一起取出來組節點」，`Row(gap=d['gap'], align=d['align'], children=d[dir])` 一行的事。內部 AST 表示可以自由，不必跟 YAML 表面 1:1。

3. **當前 sibling form 其實已經是「dict-form」**——`gap: sm` 跟 `row: [a,b]` 就是同一個 dict 的兩個 key，只是「row 這個 key 特別，它的 value 是 items 而不是 direction 屬性」。從 YAML/AST 角度看，它就是 `{row: [items], gap: sm}` 一個節點——語義上 dict 全部 key 都屬於這個 row container。**只是 items 用 `row:` key 藏起來的 sugar**。這個約定明確後，讀者不會混淆。

4. **`row: [ ... ]` 短寫的價值**：無屬性的 row 一行寫完（`row: [a, b]`），保留最重要的常見情形的簡潔性。

**要做的是文件補強，不是改設計**：README 明講：
> row/col/grid 的**方向 key 值**是 items（`row: [a, b]`）或 justify 短寫（`row: between`）。
> 容器屬性（`gap` / `align` / `justify` / `padding` / `box` / `grow` / `scroll`）**與方向 key 同層**，屬於同一個 container 節點。
> 不接受 `row: { gap, items }` 的 dict-form（會 error）。

### AST → code 的內部表示（未來規劃）

真的做 codegen 時，內部 AST 可以是：
```python
Container(
    direction='row',      # row / col / grid
    justify='between',    # 從 row: str 或 sibling justify: 讀
    align='center',
    gap='sm',
    padding='md',
    box=True,
    grow=False,
    scroll=None,
    children=[...],       # 從 row: list 或 sibling items: 讀
)
```

YAML 表面（sibling form）到這個 AST 是一個 flat pick-up；到 React/Vue 是 `<Row justify="between" align="center" gap="sm">{children}</Row>`——完全不受 YAML 縮排影響。

**結論**：**sibling form 是設計層的正解**，AST → code 是實作層的問題，兩層不衝突。

---

## P0.7 — Schema Validation & Fail-Fast（防呆早失敗）

### 為什麼要這節

目前 wfyaml.py 對錯誤 YAML 的態度是**靜默降級**：
- `row: {items: [...]}` dict-form → 靜默渲空 row（P0 bug 本質）
- `align: cetner`（typo）→ 靜默 fallback center
- `tone: dangor` → 靜默無效果
- `scroll: h-160`（Tailwind px token）→ 語義漏水但通過

**代價**：使用者以為 YAML 正確、看到 UI 怪但不知道錯在哪 → 心智負擔全在 debug 上。而 wireframe-lofi 的定位是「人機共讀媒介」，LLM 生成的 YAML 出錯機率不低 → 靜默失敗會讓 LLM 產垃圾也沒信號回饋。

### 概念名（業界術語）

| 概念 | 名字 | 對應到本專案 |
|-----|------|-------------|
| **Schema Validation** | 結構驗證 | container / leaf 節點形狀合法性 |
| **Semantic Analysis** | 語義分析 | tone 值在合法集合、slot 引用存在、include 檔案找得到 |
| **Fail-Fast** | 早失敗（哲學） | 錯了就大聲喊，不繼續跑產怪結果 |
| **Actionable Diagnostics** | 可行動診斷 | 錯誤訊息帶檔名 + 行號 + 路徑 + 修法建議 |
| **Poka-Yoke** | 防呆（原則） | 讓錯誤在源頭無法發生 |
| **Static Lint** | 靜態掃描 | `wireframe-lofi lint file.wf.yaml` 專用工具 |

### 對 AST → code 的意涵（強制前置）

TypeScript 的 `tsc` 是黃金類比：**AST codegen 前必須先 type/schema check**，錯誤責任明確歸給 YAML 作者，不會漏到下游 React runtime。wireframe-lofi loader 該扮演 `tsc` 角色。

### 建議 lint 規則（架構層）

分成 **P0.7a schema**（結構）+ **P0.7b semantic**（語義）：

#### P0.7a — 結構 schema

| 規則 | 例（違反） | 錯誤處理 |
|-----|-----------|---------|
| container 節點恰有一個 direction key | `{row: [...], col: [...]}` | error：「container 只能有一個方向 key，收到 row + col」 |
| container 的 direction key 值必須是 str / list / null | `row: {gap: sm}` | error（P0 立場，錯誤訊息參 P0） |
| leaf 節點必須有恰一個 role key | `{text: a, button: b}` | error：「leaf 只能有一個 role」 |
| 未知 key | `alighn: center` | warning：「未知 key `alighn`，是不是 `align`？」（帶 Levenshtein 建議） |
| container / leaf 屬性混掛不合法 | `text: hi` + `justify: end` | warning：「text 是 leaf，`justify` 只對 container 生效」 |

#### P0.7b — 語義集合

| 規則 | 合法集合 |
|-----|---------|
| `gap` / `padding` | `none` / `sm` / `md` / `lg` / `xl`（DISCUSSION line 27 已定） |
| `align` | `top` / `bottom` / `center` / `baseline` / `stretch` |
| `justify` | `start` / `end` / `center` / `between` / `around` |
| `tone` | 收斂為本次候選 6 名（見末段實作回饋） |
| `scroll` / `scroll-x` | `true` / `sm` / `md` / `lg` / `xl` |
| `spotlight.kind` | `focus` / `new` / `change` / `click`（DISCUSSION line 36） |
| slot 引用 | 對應 layout 有挖同名 slot |
| include 檔名 | 檔案存在（同夾 → components/layouts/partials 搜） |
| icon 名 | 在 FA / Lucide vocab 集合（見 P4 E4） |

### Actionable diagnostics 格式

錯誤訊息模板（貼 Rust compiler 風格）：

```
error: examples/expense-app/home.wf.yaml:23:5
  ┌─ slots.main[3].col[2]
  │
  │  - row:
  │      gap: sm
  │      items: [ { icon: home }, { text: 首頁 } ]
  │      ^^^^^ dict-form 的 items 不會被讀取
  │
  = help: container 屬性一律 sibling — 方向 key `row:` 只承載 items 短寫或 justify 短寫。
  = fix:  - row: [ { icon: home }, { text: 首頁 } ]
              gap: sm
```

包含：檔名 + 行號 + YAML 路徑 + 標示位置 + 為何錯 + 怎麼修。

### 實作切點

1. **Loader 階段**（yaml.safe_load 之後、expand/render 之前）走一次 `validate(doc)`，拋 `ValidationError` 帶 diagnostics list
2. **CLI 增 `--strict`**（預設）跟 `--lenient`（舊行為，只 warning）過渡期
3. **獨立 `wireframe-lofi lint`** 子命令：只驗不 render，方便 CI 掛
4. **JSON Schema 檔**（`schemas/wf.schema.json`）：可給 VS Code YAML 擴充做 in-editor 提示，DX 大幅提升

### 收攏本文其他條款到此框架下

- **P0 dict-form 明拒** = schema validation 第一條
- **A3 錯誤訊息強化** = actionable diagnostics 品質要求
- **P4 E8 lint 規則** = 本節 P0.7a/b 條款展開
- **未定 tone / icon 集合** = 依賴 lock-in 進度，先 warning 後 error

---

## P1 — 缺 leaf

### P1a — `progress` leaf（新提案，強烈建議）

記帳/預算/募款/專案完成度剛需。目前只能用 `status.strong: 78%` chip 湊，沒有 fill bar 視覺，比例感受弱。

**建議**（沿用現有 leaf `role: 值` scalar-or-map 樣式，line 38）
```yaml
- progress: { value: 0.78, tone: warn, label: "6,200/8,000" }
- progress: 0.5                              # scalar 簡寫
```

`value` 用 0–1 語義比例（非像素/百分比字串）；`tone` 走 Layer1 語義色；`label` 走現有 inline markdown。與既定葉子表風格一致。

### P1b — `avatar` leaf（已在 DISCUSSION 待補清單）

DISCUSSION line 45 已列「待補(遇到再做)：`avatar`(圓)」。本次 Me 頁確實遇到（Profile 卡的頭像），目前用 `image: {label: 頭像, ratio: 1/1, w: w-16}` 湊，語義不強。

**建議**
```yaml
- avatar: { label: EC, size: sm }            # 顯示 EC 兩字母
- avatar: EC                                 # scalar 簡寫
```

**視覺封印邊界（貼北極星②）**：
- ✅ `label`（縮寫字母）+ `size`（sm/md/lg，語義 scale）
- ❌ **不接受** `src: photo.jpg` / `bg: red` 等真圖 / 真色參數 — 屬視覺逃生口
- 大頭照全部走「圓形佔位 + label」，跟 `image:` 打叉框對稱

### P1c — `chart` leaf（低優先，可能冗餘）

DISCUSSION line 42 已把 `image: {label, ratio}` 定位為「佔位打叉框」，本次 Stats 頁的「分類佔比（環形圖）」/「支出趨勢（柱狀圖）」用 `image` label + ratio 已足夠傳達意圖。

**判斷**：新增 `chart:` 可能違反 DISCUSSION「核心精簡」原則（line 19）。建議**先不加**，等真的有多次「需要區分 chart 佔位 vs 圖片佔位」的場景再議。

若真要加，最小提案：
```yaml
- chart: { kind: donut, label: 分類佔比 }    # 相當於 image 但斜線 X 換成環形示意
```
但這只是視覺別名，語義沒質變。

---

## P2 — Slot 展開多項時無對齊 helper

**現象**（app bar 常見）
```yaml
- row:
    - slot: title
    - slot: actions
  justify: between
```
`actions` 展開為 `[icon: bell, icon: search]` 兩項，最終 row 變成 3 個孩子 `[title, bell, search]`，`justify: between` 把三者平均攤開，不是「title 靠左、actions 群組靠右」。

**目前繞開**：包一層 list-form 內 row
```yaml
- row:
    - slot: title
    - row:
        - slot: actions
      gap: sm
      align: center
  justify: between
```
語義囉嗦。

**建議**：slot 支援 `wrap` 屬性
```yaml
- slot: actions
  wrap: row                # 展開時自動包一層 row
  gap: sm
```
或提供 `role: header-bar` layout helper 直接吃 title + actions。

---

## P3 — DX 小改

### 3.1 dict-form `row:` 的 warning
在 P0 修好前（或 loader 層），偵測到 `row: {items: [...]}` 立即輸出：
```
warn: examples/x.wf.yaml:12 — row: {items: ...} 內部 items 不會被讀取。
       請改用 `row: [ ... ]`（list-form）+ 提升 gap/align 為 sibling key。
```

### 3.2 items / row.items 衝突偵測
兩者同時存在時報 conflict，避免使用者以為某層有效。

### 3.3 `include with:` 的 dict scalar 替換 — 補文件
`_subst` 已支援對任何 leaf value 字串位置的 `{{}}` 替換（`text: "{{category}}"` 是 OK 的），但被 P0 bug 掩蓋。實測後 README 應明確寫：

> `{{param}}` 替換適用於**任何葉子字串**（包括 dict role value：`text: "{{category}}"`、`tone: "{{tone}}"`），不限頂層 scalar。

並補一個 test 鎖住這行為。

---

## P4 — AST → code 對齊擴充

為未來 wireframe-lofi → React / Vue / SwiftUI codegen 前置。核心原則：
**內部 AST 是穩定接口，YAML 表面可以用 sugar，但 AST 節點 shape 必須明列且鎖住**。

### E1 — Container 屬性 schema（明列）

Container 節點的完整 shape：

```
Container {
    direction:  'row' | 'col' | 'grid'                    # 恰一個（P0.7 lint）
    justify:    'start' | 'end' | 'center' | 'between' | 'around' | null
    align:      'top' | 'bottom' | 'center' | 'baseline' | 'stretch' | null
    gap:        'none' | 'sm' | 'md' | 'lg' | 'xl'        # 語義 scale
    padding:    'none' | 'sm' | 'md' | 'lg' | 'xl'
    box:        boolean
    grow:       boolean                                    # main-axis 填滿
    scroll:     true | 'sm' | 'md' | 'lg' | 'xl' | null   # 垂直捲（P0.5）
    scroll-x:   true | 'sm' | 'md' | 'lg' | 'xl' | null   # 水平捲
    span:       int | null                                 # grid 跨欄
    tracks:     list<TailwindWidthToken> | int | null      # grid 欄寬（來自 grid: [w-24, ...] 或 grid: N）
    children:   list<Node>                                 # 從 direction key 的 list value 或 sibling items:
}
```

Cross-cutting（container/leaf 都可掛，屬節點 metadata）：
```
Metadata {
    name:       string | null                              # 隱形 data-name
    tone:       ToneEnum | null                            # Layer 1 語義色
    to:         RouteRef | null                            # 動線（見 E3）
    note:       {ref, text} | null                         # Layer 2 標註
    spotlight:  {kind, text?, step?} | null                # Layer 2 導引
}
```

**AST → React 映射**（1:1）：
```jsx
<Row justify="between" align="center" gap="sm" data-name="tab-bar">
  {children}
</Row>
```

### E2 — Leaf 屬性 schema（明列）

Leaf 節點的完整 shape：

```
Leaf {
    role:       LeafRole                                   # 恰一個（P0.7 lint）
    value:      LeafValueFor<role>                         # 依 role 定型
    metadata:   Metadata                                    # 共用（見 E1）
}
```

各 role 的 value shape：

| role | value shape | 可掛 metadata |
|------|-------------|--------------|
| `text` / `text.title` / `text.heading` / `text.label` / `text.strong` / `text.hint` | string（含 inline markdown） | name, tone |
| `input` | `{placeholder, value?}` 或 string(=placeholder) | name |
| `select` | `{text, options?}` 或 string(=text) | name |
| `button` | `{text, to?, icon?}` 或 string(=text) | name, tone, note, spotlight |
| `status` / `status.muted` / `status.strong` | string | name, tone |
| `badge` | string | name, tone |
| `alert` | string | name, tone |
| `icon` | string(=name) 或 `{set, name}` | name, tone |
| `divider` | 無 value | name, tone |
| `link` | `{text, to}` | name |
| `checkbox` / `radio` | `{label, checked?}` 或 markdown sugar | name |
| `image` | `{label, w?, h?, ratio?}` 或 string(=label) | name |
| `tabs` | `{active, items[]}` | name |
| `progress` **（新）** | `{value: 0-1, label?}` 或 number | name, tone |
| `avatar` **（新）** | `{label, size?}` 或 string(=label) | name, tone |

**跨葉子規則**（P0.7 lint）：
- `to:` 只在 `button` / `link` / 容器（動線）上有效；掛在 `text` 上 → warning
- `checked` 只在 `checkbox` / `radio` 上；其他 → warning

### E3 — `to:` 值文法形式化

現行實測有 `to: page` / `to: "page#stage.state"`。建議 lock in grammar：

```
RouteRef  ::= <page>('#'<stage>('.'<state>)?)? | '#'<stage>('.'<state>)?
page      ::= [a-z][a-z0-9-]*
stage     ::= [a-z][a-z0-9-]*
state     ::= [a-z][a-z0-9-]*
```

**AST 表示**：
```
RouteRef {
    page:  string | null           # null = 頁面內跳（純 hash）
    stage: string | null
    state: string | null
}
```

**Codegen 映射**：
- React Router：`/{page}/{stage}/{state}` 三段 path
- Next.js App Router：`app/[page]/[stage]/[state]/page.tsx`
- 純 hash（無 page）：頁面內 state 切換，對應 `useState` / `URLSearchParams`

**規則**：
- `#` 前後至少有一段（不能空字串）
- 分隔字元固定 `#` 與 `.`，不擴充
- `to:` 值必須通過 grammar parse，否則 P0.7 lint error

### E4 — Icon 語彙 lock-in（跨平台 canonical vocab）

**問題**：目前 `icon: swap` / `icon: minus` 有些找不到，靜默顯示「◻ 未找到」。且 FA/Lucide 名稱直通 → 綁死 web 圖庫。

**建議建立 canonical icon vocabulary**（跟 Layer 1 tone 一樣 lock-in），約 30 個核心語義名：

| 語義 | canonical | FA | Lucide | SF Symbols | Material Symbols |
|-----|-----------|----|----|-----------|-----------------|
| 首頁 | `home` | `fa-house` | `lu-home` | `house` | `home` |
| 返回 | `back` | `fa-arrow-left` | `lu-arrow-left` | `arrow.left` | `arrow_back` |
| 關閉 | `close` | `fa-xmark` | `lu-x` | `xmark` | `close` |
| 搜尋 | `search` | `fa-magnifying-glass` | `lu-search` | `magnifyingglass` | `search` |
| 新增 | `add` | `fa-plus` | `lu-plus` | `plus` | `add` |
| 刪除 | `remove` | `fa-minus` | `lu-minus` | `minus` | `remove` |
| … | … | … | … | … | … |

**核心約 30 個**（分類）：導覽 `home / back / forward / close / menu / more`；動作 `add / remove / edit / delete / save / share / download / upload`；狀態 `check / warn / info / question`；資料 `search / filter / sort / calendar`；使用者 `user / bell / settings`；金融場景常用 `wallet / card / receipt / chart-pie / chart-bar`。

**AST → code**：
```jsx
// wireframe-lofi
- icon: home

// codegen 到 React Native
<HomeIcon />                                 // 從 canonical vocab 表映射
```

**額外**：允許 escape hatch `icon: {set: fa, name: fa-custom}` 直通具體圖庫（用來畫本次 wireframe，但**不參與 codegen**，會被標記為 platform-specific）。

### E5 — `include` 支援 `slots:`（React `children` 對齊）

**現行缺口**：`include with:` 只能替換葉子字串，無法傳「一段內容」當子節點 → 對照 React 的 `<Card>{children}</Card>` 無解。

**擴充建議**：`include` 可以帶 `slots:`，component 可以挖 slot（跟 layout 機制對稱）：

```yaml
# component: components/card.wf.yaml
content:
  - box: true
    padding: lg
    col:
      - text.heading: "{{title}}"
      - slot: content                        # ← component 挖洞
      - slot: footer

# 頁面 include 時填 slots
- include: components/card
  with: { title: 本月結餘 }
  slots:
    content:
      - text.title: "NT$ 12,480"
    footer:
      - button: 查看明細
```

**AST → code** 映射自然：
```jsx
<Card title="本月結餘"
      content={<Amount value="12,480" />}
      footer={<Button>查看明細</Button>} />
// 或用 children prop：
<Card title="本月結餘">
  <Amount value="12,480" />
  <Button>查看明細</Button>
</Card>
```

**設計對齊**：layout 有 slots、component 也可有 slots，兩者機制**完全一致**（DISCUSSION line 23 三層對稱原則的延伸）。

### E6 — `canvas` 標記為 render meta（AST 忽略）

`canvas: 390x844` 只給 wfyaml render 用（決定 HTML 外框、PNG 尺寸、置底佈局的基準高度）。對 AST → code：

- React / Vue app 不定畫布 → **codegen 忽略 canvas**
- iOS / Android app 用系統 safe area → **codegen 忽略 canvas**

**明講 canvas 屬 meta 家族**（跟 Layer2、debug、flowmap 同族）：不進產品 AST、只用於 wireframe render / preview。

### E7 — 事件槽的立場：**不做**（明講）

真產品有 `onClick` / `onSubmit` / `onChange` / `onSelect`，wireframe-lofi 目前只表達 `to:`（導航）。

**立場**：wireframe-lofi 只表達「畫面 + 動線」，不表達事件行為。

**理由（貼 DISCUSSION line 57 保真度旋鈕）**：
- 事件屬 mockup / 高保真階段，wireframe 是低保真層
- codegen 產出的 React 只有 layout + 導航（`to:` → `router.push`），事件由後續填
- 加事件槽會膨脹 wireframe 詞彙 & 破北極星①

**明講 doc 有這行**，避免後人問「怎麼標 onClick」。

### E8 — Lint 規則（併入 P0.7 條款）

原本規劃的 lint 規則已全數併入 **P0.7 Schema Validation & Fail-Fast** 節，這裡不重複。

### E9 — 「葉子兩種寫法擇一」呼應（canonical = dict-form）

DISCUSSION line 262 待補項：「葉子兩種寫法擇一（`"role: 值"` 字串 vs `{role: 值}` dict）」。

**建議 lock in canonical = dict form** `{text: hello}`，明拒字串 sugar `"text: hello"`：

- **理由**：字串 sugar 要 wfyaml 內部 mini-parser 切 `role: value`，這**正是 DISCUSSION line 13 決策「不手刻 parser」的例外洞**。移除 sugar 後 100% 靠 `yaml.safe_load` 拿到結構。
- **遷移**：現行字串 sugar 出 warning，指向 dict 寫法。
- **AST 對齊**：codegen 只需認 dict role，不需雙 code path。

### E10 — `routes:` = single URL 對 AST 的意涵

DISCUSSION line 16：「一條路由 = 一張輸出 = 一個 URL」。對 codegen：

**明講立場**：
> `routes:` 產出的每個路由對應**獨立 URL / route path**（如 `/deal/approving/pending`），**不是 client-side state**。
> codegen 到 React Router → 每路由一個 `<Route path="/{page}/{stage}/{state}" element={...} />`。
> codegen 到 Next.js → 每路由一個 `app/[...]/page.tsx`。

**對比**：如果把 stage/state 當 React `useState`，會失去 single-URL 的深連結能力（分享、書籤、瀏覽器 back）。DISCUSSION 已定案路由化，codegen 沿用。

---

## P5 — 三環同心架構 & Pipeline 支援

為六個訴求（AI 最少 token / 最少元素 / wireframe·mockup·product 不混 / 支援 wireframe→mockup→AST→code / 版控 / 多受眾動態輸出）**收斂到單一設計**：分三個同心環，職責正交。

### 架構

```
Ring 0  結構原語（~15 個，AI 必背 · 恆定不成長）
        row / col / grid / box + text.* / button / input / icon / status / ...
        所有輸出模式共用同一組。這是 AI 的字母表。

Ring 1  語義 token（opt-in，AI 讀 wf.tokens.yaml 即懂 · 不背）
        gap: section、tone: brand、overlay.drawer、frame: strong ...
        值換皮，詞彙不變。專案帶自己的字典。已有 Phase 1/2 引用 + 組合型。

Ring 2  輸出模式（旗標，不進 YAML · 讀者面）
        --style clean/sketch/mockup
        --fidelity wireframe/mockup
        --emit html/png/ast/react
        --audience pm/eng/customer/discuss     ← sugar 別名
        renderer/emitter 決定產什麼，作者不動 YAML。
```

### 為什麼六個訴求同時解決

- **AI 最少負擔**：Ring 0 恆定小；Ring 1 靠 `wireframe-lofi list` introspection 查（不背）；Ring 2 是 CLI 不進 YAML。
- **wireframe / mockup / product 不混**：fidelity mode 結構性防漂移（8c953bb）—— 預設 renderer 硬夾 Ring 0，畫不出 mockup；要 mockup 得明給 `--mockup`。**靠模式旗標切，不靠作者自律**。
- **Pipeline**：
  - wireframe → mockup：Ring 0 YAML 不動，加 `wf.tokens.yaml` + `--mockup`
  - mockup → AST → code：`--emit ast` 產結構化節點樹（走 P4 E1/E2 schema），再進 codegen
- **版控**：YAML + tokens.yaml + style CSS 全 plain text，git diff/blame 天然 work
- **多受眾**：同一份 YAML 交叉旗標
  - PM：`--fidelity mockup --style mockup --tokens brand.yaml`
  - Eng：`--emit ast` → JSON 給 codegen
  - 客戶：`--fidelity wireframe --bundle` → 可點原型
  - 討論：`--fidelity wireframe --style sketch --debug`

### 關鍵不混淆原則（一句話）

> **YAML 詞彙 = Ring 0 + Ring 1**（作者面）；**輸出樣貌 = Ring 2**（讀者面）。
> 作者永遠不用想「我在做 wireframe 還是 mockup」，模式是讀者側旗標；
> AI 也永遠不會誤把 mockup 值塞進 wireframe YAML（fidelity mode 硬夾）。

### 現況 gap（最少改動補齊三環）

| 項 | 現況 | 需要做 | 修改量 |
|----|------|-------|-------|
| **P5.1 `wireframe-lofi list`** | 無 introspection | 列出 Ring 0 全部原語 + 專案 Ring 1（解析 wf.tokens.yaml）+ 用法/展開 | ~50 行 CLI |
| **P5.2 `--emit ast`** | 只 emit html/png/svg | 產結構化節點樹（JSON，走 P4 E1/E2 schema），codegen 前置 | 中量，走 render tree serialize |
| **P5.3 `--audience` sugar** | 無 | 打包 `fidelity + style + tokens + emit` 三四旗標成別名 | ~10 行 CLI shim |
| **P5.4 Ring 0 明列** | 散在 README 各節 | 一節「Ring 0 字母表」列全部 ~15 個原語 + 對應 Ring 1 opt-in 說明 + Ring 2 旗標對照 | 文件 |

### 與現有系統對齊

- **fidelity mode（8c953bb）** = Ring 2 的一環，已 land 且是三環結構的關鍵支柱
- **`--style` 解耦（a368d72）** = Ring 2 的另一環，已 land
- **semantic token Phase 1/2** = Ring 1 的實作，已 land
- **anti-drift 原則（8d06e63）** = 三環自動符合 —— Ring 0 恆小、Ring 1 opt-in、Ring 2 不吃作者心力
- **widget（7b08c1c）** = Ring 0 成員（自我聲明示意元件），非 Ring 1 token
- **P0/P0.5/P0.7 lint** = 分模式規則：wireframe 嚴（夾 Ring 0）、mockup 鬆（放 Ring 1）

### AI prompt 範例（三環的 payoff）

```
你是 wireframe-lofi 作者。可用詞彙：
- Ring 0（結構原語，恆定）：`wireframe-lofi list --ring 0` 輸出
- Ring 1（本專案語義 token）：`wireframe-lofi list --ring 1` 輸出（讀 wf.tokens.yaml）
- Ring 2（輸出旗標）：pm/eng/customer/discuss 別名，你不需要寫進 YAML

規則：
1. 只用 Ring 0 + Ring 1 詞彙寫 YAML
2. 不寫視覺細節（px/hex/字體）— 用語義 token
3. 不表達事件（onClick 等）— wireframe 只表達畫面+動線
```

一份 prompt 涵蓋所有情境，AI 無論產 wireframe / mockup / codegen 都用同一組詞彙。

---

## 給 DISCUSSION.md 的實作回饋（實測資料）

以下是 wireframe-lofi 尚未定案的議題，本次 5 頁記帳 app 實測可作為證據餵回：

### Layer 1 tone 命名（line 37 ⏳待議）

實測用了 6 個 tone，全數 render 有效果、語義清楚：

| tone | 用途 | 場景 |
|------|------|------|
| `danger` | 支出金額、超支預算、警示 chip | 每頁交易金額、超支狀態 |
| `success` | 收入金額、預算健康、狀態綠燈 | 收入、雲端同步已開啟 |
| `warn` | 預算接近上限（70%–99%） | 餐飲預算 78% |
| `feature` | 主要 CTA、focused UI、active tab | 完成按鈕、tab bar active、資產總額 |
| `info` | 中性資訊型分類 | 交通類分類卡 |
| `muted` | 去強調的 chip、非重點分類 | 篩選 chip 非 active 態、「其他」分類 |

**候選 lock-in**：這 6 個名稱組合覆蓋了記帳類 app 的所有語義色需求，可考慮鎖為 Layer 1 標準集合。命名軸分工清楚：
- **警示軸**（`info` → `warn` → `danger`）— 對應 line 37 的 `severity` 提議
- **正向結果**（`success`）— 獨立
- **強調度**（`feature` / `muted`）— 非顏色，是強調機制
- 建議 tone 沿用單一名稱空間（不拆 severity），因為記帳 app 這種混合場景 tone 是實作最順手的接口。

### `with:` 替換範圍（未文件化）

實測 `_subst` 已支援 dict role value 內的 `{{}}` 替換：`text: "{{category}}"`、`tone: "{{tone}}"`、`button: {text: "{{label}}", to: "{{route}}"}` 都可以 work（被 P0 bug 掩蓋才誤以為壞掉）。建議 README §2 明講：

> `{{param}}` 替換適用於**任何葉子字串位置**，含 dict role value、button map 內字串等，不限頂層 scalar。

### `name:` 隱形語意（line 20）確認

實測 `name: tab-home` 正確寫入 `data-name="tab-home"` 且不渲染。與設計一致，無需調整。

---

## 優先順序總覽

| 優先 | 項目 | 影響 | 修改量 |
|-----|------|------|-------|
| **P0** | Bug #1：`_items_of` dict-form 明拒 + actionable error | 修一處救所有嵌套 row/col；貼北極星② | ~5 行 |
| **P0.5** | `scroll:` / `scroll-x:` 純語義化（true / sm/md/lg/xl）+ 移除 h-* | 解決非語義漏水 & 支援 grow 組合 | ~15 行 + CSS var |
| **P0.6** | 命名 / canonical form 定調（文件） | `grow` 保留、sibling form 為 canonical | 文件 |
| **P0.7** | **Schema Validation + Fail-Fast**（架構決策） | 靜默失敗 → actionable diagnostics；AST codegen 前置 | 中量 + JSON Schema |
| **P1a** | `progress` leaf | 記帳/預算/儀表板剛需 | ~15 行 leaf + CSS |
| **P1b** | `avatar` leaf（DISCUSSION 已列待補；只 label 不接圖） | 社交 / 協作 / Profile | ~10 行 + CSS |
| **P1c** | `chart` leaf | 語義冗餘，暫緩 | — |
| **P2** | Slot 展開對齊 helper | app bar / toolbar 通用 | ~10 行 |
| **P3** | `with:` 替換範圍補文件 | DX | 文件 |
| **P4 E1–E2** | Container / Leaf 屬性 schema 明列 | AST 對齊；lint 依據 | 文件 + schema |
| **P4 E3** | `to:` 值 grammar 形式化 | 路由 codegen 穩定性 | 文件 + parser |
| **P4 E4** | Icon canonical vocab（~30 名 + 跨平台 mapping） | 跨平台 codegen 對齊 | 中量 + 表 |
| **P4 E5** | `include` 支援 `slots:`（component children） | React children 對齊 | 中量 |
| **P4 E6** | `canvas` 標記為 render meta | codegen 忽略 | 文件 |
| **P4 E7** | **事件槽立場：不做**（明講） | 保持低保真 + AST 邊界清楚 | 文件 |
| **P4 E9** | 葉子 canonical = dict-form（明拒字串 sugar） | 收斂 DISCUSSION 待補 | 文件 + 遷移 |
| **P4 E10** | `routes:` = single URL（codegen 立場） | 深連結能力保留 | 文件 |
| **回饋** | Layer 1 tone 候選 lock-in（6 個名稱） | 收斂 line 37 待議 | 討論 |
| **P5.1** | `wireframe-lofi list` introspection | AI/作者查 Ring 0+Ring 1 詞彙 | ~50 行 CLI |
| **P5.2** | `--emit ast` | codegen 前置；wireframe→AST→code 缺這段 | 中量 |
| **P5.3** | `--audience` sugar 別名 | 多受眾動態輸出的 CLI 打包 | ~10 行 |
| **P5.4** | Ring 0 字母表 明列（文件） | AI 一眼看完全部原語 | 文件 |
| **P6 ⏳待討論** | Flow-scoped 聚焦輸出（`--entry` 自動 walk `to:` 圖 / `flows/<name>.yaml` manifest） | 巨型專案 POC 評審的正確粒度；不動 YAML 詞彙、走 flowmap 現有 walk | 未定 |

---

## 附錄 — 從實作學到的最佳實踐（未來寫 wireframe-lofi 時遵守）

1. **一律用 list-form nested row/col**
   ```yaml
   # Good
   - row:
       - a
       - b
     gap: sm
     align: center

   # Bad（P0 bug 前）
   - row:
       gap: sm
       items: [a, b]
   ```

2. **`scroll:` 目前有 bug，繞開時一律給明確 token；未來設計為純語義**
   ```yaml
   # 現行繞開（bug 修好前）
   scroll: h-160   # OK（走 Tailwind 像素 token，非語義）
   scroll: true    # ✗ 會被鎖 16rem

   # 修好後的語義寫法（見 P0.5）
   scroll: true    # 配 grow: true → 填滿父容器剩餘 + 可捲
   scroll: sm      # / md / lg → t-shirt scale，可 theme
   ```

3. **想在 app bar 塞 title + 多 icon actions，slot 要包 wrap**
   ```yaml
   - row:
       - slot: title
       - row: [ - slot: actions ]
         gap: sm
     justify: between
   ```

4. **`{{param}}` 可用於任何 leaf value（含 dict role）**
   ```yaml
   - text: "{{category}}"
   - tone: "{{tone}}"
   - button: { text: "{{label}}", to: "{{route}}" }
   ```

5. **icon 名稱請確認在 FA/Lucide 有存在** — 打錯會顯示「◻ 未找到」。常用：
   `utensils / car / cart-shopping / film / house / heart / book / plus / minus`
   `wallet / credit-card / building-columns / calendar / tag / mug-hot / gas-pump`
   `chart-pie / arrows-rotate / cloud / download / gear / bell / magnifying-glass`
   `chevron-left / chevron-right / filter / share-nodes / delete-left / arrow-right-arrow-left`
