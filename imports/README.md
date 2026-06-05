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

## 蝦皮：用已登入瀏覽器擷取（Claude-in-Chrome）

匿名爬蟲被蝦皮反爬蟲擋（403）。改在**你已登入的瀏覽器**內，同源呼叫蝦皮搜尋 API
（`/api/v4/search/search_items`）即可取得 200 與真實資料。流程：
1. 在已登入的蝦皮分頁，於頁面內 `fetch` 該 API、過濾（價格 500–200000、排除組合包/工作站）
2. 組成 CSV（或蝦皮 JSON）→ 經剪貼簿/檔案帶出（下載在自動化環境可能不穩，剪貼簿較可靠）
3. `python tools/import_listings.py --csv imports/shopee_xxx.csv`

匯入後會自動依今日成交**重算均價快照**（排除海外參考價來源），均價即反映真實行情。

## 清理暫存檔
匯入後這些 csv/json 就沒作用了（DB 才是真資料），累積太多可一鍵清理（保留範本）：
```bash
python tools/clear_imports.py            # 直接刪除
python tools/clear_imports.py --archive  # 改為移到 imports/archive/<時間戳>/
python tools/clear_imports.py --dry-run  # 只列出，不動手
```

## 注意
- 本資料夾的 `*.csv` / `*.json`（範本除外）已被 `.gitignore` 忽略，**不會提交**（可能含個資）。
- listings 各來源預設保留 365 天、FB 90 天，匯入/爬蟲後由 `prune_by_retention()` 自動清除逾期。
