# 官方可執行範例

在 repo 根目錄執行：

```bash
python3 wfyaml.py lint examples/*.wf.yaml
./render.sh examples/deal-detail.wf.yaml
python3 wfyaml.py --bundle examples/*.wf.yaml
python3 wfyaml.py --bundle-standalone examples/*.wf.yaml  # iframe 預覽；不改 URL，無 deep link
python3 wfyaml.py --bundle --debug examples/phone-home.wf.yaml examples/phone-long.wf.yaml
python3 wfyaml.py --mockup examples/themes/inverse.yaml examples/deal-detail.wf.yaml
python3 wfyaml.py --bundle examples/expense-app/*.wf.yaml
```

`deal-detail` 展示單頁與參數化 component；`deal-routes` 展示 layout／slots、狀態元件與路由。
`phone-home`／`phone-long` 共用 `layouts/phone`，分別驗證短、長內容的獨立捲動與常駐 footer。
HTML 限定 viewport 高度；PNG／SVG 的 show-all 模式會展開內容並畫捲軸示意。

`expense-app/` 是五頁精簡記帳範例，供 layout、component 與 `to:` 動線操作；歷史設計筆記中的個人範例不代表現行完整產品。

`wf-claude-bridge.html` 為選配宿主 adapter 範例，不會預設載入。
使用 `--debug --debug-bridge examples/wf-claude-bridge.html`，並設定片段的 `data-project`；
能力契約、備份流程與共用 API 見根目錄 README。無宿主能力時可離線匯出／匯入。
