# wireframe-yaml 設計討論筆記

> 低心智記錄：一議題一區塊，決策用一句話 + 日期。記錄前會先問。

## 決策紀錄

<!-- 格式：- [YYYY-MM-DD] 議題 → 結論（一句話） -->

- [2026-07-01] 核心定位（北極星①）→ 低保真，但 UI/UX 結構與動線明確；用途是快速 demo / 快速討論。推導：書寫低負擔優先；動線(`-> ` / flowmap)必須完整保留；低保真封印 CSS 原樣複用、不開調色/字體的口。
- [2026-07-01] 核心概念（北極星②，語義優先）→ YAML key 命名「意涵/權重/角色」(text / text.title / text.label / text.hint…)，非視覺。作者不寫字級/字型/色/寬；視覺全由封印 renderer 獨佔。此語義性讓產物成為**人機共讀媒介**：LLM 可直接生成/批改/轉換、可回溯 spec，無需從視覺反推意涵——這也是必須拿掉視覺逃生口的另一理由。
  - 修正前述：葉子改用**語義角色詞彙**(非 flex 的 `<b>`/`<i>`)；拿掉 flex 的視覺逃生口(`:bg-*`/`:text-*` Tailwind 直通)；`:tone-*` 因屬語義(危險/新功能，非顏色)予以保留。複用的是 flex 的**渲染結果(wf-class + 封印 CSS)**，非其書寫詞彙。

- [2026-07-01] 為何用 YAML → 免手刻 parser：刪掉 flex 的 `parse_block`（花括號 tokenizer / 深度追蹤 / `|` 切格最易出 bug），改用 `yaml.safe_load` 免費得到解析。
- [2026-07-01] 大架構（Blade-style layout）→ 支援 extends + 多具名 slot + with 純量參數；實作用「資料結構合併」(load layout 樹 + page 樹 → 走訪換 slot 子樹)，非字串替換，故不引入 tokenizer。參數 `{{x}}` 僅對葉子字串做侷限替換。include / component 延後討論。
- [2026-07-01] include/component 合一 → 統一一個關鍵字(`include:`)，`with:` 選填、子項當 slot 選填；layout 是同一支 expand pass。slot 機制(預設+具名)、`{{x}}` 只替葉子字串、解析路徑(同夾→components/layouts/partials→多層) 皆沿用 flex。
- [2026-07-01] stage/state = **路由模型**（非排列組合）→ 頁面是一張路由表：每條 `when:{stage,state}`(或 `default`) 是一個位址，對應**一整份 layout 內容**。一條路由 = 一張輸出 = 一個 URL（single-URL 動線指得到）。只渲染明列的路由，無笛卡兒爆量。`when:` 多 key = AND、值為 list = OR（結構自明）。**路由間共用靠 (i) `extends: layout` + slot**，每條路由各自完整；不採差異覆寫(ii)（diff/override 太難）。
- [2026-07-01] 元件降階（LOD）→ 元件可定義 `placeholder:` chunk（完整內容外的佔位表現）；聚焦討論某塊 UI/UX 時，其餘元件降階為佔位塊避免視線雜訊。未定義 placeholder 者 fallback 成「虛線框 + 元件名」通用佔位。逐實例 opt-in。
- [2026-07-01] include `as:` → 統一選變體。`as: placeholder`=降階佔位；`as: {stage,state}`=pin 元件某路由；省略=繼承當前頁面路由(狀態感元件自動跟階段走)。二者互斥。意涵：元件 = 帶路由表 + placeholder 的小頁面。
- [2026-07-01] 語意來源（不做內建角色清單）→ 不預設 header/section/actions 等固定角色。語意由三者長出來：① component 檔名即語意(`include: components/header`)、② 區塊掛 `name:`(一次性語意)、③ YAML `#` 註解。引擎核心只保留空間原語 `row`/`col`/`grid`(+ between/end/center + 比例欄寬) → 同時得到自由排版 + 語意 + 核心精簡。
- [2026-07-01] `name:` 行為 → 預設**不渲染**（守低保真），寫入 HTML 當 `data-name`/註解供 LLM 讀產物；YAML source 本身為主要語意載體。（保留日後可加「圖上顯示小標籤」選項）
- [2026-07-01] 排版詞彙（兩層）→ 空間原語 `row`/`col`/`grid`(+ between/end/center + 比例欄寬如 `grid: [2fr,1fr]`；`col: [a,b]` 為 items 簡寫) 提供自由排版；語意靠 `name:`/component。不做內建角色清單。
- [2026-07-01] slot 契約明確化 → 頁面填洞用 `slots: { name: ... }` 群組（複數，明講在填 slot），對稱 layout 端 `- slot: name`（單數，挖洞）。避免裸 key 看不出是 slot。單一 slot 情形也一律用 `slots:`（規則單一）。
- [2026-07-01] 三層結構對稱 → layout 檔 = `body:` + 挖 `slot:`；獨立頁(無 extends) = `body:`(無洞，零 ceremony)；繼承頁 = `extends:` + `slots:` 填洞。`body:` 為通用頁面內容容器，僅繼承時換成 `slots:`。有/無路由、有/無 layout 心智模型一致。
- [2026-07-01] 空間原語靈活度 → 方向 `row`/`col`/`grid`；`justify:`(主軸 between/end/start/center/around)、`align:`(交錯軸 center 預設/top/bottom/baseline/stretch)；`spacer:` item 做不對稱推擠(justify 表達不了時)；**`box: true` 只畫框、不帶標題**（要標題請用語義的 `text.title`/`text.heading`，且放 grid 外避免佔格；此規則取代早期「box:標題」構想，更貼北極星②）；grid 欄寬 `N`/`[2fr,1fr]`/`[120px,1fr]`、子項 `span: N` 跨欄；不做顯式 cell（一 item=一格，多元素靠巢狀，欄寬對齊用 grid）；任意巢狀。
- [2026-07-01] 尺寸/排版值統一用 Tailwind token → 不做 `fill`/`fit` 白話別名（Tailwind 詞彙本身語意已明確）：`flex-1`/`w-auto`/`w-24`/`w-1/2`/`w-full`/`gap-*`… 取代裸 px；例 `grid: [w-24, flex-1, w-24]`。仍屬「參考非規格」（讀者認知＋SKILL.md 約定）。
- [2026-07-01] Tailwind 適用邊界（②不鬆動）→ Tailwind 只用於 **layout/排版**（尺寸/欄寬/對齊/間距）；**顏色/視覺類(bg-*/text-顏色)維持封印**，只用語義 `tone:`。此邊界關掉「是否開放視覺逃生口」的爭議。
- [2026-07-01] 間距語義化（可 theme）→ `gap:`/`padding:` 用 t-shirt 語義 scale(`none`/`xs`/`sm`/`md`/`lg`/`xl`)，**非** Tailwind 數字階(gap-1/p-1)；理由：間距是設計系統節奏核心，語義=一張對照表，換 theme 一字不動。預設封印、多數免寫（低保真不 fiddle 間距）；不開 `margin`(兄弟間距用 gap、推擠用 spacer，避 margin 疊加陷阱)。**寬度維持 Tailwind token**(w-24/w-1/2，具體參考)——職責不同故詞彙不同。
- [2026-07-01] **兩個語義層（關鍵拆分）** → 過去把 tone 混成一坨的根因。拆成：
  - **Layer 1｜UI 語義**：描繪「產品真的長這樣」的狀態（danger/muted/success…）。屬 wireframe 內容本體。
  - **Layer 2｜Demo/討論標註**：疊在 UI 上的「請看這裡」指引（這次要 demo 的功能、這版改了哪段、新功能聚焦）。不是產品的一部分。
  - 撞名證據：「highlight」在兩層都出現（L1=UI 強調狀態、L2=demo 標改動）→ 必須拆層才不混淆人/LLM。
  - **Layer 2 可剝離**：能出「乾淨 UI 版(只 L1)」與「標註版(疊 L2)」兩種輸出（demo 用途剛需）。L2 視覺刻意像便利貼/螢光筆，一看就知是註記非 UI。flex 的 gutter 邊註/`[#NEW]`/`[^ref]` 即 L2 雛形，將正式化。
  - 兩層設計成**獨立詞彙**，分開命名（避免再混著討論）。
- [2026-07-01] Layer 2 詞彙定案（Demo 標註層，兩機制、掛任意節點、全可剝離、視覺明顯是註記非 UI）：
  - **`note:`** → 右側 gutter 備註 + 物件小標。形式 `{ ref: <作者自訂>, text: ... }`。ref **作者自編**(1/1.1/2a…)、靜態不重排 → 外部文件可穩定參照(同 flex 考量)。渲染複用 flex 的 gutter 量測對齊機制(render.sh)。
  - **`spotlight:`** → 引導 overlay，enum 決定種類：`focus`(本次重點,螢光罩)/`new`(新功能,取代 flex `[#NEW]`)/`change`(改動段落)/`click`(點此操作,取代糊掉的 click:)。需文字/順序用 map `{ kind, text, step }`；`step` 渲成 ①②③ 序號徽章串出操作動線(折入原 C 選項)。
- [2026-07-01] ⏳待討論 Layer 1（UI 產品語義色）命名與集合 → 遇到再定。已釐清：混了三軸 → 警示軸(info→warn→danger,適合叫 `severity`)、正向結果(`success`)、強調度(`muted`,其實非顏色是去強調)。命名坑：`status:` 已給葉子 chip、`state:` 已給路由，皆不可重用。待決：是否用 `severity:` 只裝警示軸、success 給 chip 或獨立色、muted 抽成強調機制。
- [2026-07-01] **葉子語意詞彙表定稿**（`角色: 值`，scalar-or-map；語義 role 非視覺；複用 flex 渲染/CSS/icon 函式）：
  - **文字家族（6）**：`text:`(內文/裸字串) · `text.title:`(主標題,一頁一個) · `text.heading:`(區段標題,無框抬頭) · `text.label:`(欄位標籤) · `text.strong:`(整塊強調) · `text.hint:`(附屬最弱)。抬頭僅兩級(title/heading)。區分:`box:標題`=有框、`text.heading`=無框抬頭、`name:`=隱形 metadata。
  - **表單控制**：`input:`(值=placeholder,map `{placeholder,value}`) · `select:`(map `{text,options?}`) · `button:`(map `{text,to,icon}`) · checkbox/radio 見下。
  - **狀態/標記**：`status:`(chip 藥丸,`.muted`/`.strong` 分級) · `badge:`(方角) · `alert:`(UI 警示,色屬 Layer 1 待定)。
  - **圖示/結構/動線**：`icon:`(`check` 或 `{set:fa/lu,name}`) · `divider:` · `tabs:`(`{active,items,每項可 to}`) · `image:`(佔位打叉框;scalar=label;map `{label,w,h,ratio}`,`ratio: 16/9`→Tailwind aspect) · `to:`(動線導航,走 flowmap,teal+↗) · `link:`(產品真超連結,不進 flowmap,底線樣)。
  - **行內 markdown（在 text 值內）**：`**粗**`/`*斜*`/`~~刪除線~~`/`[字](url)` — 句中格式用 markdown(拆 role 太痛);元素層強調仍用 role。屬扁平每葉子 inline 分類(等同 flex `icons_html` 換 markdown 慣例)。
  - **checkbox/radio 用 markdown task-list 語法**：`[x]`/`[ ]`(勾選)、`(x)`/`( )`(單選) + label;附加屬性才用 `checkbox: {label,checked}` map。
  - 待補(遇到再做)：`avatar`(圓)、`table`(先用 grid)、`textarea`(input 變體)。
- [2026-07-01] ✅已實作 `--debug` 評審回饋迴路（設計定案）→ reviewer 在渲染頁點元素→寫修改建議→暫存→匯出貼給 LLM 一次改 YAML。定位：**第三種註記**，有別於 Layer2（Layer2 是作者寫、會渲染、給觀眾看；debug 是 reviewer 臨時寫、**不渲染、不進 YAML**、只為匯出）。決策：
  - **零 JS 界定**：`--debug` 為獨立模式，注入 JS + localStorage；**一般輸出維持零 `<script>`**；debug 產物 ≠ 交付物（交付走乾淨版）。
  - **id 方案（改定為 A：檔名 + YAML 路徑）**：每元素 `data-wf-src`(來源檔) + `data-wf-path`(檔內結構路徑，如 `slots.main[0].col[1]`)。取代原短碼 C——路徑用索引避開「flow 一行多元素」歧義、scalar 於 render 時依位置算出（不需掛 metadata，破除「字串掛不住」的障礙）。實作：load 時 `_stamp` 替 dict 蓋 `__src`/`__path`，展開/填 slot 保留、render 讀出並算 scalar 子路徑；跨 component/layout/slot 各帶正確來源。僅 debug 輸出這些屬性，一般輸出維持乾淨。
  - **匯出格式**：按**來源檔**分組，每條 `[path] role "內容快照" → 建議`（快照留作人讀確認）。
  - **暫存**：localStorage（per 檔、可 reload 存活）；浮動列「匯出 / 清除」，匯出跳 textarea 一鍵複製；有註記的元素標小紅點。
  - **互動**：hover 高亮 → 點擊開 inline 輸入框 → 存。
- [2026-07-01] ✅已實作 bundle 單檔原型 + debug 疊其上 → 單頁 debug 攔截點擊會失去跳轉；解法：`--bundle` 併多頁成單檔 prototype.html（左 nav + `:target` 切頁，零 JS；`to:` 改頁內錨點 `#wf-pg-...`）。`--bundle --debug` 疊評審層：**模式切換**（瀏覽=點擊照常走動線／註記=點擊開建議框），單檔共用一份 localStorage → **走動線 + 跨頁標註 + 一次匯出全部**。id 沿用「檔名+YAML路徑」，匯出按來源檔分組（實測貼回可精準鎖定，如 `routes[1].slots.actions[0]`）。
- [2026-07-01] ✅已實作 scroll 捲動標示 → 語義 `scroll: <高度>`(垂直,值=高度上限 Tailwind token)、`scroll-x: true`(水平)，掛容器上。兩種輸出各取所需：**HTML** = `overflow:auto`+封頂→**瀏覽器原生捲軸**(真能捲、模擬真實 app；不自訂 `::-webkit-scrollbar`→跨瀏覽器)；**PNG** = 複用 `wf-show-all` **解除封頂、全展開** + 右緣**手畫低保真捲軸示意**(只看圖也能看全內容並知道會捲)。即「圖片低保真示意、HTML 原生」。因 PNG 全展開無 overflow→真捲軸不會被截，故 PNG 走「畫示意」而非截真捲軸(修正原「一根真捲軸兩用」設想)。零額外管線(scroll 同 toggle 吃 wf-show-all)。
- [2026-07-01] ✅已實作 置底/填滿 → 兩個能力：(a)`col` 支援 `justify`(垂直主軸)、有 `canvas` 高度時 root 成 flex-col + body `flex:1` 撐滿(spacer/justify 才有空間把 footer 推底)；(b)採納 reviewer 建議新增 **`grow: true` 結構原語** → 容器 `flex:1 1 auto` 吃掉父主軸剩餘空間(grid 另補 `align-content:stretch`)。決策依原則：grow 屬**結構非視覺**(同 spacer/span/justify 族)不違北極星②、比 spacer 更語義(區域自己填滿 vs 插空推擠)、可用於巢狀、核心僅 +1。分工：`spacer` 簡單推擠、`grow` 區域填滿。範例 app-window(spacer)/app-grow(grow) 驗證 520px 視窗 footer 置底。
- [2026-07-01] ✅結案 會不會回到 parser 地獄 → **不會**。結構解析(遞迴/有狀態)全交給 `yaml.safe_load`；葉子 = 語義 keyed + dict 分派渲染 + 每葉子扁平 inline 分類(markdown 行內/checkbox/icon，等同 flex `icons_html`，最壞只錯一顆 chip)。既非手刻結構 parser、也非照搬 flex 符號。新寫的結構 parser = 0 行。
- [2026-07-01] ✅已實作 border-radius → CSS 變數：`--wf-radius`(一般,預設 3px)、`--wf-radius-pill`(藥丸/圓形,9999px)，於 `assets/wf.css` `:root` 定義；theme 覆蓋一處全域生效。0 硬編殘留。此為 theme 系統的第一顆 token。
- [2026-07-01] ⏳思考中 **theme = 保真度旋鈕（wireframe → mockup migrate）** → 核心框定：**同一份 YAML 永遠是唯一語義源**，theme 只調保真度；預設=低保真 wireframe(討論)，`--theme=<product>`=套產品皮 migrate 成 mockup(交付)。作者永不改 YAML、逐元素視覺永不進 YAML(連 mockup 也來自全域皮) → **強化北極星②**；低保真仍是預設與討論階段、mockup 是刻意後段升級 → **不破北極星①**。定位：wireframe-yaml = 單一語義源 × 漸進保真。
  - **前提地基**：`wf-*` class 契約要正式化成「theming API」(能換皮之前提)；Layer2 標註/debug/flowmap **不受 theme 影響**(meta 非產品)。
  - **成本認知**：token 層便宜；**skin 層 = 一個產品一份工程**；theme 到「80% 像、夠評審/handoff」，像素級回真工具。
  - **theme 可設定的面（分三層）**：
    - **Tier1 Design Tokens（便宜，`:root` var 交換）**：圓角(✅已 var)｜間距 scale 值+box/gap 預設級距(現在 Python GAP，待搬 var)｜字體(family/base size/標題級距/字重)｜基礎色盤(`--wf-ink`文字/`--wf-line`邊框/`--wf-bg`底/`--wf-muted`次要)｜強調色(`--wf-accent` teal 系)｜語義色盤 tone(danger/warn/info/success/feature/muted 各 bg/border/text)｜邊框寬。→ 做完得「低保真+」變體。
    - **Tier2 Component Skin（貴，逐 `wf-*` 重繪；mockup 保真靠此）**：button/input/select/checkbox·radio/status(chip)/badge/tabs/box/alert/divider/image/heading。
    - **Tier3 Flavor/行為**：sketch 草圖風 ↔ 乾淨 ↔ mockup；陰影/hover；低保真佔位在 mockup 是否「升級」(image 打叉框→真圖佔位? DOS 捲軸→原生?)。
  - **維持固定(meta，不受 theme)**：Layer2(note/spotlight)、debug 工具列、flowmap、空間結構(row/col/grid)。
  - **建議路徑**：先把 Tier1 全抽成 `:root` token(地基/便宜/馬上有 theme 感)；Tier2 skin 等真要為某目標產品做 mockup 時再逐元件補。
  - ✅已實作 Tier1 部分：**圓角**(`--wf-radius`/`-pill`)、**間距**(`--wf-space-sm/md/lg`，GAP 改指向 var)、**字體**(`--wf-font`/`--wf-font-size`/`--wf-h1|h2|h3`)皆抽進 `assets/wf.css` `:root`。實測覆蓋 `:root`(圓角/間距/字體)整體外觀即變 → token 機制成立。**色盤/tone、`--theme` 注入旗標、Tier2 skin 尚未做**(待需要)。
  - **待決**：density 總開關(compact/comfortable 一次調間距+padding)要不要？Tier2 先全元件還是先高頻(button/input/box/chip/tabs)？Tier3 是否至少保留 sketch flavor？image/捲軸 佔位在 mockup 的升級策略？

---

## 2026-07-02：以「記帳 app 5 頁實測」為壓力測試，收斂一批架構決策

實測位置：`examples/expense-app/`，完整討論歷程：`TOOL-SUGGESTIONS.md`（根目錄）。以下按決策時間軸排列，供 loader/renderer 開發依此推進。

### 排版原語 canonical form

- [2026-07-02] **排版 canonical = sibling form，明拒 dict-form** → `row: {gap, items:[...]}` 這種 dict-form **拋 error**（非 warning）。理由：DISCUSSION 排版原語兩層已定（line 21, 24），支援 dict-form 會製造第三種寫法違背北極星②；當前 sibling form 本就是「dict 全部 key 屬於同一 container」，只是 items 用 direction key 藏起來的 sugar，AST 對齊靠 loader 一次 pick-up（`Container(direction, justify, align, gap, children)`），跟 React `<Row gap>` 完美對應。錯誤訊息**必須教育為何是 sibling**，附修法範例（見 actionable diagnostics）。修 `wfyaml.py:_items_of`。
- [2026-07-02] **`_items_of` bug → 明拒 dict-form 的實作切點** → 目前 `v = d.get(direction)` 對 v 是 dict 時靜默 fallback 到外層 `d.get('items')` 拿到空 → 造成所有嵌套帶屬性的 row/col 靜默渲空（tx-item、app bar、預算列…全中招）。修法：dict 型 v 直接 raise ValidationError。這是本次實測發現「最痛的一個 bug」。

### `grow` 與 `scroll` 語義

- [2026-07-02] **`grow: true` 保留（不改名 `fill`）** → 討論考慮改名 `fill:` 求更語義，但 row/col 已限縮方向，`grow` 是 CSS/UI 通用詞（`flex-grow`）既有 mental model 命中；`fill` 反有 fill area / fill color 歧義；`spacer`(推擠) vs `grow`(區塊自填) 分工清楚，保留現名。
- [2026-07-02] **`scroll:` / `scroll-x:` 純語義化**（修正 line 53 原設計「Tailwind 高度 token」）→ 移除 `scroll: h-*` 像素 token 支援（違反北極星② 不寫尺寸細節），改成純語義三態：
  - `scroll: true` = 「這區塊可捲」，高度由父容器 / `grow: true` 決定 → `overflow-y:auto`
  - `scroll: sm/md/lg/xl` = 語義級距，可 theme（跟 `gap:`/`padding:` 家族對齊 line 27）→ `max-height: var(--wf-scroll-*)`；預設 `8/16/32/48rem`
  - `scroll-x:` 對稱處理
  組合語義天然成立：`grow: true` + `scroll: true` = 「填滿剩餘 + 可捲」，不需要 `scroll: fill` 之類的聯集寫法。修 `wfyaml.py:479-482`。原設計「保底 16rem」的 fallback 移除，改為 P0.7 schema validation 早失敗。

### Schema Validation + Fail-Fast（架構層決策，AST codegen 前置）

- [2026-07-02] **建立 Schema Validation + Fail-Fast 架構**（貼 poka-yoke / actionable diagnostics / TypeScript `tsc` 前置類比）→ 目前 wfyaml.py 對錯誤 YAML 是**靜默降級**（dict-form 讀不到 items 靜默渲空、typo 靜默 fallback、tone 錯值靜默無效果）→ 使用者/LLM 生成的 YAML 出錯沒有信號回饋。決策：wfyaml.py loader 該扮演 `tsc` 角色，validation 過了才進 render/expand。分兩層：
  - **P0.7a 結構 schema**：container 恰一個 direction key、leaf 恰一個 role key、未知 key warning（帶 Levenshtein 建議「是不是 X?」）、container/leaf 屬性混掛偵測
  - **P0.7b 語義集合**：gap/padding 屬 `none/sm/md/lg/xl`、align/justify 屬 enum、tone 屬 Layer1 集合（收斂後 lock-in）、scroll 屬 `true/sm/md/lg/xl`、slot 引用存在、include 檔案存在、icon 名在 vocab（見 canonical icon vocab）
  - **Actionable diagnostics 格式**（Rust compiler 風格）：檔名 + 行號 + YAML 路徑 + 位置標示 + 為何錯 + 修法範例
  - **實作切點**：loader validate(doc) → 拋 ValidationError；CLI `--strict`（預設） vs `--lenient`（過渡）；獨立 `wireframe-lofi lint` 子命令；`schemas/wf.schema.json` 供 IDE YAML 擴充
  - **與 AST → code 關係**：codegen 前置強制門，錯誤責任明確歸給 YAML 作者不外漏

### Leaf 家族擴充（P1）

- [2026-07-02] **新增 `progress` leaf**（P1，強烈建議）→ `progress: {value: 0-1, tone, label?}` 或 scalar `progress: 0.5`。value 用 0–1 語義比例（非像素/百分比字串），tone 走 Layer1，label 走 inline markdown。記帳/預算/募款/專案剛需，目前只能用 `status.strong: 78%` chip 湊，沒有 fill bar 視覺。
- [2026-07-02] **`avatar` leaf 定案**（收斂 line 45 待補項）→ `avatar: {label, size}` 或 scalar `avatar: EC`。**視覺封印邊界**：不接受 `src: photo.jpg`（真圖）/`bg: red`（真色）等視覺逃生口參數，只允許 label（縮寫字母）+ size（sm/md/lg 語義 scale），跟 `image:` 打叉框對稱。
- [2026-07-02] **`chart` leaf 暫緩** → `image: {label, ratio}` 已定位為「佔位打叉框」，chart 佔位用 image + label 已足夠傳達意圖；新增 chart 只是視覺別名、語義沒質變，違反「核心精簡」原則。等真的多次遇到「需要區分 chart 佔位 vs 圖片佔位」再議。
- [2026-07-02] **葉子 canonical = dict-form（收斂 line 262 待補項）** → 明拒字串 sugar `"role: 值"`，只留 `{role: 值}`。理由：字串 sugar 要 wfyaml 內部 mini-parser 切 `role: value`，這正是 line 13「不手刻 parser」決策的例外洞；移除後 100% 靠 `yaml.safe_load`。AST codegen 只需認 dict role，不需雙 code path。遷移期出 warning。

### Slot / Component 擴充

- [2026-07-02] **Slot 展開多項的對齊問題 → 建議 `wrap` 屬性或 grouping helper**（P2）→ app bar `[slot: title, slot: actions]` 中 actions 展開為多個 icon 時，`justify: between` 會把所有子項攤開而非「actions 群組靠右」。目前繞開：內包一層 list-form row `- row: [ - slot: actions ]`。建議：`slot: actions\n wrap: row` 讓 slot 支援展開時自動包容器。優先級中，可靠現有繞開 pattern 過渡。
- [2026-07-02] **`include` 支援 `slots:` 參數**（P4 E5，React children 對齊）→ 現行 `include with:` 只替換葉子字串，無法傳「一段內容」當子節點。擴充：component 可以挖 `- slot: content`（跟 layout 對稱），include 時 `slots: {content: [...]}` 填。對照 React 就是 `<Card>{children}</Card>` 的 slots 版。**設計對齊**：layout 有 slots、component 也可有 slots，兩者機制**完全一致**（三層對稱 line 23 延伸）。

### 動線 / 路由 / Meta 對 AST 的立場

- [2026-07-02] **`to:` 值 grammar 形式化**（P4 E3） → `to:` 只接 `<page>('#'<stage>('.'<state>)?)?` 或純 hash `'#'<stage>('.'<state>)?`；page/stage/state 皆 `[a-z][a-z0-9-]*`。AST 表示 `RouteRef {page, stage, state}`。Codegen 對應：React Router `/{page}/{stage}/{state}`、Next.js App Router `app/[page]/[stage]/[state]/page.tsx`、純 hash → 頁面內 state。違反 grammar → P0.7 lint error。
- [2026-07-02] **`routes:` = single URL 對 codegen 的意涵**（收斂 line 16 到 AST 面）→ 明講立場：`routes:` 產出的每個路由對應**獨立 URL / route path**（不是 client-side useState）。codegen 到 React Router 每路由一個 `<Route>`；到 Next.js 每路由一個 `page.tsx`。這保留深連結、分享、瀏覽器 back 能力。
- [2026-07-02] **`canvas:` 標記為 render meta（AST 忽略）**（P4 E6）→ `canvas: 390x844` 只給 wfyaml render 用（HTML 外框、PNG 尺寸、置底基準）；對 AST → code，React/Vue app 不定畫布、iOS/Android 用 safe area → codegen 忽略 canvas。明講 canvas 屬 meta 家族（跟 name / Layer2 / debug / flowmap 同族），不進產品 AST。
- [2026-07-02] **事件槽立場：wireframe-lofi 不做**（P4 E7）→ 真產品有 onClick/onSubmit/onChange，wireframe-lofi 只表達「畫面+動線」（`to:` = 導航），不表達事件行為。理由貼 line 57 保真度旋鈕邏輯：事件屬 mockup 高保真階段，wireframe 是低保真層；加事件槽會膨脹詞彙且破北極星①。**明講 doc 有這行**避免後人問「怎麼標 onClick」。codegen 產出的 React 只有 layout + 導航（`to:` → `router.push`），事件由後續填。

### AST 對齊：Container / Leaf schema 明列

- [2026-07-02] **Container 屬性 schema lock-in**（P4 E1）→ 節點 shape 明列（AST 節點形狀鎖住）：
  ```
  Container { direction: 'row'|'col'|'grid'; justify; align; gap; padding;
              box; grow; scroll; scroll-x; span; tracks; children }
  ```
  加上 cross-cutting `Metadata { name; tone; to; note; spotlight }` 可掛任意節點。AST → React 幾乎 1:1：`<Row justify align gap data-name>{children}</Row>`。
- [2026-07-02] **Leaf 屬性 schema lock-in**（P4 E2）→ 每個 role 的 value shape 與可掛 metadata 明列成表（見 TOOL-SUGGESTIONS.md P4 E2）。跨葉子規則：`to:` 只在 button/link/容器有效、`checked` 只在 checkbox/radio，其他情形 P0.7 lint 出 warning。

### Icon 語彙 lock-in（跨平台對齊）

- [2026-07-02] **Canonical icon vocab（~30 個核心語義名 + 跨平台 mapping）**（P4 E4）→ 目前 `icon: swap`/`minus` 打錯靜默顯示「◻ 未找到」，且 FA/Lucide 名直通綁死 web。建議建立跨平台 canonical vocab：
  - **~30 個核心語義名**：導覽（home/back/forward/close/menu/more）、動作（add/remove/edit/delete/save/share/download/upload）、狀態（check/warn/info/question）、資料（search/filter/sort/calendar）、使用者（user/bell/settings）、金融場景（wallet/card/receipt/chart-pie/chart-bar）
  - **跨平台 mapping table**：canonical → FA / Lucide / SF Symbols / Material Symbols
  - **Escape hatch**：`icon: {set: fa, name: fa-custom}` 直通具體圖庫，但**不參與 codegen**（標記為 platform-specific）
  - AST → RN 範例：`icon: home` → `<HomeIcon />`（從 vocab 表映射）

### Layer 1 tone 候選 lock-in（實測回饋）

- [2026-07-02] **Layer 1 tone 候選 6 名（實測驗證，收斂 line 37 待議）**：
  - `danger`（支出/超支/警示）、`success`（收入/健康/綠燈）、`warn`（接近上限 70–99%）
  - `feature`（主要 CTA/focused/active tab）、`info`（中性資訊）、`muted`（去強調）
  - **命名軸分工**：警示軸 `info → warn → danger`（對應 line 37 severity 提議）；正向 `success` 獨立；強調度 `feature`/`muted` 非顏色是強調機制
  - **建議沿用單一 tone 名稱空間不拆 severity**：實作最順手的接口，記帳 app 這種混合場景 6 名已足夠覆蓋。若日後需拆，可保留 tone 為 façade、內部映射到 severity 軸。
  - Loader P0.7 lint：tone 值必須在此 6 名集合，其他 warning。

### 其他小結

- [2026-07-02] **`with:` 替換範圍實測確認 + 文件補強**（收斂）→ `_subst` 已支援對任何 leaf 字串位置的 `{{}}` 替換（含 dict role value：`text: "{{category}}"`、`tone: "{{tone}}"`、`button: {text: "{{label}}"}`），被 P0 bug 掩蓋才誤判為壞掉。README 應明講「`{{}}` 適用於任何葉子字串位置，不限頂層 scalar」並補 test。
- [2026-07-02] **`name:` 隱形語意實測確認**（line 20 對齊）→ `name: tab-home` 正確寫入 `data-name="tab-home"` 且不渲染，與設計一致，無需調整。

### 手繪風 / style 系統 / 素材資產（2026-07-02，設計定案，待實作）

- [2026-07-02] **目標：真低保真手繪感** → 使用者要 Balsamiq 那種鉛筆抖動線。評估 `border-image`（MDN）：能做手繪框，但三個限制 —— (a) 吃掉 `border-radius`（角由切片決定）、(b) 長邊 tiling/stretch 有接縫或變形（手繪線不該規律重複）、(c) 只作用 border，hr/input/text 仍乾淨 → 視覺不一致。
- [2026-07-02] **border 用 `border-image`（使用者拍板）；其他描邊之後再做** → 框線走 border-image；hr/input/按鈕等要一致手繪時，後手用 **SVG 位移濾鏡（feTurbulence + feDisplacementMap）**（前身 `@handwritten` 手法，roughen 全描邊、零 JS、不動現有 CSS、radius 一起抖）—— 分階段，先框線。
- [2026-07-02] **樣式選擇 = `--style <名稱>` render 旗標，不進 YAML**（守北極星② 語義源純淨）→ 同一份 YAML，換 style 就換皮。這是先前 theme fidelity-dial 的使用者面呈現。`clean`(預設乾淨線/保留圓角) / `sketch`(border-image 手繪框) / 未來 `mockup`。互斥預設，各自乾淨（sketch 的 radius moot 不打架）。
- [2026-07-02] **bundle 內零-JS 即時切換器** → prototype.html 放 style 切換（checkbox + `:has()` 切 root class），reviewer 當場 clean↔sketch 切著看。
- [2026-07-02] **素材切進 `assets/` 分層分類（使用者可替換）** → 結構 `assets/styles/<風格>/style.css` + `<分類>/<元素>.<ext>`；起手 `styles/sketch/style.css` + `border/{box,button,input}`（對應 `.wf-box`/`.wf-btn`/`.wf-input,.wf-select`）。未來同層可加 `line/`(hr)、`cursor/`(spotlight click 手勢) 等分類。使用者換筆觸=直接改素材檔、重渲即生效、不碰程式。
- [2026-07-02] **素材抓「name」不鎖副檔名** → CSS 以無副檔名的名稱引用（如 `url(border/box)`），render 時 glob `border/box.*` 找實際檔（svg/png/jpg/…），依**實際副檔名**判 MIME 內嵌 → 使用者日後可把 `box.svg` 換成 `box.png`/`.jpg`，CSS/程式不動。
- [2026-07-02] **render 機制：外部素材檔 → 內嵌 data-URI（兼顧可替換 + 輸出自含）** → `--style X` 載入 `styles/X/style.css`，把其中相對 `url(...)` 素材讀進來 base64 內嵌成 data-URI（同 wf.css/icon 的做法）→ 產物仍是自含單檔，不依賴外部檔。
- [2026-07-02] **style 與 render 解耦（theming API 正式化）** → 渲染器只保證「語義 HTML + `wf-*` class 契約」；視覺全歸 style 包，不硬編在 render base。**邊界**：base(wf.css) = 結構/機制/meta（`.flex`/`.grid`/positioning、`wf-show-all`、scroll overflow、gutter 對齊、Layer2 標註 note/spotlight、debug、bundle nav/`:target`）；style = 外觀（tokens 色盤/radius/間距、字體含 `@font-face` 內嵌 woff2、border 素材或 solid、box/button/input/select/chip/badge/tabs/heading/alert 長相）。
  - **clean 變成 `styles/clean/style.css`**（現行視覺搬過去），為預設**視覺基底、永遠載入**；其他 style（sketch…）**疊在 clean 上覆寫**（DRY，非每 style 全複製；此為對「每 style 全套」的務實修正）→ 視覺已離開 render base、達成解耦，sketch 維持只寫 border/font override。
  - style 可自含 `@font-face`（woff2 放 `styles/<name>/fonts/`，data-URI 內嵌）→ sketch 配手寫字體。
  - **sketch 字體定案**：英文 **Comic**（Comic Sans MS / Comic Neue）、中文 **Yozai 悠哉體**（chinese-fonts/yozai，開源手寫圓體）。CSS `font-family: 'Comic Sans MS','Comic Neue','Yozai',cursive`（逐字 fallback：拉丁走 comic、CJK 走 Yozai）。**CJK 內嵌取捨**：Yozai 全字 woff2 肥（數 MB）→ 預設靠 render 機器已裝字體(PNG 用)，要完全自含再把（子集化）woff2 丟 `styles/sketch/fonts/` 走 data-URI 內嵌。
  - 載入順序：base 結構 + CSS_EXTRA(meta) + clean 視覺 + (選定 style override) + debug + 尺寸 override。

### sketch 字體改走 CDN（2026-07-02，定案，取代上方「CJK 內嵌取捨」）

- [2026-07-02] **不背字體檔，改 CDN `@import` + 系統回退**（使用者拍板：「不能直接用 cdn 嗎? 沒有頂多 failback 系統字體」）→ Yozai 全字 15MB、子集化又要把字體邏輯塞回 render（違背解耦），CP 值低。改：
  - 英文 `Comic Neue` → Google Fonts `@import`；中文 `Yozai` → jsdelivr `@chinese-fonts/yozai`（cn-font-split chunked 子集，只載用到的字）。
  - `--wf-font` stack 末端接系統手寫字 + `cursive`：CDN 失效/離線自動優雅回退，不影響結構呈現。
- [2026-07-02] **`_hoist_imports()`**：`@import` 規則必須位於樣式表最前否則被瀏覽器忽略；clean/sketch 疊加後 @import 會夾在中間 → 編譯時用 regex（限 `@import url(|"...`，避免誤抓註解字樣）把所有 @import 提到 `<style>` 開頭。
- [2026-07-02] **PNG/SVG 管線 route-abort 外部請求**（踩坑修正）→ headless 用 `wait_until='load'`，離線 sandbox 下 CDN `@import` 會卡住，chromium 等外部樣式表時把**本地 sketch 規則（含手繪 border-image）一起壓掉** → 整頁退回 clean。修法：`page.route` 把 http(s) 請求全 abort（產物本已全 data-URI 內嵌，不需外部）→ @import 秒失敗、本地規則正常套用、字體回退系統。**分工**：PNG/SVG = 手繪框 + 系統回退字（離線）；HTML 用瀏覽器開 = 手繪框 + CDN Comic Neue/Yozai。

### inline 連結 / 連結語義軸：意圖宣告化，不靠 compiler 嗅探 URL（2026-07-02，定案，已實作）

- [2026-07-02] **起點（helpdesk QPKG 專案回饋）**：想讓「一句話中的某個詞」可點跳頁（如「需先以 QNAP ID 登入」的 QNAP ID），但 inline `[字](url)` 與 `link:` 的 `to` 不走 `_href`，href 原樣輸出 → 作者被迫寫死 bundle 錨點，單頁/debug 就跳不動，違反「一份語義源→三種輸出」。原提案：讓 inline/link 也走 `_href`，並把 `_href` 的 external 判斷放寬到 `://|mailto|tel|#`。
- [2026-07-02] **使用者否決放寬嗅探方向**：「應該要語意化而不是把意圖跟判斷封裝在 compiler」→ 「這是外部還是動線」是**作者的意圖**，該長在 YAML 語彙，不是 compiler 用字串長相 if-else 去猜。放寬 `_href` 嗅探正是反例（把更多政策塞進 compiler）。
- [2026-07-02] **定案：語義軸各自擁有行為，compiler 只有一條規則**：
  - 目標帶 `to:`（block `to:` key / inline `to:` 前綴）= **wireframe 動線** → 走 `_href` 依單頁/bundle/debug 改寫、進 flowmap。
  - 否則（`link:`、無前綴 inline、`mailto:`/`tel:`/`#`）= **外部/字面** → 原樣輸出、不進 flowmap。
  - inline 句中連結是「詞可點跳頁」的**唯一**表達（button/to: 是區塊塞不進句中）；用 `to:` 前綴宣告意圖（與 block `to:` 同字彙）。
- [2026-07-02] **反而是「少一條判斷」**：`_href` 移除 `if '://' in t` 嗅探 → 它變純動線解析器（外部永不流經）；`mailto/tel/#` 自然歸字面、免特例。這正是使用者要的「意圖在語彙、判斷不在 compiler」。
- [2026-07-02] **實作**：`inline()` 的 `[字](目標)`：`to:` 前綴→`_href(去前綴)`，否則字面（已 esc）。`_href` 去掉 `://` 守衛。`link:` 葉子維持字面 `esc(to)`（外部）。flowmap `walk_to` 加掃 inline `[字](to:目標)`、且跳過 `link:` 子樹（外部不計入動線）。三模式 + flowmap 實測通過。

### 寬度語彙回歸「關係型」：`grow` 統一、絕對值降為逃生門（2026-07-02，設計採納，待實作）

- [2026-07-02] **起點（helpdesk QPKG 專案回饋）**：畫 wireframe 常需「搜尋框收窄置中」之類寬度意圖，目前只能用絕對量值（`grid:[w-8,w-96]`）湊 → 已在寫**視覺規格**而非**低保真結構關係**。
- [2026-07-02] **核心論點：間距=節奏、寬度=關係（兩者性質不同，不可照搬 scale）**：
  - 間距是離散節奏刻度（`gap/padding` 走 `none/sm/md/lg` + theme 對照表），「md 間距」在哪都差不多 → scale 語義成立。
  - 寬度只有**相對容器**才有意義，天生語彙是**填滿/依內容/佔幾成/滿版**，硬塞 `sm/md/lg` 是把關係偽裝成量值。
  - 分水嶺：關係型（`full`/fill/fit/比例）= 語義、合低保真 ✅；絕對量值（`w-96`）= 規格、踩線 ❌。作者能自然接受 `full` 正因它是「100%/填滿」的**關係**。
- [2026-07-02] **這是先前「間距語義化、寬度維持 Tailwind」定案的精煉，非推翻**：Tailwind token 續用，但 README 重 framing → 關係型(grow/fit/%)=正道、絕對值(w-N)=逃生門。
- [2026-07-02] **提案與現況核對（實測程式）**：
  1. **`grow` 統一 track 與節點**（主）：現況同概念兩名字——節點屬性 `grow: true`（`wfyaml.py:534`）vs grid 欄軌 `flex-1`（`_track` map 到 `1fr`）。建議 `_track` 的 `('flex-1','fill','w-full')→1fr` 那組加入 `'grow'`，讓欄軌與節點同一個字：`grid:[w-56, grow]`、`grid:[grow, 60%, grow]`。改動一行。
     - **維護者補充**：`flex-1` 是**實作洩漏詞**（與先前「grid/flex 讓 LLM 誤以為實作要照做」同坑）→ `grow`（意圖詞）應為**正名主詞**，`flex-1` 降為相容別名，非平級。
  2. **`fit` 正名依內容**：`_track` 現況 `('w-auto','fit','auto')→auto` **已 map**，只差 README 以 `fit` 為語義正名。
  3. **比例（`%`/分數）為收窄正道**：`grid:[grow, 60%, grow]` 關係清楚、隨容器縮放，不挑像素。（`_track` 已支援 `%` 與 `w-a/b` 分數→fr。）
  4. **絕對 `w-N` 降為逃生門**：不移除，README 明講「破壞低保真契約、僅必要時用」。慣用式 `grid:[w-40, grow]`（label gutter 固定 + 內容關係型）仍合理；要收斂的是**內容本身硬寬**（如搜尋框釘 `w-96`）。
- [2026-07-02] **加分項：葉子內建預設寬**（`input`/`select`）→ 多數情況 `input: 搜尋` 免寫寬度，只有特別寬/窄才覆寫；把「不必湊像素」內建進工具，比命名更治本。
  - **維護者補充（實作坑）**：(a) 此屬視覺預設，依 style 解耦應進 `styles/clean/style.css`，非 `render_leaf`；(b) `.wf-field .wf-input{width:100%}` 已存在，若對 `.wf-input` 加預設 `max-width` 會反把該撐滿的表單欄位釘死 → 須 scope 到非 field（或 field 內 `max-width:none`）。
- [2026-07-02] **維護者結論：方向成立、與北極星②一致、無阻斷問題**。實作範圍小（`_track` 一行 + README 三處 + clean.css 預設寬）。
- [2026-07-02] **已實作**：`_track` 的 `1fr` 組加入 `grow`（正名主詞，`flex-1`/`fill`/`w-full` 為相容別名）；`fit` 本已在 `auto` 組（僅 README 正名）；README 欄寬段改為關係型正道表 + `w-N` 逃生門 framing + 「間距=節奏、寬度=關係」；`styles/clean/style.css` 給 `.wf-input` 加 `max-width:20rem`（`select` 本就依內容，不加以免被撐寬）。
  - **實作中發現**：base wf.css 的 `.wf-field .wf-input{width:100%}` 其實是**死碼**——無任何 emitter 產生 `.wf-field` 容器（只有 `text.label` 的 `wf-fieldlabel`）。輸入框本就是 `inline-block` 內容寬、不填滿寬欄，故 `max-width` 對既有 inline 用法無影響。`.wf-field .wf-input{max-width:none}` 守衛保留為該（現死）慣例的防護，日後真做 field 容器兩條規則即協作。死碼清理另議。

### 低保真契約的完整輪廓：四切面 + design token 對照 + 示意元件容器（2026-07-02，定案，widget 實作中）

起於使用者提問「我訂的這些是不是很像 design token？」與「wireframe 主張排版會不會越權、封死 mockup？」，一路收斂出工具 identity 的完整輪廓。

**A. 語彙 ↔ design token 對照（值軸=token / 關係軸=primitive）**
- 你定的間距(`none/sm/md/lg`)、tone、radius、字體 = **design token 的語義層(tier-2 alias)**，`:root` CSS 變數就是標準落地格式，`--style`/`:root` 覆寫 = 換值換皮(theming)。北極星②「語義非視覺」= design token 核心原則,等於獨立推導到同一結論。
- **兩點差異**：① 你把 primitive **封印**了(顏色只有 tone、字級只有 h1/2/3、寬度 `w-96` 是逃生門)——比一般 DT 嚴;② **不是每樣都是 token**——值軸(間距/色/radius/字體)=真 token,**關係軸(寬度 grow/fit、排版、對齊、grow)=layout primitive 不是 token**(不解析成固定值)。這正是「寬度不能套 sm/md/lg」的一句話根因。
- 未來若 theming 變深：把現在內嵌在 tier-2 的原始值(hex/rem)抽成 tier-1 調色盤讓語義名 reference;跨工具再對齊 W3C DTCG。現不需要。

**B. WHERE vs HOW（主張排版不越權；用關係講、不用像素釘）**
- wireframe **主張 WHERE**(誰在誰旁邊、被推到兩端、在誰下方)——這是本體(北極星①);**不主張 HOW**(像素幾何、樣子)——那是 mockup 地盤。
- 「logo 左、setting 右」是純 WHERE,合法。**驗證**:你會寫 `row: between`(講「兩端」的關係),不是絕對座標 → **用關係表達位置 = 不越權**;用像素釘位置才越權。這跟顏色只准 tone、寬度只准 grow/fit 同一把尺。
- 「封死 mockup」是誤解兩 artifact 關係:wireframe 是**可丟鷹架**或**可升保真的活源**,改一行重渲即可,封不死 mockup;真會封死是「組織把它當綁定規格」的流程問題,而低保真長相 + 改一行就變正是抵消它的機制。設計師分歧因此變成**有意識決定**而非無聲 drift。

**C. 結構保真度（別把慣例元件拆成釘死零件）**
- low-fi 契約的**第二個維度**:除了「別釘像素」(視覺保真),還有「別把 table 的 filter/search/sort 位置釘死」(結構保真)——那是元件庫擁有的慣例,前端會挑 AntD/MUI,不會照刻,釘死 = 過度指定 + 摩擦。
- **三個高度**:① 產品結構(wireframe 擁有:頁/大區/table 在這頁) ② 元件能力/意圖(宣告「能 search/filter/sort」不擺 widget) ③ 元件內部組合(元件庫擁有:排哪、sort 記號長怎樣 → 別主張)。
- **判準**:某個擺放是「刻意 UX 決策」(filter 常駐左欄因用戶整天篩)→ 主張;還是「元件剛好的預設」→ 放手。

**D. 保真度靠「自我聲明」把關,不靠「限制內容」（關鍵轉向）**
- 前面「宣告能力、別擺內部」收太緊。真正問題不是「畫了內部」,是「內部被當規格」。**自我聲明**解掉它:元件自帶「示意」標記 → 內部一律讀作代表性、非規格。
- 於是契約從**「限制你能畫什麼」轉為「對你畫的東西誠實」**:你可以畫得很細(內部排版 + `to:` 動線 demo)又完全不越權——因為 (a) 用關係型低保真詞彙(非像素)、(b) 元件聲明了自己是代表性的。**細節 ≠ 規定**,把「封死 mockup」疑慮解得最徹底。這是低保真社交訊號從「靠手繪長相暗示」升級成「語義層明講」。

**第三條原則（前兩條北極星的推論）**
> ③ 停在對的高度:複雜元件 = **自我聲明示意的容器**,宣告「能力」與/或示意「內部排版與動線(`to:`)」,不規定「實作」;不論多細,自我聲明保真度讓它保持代表性、非規定,實作內部歸元件庫。

至此低保真契約有**四切面**(同一 identity):(A) 寬度只走關係、(B) WHERE 用關係講不用像素釘、(C) 結構保真別拆死慣例元件、(D) 複雜元件宣告能力 + 自我聲明。

**示意元件家族 `widget`（table/chart/rich editor… 的通例；決策:先做通用 widget,具名之後擴充）**
- `widget: {kind, caps?, body?}`(或 `widget: 類型` 純量)。`kind`=類型標籤;`caps`=能力標籤 chips;`body`=選填內部示意排版(複用 row/col/grid/leaf 與 `to:` 動線)。
- 渲染 = 低保真框(虛線,區別實心 box) + 上頭(類型 + `◫ 示意` 標記) + caps chips + body + 註腳「實作依設計／元件庫」。**自我聲明內建在型別**,不用每次手寫。
- **兩種用法**:輕量(只 caps)/ 豐富(內部排版 + `to:` demo 動線)。demo 深度 = **視覺示意 + 可導覽**(零-JS 的 `to:`,非真過濾資料;真互動要 JS 且等於替元件庫做事,不做)。
- **通用優先於具名**:先一個通用 `widget` 接住所有(含沒見過的 rich editor/map);常用的 table/chart 之後再加具名 kind 做較貼的示意渲染,共用同一「宣告能力 + 自我聲明」基座。
- 幾乎全複用現成機制:內部走既有容器/leaf 渲染;`to:` 走剛做好的動線(單頁/bundle/debug + flowmap 皆通,walk_to 遞迴自然涵蓋 widget body)。

### widget API 命名定案：`is` + `can`（巢狀 dict-form）（2026-07-02，取代上方 kind/caps）

- [2026-07-02] **形式=巢狀 dict-form（屬 leaf 家族，非 container）**：widget 是多屬性元件，跟 `button:{text,to,icon}`、`image:{label,w,h}` 同族 → 屬性巢狀在 widget 底下。曾誤判該用 container 的 sibling-form（`row:` 那套），套錯家族。巢狀還把 widget 內在屬性(is/can/body)與節點 metadata(name/tone/to 掛同層)乾淨分層。
- [2026-07-02] **命名 `kind→name→label→is` 的收斂**：使用者逐一否決 kind(k8s 術語)、name(撞既有隱形 metadata 保留字)、label(不直覺)。根因：一直用**名詞式術語**命名「這是什麼」。改成 **`is`(是什麼) + `can`(能做什麼)** 一對 copula+modal → 讀成句子、短小白話、無術語、無撞車，與使用者偏好的 `can` 同語感。`caps→can` 同理（能力天生是動詞）。
- [2026-07-02] **最終形**：純量簡寫 `widget: 工單表格` = `{is: 工單表格}`；完整 `widget: {is, can, body}`。`is`=標籤(顯示)、`can`=能力 chips、`body`=選填內部示意(複用容器/leaf/`to:`)。`name/tone/to` 仍為節點層 metadata 掛 widget 同層、正交。
- [2026-07-02] **命名教訓**：`caps`/`kind` 當初是把「實作者的概念詞(capabilities/kind)」順手當 key，非從作者閱讀出發——與工具「語義由作者意圖命名」原則相違。作者面新 key 應先唸唸看「像不像人話」。

### 統一模型:page / layout / component / widget = 「結構單元」,內容一律 body（2026-07-02，定案）

起於「widget 內容該叫 body 還是 template?」,拉高到四者的語意統整,結論是**不加新字**。

- [2026-07-02] **四者本質相同(一塊低保真結構),只差角色**:
  - **page** = 會被輸出的畫面(有路由/URL、`canvas` meta);直接 render。
  - **layout** = 可複用的**頁面骨架**;`extends:`(頁面「成為」它);挖 `slot:` 洞。
  - **component** = 可複用的**內容片段**;`include:`(嵌入);`with:` 參數、可挖 `slot:`、`as:` 變體。
  - **widget** = 代表元件庫擁有的**複雜元件的示意替身**;直接放進內容;`is`/`can`、自帶 `◫ 示意`。
- [2026-07-02] **貫穿哲學:layout/component/widget 都是「低保真骨架,之後被實現」**——layout 被 slots 填實、component 被 include 具現、widget 被真元件庫實作。這是「統一」的真義,也是先前想用 `template` 標記的精神。
- [2026-07-02] **關鍵決策:此精神由「單元類型」表達,不再造 `template` 字**。單元類型名(layout/component/widget)已講清角色,內容區再叫 template 是同義重複,違反「別設計過多詞彙」。→ **widget 內容維持 `body`,不加 template**(零改動,現況即是)。
- [2026-07-02] **最小詞彙集**:內容區=`body`(page/layout/component/widget 通用)、洞/填洞=`slot:`/`slots:`、複用引用=`extends:`(骨架繼承)/`include:`(片段嵌入)、參數=`with:`、身份/能力=`is`/`can`(widget 特有)。
- [2026-07-02] **解「body 語意不明確」**:body 曾感覺不清,是因 widget 被當特例;歸位成「與 page/layout 同類的結構單元」後,`body`=「任何單元的內容區」即一致清楚。「它是示意」由 widget 類型 + `◫ 示意` 標記 + `is` 扛,不靠 key 名重講。

### 浮層 / z 層:以正交原語為地基,具名角色僅為糖（2026-07-02，設計定案，待實作）

討論從 dialog(overlay 背景)→ 右下角機器人 → 抽屜 → z 層,收斂出浮層系統的地基原則。

- [2026-07-02] **決定性原則:組合原語,不列舉角色**。建立在具名角色(dialog/drawer/toast/alert…)上的系統**無法長久**——每出一種新樣式就要加一個字。改用少數**正交、封閉、可組合**的原語(同 row/col/grid 組合出任何排版的哲學),任何浮層(含未來還沒名字的)= 原語的一種組合,**永不需擴充語彙**。
- [2026-07-02] **三個正交原語**:
  1. **`pin: <錨點>`**(placement):center / 邊(right/left/top/bottom)/ 角(bottom-right…)。**邊緣值=沿邊撐開** → 左右邊=全高抽屜、上下邊=全寬橫幅/bottom sheet;角=FAB/機器人;center=dialog。一個 `pin` 收整個位置家族。
  2. **`modal: true`**(blocking):擋不擋後面(scrim + 後面 inert)。**取代先前的 `backdrop`**——`backdrop` 命名的是視覺產物(暗色層)且像為 dialog 而生;`modal` 命名互動意圖(攔截),通用於 dialog/drawer/sheet/lightbox,scrim 是它的視覺呈現(封 renderer)。預設非 modal(機器人/toast/FAB 免旗標)。
  3. **z 序**(你討論的「層」):**用關係型 ordinal**。z 序是**關係**(誰疊誰上),非絕對視覺量值(不同於 `w-96`)→ 數字只表相對順序,屬語意允許的關係型(同 `grow`/grid 比例)。好處正是**長久**:新層級=一個新數字,**零 vocab 成長**;可加 1–2 語意錨(`overlay`/`top`)當常用別名。多數浮層免寫 z(預設疊在 base 上、依出現序);僅多浮層並存需排序(如 alert 壓 dialog)才明給。
- [2026-07-02] **錨定對象 & 常駐/暫時 = 樹狀放置決定**(不加屬性):`pin` 錨定其**所在容器**(最近的 box;最外層=畫面);放 layout 根=常駐(機器人)、放 state=暫時(dialog)。`modal` 的 scrim 也只罩其所在層(放 card 內=card 級遮罩)。fixed(釘畫面)vs absolute(釘 box)由放置層級自動決定,封 renderer。
- [2026-07-02] **具名角色(dialog/drawer/toast)降為「純糖」**:是**展開成原語的捷徑**,且**缺席永不阻塞**——沒對應 preset 就直接組 `pin`+`modal`+z。常見/AI 好懂情境用糖(`drawer: right` = `pin: right`),新樣式組原語。**地基放原語,AI 才真長久可用**(AI 對「錨哪+擋不擋+疊多高」能自由組合出任何樣式,含無專名者;具名角色會讓 AI 遇沒對應詞就卡)。
- [2026-07-02] **別把新 z 概念叫「layer」**:`Layer 1/2` 已用於**關注軸**(產品 UI vs 示意註記,決定可否剝離),與 **z 深度**是正交兩軸,勿混。z 深度用上述 z 序原語;若引入 key 名避免用 `layer`(撞 L1/L2)。L2 註記可理解為 z 最頂 + 帶「可剝離」屬性,故關注軸與 z 軸組合即可涵蓋,不需併成一個「layer」傘。
- [2026-07-02] **未實作**:以上為設計定案;`pin`/`modal`/z 原語、`drawer` 等糖、state 開關動線(複用既有 `to:`+routes)待實作。

### 浮層語彙定案：`pin` + `modal` + `layer`；「Layer 1/2」關注軸更名（2026-07-02，取代上方 z-ordinal/「別叫 layer」）

- [2026-07-02] **最終三原語（值域皆封閉/語意）**:
  - **`pin: <錨點>`** — 錨哪(center / 邊 / 角)。邊緣值=沿邊撐開(抽屜/sheet/橫幅)。
  - **`modal: true`** — 擋不擋後面(scrim + 後面 inert)。**使用者拍板保留 `modal`**(捨 `blocking`)：它是精準且 AI 最穩的 UI 標準詞;dim 是它的視覺呈現,封 renderer。預設非 modal。
  - **`layer: <級>`** — 在哪一 z 層。**封閉語意 scale `base < overlay < notify < top`**(取代先前「關係型 ordinal / `raise`」構想)。理由:① 使用者要「有語境」——讀 `layer: notify` 立刻知道層級,勝過裸數字或宣告順序;② 這與 `gap: none/sm/md/lg` 同款「小而封閉的語意 scale」,封 renderer(帶→z-index)、可 theme;③ 不隨浮層型別膨脹(新型別挑一帶,不加帶),只有刻意插 z 級才動 scale(同加一階 spacing)。捨 `raise`(動詞+往上暗示,與 `base` 打架)、`elevation`(術語)。
- [2026-07-02] **`layer` 讓給 z 層 → 原「Layer 1/2」關注軸更名**(避免撞名):
  - **Layer 1(產品 UI 語義,tone/status)→「產品面」(product plane)**
  - **Layer 2(Demo 標註,note/spotlight,可剝離)→「標註面」(annotation plane)**
  - 用「面/plane」替「層/layer」;程式/CSS 無字面 `layer`(class 為 `wf-tone`/`wf-mnote`/`wf-spot`),故純文件更名(README + 本檔加對照)。歷史 log 不逐條改寫。
- [2026-07-02] **z 序的表達**:`layer` 帶別內建在浮層元件裡(dialog=overlay、toast=notify、alert=top);**共存**時(同一 overlay slot)照帶疊、全域一致;**不共存**(不同 state)無所謂。
- [2026-07-02] **具名角色仍為糖**:`dialog`/`drawer: right` 等可選,展開成 `pin`+`modal`+`layer`,缺席不阻塞。
- [2026-07-02] **未實作**:待實作 `pin`/`modal`/`layer` 原語 + overlay slot 慣例 + README 更名。

### 浮層 pin/modal/layer + Layer 更名（2026-07-02，已實作）
- [2026-07-02] **實作**：`render_item` 加 `pin`/`modal`/`layer` 三屬性 → 包一層 `.wf-layer`(絕對定位、錨定最近 box/root、flex 依 pin 對齊、z-index 由 `_LAYER_Z` 帶別決定)；`modal` 加 scrim+擋;結構在 `wf.css`、scrim/陰影在 `clean/style.css`。實測 loading(center+modal+top)/toast(bottom-right+notify)/抽屜(right+modal) 皆正確。
- [2026-07-02] **README**：新增 §5.6 浮層(pin/modal/layer + 放置決定錨定/常駐);**「Layer 1/2」關注軸更名為「產品面/標註面」**(把 layer 讓給 z 層),README 全面替換。
- [2026-07-02] **已知限制**：多個 modal 同時並存時的相互壓暗次序在極端堆疊下不完美(實務一次一浮層,無此問題)。

### 擴充性定位:專案級 design token（非 theme）× `--style` 外觀 = 兩軸（2026-07-02，方向定案，待細談/未實作）

從「使用者能否自定義 layer 語境」收斂到更根本的概念:那不是 layer 專屬機制,是**語義 token 主題化**;而且**不是 theme,是各專案自己的 design token**。

- [2026-07-02] **兩個正交軸,勿混**:
  - **`--style`(flavor/外觀)** = 手繪/乾淨/mockup 的**長相**(筆觸、字體、border 素材)。**工具內建**。
  - **專案 design token** = 這個專案的語義 scale **值**(間距階、z 層 `layer`、tone→色、radius…)。**各專案自帶**。
- [2026-07-02] **design token 本質 project-scoped**(一產品一套設計決策)→「各專案自己的 design token」是本義,不是工具全域 theme。工具只出**預設 token(可攜地板)**,專案可帶覆寫。
- [2026-07-02] **這是 wireframe→該產品 mockup 的真正橋**(保真度旋鈕實際機制):同一份 YAML + 工具預設 token = 通用低保真;+ 專案 design token = 講那產品的設計語言、逼近其 mockup。**YAML(語義源)完全不動**,只換一組 token → 守北極星②。
- [2026-07-02] **`layer` 的擴充性歸位**:它只是專案 design token 檔裡的**一個 scale**(該專案的 elevation tokens),與 spacing/tone/radius/scroll 平起平坐,**非 layer 專屬機制**。無 token 檔→用內建、YAML 照樣可攜;有→套專案語義。
- [2026-07-02] **可攜性地板**:內建 token 名/帶恆效,專案 config 只能覆寫值 / 加帶,不能廢內建 → 任何 YAML 到哪都讀得懂。
- [2026-07-02] **格式**:可對齊 **W3C DTCG**(design token 標準),讓專案既有 token 直接餵入。
- [2026-07-02] **狀態**:方向定案,細節(檔案格式、載入機制、哪些 scale 開放、layer 有序帶列形狀、lint 對齊)待後續細談;未實作。

### semantic token 擴充 vs 北極星:採納前提（2026-07-02，護欄定案）

判定:專案級 semantic token 擴充**不違反北極星,反而強化②**;但①靠三條護欄,守住才安全。

- [2026-07-02] **強化②**:`gap: section`(意圖)比 `gap: md`(大小)更語義;作者仍不寫任何 px/hex(值封在 token 表);人機共讀不減反增。semantic token 是②的巔峰,非視覺逃生口。
- [2026-07-02] **① 的護欄(必守,否則破①)**:
  1. **零設定可用**:工具永遠出內建 primitive(sm/md/lg、base/overlay/notify/top、預設 tone)→ 不寫任何 token 也能畫。
  2. **semantic token 純選配**:只在「對齊某產品」時才疊上,**永不是畫圖的前提**(若變成強制前提 = 破①,變「先做設計系統才能 sketch」)。
  3. **低保真是預設模式**:專案 token 是「往 mockup 靠」的選配升級,不取代低保真。
- [2026-07-02] **可攜性代價 + 緩解**:用了專案 semantic token 的 YAML 不再自我完備(需 token 表解讀)→ 內建預設當**可攜地板**、未知 token **優雅退回**(近似 primitive / lint 提示),少 config 仍能降級渲染。
- [2026-07-02] **非任務漂移**:這就是既定「單一語義源 × 漸進保真」旋鈕的實作——同一份 YAML 不動,換 token 表就從通用低保真→講某產品語言。**沒有這層,migrate 成 mockup 只能改 YAML,那才破②**。
- [2026-07-02] **破的唯一方式**:讓 token 表變畫圖的強制前提,或把工具做成重型 design-system 平台。
- [2026-07-02] **一句話**:低保真預設零設定即可畫;semantic token 純選配、只在對齊產品時疊上;工具詞彙不增長(專案自帶字典);內建預設當可攜地板 + 缺失優雅退回。

### semantic token Phase 0+1 實作:引用型 token(gap 驗證)（2026-07-02，已實作）
- [2026-07-02] **載入機制**:`_load_tokens(basedir)` 探測選配 `wf.tokens.yaml`(compile_all/bundle 各載一次);不存在→`_TOKENS` 空、全走內建 primitive(零設定護欄)。
- [2026-07-02] **引用型解析**:`_tokens_css()` 把 `gap: {section: lg}` 編成 `:root{--wf-gap-section:var(--wf-space-lg)}`(放 clean 之後→可引用 primitive);`_gap(name)`:內建刻度直用 / 專案 token→`var(--wf-gap-<名>)` / 未知→退回 `md`+stderr warn(可攜地板 + 優雅退回 + lint)。`render_container` 的 gap/padding 改走 `_gap`。
- [2026-07-02] **實測**:有 token→`gap: section/list` 生效(section 寬、list 緊);移掉 token 檔同份 YAML 仍渲染(退回 md + warn);全 examples 回歸無誤(頂層無 token 檔、primitive 照舊)。三條護欄驗證通過。
- [2026-07-02] **待續**:Phase 2 組合型(overlay 角色 dialog/toast 由 token 定義、render_item 展開);tone/scroll 納入引用型;`--tokens` 顯式旗標;DTCG 匯入;lint 併入 P0.7。

### semantic token Phase 2 實作:組合型 overlay 角色（2026-07-02，已實作）
- [2026-07-02] **內建 overlay 角色(可攜地板)**:`_OVERLAY_DEFAULTS` = dialog/drawer/sheet/toast/loading，各為 pin/modal/layer 的組合;`_overlay_tokens()` = 內建 ∪ 專案 `wf.tokens.yaml` 的 `overlay:`。
- [2026-07-02] **展開**:`render_item` 開頭偵測 node 是否帶 overlay 角色 key → 取出內容當 col、把角色的 pin/modal/layer 以 `setdefault` 注入(**node 顯式屬性可覆寫 token 預設**),再走既有容器 + pin/modal/layer 渲染。
- [2026-07-02] **實測**:無 token 檔即可用 `loading:`/`toast:`/`drawer:`(內建地板);專案可覆寫(drawer→左)、自定新角色(banner)、node 顯式覆寫(dialog+layer:notify);全回歸無誤。
- [2026-07-02] **成果**:之前一直當「糖」推遲的具名角色,正式成為**組合型 semantic token**——作者寫意圖(dialog)、地基是原語(pin/modal/layer)、專案可自定,三者兼得。待續:tone/scroll 引用型納管、`--tokens` 旗標、DTCG 匯入、lint。

### semantic token 保留角色指紋(drawer ≠ box)（2026-07-02，已實作,修 Phase 2 缺口）
- [2026-07-02] **問題(使用者提)**:組合型 token 展開成 primitive 後,`drawer` 變成純 `box + pin`,「它是 drawer」在產物裡消失 → 無法區分/針對 styling(drawer 貼邊無圓角 vs box 有框)、也丟語義(LLM/debug 讀不出)。
- [2026-07-02] **修法**:展開時**保留角色名當指紋**——node 加 class `wf-role-<角色>` + 屬性 `data-wf-role="<角色>"`。primitive 驅動機制、角色名留可讀/可 target 的指紋。同 `tone: danger`→`wf-tone-danger`、widget 留 `is` 的原則:semantic token 不該展開後蒸發。
- [2026-07-02] **成果**:`.wf-role-drawer` 可獨立 styling(已加「貼邊無圓角」示範);`data-wf-role` 讓產物語義可讀;drawer/toast/loading 各留指紋、與一般 box 可區分。

---

## 【彙整】語義 token 系統總覽（2026-07-02，散條目索引 + 現況圖）

> 以下為前述分散條目的統整;細節見各原始條目。

### A. 三層模型
- **primitive(tier-1)**:原始刻度/值——space `sm/md/lg`、色盤、z-scale、border、font。工具內建。
- **semantic token(tier-2)**:意圖命名、引用/組合 primitive、**專案可定義**。兩型態:
  - 引用型(單值):`gap: section`→space.lg、`tone: danger`→色、`frame: strong`→border。
  - 組合型(一包屬性):`box.section`={gap:sm,frame:strong,padding:sm}、`overlay.drawer`={pin,modal,layer} → **tier 鏈**(容器 token→屬性 token→primitive)。
- **grammar**:結構文法,不 token 化。

### B. 全語彙五分類(+標註)
| 類 | 判準 | 成員 | token 面 |
|---|---|---|---|
| ① 參數 | 配置頁/輸出 | page, canvas, routes | grammar |
| ② 函式 | 引用/組合/控制 | extends, include, with, slot(s), as, when | grammar |
| ③ 容器 | 有 children(key 位)| row, col, grid, box/box.*, widget, overlay.* | 家族點式 |
| ④ 元件 | 終端葉子(key 位)| text.*, input, button, status.*, badge, icon… | 家族點式 |
| ⑤ 屬性 | 掛節點的修飾(value 位)| name, gap, tone, frame, pin, modal, layer, to | 裸值,值可 token 化 |
| 標註 | Layer2 meta | note, spotlight | meta,不 token |

### C. 命名規則
- 容器③+元件④(key 位)→ `family.variant` 點式(有變體);單一裸。
- 屬性⑤(value 位)→ 裸值(`gap: section`);類別由 key 決定。
- ①②+標註 = grammar/meta,不 token。

### D. 浮層 / box / frame
- 浮層三原語:`pin`(錨)+ `modal`(擋)+ `layer`(z 帶 base<overlay<notify<top)。
- box 容器化:`box`/`box.header/section/footer`(語義容器家族,專案定義屬性預設包);**框線降為 `frame` 屬性**(可 token 化 DTCG border 複合);box 預設框由角色 style 給、`frame` 可覆寫。
- 組合 token 展開留 `wf-role` 指紋(drawer ≠ 一般 box、可 target styling、語義可讀)。
- ⏳ 待決:z 帶名 `overlay` 撞容器家族 `overlay.*` → 考慮改 `raised`。

### E. 擴充:專案 design token(非 theme)
- `wf.tokens.yaml`(選配):各專案自帶語義 scale 值;與 `--style`(外觀 flavor)**正交**。
- 「單一語義源 × 漸進保真」旋鈕:換 token 不動 YAML → 逼近某產品 mockup。
- 對齊 W3C DTCG(color/dimension/border/typography 有型別;`layer` 無型別需 `$extensions`)。
- origin(內建 vs 專案):type-namespace + lint/introspection(放棄 `$` sigil)。

### F. 護欄(不破北極星)
強化②;①靠三條:零設定可用 / semantic token 純選配 / 低保真為預設;+ 內建可攜地板 + 未知優雅退回。

### G. 實作進度
- ✅ pin/modal/layer 原語;Layer 1/2 → 產品面/標註面。
- ✅ Phase 1 引用型 token(gap)+ CSS var 別名 + fallback + lint warn。
- ✅ Phase 2 組合型 overlay.* token + wf-role 指紋。
- ⏳ 待實作:box 容器家族 + frame 屬性/token、組合型一般化(任意專案家族)、frame/tone/scroll 納引用型、`--tokens` 旗標、DTCG 匯入、lint 併 P0.7、z 帶改名。

### 命名空間 / box 容器化 / frame 屬性化（2026-07-02，定案;`$` marker 否決）

本輪把「容器身份、box、frame、命名空間」一次收斂。

**A. box 容器化 + frame 降級為屬性**
- 舊 `box: true` 同時扛「容器 + 框線」→ 拆:
  - **`box` / `box.header` / `box.section` / `box.footer`** = 語義**容器家族**(③),專案在 `wf.tokens.yaml` 定義一包屬性預設。
  - **`frame`** = 視覺**屬性**(⑤,裸值);`frame: true/false`(內建)或 `frame: subtle/strong…`(專案 semantic → DTCG `border` 複合)。
  - box 預設框由**角色 style**(`.wf-box`/`.wf-role-box-*`)給、`frame` 可覆寫。「畫框是視覺,不該是語義容器的本質」。

**B. 容器 semantic token = 屬性預設包(tier 鏈)**
- `box.section` = `{gap:sm, frame:strong, padding:sm}`;`overlay.drawer` = `{pin,modal,layer}`。
- 包裡每個值各自再解析:`gap:sm`→primitive、`frame:strong`→border token→複合。形成 **容器 token → 屬性 token → primitive** 三層鏈(DTCG alias chain)。
- 展開機制通用(overlay/box/任意專案家族共用一條);展開後留 `wf-role` 指紋。node 顯式屬性覆寫 token 預設。

**C. box 是「隱含的基底語義容器」**
- 洞察:`widget` / `overlay.drawer` / `box.section` 全是「box + 角色 + 屬性包」的特化。共同基底 = 語義容器(box)+ `wf-role` + 屬性包。
- 實作收斂成**一條**「語義容器展開器」;`widget` 是同底 + caps/示意 的特製子渲染(唯一特例)。「box 家族不是新增,是把已隱含的基底顯性化」。

**D. 命名空間分層（`$` marker 否決 —— 冗餘）**
- **文件/組合層(grammar 關鍵字,封閉)**:`page` `canvas` `routes` `body` `extends` `include` `with` `slots`/`slot` `as` `when`。不套命名空間、不 token 化、無 marker;靠「已知關鍵字 + 位置」辨識;未知頂層 key → lint error。
- **內容層(節點身份)**:
  - **一次性**:`name: 說明`(通用 box + 標籤)。
  - **內建角色**:裸 `row`/`box`/`widget` 或內建點式家族 `overlay.drawer`/`text.title`。
  - **專案 token**:`family.variant` 點式(`box.section`/`card.hero`),定義在 `wf.tokens.yaml`。**點式結構由專案自組**(扁平或分層)。
  - **參數/區域變數**:`{{title}}`(`with:` 填,局部);與全域 token 不同 scope。
  - **屬性值 token**:裸值(`gap: section`、`frame: strong`)。
- **`$` 前綴 marker:考慮後否決**——雖能一眼標 origin,但覺得**冗餘**。改由 **built-in 為已知封閉集 + lint/introspection** 分辨內建 vs 專案;未知裸名→lint error、未知 token→warn+退回。
- **origin 分辨責任**:lint/introspection(枚舉生效詞彙、標源),不進語法。

### 更正:box 不容器化,維持 primitive（2026-07-02,推翻上則 A/B 的 box 部分）
- [2026-07-02] **box 維持原始 framing 屬性 `box: true`,不做語義容器家族**。撤銷 `box.header/section/footer`;也不另切 `frame` 屬性(box:true 本身即框)。
- **理由**:box 是 primitive(框這個原始能力),和 gap/tone 同層;把它做成語義 token 家族(box.*)是把 primitive 混進語義命名,不乾淨。
- **專案語義區塊**(header/section…)→ 走 widget / `name:` 標籤 / **專案自己的家族**(如 `card.hero`);這些內部可用 box,但不命名為 `box.*`。
- **保留**:組合型 token 機制(overlay.* 內建 + 專案自定家族)、命名空間分層、屬性值 token 化——只是 box 留在 primitive 層、不參與語義容器命名。
- **實作面**:無需改碼(box.*/frame 皆未實作)。

### 統一擴充願景 + `list leaf` 探索;附防漂移原則（2026-07-02，記錄為「opt-in / 按需再建」的方向,非承諾）

**願景(方向,未實作)**
- **統一擴充**:同一條 `family.variant`/新家族機制套到**所有節點**——擴既有家族(`text.error`、`row.jumbo`)或定義新家族(`section`);擴既有→base 由家族決定,新家族→token 宣告 `base`。展開=基底+屬性包+`wf-role` 指紋,屬性各自走既有解析。overlay/box 那套推廣到全部。
- **`list leaf`(introspection)**:`wfyaml --list` 枚舉所有語意節點(built-in + project)+ 標源 + 用法/展開。AI 動筆前先 list → 一次看懂全部詞彙 + origin。
- **這證成 `$` 可拿掉**:discovery/origin 交給 `list`(工具回答),不塞進語法。

**⚠️ 防漂移原則(明確寫下,免得工具失焦)**
- [2026-07-02] **身份不動**:工具是「**低保真 UI/UX 快速討論**」;token 系統是**選配腳註**,收進進階章節,新手/核心路徑看不到、不受影響。
- **兩個真實風險**:① **概念重量**——即使 opt-in,一整套 token 詞彙「看起來很重」本身就違反①(低心智)。② **注意力漂移**——設計 token 不該吸走本該投在核心(真實 wireframe 使用、動線/評審迴路)的心力;做成 design-token 引擎會失 niche、且打不贏 Style Dictionary/Tokens Studio/Figma。
- **YAGNI 收手**:Phase 1/2(gap/overlay)**已證明 pattern**;**不**投機式把 list/family 一般化/DTCG 引擎全建出來,**等真有專案要 mockup-align 才拉動**。
- **記錄 ≠ 承諾**:本區塊是保存思考,不代表要實作;實作優先級**低於**核心低保真/討論體驗。
- **判準**:任何 token 功能要通過「零設定核心是否更快更簡?新手是否仍看不到複雜?是否有真實需求拉動?」三問,否則不做。

### fidelity 輸出模式 = 結構性防漂移（2026-07-02,採納,列為 token 系統前置地基）

使用者提出的最強防漂移設計:把「保真度」變成**輸出模式**,預設把輸出夾在內建低保真詞彙內。

- [2026-07-02] **機制**:
  - **wireframe(預設)**:renderer **夾在內建詞彙**——token 值落在內建刻度內就用(`section=lg`→lg),**超出內建就退回預設**(`jumbo=xl/40px`→md);tone 非內建 6 名→muted、frame 自訂→內建框、色/字精確值→內建。
  - **`--mockup`(明確要求)**:才榮譽全套專案 token 的精確/自訂值。
- [2026-07-02] **為何是「結構性」防漂移(勝過文件紀律)**:預設輸出**本質上畫不出高保真**——沒說 mockup 就出不了 mockup,預設永遠收斂成 wireframe,不管專案 token 定義多豐富。renderer 預設的**能力上限就是內建低保真詞彙**。
- [2026-07-02] **順手解掉的漂移憂慮**:概念重量(定義再多、預設體驗純低保真)、可攜性(無 `--mockup` 永遠低保真可攜)、單一語義源(旗標切保真度)、失焦(要 mockup 是刻意動作,身份不動)。
- [2026-07-02] **統一規則**:wireframe 模式 = 只認內建詞彙;任何專案 richness 一律夾回內建低保真。
- [2026-07-02] **對現況小調整**:Phase 1 的 `gap: section` 目前永遠出值;改為**預設夾內建刻度、`--mockup` 才解全套**;加 `--mockup`/`--fidelity` 旗標 + resolver 分模式。

### 三環同心架構定案（2026-07-02，收斂全部訴求為單一設計）

起於使用者統合思考:最少 token 讓 AI 理解 + 最少元素讓 AI 創作 + wireframe/mockup/product 不混 + 支援 wireframe→mockup→AST→code 開發鏈路 + 版控 + 多受眾動態輸出。

- [2026-07-02] **三環同心，職責正交**:
  - **Ring 0 結構原語（~15 個，AI 必背，恆定不成長）**:`row`/`col`/`grid`/`box` + `text.*`/`button`/`input`/`icon`/`status`/… 所有輸出模式共用同一組。AI 字母表。
  - **Ring 1 語義 token（opt-in，AI 讀 `wf.tokens.yaml` 即懂，不背）**:`gap: section`、`tone: brand`、`overlay.drawer`、`frame: strong`。值換皮詞彙不變。Phase 1/2 已 land。
  - **Ring 2 輸出模式（旗標，不進 YAML，讀者面）**:`--style clean/sketch/mockup`、`--fidelity wireframe/mockup`、`--emit html/png/ast/react`、`--audience pm/eng/customer/discuss`(sugar 別名)。
- [2026-07-02] **關鍵不混淆原則**:**YAML 詞彙 = Ring 0 + Ring 1**(作者面)；**輸出樣貌 = Ring 2**(讀者面)。作者永遠不用想「我在做 wireframe 還是 mockup」——模式是讀者側旗標;AI 也永遠不會誤把 mockup 值塞進 wireframe YAML(fidelity mode 硬夾)。
- [2026-07-02] **六訴求同時解決的推導**:
  - AI 最少負擔:Ring 0 恆定小、Ring 1 靠 introspection 查、Ring 2 不進 YAML。
  - 三面不混:靠 fidelity mode **結構性防漂移**(renderer 硬夾)，不靠作者自律。
  - Pipeline:wireframe→mockup=加 tokens+`--mockup`；mockup→AST→code=`--emit ast`+codegen。
  - 版控:YAML/tokens.yaml/style CSS 全 plain text，git-native。
  - 多受眾:同一份 YAML 交叉旗標(PM/Eng/客戶/討論)。
- [2026-07-02] **與現有系統對齊**:fidelity mode(8c953bb)/`--style`解耦(a368d72)/semantic token Phase 1/2/anti-drift 原則(8d06e63)/widget(7b08c1c) 全部落在三環正確位置——結構驗證方向定案。
- [2026-07-02] **現況 gap(補齊三環最少改動)**:
  - **P5.1 `wireframe-lofi list`** introspection 子命令(枚舉 Ring 0 + 專案 Ring 1，AI/作者查詞彙)——~50 行 CLI
  - **P5.2 `--emit ast`**(產結構化節點樹 JSON，走 P4 E1/E2 schema，codegen 前置)——中量
  - **P5.3 `--audience` sugar**(打包 fidelity+style+tokens+emit 成 pm/eng/customer/discuss 別名)——~10 行
  - **P5.4 Ring 0 字母表明列**(README 一節列全部 ~15 原語 + Ring 1 opt-in 說明 + Ring 2 旗標對照)——文件
- [2026-07-02] **AI prompt 範例（三環的 payoff）**:一份 prompt 涵蓋所有情境——
  ```
  可用詞彙：Ring 0(結構原語,恆定) + Ring 1(本專案語義 token,查 list)
  規則：不寫視覺細節(px/hex);不表達事件(onClick);Ring 2 是 CLI 旗標不進 YAML
  ```
  AI 無論產 wireframe / mockup / codegen 都用同一組詞彙寫。
- [2026-07-02] **細節見** `TOOL-SUGGESTIONS.md` P5 節。

### ⏳待討論：Flow-scoped 聚焦輸出（P6，2026-07-02）

- **問題**：巨型專案 POC/評審不該 bundle 整包 500 頁；單頁又無動線；手選一組頁無命名。**flow 是對的粒度**（一次決策對應一條 flow）。
- **兩個機制構想**（並存互補）：
  - **A. 自動 walk**：`--bundle --entry X --depth N` 從入口沿 `to:` 動線圖走 N 跳（`flowmap.py` 已有 walk 演算法可 reuse）。適用探索期。
  - **B. 具名 manifest**：`flows/<name>.yaml` 只寫 `entry` + 選填 `include/exclude`，pages 靠 `to:` 自動 walk。適用固化流程反覆評審。
- **屬 Ring 2 擴充**：不動 YAML 詞彙、走既有動線、~30 行複用 flowmap；符合 anti-drift。
- **附加價值**：flow 天然是團隊分工/PR/評審排程單位；`flows/` 目錄=專案 sitemap。
- **狀態**：**方向紀錄，未承諾實作**。等真的多條 flow 需求拉動再做（YAGNI）。細節見 `TOOL-SUGGESTIONS.md` 優先序表 P6 欄。

### Theme-as-binding-YAML：四層架構 + CLI 收斂（2026-07-03，設計定案，待實作）

起於使用者提出「theme 用 binding 執行、component 專注語境、page 用 component/primitive、theme 綁 primitive」的乾淨模型，與後續「`--fidelity` 冗餘、`--mockup <theme>` 一箭雙鵰」的收斂。

- [2026-07-03] **四層 + 消費矩陣**：
  - **Primitive** = 原子刻度（spacing/tones/sizes/radius/z-scale）
  - **Component** = 純語境合約（is/can/layer/pin/結構）— **禁物理視覺**
  - **Page** = 組 Component + Primitive 出畫面
  - **Theme** = 綁定物理到 Component 名（用 Primitive 值），render 時注入
  - **誰可用誰**：Component 只能用 Primitive；Page 用 Component + Primitive；Theme 用 Primitive（單向綁 Component 名，不反查 Component）。
- [2026-07-03] **相對現況強在何處**：現況 style 是 CSS-driven（web-only），theme 資訊卡在 web；改成 **YAML-driven binding** → theme 是資料可跨 target 翻譯（web→CSS、native→SwiftUI/RN），補齊 Ring 2 `--emit ast` → code 路線缺口（P5.2）。
- [2026-07-03] **命名不用「多態」等術語**：Theme YAML key 對 Component key 同名 → render 時疊上，就是 **binding**（同 CSS-in-JS / styled-components），命名直白。
- [2026-07-03] **CLI 收斂：`--mockup <theme.yaml>` 取代 `--fidelity`**：
  - 沒 `--mockup` = wireframe 模式（結構性防漂移，硬夾 Ring 0），`--style clean/sketch` 決定線框美學
  - 有 `--mockup <file>` = mockup 模式 + 該 theme 綁定
  - **`--fidelity` 旗標消失**（theme 存在本身即 fidelity 訊號）
  - **`--style mockup` 移除**（跟 `--mockup <theme>` 撞用途；mockup 樣貌由 theme 決定不是 style）
  - **`--style sketch` × `--mockup` 互斥**（語義衝突 → error）
  - 好處：進 mockup 要**明講哪個 theme**（品牌 A / B / 標準），不能空喊 → anti-drift 更嚴。
- [2026-07-03] **檔案結構**：
  ```
  src/
    page.wf.yaml
    components/               # 純語境合約
    tokens/                   # Primitive 分檔（spacing/tones/sizes/z-scale）
    themes/                   # 綁定（mockup.yaml、brand.yaml…）
  ```
- [2026-07-03] **P0.7 消費規則 lint**（併入 schema validation）：
  - Component YAML 禁物理視覺 key（`border: 5px` → error）
  - Component YAML 禁引用 `theme.*`
  - Page YAML 禁引用 `theme.*`
  - Theme YAML 禁引用 `component.*`（反查禁止）
  - 未知 primitive 引用 → warn 退回預設
- [2026-07-03] **對三環架構的定位**：四層是**如何組織 Ring 1 資產**（primitive → component → page；theme 側路綁定），三環是**如何暴露給作者/AI/讀者**。兩者正交、不衝突。
- [2026-07-03] **對現況改動**：`wf.tokens.yaml` 拆成 `tokens/*.yaml`（primitive 分類）；現有 `assets/styles/<name>/style.css` 保留為 web renderer 實作細節；新增 `themes/*.yaml` 資料層；`--fidelity` 移除；P0.7 lint 加消費規則 5 條。細節見 `TOOL-SUGGESTIONS.md` P7 節。

### 全字詞審查 & 分階段執行計畫（2026-07-03，決策定案，Phase 0-2 執行中）

一次性 review 全部 keyword/CLI/scale，收斂**換名 / 合併 / 新增 / 移除**動作，分三階段執行。動作圖例：⚠️ 換名 · 🔀 合併 · 🔵 新增 · ❌ 移除。

- [2026-07-03] **⚠️ `include:` → `embed:`**（Phase 0a）→ Twig `{% embed %}` = include + slot 覆寫，命中 wireframe-lofi include-with-slots 真實語義；`extends` + `embed` 骨架/片段對比更清晰。POC 階段換名成本最低。loader 相容 `include:` 走 deprecated warning，過渡期後移除。
- [2026-07-03] **❌ `--fidelity` 旗標移除 + `--style mockup` 移除**（Phase 0b）→ `--mockup <theme.yaml>` 一箭雙鵰（見前 P7 定案）：theme 存在即 fidelity 訊號、`--style` 只留 wireframe 側美學 `clean/sketch`。CLI 少兩個旗標。
- [2026-07-03] **🔵 新增 `progress` leaf**（Phase 0c）→ `progress: {value: 0-1, tone, label?}` 或 scalar `progress: 0.5`。value 用 0-1 語義比例（非像素/%字串）；記帳/預算/募款/專案剛需。
- [2026-07-03] **🔵 新增 `avatar` leaf**（Phase 0d）→ `avatar: {label, size}`（`size: sm/md/lg`）或 scalar `avatar: EC`。**視覺封印邊界**：禁 `src` / `bg` 等視覺逃生口。收斂 DISCUSSION line 45 待補項。
- [2026-07-03] **🔀 `items:` 用法合併**（Phase 1a）→ row/col 只認 `row: [ ... ]` list 短寫，禁 `items:` 顯式（跟 P0 sibling form 明拒 dict-form 同步）；grid 保留 items（因 grid 值是 tracks 不是 items）。違者 error + actionable diagnostic。
- [2026-07-03] **🔀 `badge` → `status.badge` 合併**（Phase 1b）→ badge 併入 status 家族（`status` 圓角 chip、`status.muted`、`status.strong`、`status.badge` 方角）。Ring 0 少一詞、家族一致。相容 `badge:` 走 deprecated warning。
- [2026-07-03] **🔀 tokens 檔案結構扁平化**（Phase 2a）→ 從單檔 `wf.tokens.yaml` 改成 `tokens/*.yaml` 目錄（`spacing.yaml`/`tones.yaml`/`overlay.yaml`…），loader 合併載入；primitive vs composite 靠檔名/約定，不做 sub-dir（減少目錄深度）。
- [2026-07-03] **🔵 `wireframe-lofi list` introspection 子命令**（Phase 2b）→ 列 Ring 0 全部原語 + 專案 Ring 1（讀 tokens/）；分 `--ring 0/1` 過濾。給 AI 動筆前一次看懂全詞彙。
- [2026-07-03] **⏳ 保留待後續議題**：
  - `as:` 雙重語義（`as: placeholder` 降階 vs `as: {stage}` 變體）—— 是否拆 `stub:` + `variant:`？換名成本高，先文件明講兩用法（Phase 3+）
  - `--emit ast/react/swiftui` codegen（P5.2）—— 等 P0.7 schema validation 上線再議
  - `--audience` sugar（P5.3）—— CLI shim，後補
- [2026-07-03] **執行順序**：Phase 0（換名 + 移旗標 + 兩枚 leaf）→ Phase 1（items/badge 合併）→ Phase 2（tokens 目錄 + `list` 子命令）→ 5 頁記帳 app 回歸驗證。細節動作見 `TOOL-SUGGESTIONS.md` 尾段動作表。

### ⚠️ `canvas:` → `viewport:` 換名（2026-07-03，已實作）

- [2026-07-03] **決策**：`canvas: 390x844` 改成 `viewport: 390x844`。理由：
  - 語義精準：wireframe-lofi 不是繪圖工具，是「示意頁面在多大螢幕上呈現」；`viewport` 是響應式設計的核心詞（HTML meta / CSS vw/vh / RN Dimensions / iOS safe area），命中此意圖；`canvas` 是「畫布」隱喻（Illustrator/Figma/HTML5 canvas API）不對。
  - **AI 友善**：viewport 在 Web/RN/iOS 訓練資料密度極高，codegen 自然對齊（`viewport: 390x844` → CSS `@media` / RN `Dimensions.get('window')`）；canvas 反有 HTML5 `<canvas>` API 混淆風險。
  - **不撞名**：HTML `<meta name="viewport">` 是文件 property；YAML `viewport: 390x844` 是頁面 property，同意涵、無實際衝突，AI 秒懂。
- [2026-07-03] **實作**：wfyaml `_viewport_of(node)` 認 `viewport:` 為 canonical；相容 `canvas:` 走 deprecated warn。`_canvas_wh` 改名 `_viewport_wh`（保留舊名為別名向後相容）。`list` 子命令 Ring 0 grammar/meta 家族詞彙同步更新。
- [2026-07-03] **遷移**：examples/expense-app sed 換名（`^canvas:` → `^viewport:`）；5 頁 + bundle 回歸通過。舊 YAML 檔繼續 work 但會出 warn 引導遷移。

### P0.7 lint 子命令實作（2026-07-03，已實作）+ P0.5 scroll 純語義化補齊

- [2026-07-03] **`wfyaml.py lint <file>` 子命令 land**：Schema Validation + Fail-Fast，Rust compiler 風格 actionable diagnostics（檔名 + YAML path + 為何錯 + hint/建議）。回傳 exit code 0/1/2（clean/warn/error）供 CI 掛。
- [2026-07-03] **檢查條款**：
  1. **container 恰一個方向 key**（row/col/grid 互斥）→ error
  2. **leaf 恰一個 role key** → error
  3. **container+leaf key 混掛** → warn
  4. **Scale 集合驗證**：`gap`/`padding`/`align`/`justify`/`scroll`/`tone`/`pin`/`layer` 全部按 `_ENUMS` 檢查；允許 Ring 1 專案 token（讀 `_TOKENS`）
  5. **`spotlight.kind`** in `focus/new/change/click`
  6. **未知 key typo** → warn + Levenshtein 建議「是不是 X？」
  7. **Deprecated key** (`canvas`/`include`/`badge`) → warn 指向 canonical (`viewport`/`embed`/`status.badge`)
- [2026-07-03] **走訪策略**：只走結構性 key（`body`/`slots.*`/`routes[]`/direction key list/`items`），跳過 leaf value dict（`button:{text,to,icon}` 等）/ `with:` / `as:` / `note:` / `spotlight:` 內部值——避免 leaf value dict 內鍵被誤判為節點 keys。
- [2026-07-03] **lint 抓到既有真 bug**：`align: end` 在 ALIGN dict 沒定義（`col` 交錯軸=水平需要 start/end，但原本只有 top/bottom/center/baseline/stretch）→ 補進 ALIGN + `_ENUMS`（CSS Flex 標準對齊）。
- [2026-07-03] **順手完成 P0.5 scroll 純語義化**（前案定案未實作）：`scroll: true` × `grow: true` = 「填滿剩餘 + 可捲」（`overflow-y:auto`，無 max-height）；`scroll: sm/md/lg/xl` = 語義級距（`8/16/32/48rem`），舊 Tailwind `h-*` token 走 deprecated warn 但仍支援。`scroll-x` 對稱。examples/expense-app 的 layout `scroll: h-160` 改回 canonical `scroll: true`。
- [2026-07-03] **Grammar keys 擴充**：`content` / `placeholder`（component 檔頂層）加進 `_GRAMMAR_KEYS`。
- [2026-07-03] **驗證**：examples/expense-app 8 個 YAML 檔 lint 全 clean（0 error / 0 warning）；記帳 app 5 頁 + bundle 回歸零視覺變化。

### P7 Theme-as-binding-YAML MVP land（2026-07-03，已實作）

- [2026-07-03] **Theme loader `_load_theme(path)`**：讀 themes/*.yaml；schema 驗證頂層只允許 `bindings:` key（禁 `components:` 等反查）；每 role 的 rules 只能是已知綁定屬性；未知綁定屬性 → error + Levenshtein hint（fail-fast，禁靜默）。
- [2026-07-03] **7 個 MVP 綁定屬性**（`_THEME_BINDABLE`）：
  - `padding` / `margin` / `gap` → 走 `_gap` 解析（primitive scale + Ring 1 token）
  - `radius` → none/sm/md/lg/pill/full → CSS border-radius
  - `shadow` → none/sm/md/lg → CSS box-shadow
  - `border` → none/subtle/default/strong → CSS border
  - `background` → surface / surface-alt / surface-sunk / ink → CSS background
  - 所有值都是**語義 primitive**（none/sm/md/lg/xl 或 named tone），**禁像素/hex**（fail-fast）
- [2026-07-03] **CSS 編譯 `_theme_css()`**：把 `bindings.<role>` 編成 `.wf-role-<role> { ... }` 規則，注入到 base + clean + tokens 之後（覆蓋前面）。空 theme（wireframe 模式）→ 空字串（fidelity mode 硬夾）。
- [2026-07-03] **`embed` 加 wf-role 指紋**：expand 展開 embed 時，若有 `_THEME` 或標註，包一層 transparent 容器（`gap: none`, `padding: none`）並蓋 `__embed_role: <basename>`（`components/tx-item` → `tx-item`）；render_item pop 後加 `.wf-role-tx-item` class + `data-wf-role="tx-item"` 屬性。**這是 theme 綁定 component 名的關鍵機制**。
- [2026-07-03] **CLI 掛進管線**：
  - `wfyaml.py --mockup <theme.yaml> <files>` → 載 theme + inject CSS
  - `render.sh --mockup <theme.yaml> ...` → 透過 `WFYAML_MOCKUP` env + `MOCKUP_ARG` 傳給 wfyaml 及 inline python 截圖管線
  - `--style sketch` × `--mockup` 互斥（語義衝突 → error）
- [2026-07-03] **驗證**：`examples/expense-app/themes/mockup.yaml` 綁 5 個 role（mobile/tx-item/tab-bar/dialog/drawer/toast）；5 頁 + bundle 帶 `--mockup` 全渲成功；tab-bar 有 shadow、tx-item 變成獨立圓角卡片、視覺明顯升級到 mockup。無 `--mockup` 的 wireframe 模式**零回歸**（結構性防漂移驗證通過）。
- [2026-07-03] **P7 未涵蓋（後續）**：Component YAML 內禁物理視覺 key 的 lint（P0.7 消費規則）；theme YAML 進 lint 子命令支援；`themes/*.yaml` 目錄支援（多 theme 檔合併）；tone/color primitive 從 theme 抽出到 tokens/ 統一管。

### ⏳待討論：Story-as-Code（SAC）— 故事綁定層（2026-07-03，可行性評估完成，語法待定案）

外部提案（SAC 規格書 v1.0.0）核心：把「使用者故事的標註 + 動線」從 page YAML 抽成外部 `.story.yaml` overlay，底圖單一事實來源，故事按需疊加。**概念強烈建議採納，語法必須用本 repo 詞彙重寫**。

- **痛點真實**：現在 Layer 2（note/spotlight）寫在 page 內 → 一頁多故事就要改底圖或複製多份，正是維護地獄。SAC = Layer 2 的正確終局（externalize）。
- **現有地基已鋪一半**：spotlight（focus/new/change/click + step ①②③）、note、to/flowmap、`.clean.png` 剝離、**debug 的「檔名+YAML路徑」定址**（現成 selector 機制）—— 實作是「把 Layer 2 注入點從 page 內移到外部檔」，MVP 約 100–150 行；SVG 動線箭頭最貴、可後補。
- **與已定案的衝突（不能照抄原規格）**：
  - `kind:` 已否決（2026-07-02 kind→is）；原規格 page 文法（`children:`/`layout: vertical`/`cols:`）不是本 repo 文法，等於另一套 DSL
  - 強制全節點唯一 `id` 違反北極星①（高 ceremony）→ 改用**選配 `name:` 錨點 + 自動 YAML 路徑** 雙軌
  - `highlight: fire/alert/info` 新 enum 撞 spotlight/tone → **bindings 只允許既有 Layer 2 詞彙，Ring 0 零成長**
  - 「高亮顏色放 theme」越權：已定案 Layer 2 標註不受 theme 影響（meta 非產品）
- **落地版語法草案**：
  ```yaml
  # stories/god-30s-check.story.yaml
  story: god-30s-check
  actor: 神様
  intent: 打開 app 30 秒內知道昨晚世界發生了什麼
  page: world                      # 綁 world.wf.yaml
  bindings:
    - target: area-asia            # name: 錨點；fallback YAML 路徑
      spotlight: focus
      note: { ref: 1, text: 一眼看出哪個領地最熱 }
    - target: gate-bell
      spotlight: { kind: click, step: 2, text: 點擊直達 }
      to: gate-audit               # 沿用 to:，進 flowmap
  ```
- **三種輸出模式（Ring 2）**：
  - (a) **單獨生成**：`--story stories/x.story.yaml` → 出 `x.story.html/.png`（底圖+疊加；檔名跟 story 走，不覆蓋底圖產物）
  - (b) **渲進 bundle 整體查看**：`--bundle --story x.story.yaml pages/*.wf.yaml` → prototype 左 nav 多一組「📖 story」；**story 版 = 底圖的另一個渲染實例**（同一份 YAML 樹疊加後再渲一次，非複製）；乾淨頁與故事版並存可對照
  - (c) **多故事並存**：`--story stories/*.story.yaml` → 每 story 一個 nav 分組；同一底圖被 N 故事引用仍只維護一份
  - `flow.goto` 跨頁在 bundle 模式自動改寫成頁內錨點（沿用 `to:` 現有機制）→ 點著走完整故事動線
- **lint（P0.7 延伸）**：target 解析不到 name/路徑 → error；story 檔 bindings 用了白名單（spotlight/note/to/tone）以外的 key → error；story 頂層 key 白名單（story/actor/intent/page/bindings/flow）。
- **與 P6 flow-scoped 輸出同題兩面**：P6 =「輸出哪些頁」、SAC =「疊什麼故事」；一個 story 天然定義一條 flow → `--story` 可直接驅動「只 bundle 該動線的頁」。實作時兩者可共用 walk 機制。

### SAC 規格定稿（2026-07-03，兩輪 review 後 lock，待實作 MVP）

**最終語法**（`stories/<id>.story.yaml`）：
```yaml
story: god-30s-check               # 一詞兩用：類型宣告 + id（同 widget scalar 簡寫精神）
actor: 神様
intent: 打開 app 30 秒內知道昨晚世界發生了什麼
page: world                        # 或 world#stage.state（複用 RouteRef 文法）

bindings:                          # 白名單：spotlight / note / badge（tone 越權產品面，禁）
  - target: area-asia              # name 錨點；命中多個=全疊；0 個=lint error
    spotlight: focus
    badge: 昨晚發生暴動            # 新增 Layer 2 詞彙：元素角落小貼紙（可剝離）
    note: { ref: s1, text: 一眼看出哪個領地最熱 }   # ref 慣例字母前綴避免與底圖撞號

flow:                              # 敘事主體；list 有序 → step 序號自動編（無 step: 欄位）
  - target: area-asia              # 序號 ① 疊到該節點（獨立 overlay，不合併進 spotlight）
    desc: 著陸後視線第一時間被東方領地吸引
  - target: gate-bell
    to: gate-audit                 # to 掛在序號徽章 ② 上（徽章即 <a>）；底圖元素連結不動
    desc: 點城門口，直達審查頁
  - desc: 純敘事步驟（無 target）── 序號只進 desc 清單、不疊圖
```

**兩輪 review 的定案**：
- [2026-07-03] **`tone` 從 bindings 白名單移除** → tone 是 Layer 1 產品面，story 是標註面，越權禁止。故事表達「這裡熱」用 `spotlight: focus`。
- [2026-07-03] **新增 `badge` 進 Layer 2 詞彙**（標註面成長 ≠ Ring 0 成長，邊界判準：Ring 0 管產品詞彙、標註面管評審溝通）→ 元素右上角小貼紙、可剝離、純文字不帶 to。
- [2026-07-03] **恢復獨立 `flow:` 區塊** → desc 是評審 checklist 敘事主體；渲染 = step 序號疊 target + desc 清單進 gutter/頁首。原 SAC 的 `action: Focus/Click/Input` enum 不採（過度指定，desc 自由文字已足）。
- [2026-07-03] **`step:` 欄位刪除** → YAML list 天然有序，自動從 1 編號；消滅 step 重複/跳號整類 lint 問題。
- [2026-07-03] **動線歸 flow、不歸 bindings** → 避免與底圖節點自帶 `to:` 衝突；story 的 to 掛在序號徽章上（徽章即 `<a>`），與產品動線物理分離。
- [2026-07-03] **flow 序號 = 獨立 overlay** → 不塞進 spotlight step 機制、不與 binding 合併；spotlight 的 `step:` 參數保留給 page 內作者用。
- [2026-07-03] **actor/intent 渲染** → 頁首 story banner（Layer 2 樣式）：`📖 <id>｜<actor>｜<intent>`；bundle 模式兼任 nav 分組標題。
- [2026-07-03] **解析規則**：`page:` 從 story 檔同目錄 → 父目錄 → `pages/` 搜（沿用 _resolve 慣例）；注入時機 `resolve_body → expand → story inject → render`（name 錨點需 embed 展開後才存在）；`lint stories/x.story.yaml` 自動拉底圖驗 target。
- [2026-07-03] **輸出細節**：(a) 模式產物跟 story 檔同目錄；bundle section id 用 `wf-pg-story-<id>` 避撞；story 版不出 `.clean.png`（剝掉標註=底圖，無意義）；story × `--mockup` / `--style sketch` 正交允許。
- [2026-07-03] **lint 規則**：story 頂層白名單（story/actor/intent/page/bindings/flow）；bindings 白名單（target/spotlight/note/badge）；target 解析 0 命中 → error；同 target 同 key 重複 binding → error；同頁 note ref 撞號 → error。
- [2026-07-03] **YAGNI 界線**：一 story 一條 flow，分支動線可用字串 step（2a/2b）表達並行、複雜分支仍拆 story 檔；badge 不帶動線。

**三輪 review 補充定案（使用者提出：step 特殊寫法 / 複寫 to / 取代文字）**：

- [2026-07-03] **bindings 分兩類 key：標註（additive）vs 變體（mutation，包進 `set:`）**：
  ```yaml
  bindings:
    - target: area-asia
      spotlight: focus            # 標註類（頂層）：spotlight / note / badge
      set:                        # 變體類（隔離區）：改寫節點自身產品屬性
        text: 東方領地・暴動中     # 取代節點主要顯示字串（placeholder → 情境資料）
        to: gate-audit            # 複寫節點產品動線（demo 替代路徑）
  ```
  - 包 `set:` 理由：mutation 是更重的操作需視覺邊界；lint 兩張白名單不混；意圖自明。
  - **`set.text` 是 SAC 最有價值的一刀**：底圖放 placeholder、故事情境資料住 story 檔——正面解掉原 SAC「動態資料塞底圖弄髒骨架」的核心痛點。語義 = 取代節點主要顯示字串（text 家族值 / button text / input placeholder，通用一條規則）。
  - **`set:` 白名單只有 text/to（防滑坡）**：tone/status/結構 ❌——產品狀態變體歸 `routes`/`when` 系統，story 不重造。三系統分工：routes=產品狀態、story=情境資料+標註、theme=視覺綁定。
  - `set.to`（改元素本身連結）與 flow 的 to（掛序號徽章）物理分離、不衝突。
- [2026-07-03] **`step:` 改選填**：未寫 = 上一個整數 step +1（首項 1）；可寫 int 或短字串（`2a`/`2b` 表達並行動作）；字串 step 後的未編號項 → lint error（要求明寫）；重複 step → lint error。
**四輪（final）review 明定 6 細節**：

- [2026-07-03] **target 消歧**：含 `[` 即視為 YAML 路徑，否則視為 name 錨點（實務上路徑必帶索引括號；啟發式，文件明講）。
- [2026-07-03] **set.text 只對 leaf**：命中 container 又給 set.text → lint error（container 無「主要顯示字串」）。
- [2026-07-03] **set 遵守全命中規則**：target 命中多節點 → set 全改（與標註同一條規則，不開特例）；精準改單一實例用路徑。
- [2026-07-03] **page 無 fragment → 綁 default 路由**；特定路由明寫 `page: world#stage.state`。
- [2026-07-03] **flow.desc 必填**（敘事主體）；target / to / step 全選填。
- [2026-07-03] **(b) bundle 的 story 分組 = 只含綁定頁疊加版一頁**；flow 跳轉目標連 bundle 內 clean 頁（沿用錨點改寫）；「story 驅動整條 flow 頁集合」留給 P6 一起做。
- 已知限制（記錄不擋 MVP）：底圖 spotlight step 與 story flow 序號可能撞號 → lint warn 不阻斷；`set.to` 語義是「設定」非「複寫」，底圖有無 to 都直接生效不 warn。
- 一致性掃描確認：詞彙複用無 Ring 0 成長（新 key 全限 story 檔作用域）；三系統分工無重疊；fail-fast 全覆蓋；banner 有 `_stagebar` 先例。

- **狀態**：規格 final lock（四輪），可實作 MVP（估 180–230 行：story loader + lint 兩張白名單 + target 雙軌解析 + 標註/變體雙注入 + banner/badge/序號 CSS + bundle nav 分組）。

### SAC MVP land（2026-07-03，已實作）

- [2026-07-03] **實作範圍**（wfyaml.py +約 240 行、render.sh passthrough、範例 story）：
  - `_load_story`：頂層/bindings/set/flow 四張白名單 + step 選填規則（自動編號/字串 step 後必明寫/重複 error）全照規格
  - `_resolve_story_page`：story 同目錄 → 父目錄 → pages/；`#fragment` 選路由、無 fragment 綁 default
  - `_apply_story`：expand 後注入；target 消歧（含 `[` = 路徑比對 `__path` 蓋章，否則 name）；命中多個全疊；0 命中 error；`set.text` 打 container error；`set.to` 限 container/widget/button/link
  - 渲染：`_story_header_html`（📖 banner + flow desc 清單）、`.wf-story-badge` 貼紙、`.wf-story-step` 序號徽章（有 to 即 `<a>`，掛徽章不動底圖連結）、紫色系明顯非 UI
  - CLI：`--story` 單獨生成（產 `<id>.story.html` 於 story 檔旁；底圖先過 lint gate）；`--bundle --story` 附加「📖 <id>」nav 分組（故事版 section id `wf-pg-story-<id>`，clean 頁並存）；render.sh 兩模式 passthrough
  - lint：story 檔（含 `story:` 頂層 key）走 story schema 驗證 + page 存在性；target 命中驗證留 render 時 fail-fast
- [2026-07-03] **實測**：overspend-alert 範例（記帳 app）驗證全開——banner/flow ①②③ 清單/spotlight 螢光/badge×3/set.text（記支出→補記支出）/set.to/note gutter [s1][s2]/序號徽章疊節點/純敘事步驟；bundle nav 分組 + clean 頁並存；錯誤案例（target 不存在/set 白名單外/set.text 打 container）全 fail-fast；wireframe 無 story 模式零回歸。
- [2026-07-03] **底圖成本實測**：home.wf.yaml 只加 3 個 `name:` 錨點（balance-card/btn-add-expense/budget-entertainment），符合「作者只給要綁的節點掛 name」設計。
- [2026-07-03] **MVP 未涵蓋（後續）**：story PNG 截圖管線（HTML 已是評審主載體）；SVG 動線箭頭（序號徽章已足）；多 `--story` 並存（(c) 模式，一次一個先）；story × P6 flow-scoped 頁集合。
- [2026-07-02] **定位**:這是「單一語義源 × 漸進保真」從口號變可執行輸出模式,也是 token 系統的**前置地基**——**先於**任何進一步 token 擴充(有它才安全地讓 token 變豐富而不失焦)。

### tone 移除決策（2026-07-08，設計定案，待實作）

使用者：「tone 我其實想拿掉，因為我還沒想好他存在的意義」。評估後**支持移除**——「還沒想好存在意義」是癥狀不是疏忽。

- [2026-07-08] **為何移除**：tone 從 line 37 起長年 ⏳ 待議收斂不了（混警示軸/正向/強調度三軸），根因是**層級定位曖昧**——它是「產品色」卻住在「低保真層」，與北極星①視覺封印天生打架。R2-3 發現 tone 對 chip/badge 只實作半套（文字有色、bg/border 沒做），半殘撐了整輪實測也沒人痛 → 非剛需的實證。
- [2026-07-08] **色彩三歸宿（拿掉後各歸其層）**：
  - 產品狀態色（危險紅/成功綠）→ **theme binding**（P7 已有機制，`--mockup` 才上色）
  - 評審「看這裡」→ **spotlight / badge**（標註面本來就有色、明顯非 UI）
  - 語義強調 → **text.strong / status.strong**（灰階權重）
  - 收斂成一句：**色彩 = 保真度的函數**——wireframe 全灰階、標註面紫黃、mockup 才有產品色。
- [2026-07-08] **順帶收益**：資訊不靠色彩（「+32,000/-120」符號、「超支 900」文字已足；靠色才能傳達=設計壞味道，wireframe 階段逼出此檢查是 feature）；Ring 0 少一屬性；R2-3（tone 三元組補 CSS）直接作廢。
- [2026-07-08] **移除範圍**：render_item tone pop/class、lint `_ENUMS['tone']`、`list` 子命令 tone 段、progress fill tone 變色（改全灰）、examples sed、CSS `wf-tone-*` 清除（POC 無 deprecated 包袱）。SAC 不受影響（bindings 白名單本來就禁 tone）。
- [2026-07-08] **已知代價**：progress bar 的 warn 黃/danger 紅變全灰——灰 fill + 文字（78%/超支 900）仍可讀，符合低保真。
- [2026-07-08] **未來回歸路徑**：若真需要「wireframe 階段就有語義色」，走 **theme binding 綁 role**（機制已在），不復活 tone。
- **狀態**：✅已實作（同日）。此條同時收斂掉 line 37「Layer 1 命名與集合」長年待議（答案：整個維度移除）。

### tone 移除 + R2 視覺渲染層 land（2026-07-08，已實作）

- [2026-07-08] **tone 全面移除實作**：render_item 偵測 `tone:` 直接 raise（fail-fast + 教育訊息：三歸宿各歸其層）；lint 加專用 error 條款（比 typo warn 明確）；`_ENUMS`/`_CONTAINER_ATTRS`/slot-marker/embed ann 全清；`list` 子命令刪 tone 段；progress fill 改全灰；clean/style.css 刪 `wf-tone-*` 11 條（含從未進 `_ENUMS` 的殘留 `wf-tone-action`）；examples 7 檔 sed 清 `tone:`（含 tx-item 的 `{{tone}}` 參數鏈）；README §6 改寫成「色彩=保真度的函數」三歸宿表；SKILL.md 紅線同步。負面案例驗證：lint 出 error、render 拋 ValueError。
- [2026-07-08] **R2-1 ↗ 角標化**：根因是 `.wf-blocklink-a` 同時掛 `.wf-link`，吃到 inline `' ↗'` ::after → 內容為 col 時折行撐高 tab bar。修法：`.wf-blocklink-a` 與 `.wf-btn.wf-link` 的 ::after 改**絕對定位右上角小角標**（.6em、opacity .6，不進 inline flow）；inline 文字連結維持行內 ↗。順手刪死碼 `.wf-blocklink`（無 -a；python 從未產出此 class）。
- [2026-07-08] **R2-2 leaf grow**：render_item leaf 分支 pop `grow` → `wf-grow` class（`flex:1 1 0; min-width:0; text-align:center`，1 1 **0** 使等寬起算）；`.wf-input.wf-grow { max-width:none }` 解除預設收窄。與 track `grow`/container `grow: true` 同一語義，補齊第三塊。home 快速記帳三鈕改 `grow: true` 驗證等寬撐滿。
- [2026-07-08] **R2-4 image 置中**：`.flex-col > .wf-image[style*="width:"] { align-self:center }`——帶明確寬度才置中，無寬度者維持 stretch 滿版（attribute selector 區分，CSS 1 條）。stats 環形圖驗證置中。
- [2026-07-08] **R2-3 作廢確認**：tone 三元組補 CSS 隨 tone 移除直接消滅。R2-5（tab bar 壓縮）維持掛「組合型 token 一般化」待續項。
- [2026-07-08] **回歸**：examples/expense-app 全檔 lint 0 error/0 warning；5 頁 + bundle + story + `--mockup` + `--style sketch` 全渲成功；視覺抽查（home/stats PNG）：按鈕等寬、tab bar 不撐高、↗ 角標、全灰階、環形圖置中。

### 外部專案實測（kamisama worldgrid-v2）抓到的三隻 bug（2026-07-08，已修）

同日以 kamisama worldgrid-v2（9 頁 + 神諭台 redesign + P7 mockup theme 首次外部實戰）回歸，連環抓到：

- [2026-07-08] **`gap: xl` lint/render 不同步**：`_ENUMS` 允許 xl（P0.7b/P4 E1 定案 scale 本含 xl）但 `GAP` dict 只到 lg → lint 過、render 拋。補 `GAP['xl']` + `--wf-space-xl:2rem`。教訓：**enum 表與實作 dict 要同源**，否則 lint gate 反而製造假信任。
- [2026-07-08] **lint 不認 dict 形 spacer（`- spacer:`）**：字串形不走 dict 檢查所以一直沒被抓；修為與 render `_is_spacer` 同判定（恰一 spacer key）；混掛其他 key 仍 warn 但改專屬 hint（指向 `grow: true`）。
- [2026-07-08] **lint 不認專案自定 overlay token 角色**：`wf.tokens.yaml` overlay 自定角色（如 `oracle`）render 正常、lint 誤報未知 key——`has_overlay_sugar` 只查內建 `_OVERLAY_SUGARS`，補併 `_TOKENS['overlay']`。
- [2026-07-08] **最大隻：expand/_fill_slots/lint 全都不走訪 overlay 角色內容**（dialog/sheet/自定 oracle…）→ 藏在裡面的 embed/slot **從未展開**、render 退化空容器**靜默渲空**（違反 fail-fast 鐵律的漏網）。widget.body 同病。修法：`_child_list_keys()`（方向 key/items ∪ overlay 角色）供 expand 與 _fill_slots 共用 + widget.body 一併走訪 + lint 遞迴同步 + render_item 加「未展開 embed 直接 raise」護欄。
- **模式教訓**：三隻 lint bug 同根——**lint 的詞彙/走訪表是手抄的第二真理**，與 render 實作漂移。長期解是 lint 與 render 共用同一組結構定義（`_child_list_keys` 是第一步）；短期靠外部專案實測當回歸網。
- [2026-07-09] **P7 phase 2：mockup 基底皮 + 色彩 primitive（實測回饋「mockup 跟 wireframe 幾乎一樣」）** → MVP 綁定只有間距/圓角/陰影/框線/灰階底色，wireframe 本來就是灰框 → 套完看不出保真度差。補兩個視覺槓桿：
  - **mockup 基底皮**（`_MOCKUP_BASE_CSS`，有 theme 就套）：字體換無襯線（打字機字體一換，產品感立刻出現）、`--wf-radius` 放大、頁面 chrome（灰底+白卡+浮起陰影、box 框線變淡）。**標註面（gutter/spotlight/story）保持 mono 字體**——meta 非產品、不受 theme（沿用既定原則）。
  - **色彩 primitive 進綁定詞彙**：`background: brand/brand-soft`、`border: brand`、新 `text: ink/soft/inverse/brand`——值仍是語義名（hex 封在 `--wf-brand` var），兌現 tone 移除時的承諾「產品色住 theme binding」。brand 預設 teal（可攜地板），專案改色 = 覆寫 var（未來 tokens/colors DTCG 再議）。
- [2026-07-09] **P7 phase 2b：mockup 元件皮加厚 + theme 綁 `name:` + gutter 外置**（實測回饋二輪「還不夠像」+「note 應該在 viewport 外面」）：
  - **元件皮**：`_MOCKUP_BASE_CSS` 補 btn/input/select/tag/badge 產品長相；**動線 ↗ 在 mockup 隱藏**（↗ 是線框註記，產品不長這樣；連結仍可點）。
  - **theme 綁定目標擴為 role ∪ `name:`**：selector 加 `[data-name="X"]`——name 是一次性語義身份，theme 綁語義身份順理成章（layout 內非 component 的節點如 top-bar/oracle-entry 因此可綁）。
  - **gutter 便利貼站畫布外**：原本 root 寬 = viewport+240+gap、頁框把 note 包在「圖裡面」——語義錯位（note 是標註面 meta，不屬 viewport 內容）。改 root=viewport 寬、gutter `left:calc(100%+gap)` 外掛、body 預留右緣；render.sh `shoot()` 改取 root∪gutter 聯集 clip（SVG 尺寸同源自動跟進）。wireframe/mockup 兩模式都受益——mockup 下白卡=產品、灰底上的黃便利貼=註記，保真度邊界從此看得見。
- [2026-07-09] **續抓兩隻（同日 worldgrid-v2 全站 redesign 實測）**：
  - **`pin: *-center` 有 enum 沒 CSS**：`_ENUMS['pin']` 允許 top/bottom/left/right-center 四值，wf.css 只寫了 9 個錨點——缺 CSS 時 flex 預設 stretch 把 pinned 元素撐成整條邊帶。補四條 `.wf-pin-*-center`。同「enum 表與實作不同源」病。
  - **note ref 的 `[n]` sup 在 grid 容器裡自己佔一格**：`_wrap` 用 `core += <sup>` 讓錨點變 sibling → grid cell 全推位。修法比照 `wf-story-anchor` 前例：包 `.wf-refwrap`（relative）+ sup 絕對定位右上、不進 flow；gutter 量測仍讀 `.wf-ref` 幾何。
