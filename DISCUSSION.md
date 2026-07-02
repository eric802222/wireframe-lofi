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
