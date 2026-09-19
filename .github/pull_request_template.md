## 這個 PR 做什麼

<!-- 一兩句話說清楚。如果是修 bug，先寫症狀 -->

## 為什麼這樣做

<!-- 取捨與被拒絕的替代方案。這裡比實作細節重要 -->

## 檢查清單

- [ ] `python -m unittest discover -s tests` 全過
- [ ] 新行為有測試（含邊界與錯誤情況）
- [ ] `python wfyaml.py lint examples/*.wf.yaml` 乾淨
- [ ] 沒有把視覺值寫進畫面層或把字面值寫進 theme（見 CONTRIBUTING 的紅線）
- [ ] 若新增語彙：README／`list --ring 0`／AGENTS.md 同步更新
- [ ] 若為行為改變：在 PR 內文標明，並說明既有檔案是否需要遷移

## 相關 issue

<!-- Closes #  /  Refs # -->
