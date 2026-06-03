# imports/ — 匯入資料夾

蝦皮、FB 等需登入的來源改走「匯入式」。把你在**自己已登入的瀏覽器**取得的資料
放到這個資料夾，再用匯入器寫入資料庫：

```bash
# 通用 CSV（任何來源，含 FB 社團貼文整理後）
python tools/import_listings.py --csv imports/your_file.csv

# 蝦皮：登入蝦皮後於瀏覽器開 search_items API 連結，另存 JSON
python tools/import_listings.py --shopee imports/shopee_xxx.json --part gpu_rtx5090
```

## CSV 欄位
`part_id, source, title, price, condition, location, date, url, sold`
- **必填**：`part_id`（須為現有零件 id，見前端 DB / 後端 PARTS_DB）、`source`、`price`
- `price` 須為 TWD 整數，範圍 500–200000；其餘欄位可留空
- 範例見 `sample_listings.csv`

## 注意
- 本資料夾的 `*.csv` / `*.json`（範本除外）已被 `.gitignore` 忽略，**不會提交**（可能含個資）。
- FB 來源僅保留近 90 天（見 `SOURCE_RETENTION`），匯入後逾期資料會自動清除。
