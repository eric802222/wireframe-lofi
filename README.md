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
> 顏色一律封印：**wireframe 全灰階**（色彩=保真度的函數，見下 §6）。不寫 `bg-red-500` 之類視覺 class，
> 也沒有節點級顏色屬性。

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

官方範例已納入 `examples/`，入口與完整指令見 [`examples/README.md`](examples/README.md)。
`examples/layouts/` 與 `examples/components/` 是實際共用檔案；語法說明中的 `layouts/x`、`components/x` 等未指向範例的名稱是示意路徑。

### lint 與錯誤診斷

```bash
python3 wfyaml.py lint examples/*.wf.yaml  # exit 0/1/2 = clean/warning/error
python3 wfyaml.py --traceback --no-lint bad.wf.yaml
WF_TRACEBACK=1 ./render.sh bad.wf.yaml
```

一般 render 先跑 lint gate（compiler 可用 `--no-lint` 略過）。lint 共用 renderer 的 items／leaf 驗證，
並遞迴檢查 extends/embed、相對路徑、循環引用、component content/placeholder 與 widget.body。
引用檔案錯誤會列出該檔與 YAML path。CLI 的作者錯誤預設只顯示來源、位置與修正提示；
`--traceback` 或 `WF_TRACEBACK=1` 保留完整 traceback，非預期程式例外仍顯示 traceback。

### `--bundle` 單檔原型（走動線）

`--bundle` 把多張畫面（含各 routes）併成單一 `prototype.html`：左側 nav 分組 + `:target` 切頁（**零 JS**），
`to:` 連結自動改寫成頁內錨點 → 點著走完整動線。交付時只給一個 `.html` 即可跨平台點擊探索。

若預覽宿主（例如 artifact iframe）攔截同文件錨點，可改用 radio／label 導覽：

```bash
./render.sh --bundle-standalone examples/*.wf.yaml
python3 wfyaml.py --bundle-standalone --debug examples/*.wf.yaml
```

`--bundle-standalone` 已包含 bundle，不必再加 `--bundle`。頁籤和頁內 `to:` 使用原生 radio，
切頁不改 URL、一般產物仍零 JS；真正外部連結保持 `<a>`。Tab 聚焦選頁控制項，方向鍵或 Space 選頁，
焦點和目前頁面會顯示在頁籤上。這個模式不支援 URL hash deep link，也不把切頁記入瀏覽器上一頁／下一頁歷史；
需要 deep link 時使用預設 `--bundle`。`--debug` 的評審功能仍使用 JavaScript。

兩種模式在 860px 以下都改為頂部可橫向捲動頁籤；畫布置中，固定 viewport 不縮小，
比螢幕寬時可在畫布區橫向捲動。

頁面可用 render metadata 控制 nav 顯示與分組，與 `viewport` 同層，不會產生 UI 節點：

```yaml
title: 旅途首頁
group: 旅途中
viewport: 390x844
body: [ { text: 行程內容 } ]
```

`title` 未指定時沿用檔名；`group` 未指定時不加入具名群組。群組按輸入中的首次出現排序，
組內保留輸入順序（無獨立 order 欄位）。有 routes 時，title 是頁面標題，子連結仍顯示既有 route label。
改 title/group 不改檔名、頁面 id、輸出檔名或 `to:`；動線仍使用穩定檔名，例如 `to: phone-home`。

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
viewport: 1100x          # 視窗：1100x / 1200x900 / x800（皆「參考」寬高）
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
viewport: 1100x
body:
  - row: between
    box: true
    items: [ "text.title: {{title}}", { button: 關閉, to: list } ]
  - slot: main                  # ← 洞，由頁面 slots.main 填入
  - row: end
    items: [ - slot: actions ]
```

> 對稱：layout `- slot: name`（單數，挖洞）↔ 頁面 `slots: { name: ... }`（複數，填洞）。

### 2. embed（複用區塊 / component）

任何節點位置都能 `embed`。`with` 選填（`{{param}}` 只替換葉子字串）、子項/`as` 選填：

```yaml
- embed: components/quote-lines                      # 靜態引入
- embed: components/option-row
  with: { label: B, price: "¥6,120,000" }              # 帶參數
- embed: components/side-panel
  as: placeholder                                      # 降階為佔位塊（聚焦討論時把非重點收起來）
- embed: components/status-banner                    # 省略 as → 繼承當前頁面路由(stage/state)
- embed: components/status-banner
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
| `grow: true`（掛容器或 leaf） | 吃掉父主軸剩餘空間（主體區撐滿→footer 置底；leaf 等分→等寬按鈕列）。grid 欄軌用 `grow` 同義 |
| `gap: md` / `padding: lg` | **語義**間距（見下），非 `gap-4` |
| `scroll: true`（配 `grow:`）或 `scroll: sm/md/lg/xl`；`scroll-x:` 對稱 | 捲動區：HTML 真捲軸（封頂 + overflow）；PNG 全展開 + 畫捲軸示意（只看圖也看得到全部內容並知道會捲） |

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

> **置底/固定視窗**：`viewport` 設高度(如 `820x520`)時，body 會撐滿該高 → 用 `spacer:` 或 `col` + `justify:end|between` 可把 footer/動作列釘到底。

### 3.1 手機 app shell：頁首常駐、中間可捲、底部常駐

`spacer`／`justify: end` 適合短內容的置底；長內容需讓 main 自己捲動。
官方 [`examples/layouts/phone.wf.yaml`](examples/layouts/phone.wf.yaml) 用 `grow: true` 分配剩餘高度，
`scroll: true` 讓 main 獨立捲動；header/footer 留在同一個固定高度 viewport 內。

```yaml
# 使用 examples/layouts/phone；放在 examples/ 下
extends: layouts/phone
with: { title: 我的行程 }
slots:
  main:
    - text: 今日內容
  footer:
    - button: 完成
```

短、長內容的可執行頁面分別是 `examples/phone-home.wf.yaml`、`examples/phone-long.wf.yaml`。
HTML 在 `390x844` 中只有 main 捲動；PNG/SVG 的 show-all 模式解除固定高度，展開全部內容並畫捲軸示意。

**間距用語義 scale**（可 theme，非數字階）：`none` / `sm` / `md`(**預設**) / `lg` / `xl`。`gap`（子項間距）與 `box` 內距
都預設 `md`，用 `gap:`/`padding:` 覆寫（`box` 內距亦吃 `padding:`）。
> **間距=節奏（語義刻度）、寬度=關係（填滿/依內容/比例）**——間距是設計系統節奏核心，語義名換 theme 只改一張對照表；寬度只有相對容器才有意義，故走關係型而非另發明一套刻度。

**專案 semantic token（選配，`wf.tokens.yaml`）**：想用**用途**命名而非大小時，在來源夾放 `wf.tokens.yaml`：

```yaml
gap: { section: lg, list: sm }     # 用途名 → 引用內建刻度
```
→ 即可寫 `gap: section`（意圖自明、一處改全站變、可對齊某產品的設計系統）。**純選配**：沒有此檔就用內建 `none/sm/md/lg/xl`；未知名 → error（fail-fast）。詳見 `DISCUSSION.md`「semantic token」。

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
| `status.badge: BETA` | 方角標籤 |
| `alert: 已送出待審` | UI 警示訊息 |
| `icon: check` | 圖示（`{set: fa\|lu, name}`；混用 Font Awesome / Lucide） |
| `divider:` | 分隔線 |
| `image: 主圖` | 佔位圖（map `{label, w, h, ratio}`；`ratio: 16/9`） |
| `tabs: {active: 報價, items: [...]}` | 分頁列 |

**行內 markdown**（在任一 text 值內）：`**粗**` / `*斜*` / `~~刪除線~~` / `[字](目標)`。

### 4.1 YAML 引號與未定值

文字值含 `[ ] , : #` 時，建議為**整個值加引號**，尤其在 flow sequence 中。
方括號可能造成解析失敗；逗號可能拆成兩項、冒號配空白可能產生 mapping、空白後的井號可能開始註解，
後三者可能沒有 error 卻改變內容。這是保守寫作建議，不表示所有情境都必須加引號。

```yaml
- row: ["11:12", "照片 ×3 · [N] MB", "檢視, 刪除", "備註: 待定", "編號 #1"]
```

文字中的 `[金額]`、`[旅伴]`、`[出發日]` 等未定值顯示灰字與虛線底線；按每次出現統計，
重複名稱算多次。lint 列出每份來源檔的未定值數（包含文字參數 with），引用同一 component 多次只統計來源一次，
不按 layout/component 展開後重複計數，也不計 title/group、URL 等 metadata。統計是 info，不增加 warning、不改 exit code。
Markdown 連結、checkbox `[x]`／`[ ]` 及 YAML list 不當作未定值；`\[字面值]` 可避開辨識（雙引號 YAML 中需寫 `\\[字面值]`）。
這與 component 的 `placeholder:`／`as: placeholder` 降階佔位功能獨立。

### 4.2 多人成員與地圖示意

```yaml
- avatars: { items: [我, 伴, 友, 家], max: 3 }  # 前三個 avatar +「+1」
- map: { label: 今日路線, markers: [飯店, 車站], can: [pan, zoom, markers] }
```

`avatars.items` 接 avatar 簡寫文字或 `{label, size}`；`max` 是顯示成員上限（正整數，預設 3），
不包含額外的 `+N` 溢出標記。空集合顯示空群組，既有 `avatar` 行為不變。
`map` 純量可簡寫地圖名稱；具名版沿用 widget 的能力 chips 與「◫ 示意」標記，
標記是文字，預設 can 為 pan/zoom/markers，沒有地圖服務或真實拖曳縮放。時間軸、曲線等仍用 widget 的 is/can/body 表達。

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
  row: [ icon: check, text: 已儲存 ]
```

- **錨定對象與常駐/暫時由「放在樹的哪裡」決定**：放頁面根=錨畫面/每頁常駐(機器人)；放某 `box` 內=錨那張卡；放某 `state` 的 `overlay` slot=按動線開關的暫時浮層。
- **開關動線**：dialog 開啟 = 某個 state；`to: '#confirm'` 進入、`to: '#'` 關閉，複用既有 `to:`/routes。
**具名語義 token（已內建，可攜地板）**：`dialog` / `drawer` / `sheet` / `toast` / `loading` —— 直接寫角色、免拼原語：

```yaml
- loading: [ row: [ icon: reload, text: 載入中… ] ]     # = pin:center + modal + layer:top
- toast:   [ row: [ icon: check,  text: 已儲存 ] ]       # = pin:bottom-right + layer:notify
- drawer:  [ text.heading: 篩選, row: [ spacer, { button: 套用 } ] ]   # = pin:right + modal
```
- 每個角色 = **組合 pin/modal/layer 的 semantic token**；node 上顯式 `pin`/`layer` 可覆寫其預設（如 `drawer` + `pin: left`）。
- **專案可覆寫/加角色**：`wf.tokens.yaml` 的 `overlay:` 段（把 `drawer` 改左、或自定 `banner`）。沒定義 → 用內建；地基永遠是 `pin`/`modal`/`layer` 原語，不因新樣式擴充工具語彙。

### 6. 色彩 = 保真度的函數（`tone` 已移除）

wireframe 階段**全灰階**，沒有節點級顏色屬性（`tone:` 已於 2026-07-08 移除，寫了會 error）。三種需求各歸其層：

| 需求 | 歸宿 |
|------|------|
| 產品狀態色（危險紅/成功綠） | `--mockup <theme.yaml>` theme binding（mockup 才上色） |
| 評審「看這裡」 | 標註面 `spotlight` / story `badge`（本來就有色、明顯非 UI） |
| 語義強調 | `text.strong` / `status.strong`（灰階權重） |

資訊不靠色彩傳達（「+32,000 / -120」符號、「超支 900」文字已足）——靠色才能傳達＝設計壞味道，wireframe 階段逼出此檢查是 feature。

### 7. 標註面：Demo 標註（可剝離，明顯是註記非 UI）

與 產品面（產品語義）**分層**：標註面 是疊在 UI 上「給觀眾看」的指引，
`render.sh` 會另出一份 `.clean.png`（剝離所有 標註面）。

**`note:`** — 右側 gutter 便利貼 + 物件小標。`ref` **作者自編**（靜態、外部可穩定參照）：

```yaml
- embed: components/quote-lines
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

## 詞彙表（生成）

下表由 `python3 tools/update_docs.py` 從 `wfyaml.py` 的角色註冊表生成，不手改。
新增角色或節點標註時只改程式碼，這裡與 `wfyaml.py list --ring 0`、`AGENTS.md`、`SKILL.md`
一起更新；漏跑會被 `tests/test_docs_generated.py` 擋下。

<!-- BEGIN GENERATED: vocabulary -->
<!-- 由 `python3 tools/update_docs.py` 從 wfyaml.py 的註冊表生成，請勿手改 -->

### Grammar 關鍵字

`body` / `content` / `extends` / `group` / `placeholder` / `routes` / `slots` / `title` / `viewport` / `with`

### 結構單元類型

| 詞彙 | 說明 |
| --- | --- |
| `page` | 一個畫面 |
| `layout` | 可被 extends 的版型 |
| `component` | 可被 embed 的片段 |
| `widget` | 有狀態的複合元件 |

### Container

| 詞彙 | 說明 |
| --- | --- |
| `row` | 橫向排列 |
| `col` | 縱向排列 |
| `grid` | 網格 |
| `box` | 有邊框的容器，同時是浮層的錨點 |
| `section` | 有名字的一段 |
| `dialog` | overlay sugar → pin: center / modal: True / layer: overlay |
| `drawer` | overlay sugar → pin: right / modal: True / layer: overlay |
| `sheet` | overlay sugar → pin: bottom / modal: True / layer: overlay |
| `toast` | overlay sugar → pin: bottom-right / layer: notify |
| `loading` | overlay sugar → pin: center / modal: True / layer: top |

### Leaf 元件 · 文字

| 詞彙 | 說明 |
| --- | --- |
| `text.title` | 畫面主標題 |
| `text.heading` | 段落標題 |
| `text.label` | 表單欄位的標籤 |
| `text.strong` | 語義強調（不是視覺加粗） |
| `text.hint` | 次要說明、輔助文字 |
| `text` | 一般內文 |

### Leaf 元件 · 表單

| 詞彙 | 說明 |
| --- | --- |
| `input` | 文字輸入框（真 <input>，零 JS） |
| `select` | 下拉選擇 |
| `button` | 動作按鈕；帶 to: 即為站內導航 |
| `checkbox` | 多選；綁的是畫出來的控制項，不含旁邊文字 |
| `radio` | 單選 |

### Leaf 元件 · 狀態

| 詞彙 | 說明 |
| --- | --- |
| `status.badge` | 小圓標：數量、角標 |
| `status.muted` | 弱化狀態標籤 |
| `status.strong` | 強調狀態標籤 |
| `status` | 一般狀態標籤 |
| `alert` | 提示區塊（圖示＋文字） |

### Leaf 元件 · 其他

| 詞彙 | 說明 |
| --- | --- |
| `icon` | 圖示（FA / Lucide canonical 名） |
| `divider` | 分隔線 |
| `tabs` | 分頁切換列 |
| `image` | 圖片佔位；ratio 指定長寬比 |
| `link` | 站外真連結；to: 原樣輸出，站內跳頁請用 button |
| `progress` | 進度條 |
| `avatar` | 單一頭像 |
| `avatars` | 一組疊加頭像 |
| `map` | 地圖佔位 |

### 節點標註

| 詞彙 | 說明 |
| --- | --- |
| `name` | 語義身份：theme 綁它、debug 定位靠它 |
| `to` | 動線：跳到哪個畫面 |
| `note` | 標註面：右側邊註（可剝離） |
| `spotlight` | 標註面：聚焦標記（focus / new / change / click） |
| `span` | grid 內跨幾欄 |
| `grow` | 吃掉剩餘空間（col 內是長高） |
| `pin` | 浮層錨點方位；錨在最近的 box/root，父容器要有 box: true |
| `modal` | 浮層擋住後面（scrim + inert） |
| `layer` | 浮層的 z 帶（base / overlay / notify / top） |
| `ui-state` | 顯示態（selected / disabled / hover / focus / active） |
| `max-lines` | 最多幾行，超過截斷；只能用在文字節點 |
| `wrap` | false = 不換行、單行省略；不能與 max-lines 並用 |

### 綁不到 theme 的角色

| 詞彙 | 說明 |
| --- | --- |
| `alert` | alert 是容器型輸出（圖示＋文字），沒有單一元素可綁；要改外觀請綁 status / text 家族 |
| `tabs` | tabs 渲染成一組 .wf-tab，綁單一 tab 請用 tab / tab.active |
| `map` | map 是佔位示意，產品階段會被真地圖取代，綁它沒有意義 |

<!-- END GENERATED: vocabulary -->

## 目錄結構

```
wireframe-yaml/
  wfyaml.py        compiler：YAML → HTML；routes 多輸出、狀態感元件、標註面、bundle、debug
  flowmap.py       掃 to: 連結 → 畫面動線圖（graphviz；render.sh 自動呼叫）
  render.sh        .wf.yaml → .html + .png + .svg + .clean.png + flowmap；--bundle / --debug
  watch.sh         監看 .wf.yaml 變動自動重渲（含 embed/layout 依賴）
  assets/          自帶封印資產：wf.css + fa-icons/lucide-icons.json.gz（→ 可整包帶走）
  examples/        範例（deal-detail 單頁 / deal-routes 路由 + layouts/ components/）
  DISCUSSION.md    設計討論筆記（決策鏈與待議）
  README.md
```

## 現況（prototype v0.1）與待補

**已實作**：獨立頁 / extends+slots / embed+with / **狀態感元件（`when:` 過濾 + `as: placeholder|{stage,state}` + 繼承當前路由）** / **routes 多輸出（各路由可定址 .html + stagebar + single-URL 連結）** / row-col-grid（+box/對齊/spacer/span/gap/padding/Tailwind 欄寬）/ 葉子全表 / 行內 markdown / checkbox-radio / to-link / name / 標註面 note+spotlight / 乾淨版剝離 / flowmap / **`--bundle` 單檔原型（走動線）** / **`--debug` 評審回饋（模式切換 + 檔名+路徑定位 + 跨頁匯出）** / 零 JS（一般輸出）。

**待補**（見 `DISCUSSION.md`）：
- **葉子兩種寫法擇一**（`"role: 值"` 字串 vs `{role: 值}` dict）+ README 明講（消歧義）。
- flow PDF；`table` / `textarea` 等葉子。

## 依賴備忘

### Theme：tokens 是物理值，bindings 是語義名

```yaml
# examples/themes/inverse.yaml 的精簡形式
tokens:
  color: { inverse: "#ffffff" }
  radius: { lg: 16px }
bindings:
  box: { background: inverse, text: ink, radius: lg }
```

`tokens.radius.lg` 收 CSS 值；`bindings.box.radius` 收 none/sm/md/lg/pill/full 等語義名。
不要把 `16px` 寫進 bindings；錯誤提示會指出 binding 路徑與應移到 tokens 的修正方式。

除 `button`／`input`／`box` 等容器外，theme binding 也可直接使用既有 leaf role：
`checkbox`、`radio`、`progress`、`progress.fill`、`avatar`、`avatars`、`icon`、`image`、
`divider`、`widget`、`tab`、`tab.active`、`link`。它們沿用同一組 background / border /
radius / shadow / padding / text 等屬性；不需要另記 class 名。`widget` 綁定不會影響
「◫ 示意」標記，讓 mockup 仍清楚保留示意元件的邊界。
`background: inverse` 與 `text: inverse` 共用 `--wf-inverse`（未指定時 fallback 白色 `#ffffff`）；
表面背景也可用既有 surface／surface-alt／surface-sunk。
text 的 surface 系列未新增。theme 只在 `--mockup` 生效，一般 wireframe 仍使用既有灰階元件。

```bash
python3 wfyaml.py --mockup examples/themes/inverse.yaml examples/deal-detail.wf.yaml
python3 -m unittest discover -s tests -v
python3 tests/check_browser.py  # 另需 playwright + chromium
```

**自含、可整包帶走**：runtime 只需 `python3 + pyyaml`（截圖另需 `playwright`、動線圖需 `graphviz dot`），
封印 CSS 與 icon 圖庫都 vendored 在 `assets/`，**無外部依賴**。
### Mockup 素材綁定

素材只在 theme 定義，結構檔使用穩定的 `name:`，不含素材路徑。相同 label 不會自動選圖。

```yaml
# themes/tripbook.yaml；路徑相對這個 theme 檔
assets:
  cover-kyoto: tripbook.assets/covers/kyoto.jpg
  stamp: tripbook.assets/icons/stamp.svg
bindings:
  封面: {image: cover-kyoto, fit: cover}
  郵票圖示: {icon: stamp, text: primary}
```

```yaml
# 畫面結構
body:
  - image: {label: 京都 · 封面, ratio: 3/4}
    name: 封面
  - icon: star
    name: 郵票圖示
```

`image` 素材綁定適用 image 與 avatar；`icon` 綁定只接 SVG。`fit` 為 cover/contain，預設 contain。
保留 image 的 ratio/w/h 與 avatar 的 size。素材只依具名 binding 生效，role 綁定仍用於樣式。
一般線框仍顯示原本佔位。PNG/JPEG/GIF/WebP 與圖形型 SVG 皆內嵌，單頁及 bundle 不依賴外部檔案。
SVG 圖示的填色／筆畫使用 currentColor（保留 none）；白名單限於基本圖形、群組、title/desc，
會移除 script、外部引用、foreignObject、style、漸層／濾鏡等。複雜 SVG 請先轉點陣圖。

缺檔或無法解析的 SVG 回退佔位並 warning；未定義素材名、格式或 fit 是 schema error。
單素材超過 300KiB、已載入素材或產物重複內嵌總量超過 5MiB 會提醒，仍可 render。
`lint --mockup` 包含素材 warning（exit 1）；一般 lint 不讀 theme。debug 的來源路徑不變。

```bash
python3 wfyaml.py lint --mockup examples/themes/gallery.yaml examples/gallery.wf.yaml
python3 wfyaml.py --bundle-standalone --mockup examples/themes/gallery.yaml examples/gallery.wf.yaml
```

### Kit：專案自己的元件型別

`kit/components.yaml` 只宣告專案詞彙，不放樣式。工具會自動讀取頁面旁的這個路徑，也可用
`--kit <file>` 明確選擇；因此換 kit 時，缺少的型別會在 lint 直接報錯。

```yaml
components:
  jumbo-button: {of: button}
  stamp-card:
    props: [place, time]
    states: [done, next, todo]
    content:
      - col: [{icon: star}, "text.hint: {{time}}", "text.strong: {{place}}"]
        box: true
```

`of` 只能繼承內建 leaf；省略 `of` 時必須提供 `content`。組合只有有限的 `{{prop}}` 字串替換，
沒有 if / each / 運算。畫面可在任何 items 位置使用型別：

```yaml
- jumbo-button: {text: 開始冒險, to: next}
- stamp-card: {place: 渡月橋, time: "11:08", state: next}
```

樣式只放 theme 的 `components`，kit 內出現 style 等未知欄位會 error。theme 的 CSS 值必須引用
tokens；字面尺寸、色碼與非零數字會 error。`0`、`none`、`transparent`、`inherit`、
`currentColor`、`auto` 可作結構值。state 必須先由 kit 宣告：

```yaml
tokens:
  color: {surface: '#fff', brand-soft: '#ede9fe'}
  space: {md: 14px, xl: 50px}
components:
  jumbo-button: {padding: '{space.xl}'}
  stamp-card:
    background: '{color.surface}'
    state.next: {box-shadow: '0 0 0 {space.md} {color.brand-soft}'}
```

#### Canvas：一組被定位的元件實例

`of: canvas` 是不綁領域的複合基底：一個底、一組有 state 的定位元件，以及可省略的關聯線。
kit 決定底的種類、item 元件、link 結構與 state 值域；畫面只給內容和 0–1 相對座標；theme
才決定外觀。地圖、座位表、流程板、商品熱點都使用同一個基底。

```yaml
# kit/components.yaml
components:
  trip-map:
    of: canvas
    base: {asset: arashiyama, ratio: 4/3}
    item: {use: stamp-card}
    link: {shape: smooth}        # straight | smooth；可加 arrow: true
    states: [done, next, todo]

# page.wf.yaml
- trip-map:
    items:
      - {place: 竹林小徑, at: [0.22, 0.83], state: done, time: "08:40"}
      - {place: 渡月橋, at: [0.50, 0.42], state: next, to: c3-arrive, time: "11:00"}
    link: [竹林小徑, 渡月橋]
```

`base` 恰選 `asset`、`grid: true`、`blank: true` 之一；後兩者不需要 theme 素材。`at` 可省略，
但 kit 的 `base.anchors` 必須能以 item 的 `id` 或某個語義 prop 值找到座標。item 一律展開成
`item.use` 指定的 kit 元件，所以同一張 `stamp-card` 可在 canvas 與列表復用；`to` 包在該 item 上。
畫面的 `link` 以 `id` 或 prop 值指向 item，省略就不畫線。編譯器只為 link 產生 SVG path／箭頭，
不替 item 畫 circle/path。asset 底在 mockup theme 的 `assets:` 綁定：

```yaml
assets: {arashiyama: trip.assets/arashiyama.svg}
tokens:
  color: {brand: '#7c3aed', brand-soft: '#ede9fe'}
  stroke: {md: 3px, dash: '8 6'}
  space: {md: 14px}
components:
  trip-map:
    link: {stroke: '{color.brand}', stroke-width: '{stroke.md}', dash: true}
    item.state.next: {box-shadow: '0 0 0 {space.md} {color.brand-soft}'}
```

`dash: true` 是結構開關，虛線節奏必須由 `tokens.stroke.dash` 提供。沒有 `--mockup` 時 canvas
使用素材名佔位與灰階 link；缺素材檔時沿用 assets warning 並退回佔位。完整地圖範例見
`examples/kit-demo/`。領域別名（例如 stops/route）留待後續；目前編譯器只認 items/link。

不加 mockup 時，特化元件退回原 leaf 灰階外觀，組合元件使用灰階結構。兩者都輸出
`data-wf-role`，debug 的 invocation path 維持穩定。`--strict-kit` 會禁止頁面直接使用 leaf、widget
或裸露 `box`，只留下 kit 型別與 row/col/grid 等基本排版。lint 多檔時若相同容器結構出現在至少
三個畫面，會輸出不影響 exit code 的抽取提示。

```bash
python3 wfyaml.py lint --kit kit/components.yaml --strict-kit pages/*.wf.yaml
```

> **Theming hook**：圓角/間距/字體走 `assets/wf.css` `:root` 的 CSS 變數——圓角 `--wf-radius`/`--wf-radius-pill`、間距 `--wf-space-sm/md/lg`、字體 `--wf-font`/`--wf-font-size`/`--wf-h1|h2|h3`、頁框 `--wf-page-border`/`--wf-page-pad`。改一處即全域生效；覆蓋 `:root` 即成一個 theme（產品色走 `--mockup <theme.yaml>` binding）。
> 要更新視覺改 `assets/wf.css`；要更新圖庫用 Font Awesome / Lucide 來源重新打包後覆蓋 `assets/*.json.gz`。
