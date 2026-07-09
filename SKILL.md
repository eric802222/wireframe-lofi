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
python3 wfyaml.py --story stories/x.story.yaml # SAC 故事疊加（底圖+spotlight/badge/flow 序號）
```
需 `python3 + pyyaml + playwright`（截圖）；動線圖需 `graphviz dot`。bundle/debug 不需截圖。

## 語法速查

```yaml
# 頁面三形態（body 通用內容容器；繼承時換成 slots）
viewport: 1100x                            # 或 390x844（render meta，AST/codegen 忽略）
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
`nav-item:{text,to,icon}`（側欄選單列，視覺歸 theme）；`[x]`/`[ ]` checkbox、`(x)`/`( )` radio。
text 值內行內 markdown：`**粗**` `*斜*` `~~刪除線~~` `[字](url)`。

**側欄選單**：`nav-item:{text,to,icon}` = 滿版可點選單列；`nav-group:{text,icon,expanded}` + `children:[nav-item…]`
= 可展開群組（chevron + 巢狀縮排）。顯示態 `ui-state: selected|disabled|hover|focus`（→ `data-ui-state`，
theme `components.nav-item.states` 綁長相；與路由 `when.state` 區隔）。

**widget（示意複雜元件）**：`widget: {is: 工單表格, can: [search, filter], body: [...]}`（純量簡寫 `widget: 名`）——
自帶「◫ 示意」標記，內部排版是代表性非規格，實作歸元件庫。

**浮層**：`pin:`（center/邊/角，邊=沿邊撐開）+ `modal: true`（scrim 擋後面）+ `layer:`（base/overlay/notify/top）；
具名 sugar `dialog:`/`drawer:`/`sheet:`/`toast:`/`loading:`（= 組合 token，顯式 pin/layer 可覆寫）。

**動線/連結**：`to: page` 或 `to: "page#stage.state"`（wireframe 動線，走 flowmap）；`link:{text,to}`（真超連結，不進 flowmap）；
句中詞可點用 `[字](to:page)`（無 `to:` 前綴=字面外連）。

**複用**：`embed: components/x` + `with:{...}` + `as: placeholder`（降階佔位）/ `as: {stage,state}`（pin 變體）。

**色彩**：wireframe 全灰階，無節點顏色屬性（`tone` 已移除）。產品色走 `--mockup <theme.yaml>`；評審聚焦走標註面。

**mockup theme（三層 token 化）**：`tokens:`（值層，`{family.name}` 引用、`$value` DTCG 相容、`tokens.preset` composite
＝一組 property 被 `apply:` 組合）→ `components:`（元件皮，`base`/`variants`/`states`，值引用 token/preset）→
`bindings:`（綁 `name:`/role 的專案微調）→ `base:`（chrome/link-marker/scrollbar 模式開關）。
優先序：tokens < base < components < bindings。舊扁平 `bindings` 格式續相容。

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
