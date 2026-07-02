# wireframe-lofi

> **語義化 YAML → 低保真、零 JS 的 wireframe（wireframe-as-code）。** 用來快速 demo 與快速討論 UI/UX 結構與動線。

用**文字（YAML）**寫線框：可版控、可 diff、人與 LLM 都能讀寫。
封印 CSS 與 icon 圖庫已 **vendored 進 `assets/`**（`wf.css` + `*-icons.json.gz`）→ **自含、可整包帶走、無外部依賴**。

---

## 為什麼是 YAML

不想從頭訂一套文字語法 + 手刻 parser（那是 bug 溫床）。改用 YAML 後：

- **結構解析全交給 `yaml.safe_load`**（久經考驗），本專案**一行結構 parser 都不寫**。
- 葉子是**語義 key**（`text.title` / `button` / `status`…），dict 分派渲染，非遞迴解析。
- 產物是**人機共讀媒介**：key 命名「意涵」，LLM 可直接生成/批改/回溯 spec，不必從視覺反推。

## 兩根北極星（設計紅線）

1. **低保真、但結構/動線明確** — 專注「元件在哪、動線怎走、功能是什麼」。視覺被封印。
2. **語義優先** — YAML key 命名**意涵/權重/角色**，不是視覺。作者**不寫**字級/字型/顏色/寬度；
   視覺全由封印 renderer 獨佔。

> **尺寸皆為「參考」非「規格」。** YAML 裡的寬度（`w-24` 等 Tailwind token）只表達「大約這麼寬」的
> 意圖，**不是實作綁定**——實作要用 flex / grid / table 都行。此約定屬**閱讀者認知**，請據此理解產物。
> 顏色一律封印，只用語義 `tone`/`severity`（見下），不寫 `bg-red-500` 之類視覺 class。

---

## 快速開始

```bash
./render.sh examples/deal-detail.wf.yaml
# → deal-detail.html（自帶 CSS、零 <script>）
#   deal-detail.png（截圖 = 標註版，含 標註面）
#   deal-detail.svg（向量版，foreignObject 包 XHTML；瀏覽器渲染完美，librsvg/GitHub 等不支援 foreignObject 的 viewer 會空白）
#   deal-detail.clean.png（剝離 標註面 的乾淨 UI 版）

python3 wfyaml.py examples/deal-detail.wf.yaml    # 只出 .html（不截圖）

# --bundle：把多檔併成單一可點擊 prototype.html（左 nav + 走動線）。加 --debug 可邊走邊標註。
./render.sh --bundle examples/*.wf.yaml            # → prototype.html（零 JS 可點原型）
./render.sh --bundle --debug examples/*.wf.yaml    # → prototype.debug.html（走動線 + 跨頁標註）

# --debug：單頁評審回饋 → 出 .debug.html（可點擊註記）。一般輸出不受影響、仍零 JS。
./render.sh --debug examples/deal-detail.wf.yaml
python3 wfyaml.py --debug examples/deal-detail.wf.yaml
```

需求：`python3` + `pyyaml` + `playwright`（截圖用；`pip3 install pyyaml playwright && python3 -m playwright install chromium`）。
CJK 對齊靠系統 `Sarasa Mono TC`，無則 fallback monospace（不影響 layout）。

### `--bundle` 單檔原型（走動線）

`--bundle` 把多張畫面（含各 routes）併成單一 `prototype.html`：左側 nav 分組 + `:target` 切頁（**零 JS**），
`to:` 連結自動改寫成頁內錨點 → 點著走完整動線。交付時只給一個 `.html` 即可跨平台點擊探索。

### `--debug` 評審回饋迴路

瀏覽器開 debug 產物 → 右上工具列切「**模式:註記**」→ **點任一元素**寫修改建議（存 localStorage、reload 存活）
→「**匯出**」複製清單貼回給 LLM 一次改 YAML。「模式:瀏覽」時點擊照常跳轉（可走動線）。

- **id = 來源檔 + YAML 路徑**：匯出按**檔**分組，每條 `[路徑] role "內容快照" → 建議`，例：
  `[routes[1].slots.actions[0]] wf-tag "待核准" → 移除`。路徑用索引精準鎖定（跨 component/layout/slot 皆帶正確來源檔），LLM 不需猜。
- **`--bundle --debug`**：整組畫面一份 prototype、**共用一份 localStorage** → 走動線邊標註、**一次匯出全部頁**（最貼「評審整條流程」）。
- 註記**不渲染、不進 YAML**（有別於 標註面 作者標註），純評審回饋。debug/bundle 注入 JS →
  **僅這些模式非零 JS，一般輸出（`.html`/`.png`）維持零 `<script>`**。

---

## 語法

### 1. 頁面結構

一份 `.wf.yaml` 是一個頁面。三種形態，心智模型一致（`body` 是通用內容容器）：

```yaml
# (a) 獨立頁：直接寫 body
canvas: 1100x            # 畫布：1100x / 1200x900 / x800（皆「參考」寬高）
body:
  - ...

# (b) 繼承 layout：extends + 填 slots
extends: layouts/detail-page
with: { title: 報價單 Q-1 }     # 傳給 layout 的純量參數（{{title}}）
slots:                          # 填 layout 挖的洞
  main: [ ... ]
  actions: [ ... ]
```

layout 檔本身就是一個 `body` + 挖洞（`- slot: 名稱`）：

```yaml
# layouts/detail-page.wf.yaml
canvas: 1100x
body:
  - row: between
    box: true
    items: [ "text.title: {{title}}", { button: 關閉, to: list } ]
  - slot: main                  # ← 洞，由頁面 slots.main 填入
  - row: end
    items: [ - slot: actions ]
```

> 對稱：layout `- slot: name`（單數，挖洞）↔ 頁面 `slots: { name: ... }`（複數，填洞）。

### 2. include（複用區塊 / component）

任何節點位置都能 `include`。`with` 選填（`{{param}}` 只替換葉子字串）、子項/`as` 選填：

```yaml
- include: components/quote-lines                      # 靜態引入
- include: components/option-row
  with: { label: B, price: "¥6,120,000" }              # 帶參數
- include: components/side-panel
  as: placeholder                                      # 降階為佔位塊（聚焦討論時把非重點收起來）
- include: components/status-banner                    # 省略 as → 繼承當前頁面路由(stage/state)
- include: components/status-banner
  as: { stage: approved }                              # 明確 pin 某狀態變體
```

**狀態感元件**：元件內節點可帶 `when: {stage, state}`（多 key = AND、值為 list = OR、無 when = 恆顯），
依「當前路由 ctx」過濾。ctx 來自：`as: {stage, state}`（明確）或繼承所在頁面/路由（省略 as）：

```yaml
# components/status-banner.wf.yaml
content:
  - when: { state: pending }
    alert: 已送出，等待主管核准
  - when: { stage: approved }
    status.strong: 已核准
```

component 檔可定義 `content:`（完整）與 `placeholder:`（降階佔位）：

```yaml
# components/quote-lines.wf.yaml
placeholder: [ { box: true, items: [ "text.hint: 報價明細（略）" ] } ]
content:
  - box: 報價明細
    col: [ ... ]
```

解析路徑：同夾 → `components/` `layouts/` `partials/` 子夾（支援多層路徑）。

### 3. 空間排版（自由）

一切都是 block；選一個方向（`row`/`col`/`grid`），疊屬性：

| 寫法 | 說明 |
|------|------|
| `col: [a, b]` / `row: [a, b]` | 直/橫排；值為 list 即 items 簡寫 |
| `row: between` / `justify: between` | 主軸對齊 `between`/`end`/`start`/`center`/`around`（`row` 主軸=橫；`col` 主軸=直，可置底/頭尾撐開） |
| `align: top` | 交錯軸對齊：`center`(預設)/`top`/`bottom`/`baseline`/`stretch` |
| `grid: 3` / `grid: [w-24, grow, w-24]` | N 等欄 / 指定欄寬（見下） |
| 子項 `span: 2` | grid 跨欄 |
| `box: true` | 外框（只畫框；要標題請用 `text.title`/`text.heading`，語義化） |
| `spacer:`（當一個 item） | 不對稱推擠（撐開剩餘） |
| `grow: true`（掛容器上） | 該容器吃掉父主軸剩餘空間（主體區撐滿→footer 自然置底；比 spacer 更語義）。grid 欄軌用 `grow` 同義 |
| `gap: md` / `padding: lg` | **語義**間距（見下），非 `gap-4` |
| `scroll: h-48` / `scroll-x: true` | 捲動區：HTML 真捲軸（封頂 + overflow）；PNG 全展開 + 畫捲軸示意（只看圖也看得到全部內容並知道會捲） |

**欄寬是「關係」，不是「量值」**（`grid` 的 track）。正道是關係型 —— 隨容器縮放、合低保真：

| 正道（關係型） | 意涵 |
|------|------|
| `grow`（撐滿剩餘） | 與節點屬性 `grow: true` **同一個字、同一心智模型**。別名 `fill`/`w-full`/`flex-1`（`flex-1` 是實作詞，建議用 `grow`） |
| `fit`（依內容） | 收到內容寬。別名 `w-auto`/`auto` |
| `60%` / `w-1/2`（比例） | 「約佔六成、置中」寫 `grid: [grow, 60%, grow]` —— 關係清楚、隨容器縮放，不必挑像素 |

> **逃生門**：`w-24`(=6rem)/`w-96`/`120px` 等**絕對量值會破壞低保真契約**（等於在寫視覺規格），僅真的必要時用。
> 慣用式 `grid: [w-40, grow]`（label gutter 固定 + 內容撐滿）仍合理 —— 固定的只是標籤欄；要避免的是把**內容本身**（如搜尋框）釘成 `w-96`。
> 例：`grid: [w-24, grow, w-24]` = 左右固定、中間撐開。

`input` 已內建預設寬上限（收窄，`select` 本就依內容）→ 多數情況 `input: 搜尋` 免寫寬度；要特別寬窄才用欄軌 `grow`/比例覆寫。表單欄位（`.wf-field` 內）仍填滿欄寬。

> **置底/固定視窗**：`canvas` 設高度(如 `820x520`)時，body 會撐滿該高 → 用 `spacer:` 或 `col` + `justify:end|between` 可把 footer/動作列釘到底。

**間距用語義 scale**（可 theme，非數字階）：`none` / `sm` / `md`(**預設**) / `lg`。`gap`（子項間距）與 `box` 內距
都預設 `md`，用 `gap:`/`padding:` 覆寫（`box` 內距亦吃 `padding:`）。
> **間距=節奏（語義刻度）、寬度=關係（填滿/依內容/比例）**——間距是設計系統節奏核心，語義名換 theme 只改一張對照表；寬度只有相對容器才有意義，故走關係型而非另發明一套刻度。

### 4. 葉子（語義角色，`role: 值`；scalar 或 map）

**文字家族**（權重/角色，非視覺）：

| `text:` 內文 · `text.title:` 主標題 · `text.heading:` 區段標題 · `text.label:` 欄位標籤 · `text.strong:` 強調 · `text.hint:` 附屬 |

**表單/元件**：

| 寫法 | 說明 |
|------|------|
| `input: 請輸入名稱` | 輸入框（值=placeholder；map `{placeholder, value}`） |
| `select: Admin` | 下拉（map `{text}`） |
| `button: 送出` | 按鈕；`button: {text, to, icon}`，有 `to` 即導航色 |
| `[x] 已同意` / `[ ] 未勾` | checkbox（markdown task-list） |
| `(x) 已選` / `( ) 未選` | radio |
| `status: 已核准` | 狀態 chip；`status.muted:` / `status.strong:` 分級 |
| `badge: BETA` | 方角標籤 |
| `alert: 已送出待審` | UI 警示訊息 |
| `icon: check` | 圖示（`{set: fa\|lu, name}`；混用 Font Awesome / Lucide） |
| `divider:` | 分隔線 |
| `image: 主圖` | 佔位圖（map `{label, w, h, ratio}`；`ratio: 16/9`） |
| `tabs: {active: 報價, items: [...]}` | 分頁列 |

**行內 markdown**（在任一 text 值內）：`**粗**` / `*斜*` / `~~刪除線~~` / `[字](目標)`。

### 5. 動線 / 連結

**語義軸：意圖由作者宣告，不靠 compiler 猜 URL 長相。** 目標帶 `to:` = wireframe 動線；否則 = 外部真連結。

| 寫法 | 說明 |
|------|------|
| `to: page`（掛元件/區塊上） | **wireframe 動線**：跳到另一頁/路由（`to: "deal#approving.pending"`）。依輸出（單頁/bundle/debug）自動改寫、進 flowmap |
| `[字](to:page#stage)`（句中行內） | **句中 inline 動線**：唯一能讓「一句話中的某個詞」可點跳頁的寫法。`to:` 前綴同 block `to:` 同義，依輸出改寫、進 flowmap |
| `[字](https://…)`（句中行內） | **外部真連結**：無 `to:` 前綴 → 原樣輸出（`mailto:`/`tel:`/`#` 同理，皆字面）；不進 flowmap |
| `link: {text, to}` | **產品裡真的超連結**（外部 URL）；原樣輸出、不進 flowmap |

### 5.5 `widget`：示意複雜元件（table / chart / rich editor…）

複雜元件（表格、圖表、富文字編輯器…）的**內部排法歸元件庫**，wireframe 不該釘死。`widget` 是一個**自我聲明示意的容器**：宣告它*能做什麼*、選填示意*大概長怎樣*，並**自帶「◫ 示意」標記** → 內部一律讀作代表性、非規格，實作依設計/元件庫。

讀成一句話：**`is`（是什麼）+ `can`（能做什麼）**。屬性巢狀在 widget 底下（同 `button`/`image` 這類 leaf）。

```yaml
# 純量簡寫：widget: 就是「是什麼」
- widget: 工單表格

# 輕量：宣告能力
- widget: { is: 工單表格, can: [search, filter, sort, paginate] }

# 豐富：示意內部排版 + 接 to: 走 prototype 動線（點列跳詳情）
- widget:
    is: 工單表格
    can: [search, filter, sort]
    body:
      - row: [狀態, 單號, 建立時間, 操作]                         # 示意欄頭
      - { row: [待處理, "#1024", 07-01, 檢視], to: ticket-detail }  # 點列跳頁
```

- `is`：這是什麼（純量簡寫即此值）；`can`：能做什麼 → chips；`body`：選填內部示意（複用 row/col/grid/leaf 與 `to:`）。
- demo = **視覺示意 + 可導覽**（零-JS 的 `to:` 動線；不做真資料過濾——那屬 mockup/實作）。
- 你可以畫得細、又不越權：內部走關係型低保真詞彙，且元件自我聲明是代表性的。**細節 ≠ 規定**。
- 通用 `widget` 接住所有（含沒見過的元件）；常用的 `table:`/`chart:` 具名版之後擴充，共用同一「宣告能力 + 自我聲明」基座。

### 5.6 浮層（dialog / drawer / toast / loading…）

浮層不用一種樣式一個關鍵字，而是**三個正交原語組合**——任何浮層(含未來沒名字的)都是它們的一種組合，**不需擴充語彙**：

| 原語 | 問 | 值 |
|------|------|------|
| `pin: <錨點>` | 錨在哪 | `center` / 邊 `top`·`bottom`·`left`·`right`（**邊=沿邊撐開**：左右=全高抽屜、上下=橫幅）/ 角 `top-right`·`bottom-right`… |
| `modal: true` | 擋不擋後面 | 加=遮罩壓暗+後面 inert；省=浮著不擋（toast/FAB）|
| `layer: <帶>` | 在哪一 z 層 | 封閉語意 scale `base < overlay < notify < top`；多數浮層免寫（預設 overlay）|

```yaml
# 載入中：置中 + 遮罩 + 最上層
- box: true
  pin: center
  modal: true
  layer: top
  row: [ icon: reload, text: 資料讀取中，請稍候… ]

# 右側抽屜(pin 邊緣值=沿邊撐滿) + 遮罩
- box: true
  pin: right
  modal: true
  col: [ text.heading: 篩選, "[ ] 進行中", "[ ] 已完成", row: [ spacer, { button: 套用 } ] ]

# toast：右下角、非 modal(不擋)、疊在 dialog 之上
- box: true
  pin: bottom-right
  layer: notify
  tone: success
  row: [ icon: check, text: 已儲存 ]
```

- **錨定對象與常駐/暫時由「放在樹的哪裡」決定**：放頁面根=錨畫面/每頁常駐(機器人)；放某 `box` 內=錨那張卡；放某 `state` 的 `overlay` slot=按動線開關的暫時浮層。
- **開關動線**：dialog 開啟 = 某個 state；`to: '#confirm'` 進入、`to: '#'` 關閉，複用既有 `to:`/routes。
- 具名糖(如 `drawer: right`)可之後加，展開成上面原語；地基是原語，永不因新樣式擴充語彙。

### 6. 語義色（產品面，UI 產品狀態）

`tone:`（或 `severity:`）掛在 block/leaf 上。**唯一被授權的顏色**，語義非視覺，其餘一律中性灰。
色票對映集中一處 → 可 theme。（集合與命名仍在收斂，見 `DISCUSSION.md`。）

```yaml
- box: 逾期提醒
  tone: danger              # feature / info / warn / danger / success / muted …
```

### 7. 標註面：Demo 標註（可剝離，明顯是註記非 UI）

與 產品面（產品語義）**分層**：標註面 是疊在 UI 上「給觀眾看」的指引，
`render.sh` 會另出一份 `.clean.png`（剝離所有 標註面）。

**`note:`** — 右側 gutter 便利貼 + 物件小標。`ref` **作者自編**（靜態、外部可穩定參照）：

```yaml
- include: components/quote-lines
  note: { ref: 1, text: 這區這版才新增 }      # 物件旁 [1]，右側對齊列出
```

**`spotlight:`** — 引導 overlay，enum 定種類；需文字/順序用 map：

```yaml
- box: 報價明細
  spotlight: focus                              # focus 螢光罩 / new 新功能 / change 改動 / click 點此
- button: { text: 送審, to: next }
  spotlight: { kind: click, text: 點此送審, step: 1 }   # step → ①②③ 操作序
```

### 8. `name:`（隱形語意標記）

掛在任何 block/leaf 上，寫入 `data-name`（**不渲染**、守低保真），供人/LLM 讀產物時辨識角色。
語意主要靠 **component 檔名 + `name:` + YAML 註解**長出來——**刻意不做內建角色清單**（header/section…）。

---

## 目錄結構

```
wireframe-yaml/
  wfyaml.py        compiler：YAML → HTML；routes 多輸出、狀態感元件、標註面、bundle、debug
  flowmap.py       掃 to: 連結 → 畫面動線圖（graphviz；render.sh 自動呼叫）
  render.sh        .wf.yaml → .html + .png + .svg + .clean.png + flowmap；--bundle / --debug
  watch.sh         監看 .wf.yaml 變動自動重渲（含 include/layout 依賴）
  assets/          自帶封印資產：wf.css + fa-icons/lucide-icons.json.gz（→ 可整包帶走）
  examples/        範例（deal-detail 單頁 / deal-routes 路由 + layouts/ components/）
  DISCUSSION.md    設計討論筆記（決策鏈與待議）
  README.md
```

## 現況（prototype v0.1）與待補

**已實作**：獨立頁 / extends+slots / include+with / **狀態感元件（`when:` 過濾 + `as: placeholder|{stage,state}` + 繼承當前路由）** / **routes 多輸出（各路由可定址 .html + stagebar + single-URL 連結）** / row-col-grid（+box/對齊/spacer/span/gap/padding/Tailwind 欄寬）/ 葉子全表 / 行內 markdown / checkbox-radio / to-link / tone / name / 標註面 note+spotlight / 乾淨版剝離 / flowmap / **`--bundle` 單檔原型（走動線）** / **`--debug` 評審回饋（模式切換 + 檔名+路徑定位 + 跨頁匯出）** / 零 JS（一般輸出）。

**待補**（見 `DISCUSSION.md`）：
- **產品面 色彩**：`tone` vs `severity` 命名、success/muted 歸屬未定。
- **葉子兩種寫法擇一**（`"role: 值"` 字串 vs `{role: 值}` dict）+ README 明講（消歧義）。
- flow PDF；`avatar` / `table` / `textarea` 等葉子。

## 依賴備忘

**自含、可整包帶走**：runtime 只需 `python3 + pyyaml`（截圖另需 `playwright`、動線圖需 `graphviz dot`），
封印 CSS 與 icon 圖庫都 vendored 在 `assets/`，**無外部依賴**。
> **Theming hook**：圓角/間距/字體走 `assets/wf.css` `:root` 的 CSS 變數——圓角 `--wf-radius`/`--wf-radius-pill`、間距 `--wf-space-sm/md/lg`、字體 `--wf-font`/`--wf-font-size`/`--wf-h1|h2|h3`、頁框 `--wf-page-border`/`--wf-page-pad`。改一處即全域生效；覆蓋 `:root` 即成一個 theme（色盤/tone 與 `--theme` 注入旗標尚未做）。
> 要更新視覺改 `assets/wf.css`；要更新圖庫用 Font Awesome / Lucide 來源重新打包後覆蓋 `assets/*.json.gz`。
