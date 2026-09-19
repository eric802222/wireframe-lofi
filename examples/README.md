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

`gallery.wf.yaml` 搭配 `themes/gallery.yaml` 展示具名封面、avatar 與 SVG 圖示。
不加 `--mockup` 時仍是線框佔位；素材放在 `themes/gallery.assets/`，產物內嵌且可離線。

`kit-demo/` 展示 kit 的 leaf 特化、組合元件、props/state 與 token-only theme：

```bash
python3 wfyaml.py lint --kit examples/kit-demo/kit/components.yaml --mockup examples/kit-demo/theme.yaml examples/kit-demo/page.wf.yaml
python3 wfyaml.py --kit examples/kit-demo/kit/components.yaml --mockup examples/kit-demo/theme.yaml examples/kit-demo/page.wf.yaml
```
