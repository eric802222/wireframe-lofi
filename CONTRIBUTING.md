# 參與開發

## 快速開始

```bash
git clone https://github.com/eric802222/wireframe-lofi.git
cd wireframe-lofi
pip install pyyaml                    # runtime 只需要這個
pip install playwright && python -m playwright install chromium   # 只有截圖需要

python -m unittest discover -s tests  # 跑測試
python wfyaml.py examples/deal-detail.wf.yaml
```

沒有建置步驟、沒有 node_modules。封印 CSS 與 icon 圖庫已 vendored 在 `assets/`。

## 專案結構

```
wfyaml.py      編譯器：YAML → HTML。lint、routes、theme、kit、bundle、debug 都在這裡
wfexport.py    匯出：tokens（DTCG）、props 型別契約、DTCG 匯入
wfcheck.py     檢查與規格：動線完整性、每頁 spec
flowmap.py     動線圖（graphviz）
render.sh      一鍵產 .html + .png + .svg + flowmap
assets/        vendored 的封印 CSS 與 icon 圖庫
examples/      可執行的範例（CI 會拿它們自我檢查）
tests/         單元測試；check_*.py 是需要瀏覽器的檢查
AGENTS.md      給 AI 的操作說明（改 DSL 時的詞彙與紅線）
DISCUSSION.md  設計決策的來龍去脈 —— 提架構建議前先讀
```

## 五條紅線

這個工具的價值來自**刻意不做什麼**。以下違反了就不會被接受，即使實作正確：

1. **畫面層不出現視覺值**。沒有顏色、像素、字級。那些住在 theme。
2. **theme 的樣式值只能是 token 參照**（`'{space.md}'`）。字面值只准出現在 `tokens:` 定義處。
3. **不發明新詞彙來解決個案**。專案自己的元件放 `kit/components.yaml`；
   工具內建詞彙（Ring 0）的擴張要能說明為何**所有**專案都需要它。
4. **不要條件、迴圈、運算式**。狀態用 `routes:` 列舉，列表交給外部腳本先展開。
   一旦加進來，lint 就檢查不了語義、`data-wf-path` 會失去穩定性、LLM 也寫不動。
5. **不硬編任何 mockup 長相進編譯器**。工具只認名字，值全歸 theme。

前四條在 `.github/ISSUE_TEMPLATE/feature_request.yml` 有對應的勾選項；
提功能建議時請正面回答「界線在哪」。

## 改動的慣例

- **一個 PR 一件事**。語彙擴張、bug 修正、文件更新不要混在一起。
- **新行為要有測試**，含邊界與錯誤情況。錯誤訊息本身也值得測 —— 它是使用者介面。
- **行為改變要在 PR 內文標明**，並說明既有檔案是否需要遷移。
  能加相容別名就加（例：`nodes` / `edges` 保留 `items` / `link`），讓遷移不必一次做完。
- **新增語彙時同步三處**：README、`wfyaml.py list --ring 0`、AGENTS.md。
  三者不同步比沒有文件更糟。
- **大檔改動**：`wfyaml.py` 目前是單一大檔（見 #45 的拆檔計畫）。
  在拆檔完成前，盡量把新功能放獨立模組（`wfexport.py`、`wfcheck.py` 就是這樣長出來的）。

## 測試

```bash
python -m unittest discover -s tests          # 單元測試（不需要瀏覽器）
python tests/check_browser.py                 # 需要 playwright + chromium
python wfyaml.py lint examples/*.wf.yaml      # 範例必須 lint 乾淨
python wfcheck.py flow examples/*.wf.yaml     # 動線不能有破洞
```

CI 會跑前面三項，外加「token 匯出必須合規」。

## 錯誤訊息的標準

作者錯誤（YAML 寫錯）預設**只印一行**：來源、位置、修正提示，不噴 traceback。
`--traceback` 或 `WF_TRACEBACK=1` 才顯示完整堆疊。非預期的程式例外仍然要噴 traceback。

好的錯誤訊息會說「應該怎麼寫」，不只說「錯了」：

```
theme components.alert.border 不接受字面設計值 `2px solid {color.line-strong}`；
請先在 tokens: 定義級距，再用 {family.name} 引用
```

## 設計討論

架構層級的提議請先讀 `DISCUSSION.md` —— 許多方向已經討論並做過取捨，
裡面記著「為什麼那樣決定」以及被拒絕的替代方案。
若要推翻既有決策，請針對當初的理由回應，而不是重新提一次。
