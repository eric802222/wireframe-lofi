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

隨時可跑 `python3 wfyaml.py list --ring 0` 拿到同一份（這份是從程式碼生成的，不會過期）。

**專案元件**：看 `kit/components.yaml`，**優先用既有元件而不是重拼一次**。

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

## 常見錯誤（這些我都踩過）

| 症狀 | 原因 | 正解 |
|---|---|---|
| 按鈕變得超高 | `grow: true` 在 `col` 裡是沿主軸長高 | 滿版寬不用加任何東西，交叉軸預設就是 stretch |
| 輸入框沒有滿版 | `input` 自帶寬度上限 | 包一層 `row: [ { input: …, grow: true } ]` |
| YAML 解析失敗或內容跑掉 | 值裡有 `[ ] , : #` | 整個值加引號：`"11:12"`、`"照片 ×3 · [N] MB"` |
| lint 說未知 key | 用了不存在的詞 | 跑 `list --ring 0` 對照；不要自己發明 key |
| 樣式沒套到 | theme 綁的是 `name:`，打錯字不會報錯 | 檢查 `name:` 與 theme 的 binding 名稱一致 |
| 連結點下去沒反應 | 用 `link:` 寫站內導航；它的 `to:` 原樣輸出成 href，不補 `.html`、bundle 也不改成頁內錨點 | 站內跳頁用 `button:` 或在節點上寫 `to:`；`link:` 只給站外完整 URL |
| 角標/浮層跑到畫面左上角 | `pin` 錨在最近的 `box`／`.wf-root`，父容器沒有 `box: true` 就會飄上去 | 父容器加 `box: true`；要貼整個畫面請用 `modal` 或 `dialog`/`toast` 這類 sugar |
| 說明文字爆版 | 假資料很短，真資料會長 | 需要截斷的地方寫 `max-lines: 2`（只能用在文字節點，不能和 `wrap: false` 並用）|

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
