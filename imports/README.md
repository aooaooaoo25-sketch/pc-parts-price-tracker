# imports/ — 匯入資料夾

蝦皮、FB 等需登入的來源改走「匯入式」。把你在**自己已登入的瀏覽器**取得的資料
放到這個資料夾，再用匯入器寫入資料庫：

```bash
# 通用 CSV（任何來源，含 FB 社團貼文整理後）
python tools/import_listings.py --csv imports/your_file.csv

# 蝦皮：登入蝦皮後於瀏覽器開 search_items API 連結，另存 JSON（單一零件）
python tools/import_listings.py --shopee imports/shopee_xxx.json --part gpu_rtx5090

# 蝦皮：一波抓多顆 → 合併成 {part_id:{items:[...]}} 單檔，一次匯入多顆
python tools/import_listings.py --shopee-multi imports/shopee_cpu.json
```

> 匯入時 `parse_shopee_items` 會自動過濾**整機/套裝/分期/夾帶顯卡等組合**與跨型號
> 「可參考」雜訊（`SHOPEE_NOISE`），並做後綴比對（避免 14900K 收到 14900KF）。
> 均價快照另以 `robust_price_stats`（IQR 去極值）計算，抵抗殘留離群價。

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

### ⚠️ 蝦皮反爬蟲節流（實測）
蝦皮對自動化很敏感，**一旦被標記就會跳圖形驗證碼（captcha）**，而 captcha 需**本人手動解**：
- 41 個關鍵字連發 → 立刻 captcha；即使每筆延遲 4–5 秒，被標記後**約第 6 個請求**就再次 captcha。
- **可行節奏**：每波只抓 **≤5 個型號**就停；**不同天**分次補（讓偵測冷卻）；遇 captcha 先手動解再續。
- 想要全自動/排程的來源只有 **PTT**（匿名）。蝦皮定位為「小量、偶爾、半手動」。

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
