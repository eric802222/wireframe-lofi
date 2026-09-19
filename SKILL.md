---
description: wireframe-lofi：把語義化 YAML 編譯成低保真、零 JS 的 HTML/PNG wireframe（wireframe-as-code）。用來快速 demo 與討論 UI/UX 結構與動線。YAML key 命名意涵/角色（非視覺），支援 Blade 式 layout(extends/slots)、可複用 component(embed/as)、stage-state 路由多輸出(single-URL 動線)、標註面(spotlight/note，可剝離)、story 疊加(SAC)。適合結構清楚、可被人與 LLM 共讀的線框圖。
name: wireframe-lofi
triggers:
  - wireframe lofi
  - wireframe-lofi
  - wireframe as code
  - 低保真 wireframe
  - 語義 wireframe
  - render wf yaml
---

# wireframe-lofi

語義化 YAML → 低保真、零 JS wireframe（wireframe-as-code）。用文字（YAML）寫線框：可版控、可 diff、
人與 LLM 都能讀寫。封印 CSS/icon 已 vendored 進 `assets/`（**自含、可整包帶走、無外部依賴**）。
**完整語法見 [`README.md`](README.md)，設計脈絡見 [`DISCUSSION.md`](DISCUSSION.md)。**

## 何時用

要「快速 demo / 討論 UI/UX 結構與動線」時。專注**元件在哪、動線怎走、功能是什麼**；視覺被封印
（不寫字級/字型/顏色/寬度細節）。產物是人機共讀媒介，LLM 可直接生成/批改。

## 兩條紅線

1. **低保真**：只描述結構+動線+功能，視覺封印。尺寸皆為「參考」非規格（閱讀者認知）。
2. **語義優先**：YAML key 命名意涵/角色，不寫視覺。wireframe 全灰階（產品色走 `--mockup` theme；強調用 `text.strong`）。

## 用法

```bash
./render.sh <file.wf.yaml>                     # → .html + .png + .clean.png（+ flowmap）
python3 wfyaml.py <file.wf.yaml>               # 只出 .html（不截圖；render 前自動過 lint gate）
./render.sh --bundle *.wf.yaml                 # 併成單檔 prototype.html（左 nav + 走動線，零 JS）
./render.sh --bundle --debug *.wf.yaml         # 可走動線的評審版：切「模式:註記」點元素寫建議→匯出
./render.sh --debug <file.wf.yaml>             # 單頁評審版 .debug.html
./watch.sh [render 旗標] <資料夾|檔>            # 監看變動自動重渲（微調即時看；含 embed/layout 依賴）

python3 wfyaml.py list [--ring 0|1]            # introspection：動筆前列全部詞彙（Ring 0 原語 + 專案 token）
python3 wfyaml.py lint <file.wf.yaml> [...]    # schema validation（exit 0/1/2 = clean/warn/error，可掛 CI）
./render.sh --style sketch <file>              # 手繪風（與 --mockup 互斥）
./render.sh --mockup themes/x.yaml <files>     # mockup 模式：theme binding 上色（無此旗標=永遠低保真）
./render.sh --kit kit/components.yaml <files>  # 專案型別詞彙（預設亦會探測 kit/components.yaml）
./render.sh --kit kit/components.yaml --strict-kit <files> # 禁止裸 leaf/widget/box
python3 wfyaml.py --story stories/x.story.yaml # SAC 故事疊加（底圖+spotlight/badge/flow 序號）
```
需 `python3 + pyyaml + playwright`（截圖）；動線圖需 `graphviz dot`。bundle/debug 不需截圖。

官方可執行範例見 [`examples/README.md`](examples/README.md)：`deal-detail` 單頁、`deal-routes` 路由、
`layouts/`／`components/` 共用，以及五頁 `expense-app/`。手機常駐頁首/footer 與獨立捲動 main，
直接用 `examples/layouts/phone.wf.yaml`，參考 `phone-home`（短內容）／`phone-long`（長內容）。
lint 遞迴驗證引用檔案、component content/placeholder 與 widget.body；錯誤列來源檔與 YAML path。
CLI 的作者錯誤預設簡潔輸出，除錯工具時用 `--traceback` 或 `WF_TRACEBACK=1`。

## 詞彙表

下表由 `tools/update_docs.py` 從程式碼生成；隨時可跑 `python3 wfyaml.py list --ring 0` 拿到同一份。

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

## 語法速查

```yaml
# 頁面三形態（body 通用內容容器；繼承時換成 slots）
viewport: 1100x                            # 或 390x844（render meta，AST/codegen 忽略）
title: 顯示名稱                            # 選填，bundle nav 預設檔名
group: 群組                                # 選填，群組按首次出現，組內按輸入順序
body: [ ... ]                              # (a) 獨立頁
# ---
extends: layouts/x                         # (b) 繼承 layout
with: { title: X }                         #     純量參數 → layout 的 {{title}}
slots: { main: [...], actions: [...] }     #     填 layout 的 - slot: 名稱
# ---
routes:                                    # (c) 路由多輸出（各產可定址 .html）
  - default: true
    slots: { ... }
  - when: { stage: approving, state: pending }
    slots: { ... }
```

**排版原語**：`row`/`col`/`grid`（`col: [a,b]` = items 簡寫；**容器屬性一律 sibling**，`row: {gap,items}` dict-form 會 error）；
`row: between`（主軸 between/end/start/center/around）；`align: top`（交錯軸）；`spacer:`（推擠）；
`grow: true`（區塊/leaf 自己填滿主軸剩餘——等寬按鈕列、main 撐滿置底 footer 都靠它）；
`box: true`（外框，標題請用 text.heading）；子項 `span: 2`；`gap: md`/`padding: lg`（語義間距）。
欄寬**關係型為正道**：`grid: [w-40, grow]`、`grid: [grow, 60%, grow]`（`grow` 填滿/`fit` 依內容/比例；絕對 `w-N` 是逃生門）。
間距語義 scale `none`/`sm`/`md`/`lg`/`xl`，`gap` 與 `box` 內距皆**預設 md**。
捲動：`scroll: true`（高度由父容器/`grow` 決定）或 `scroll: sm|md|lg|xl`；`scroll-x:` 對稱（HTML 真捲、PNG 全展開+畫捲軸示意）。

**葉子（`role: 值`）**：`text` / `text.title` / `text.heading` / `text.label` / `text.strong` / `text.hint`；
`input` `select` `button:{text,to,icon}` `status`(.muted/.strong/.badge 方角) `alert` `icon` `divider`
`image:{label,w,h,ratio}` `tabs:{active,items}` `progress:{value: 0-1, label}` `avatar:{label,size}`；
`avatars:{items:[我,伴,友,家],max:3}`（顯示前三位與 +1；max 不含溢出標記）、
`map:{label,markers:[飯店,車站],can:[pan,zoom,markers]}`（沿用 widget 的示意／能力宣告，無真實地圖互動）；
`[x]`/`[ ]` checkbox、`(x)`/`( )` radio。text 值內行內 markdown：`**粗**` `*斜*` `~~刪除線~~` `[字](url)`。

**顯示態**：`ui-state: selected|disabled|hover|focus|active`（cross-cutting metadata，可掛任意 leaf/容器）→
`data-ui-state`，由 theme `components.<x>.states` 綁各態長相；與路由 `when.state` 區隔。
（選單列這類「現有原語 + 語義身份」用 component（`embed`）+ theme 綁其 `wf-role-<名>`，不新增 leaf type。）

**可收合**：`collapsible: <摘要>`（或 `collapsible: true` + `summary:`）掛容器 + `expanded: true`
→ 原生 `<details>/<summary>`（零 JS 可展開）。通用（FAQ/設定分組/明細皆可），非選單專屬。

文字含 `[ ] , : #` 時建議整個值加引號，尤其 flow sequence，避免解析失敗或內容被拆項／截斷。
`[金額]`／`[旅伴]` 會顯示為灰階虛線底線未定值；Markdown link/task-list 不誤判。
lint 按來源出現次數統計（引用來源只計一次，含 with 文字參數、不按展開倍增），只輸出 info、不影響 exit code。
title/group 不渲染產品 UI、不改 id；to 仍用檔名，route 子連結仍顯示原 label。

**widget（示意複雜元件）**：`widget: {is: 工單表格, can: [search, filter], body: [...]}`（純量簡寫 `widget: 名`）——
自帶「◫ 示意」標記，內部排版是代表性非規格，實作歸元件庫。

**浮層**：`pin:`（center/邊/角，邊=沿邊撐開）+ `modal: true`（scrim 擋後面）+ `layer:`（base/overlay/notify/top）；
具名 sugar `dialog:`/`drawer:`/`sheet:`/`toast:`/`loading:`（= 組合 token，顯式 pin/layer 可覆寫）。

**動線/連結**：`to: page` 或 `to: "page#stage.state"`（wireframe 動線，走 flowmap）；`link:{text,to}`（真超連結，不進 flowmap）；
句中詞可點用 `[字](to:page)`（無 `to:` 前綴=字面外連）。

**複用**：`embed: components/x` + `with:{...}` + `as: placeholder`（降階佔位）/ `as: {stage,state}`（pin 變體）。

**kit 元件型別**：`kit/components.yaml` 的 `components:` 可用 `of: <既有 leaf>` 特化，或用
`props` / `states` / `content` 組合新型別。kit 只宣告型別與結構，禁止任何 style；樣式放 theme
`components.<型別>`，值必須引用 token。畫面以 `{stamp-card: {place: ..., state: next}}` 使用。
不要加入 if / each / 運算；大量資料由外部產生 YAML。`--strict-kit` 用於成熟專案強制復用。

**kit canvas**：定位型複合元件用 `of: canvas`。kit 以
`base:{asset|grid|blank,anchors?,ratio?}`、`item:{use:<kit-type>}`、可選的
`link:{shape:straight|smooth,arrow?:true}`、`states` 宣告契約；畫面只給
`items:[{id?,at:[0..1,0..1],state,to?,...item props}]` 與可選 `link:[item-ref,...]`。
`at` 省略時必須命中 kit anchor。theme 可用 `base`、`link`、`item.state.<state>`（值仍全走 token）綁皮；
asset 底必須宣告 theme asset。編譯器只准替 link 畫 SVG path／箭頭；item 必須展開既有 kit 元件。

**色彩**：wireframe 全灰階，無節點顏色屬性（`tone` 已移除）。產品色走 `--mockup <theme.yaml>`；評審聚焦走標註面。

**mockup theme（三層 token 化）**：`tokens:`（值層，`{family.name}` 引用、`$value` DTCG 相容、`tokens.preset` composite
＝一組 property 被 `apply:` 組合）→ `components:`（元件皮，`base`/`variants`/`states`，值引用 token/preset）→
`bindings:`（綁 `name:`/role 的專案微調）→ `base:`（chrome/link-marker/scrollbar 模式開關）。
優先序：tokens < base < components < bindings。舊扁平 `bindings` 格式續相容。

theme 的 `tokens.radius.lg: 16px` 定義物理 CSS 值，`bindings.box.radius: lg` 引用語義名，勿在 bindings 寫 16px。
`background: inverse`／`text: inverse` 共用 `tokens.color.inverse`（fallback 白色）；完整範例在 `examples/themes/inverse.yaml`。

**Demo 標註（標註面，可剝離；render 另出 .clean.png）**：
`note: {ref: 1, text: ...}`（右側便利貼 + 物件小標，ref 作者自編）；
`spotlight: focus|new|change|click` 或 `{kind, text, step}`（step → ①②③ 操作序）。
多故事共用一張底圖 → 抽成 `stories/<id>.story.yaml`（SAC：bindings 疊 spotlight/note/badge、
`set.text/to` 換情境資料、flow 敘事序號；`--story` 渲染，底圖不動）。

**隱形語意**：`name: 頁首`（寫 data-name，不渲染）。語意靠 component 檔名 + name + 註解，無內建角色清單。

**評審回饋（`--debug` / `--bundle --debug`）**：瀏覽器開 debug 產物 → 切「模式:註記」點元素寫建議 →「匯出」
得「`[YAML路徑] role "內容" → 建議`」（按來源檔分組）→ 貼回給 LLM 依路徑改 YAML。註記不進 YAML。
`--bundle --debug` 可走動線 + 跨頁一次匯出。

## 現況與待補

見 `README.md` 末段。已實作：獨立頁/extends+slots/embed/狀態感元件(when+as+繼承)/routes 多輸出/
排版全套/葉子全表/行內 markdown/標註面/乾淨版剝離/flowmap/**bundle 單檔原型**/**debug 評審回饋(檔名+路徑定位)**/
浮層(pin/modal/layer)/widget/semantic token(Ring 1)/**lint + list 子命令**/**--mockup theme binding**/**SAC story**/
一般輸出零 JS。待補：葉子兩種寫法擇一、flow PDF、table/textarea。

## 注意

- **自含、可整包帶走**：封印 CSS/icon 在 `assets/`，無外部依賴。
- CSS 分層：`assets/wf.css` = 結構/機制/meta；外觀在 `assets/styles/clean/style.css`（視覺基底、永遠載入），
  `sketch` 疊其上覆寫；`wfyaml.py` 的 `CSS_EXTRA` 放 skill 專屬（image/spotlight/story…）。
- 語法/設計爭議 → 先看 `DISCUSSION.md` 的決策鏈與待議項。
