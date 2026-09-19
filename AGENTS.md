# 給 AI 的操作說明（wireframe-lofi）

這份是給協助修改線框的 AI 讀的。目標：**改完的檔案 lint 過、動線不斷、視覺封印不破**。

## 這個工具在做什麼

語義化 YAML → 低保真線框（零 JS）。一份來源可出兩種保真度：
不加 theme 是灰階線框；加 `--mockup` 才長出產品外觀。

**最重要的一條規則：畫面檔不寫任何視覺。** 沒有顏色、沒有像素、沒有字級。
那些住在 theme；畫面只寫「這是什麼、在哪、去哪」。

## 改完一定要跑這三個

```bash
python3 wfyaml.py lint --kit kit/components.yaml <改過的檔>   # 語法與詞彙
python3 wfcheck.py flow *.wf.yaml --entry <進入點>            # 動線有沒有斷
python3 wfyaml.py --kit kit/components.yaml <改過的檔>        # 真的編得出來
```

`flow` 會報三種破洞：**斷鏈**（`to:` 指到不存在的畫面）、**孤島**（沒有入口）、
**死路**（沒有出口）。這三種都是 error，要修掉。

## 詞彙表

完整清單跑 `python3 wfyaml.py list --ring 0`。常用的：

- **容器**：`row` / `col` / `grid` / `box: true` / `section`
- **文字**：`text` / `text.title` / `text.heading` / `text.label` / `text.strong` / `text.hint`
- **表單**：`input` / `select` / `button` / `[x] 勾選` / `(x) 單選`
- **狀態**：`status` / `status.strong` / `status.muted` / `status.badge` / `alert` / `progress`
- **其他**：`icon` / `divider` / `image` / `tabs` / `avatar` / `avatars` / `link` / `widget`
- **動線**：在任何節點上寫 `to: 畫面id`
- **專案元件**：看 `kit/components.yaml`，**優先用既有元件而不是重拼一次**

## 常見錯誤（這些我都踩過）

| 症狀 | 原因 | 正解 |
|---|---|---|
| 按鈕變得超高 | `grow: true` 在 `col` 裡是沿主軸長高 | 滿版寬不用加任何東西，交叉軸預設就是 stretch |
| 輸入框沒有滿版 | `input` 自帶寬度上限 | 包一層 `row: [ { input: …, grow: true } ]` |
| YAML 解析失敗或內容跑掉 | 值裡有 `[ ] , : #` | 整個值加引號：`"11:12"`、`"照片 ×3 · [N] MB"` |
| lint 說未知 key | 用了不存在的詞 | 跑 `list --ring 0` 對照；不要自己發明 key |
| 樣式沒套到 | theme 綁的是 `name:`，打錯字不會報錯 | 檢查 `name:` 與 theme 的 binding 名稱一致 |

## 紅線（違反就會被 lint 擋，或破壞這個工具的價值）

1. **畫面檔不准出現顏色、像素、字級**。要改外觀就改 theme 的 token。
2. **theme 的樣式值只能是 token 參照**（`'{space.md}'`），字面值只准出現在 `tokens:` 定義處。
3. **不要發明新的 key**。需要新元件就加進 `kit/components.yaml`，不要在畫面裡拼。
4. **不要寫邏輯**。沒有 if、沒有迴圈、沒有計算。狀態用 `routes:` 列舉表達。
5. **同一種卡片出現第三次就抽成 kit 元件**。lint 會提示，別忽略。

## 改動的慣例

- **改文案**：直接改字串就好。
- **加畫面**：新開一個 `.wf.yaml`，記得**給它入口**（從某頁 `to:` 過來）和**出口**，否則 flow 會報孤島或死路。
- **加一段內容**：用 `section: 名稱` 包起來，不要一路 `col` 疊下去。
- **改動線**：改 `to:`，然後跑 `flow` 確認沒斷。
- **改外觀**：只動 theme；如果要改的東西在 theme 裡沒有對應 token，先加 token 再引用。

## 交付

```bash
python3 wfcheck.py spec *.wf.yaml --kit kit/components.yaml   # 每頁規格（元件/狀態/動線/未定值）
python3 wfexport.py tokens themes/x.yaml --format css         # design token
python3 wfexport.py types kit/components.yaml                 # props 型別契約
```

給 RD 的是這三樣，不是一份巨量 HTML。
