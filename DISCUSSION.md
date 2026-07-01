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
