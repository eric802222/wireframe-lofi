# Changelog

格式依循 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，
版本依循 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

DSL 語彙的相容性視同 API：移除或改變既有 key 的語義是 breaking change。

## [Unreleased]

### Added
- `section:` 帶語義的一段（SDUI 的 ViewLayout → Section → Component 中間層），
  可 `collapsed: true` 走原生 `<details>`
- `wfcheck.py flow`：動線完整性檢查（斷鏈／孤島／死路／跨階段），exit code 可進 CI
- `wfcheck.py spec`：每頁規格輸出（元件、狀態、動線、未定值；md 或 json）
- `wfexport.py tokens`：theme → DTCG `.tokens.json`（也可 css / ts）
- `wfexport.py types`：kit 的 props / states → TS 型別契約
- `wfexport.py import`：DTCG JSON → theme 的書寫形式（往返一致）
- 複合型 token 匯出：`border` / `shadow` / `strokeStyle`
- 表單葉子改用真的 HTML 控制項：`input` / `select` 可輸入、checkbox / radio 可勾選
- `reveals:`：勾選才顯示某個 `name:` 節點（純 CSS `:has()`，零 JS）
- radio 的 `group:`、select 的 `options:`
- `AGENTS.md`：給 AI 的操作說明（詞彙、必跑指令、常見錯誤、紅線）

### Changed
- canvas 的 `item` / `link` 更名為 `node` / `edge`（畫面層 `items` / `link` → `nodes` / `edges`）；
  **舊名保留為別名且可與新名混用**，遷移不必一次完成

### Fixed
- `wfexport.py tokens` 加 `--kit`：theme 為 canvas 元件寫 components 規則時不再誤報

### Known trade-off
- `input` 的未定值改由 `placeholder` 承載，失去虛線底線的視覺標記（lint 統計不受影響）
