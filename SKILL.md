---
description: wireframe-lofi：把語義化 YAML 編譯成低保真、零 JS 的 HTML/PNG wireframe（wireframe-as-code）。用來快速 demo 與討論 UI/UX 結構與動線。YAML key 命名意涵/角色（非視覺），支援 Blade 式 layout(extends/slots)、可複用 component(include/as)、stage-state 路由多輸出(single-URL 動線)、Layer2 標註(spotlight/note，可剝離)。適合結構清楚、可被人與 LLM 共讀的線框圖。
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
2. **語義優先**：YAML key 命名意涵/角色，不寫視覺。顏色只用語義 `tone`（其餘中性灰）。

## 用法

```bash
./render.sh examples/deal-routes.wf.yaml       # → .html + .png + .clean.png（+ flowmap）
python3 wfyaml.py <file.wf.yaml>               # 只出 .html（不截圖）
./render.sh --bundle *.wf.yaml                 # 併成單檔 prototype.html（左 nav + 走動線，零 JS）
./render.sh --bundle --debug *.wf.yaml         # 可走動線的評審版：切「模式:註記」點元素寫建議→匯出
./render.sh --debug <file.wf.yaml>             # 單頁評審版 .debug.html
./watch.sh [render 旗標] <資料夾|檔>            # 監看變動自動重渲（微調即時看；含 include/layout 依賴）
```
需 `python3 + pyyaml + playwright`（截圖）；動線圖需 `graphviz dot`。bundle/debug 不需截圖。

## 語法速查

```yaml
# 頁面三形態（body 通用內容容器；繼承時換成 slots）
canvas: 1100x
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

**排版原語**：`row`/`col`/`grid`（`col: [a,b]` = items 簡寫）；`row: between`（主軸 between/end/start/center/around）；
`align: top`（交錯軸）；`spacer:`（推擠）；`box: true`（外框，標題請用 text.heading）；
`grid: [w-24, flex-1, w-24]`（欄寬 Tailwind token）；子項 `span: 2`；`gap: md`/`padding: lg`（語義間距）；
`scroll: h-48`/`scroll-x: true`（捲動區：HTML 真捲、PNG 全展開+畫捲軸示意）。
間距語義 scale 僅 `none`/`sm`/`md`/`lg`，`gap` 與 `box` 內距皆**預設 md**、可 `gap:`/`padding:` 覆寫。

**葉子（`role: 值`）**：`text` / `text.title` / `text.heading` / `text.label` / `text.strong` / `text.hint`；
`input` `select` `button:{text,to,icon}` `status`(.muted/.strong) `badge` `alert` `icon` `divider`
`image:{label,w,h,ratio}` `tabs:{active,items}`；`[x]`/`[ ]` checkbox、`(x)`/`( )` radio。
text 值內行內 markdown：`**粗**` `*斜*` `~~刪除線~~` `[字](url)`。

**動線/連結**：`to: page` 或 `to: "page#stage.state"`（wireframe 動線，走 flowmap）；`link:{text,to}`（真超連結）。

**複用**：`include: components/x` + `with:{...}` + `as: placeholder`（降階佔位）。

**語義色（Layer1）**：`tone: danger`（feature/info/warn/danger/success/muted…）。

**Demo 標註（Layer2，可剝離；render 另出 .clean.png）**：
`note: {ref: 1, text: ...}`（右側便利貼 + 物件小標，ref 作者自編）；
`spotlight: focus|new|change|click` 或 `{kind, text, step}`（step → ①②③ 操作序）。

**隱形語意**：`name: 頁首`（寫 data-name，不渲染）。語意靠 component 檔名 + name + 註解，無內建角色清單。

**評審回饋（`--debug` / `--bundle --debug`）**：瀏覽器開 debug 產物 → 切「模式:註記」點元素寫建議 →「匯出」
得「`[YAML路徑] role "內容" → 建議`」（按來源檔分組）→ 貼回給 LLM 依路徑改 YAML。註記不進 YAML。
`--bundle --debug` 可走動線 + 跨頁一次匯出。

## 現況與待補

見 `README.md` 末段。已實作：獨立頁/extends+slots/include/狀態感元件(when+as+繼承)/routes 多輸出/
排版全套/葉子全表/行內 markdown/Layer2/乾淨版剝離/flowmap/**bundle 單檔原型**/**debug 評審回饋(檔名+路徑定位)**/
一般輸出零 JS。待補：Layer1 色彩命名、葉子兩種寫法擇一、flow PDF、avatar/table/textarea。

## 注意

- **自含、可整包帶走**：封印 CSS/icon 在 `assets/`，無外部依賴。
- 視覺/CSS 要調 → 動 `assets/wf.css`（封印基底）或 `wfyaml.py` 的 `CSS_EXTRA`（本 skill 專屬：image/spotlight…）。
- 語法/設計爭議 → 先看 `DISCUSSION.md` 的決策鏈與待議項。
