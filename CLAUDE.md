# CLAUDE.md — PC 零件二手市場價格追蹤系統

此文件供 Claude Code 在開發本專案時參考。請在每次對話開始前先讀取此文件。

---

## 專案概述

**目標**：追蹤台灣中文圈二手市場（蝦皮、PTT、FB 公開二手社團）中，消費級 PC 零件的二手成交價格，並與全新定價做差價比較，產生歷史折線圖。

**定位**：個人研究 / 學術用途，非商業產品。請求頻率已加入隨機延遲以避免對平台造成負擔。

---

## 專案結構

```
pc_price_tracker/
├── CLAUDE.md                  # 本文件
├── index.html                 # 前端介面（純靜態可直接開啟；有 API 時自動取真實資料）
├── pc_scraper_backend.py      # 後端爬蟲主程式（Python 非同步）
├── api_server.py              # 本地 API server（Flask）：前端橋接層
├── tools/
│   ├── sync_parts.py          # 零件目錄同步器：以前端 DB 為主重建後端 PARTS_DB
│   ├── seed_demo_data.py      # 產生示範用價格資料寫入 pc_prices.db（開發/展示）
│   └── validate_selectors.py  # 驗證露天/巴哈爬蟲選擇器是否符合現行 DOM（待辦 #4）
├── pc_prices.db               # SQLite 資料庫（執行後自動產生）
├── price_report.json          # 匯出報表（執行後自動產生）
├── requirements.txt           # Python 依賴
├── .env                       # API 金鑰（不得提交至 git）
├── .env.example               # API 金鑰範本
└── .gitignore                 # 含 .env、*.db、price_report.json
```

---

## 技術架構

### 前端（index.html）

- **純靜態單頁 HTML**，無框架、無建置步驟，可直接在瀏覽器開啟
- **Chart.js 4.4.1**（CDN）：繪製二手價格折線圖
- **目前資料為模擬數據**（`genUsed()`、`genHist()`、`genLs()`），待後端實作後需替換為真實 API 資料
- 整體採用深色主題，CSS 變數集中定義於 `:root{}`

**前端主要模組（JS 函式）：**

| 函式 | 用途 |
|------|------|
| `setCat(cat, el)` | 切換側邊欄分類 |
| `onSearch()` | 搜尋欄輸入處理，含未收錄零件偵測 |
| `searchUnknown()` | 對自訂輸入執行模擬行情搜尋 |
| `addCustom()` | 將未收錄零件加入自訂追蹤清單 |
| `selP(id)` | 點選零件列表列，展開詳情面板 |
| `showDp(p)` | 渲染右側詳情面板（統計卡 + 圖表 + 來源 + 成交記錄） |
| `renderChart(p, range)` | 以 Chart.js 繪製特定時間區間折線圖 |
| `runDb()` | 模擬製造商產品庫更新流程（Modal 動畫） |
| `startCrawl()` | 模擬觸發爬蟲（目前為前端模擬，待串接後端） |
| `loadLive()` | 向 `/api/report` 取真實資料存入 `RPT`，設定 `LIVE` 並重繪；失敗則維持模擬 |
| `genUsed(p)` | 取二手均價：`RPT[p.id]` 有資料用真實（含 `_ls`/`_h`/`_src`），否則模擬回退 |
| `genHist(base)` | **【模擬回退】** 無真實資料時產生 365 天歷史 |
| `genLs(p)` | **【模擬回退】** 無真實資料時產生成交列表 |

**前端零件資料庫（`DB` 物件）：**

每個零件物件結構如下：
```javascript
{
  id: 'gpu_rtx5090',    // 統一識別碼，格式 <cat>_<model>，前後端共用
  cat: 'gpu',           // 分類：cpu / gpu / ram / mb / ssd / hdd / psu / cooler
  name: 'GeForce RTX 5090',
  spec: '21760 CUDA・32GB GDDR7・575W・PCIe5.0・Blackwell・2025',
  new_price: 89900,     // 全新建議售價 TWD，停售品填 0
  tags: ['NEW','2025','旗艦'],  // 可用標籤：NEW / 熱門 / 旗艦 / CP值 / 高頻 / 頂級 / 年份
}
```

**ID 命名規則（前後端統一，2026-06-03 起）：**
- CPU：`cpu_<tier>_<model>` — 例 `cpu_i9_14900k`、`cpu_ultra9_285k`、`cpu_r7_5800x3d`
- GPU：`gpu_<brand><model>` — 例 `gpu_rtx5090`、`gpu_rx7900xtx`、`gpu_arcb580`
- 其他（RAM/主機板/SSD/HDD/PSU/散熱）：`<cat>_<完整名稱 slug>` — 例 `ram_corsair_vengeance_ddr5_5600_32gb`、`ssd_samsung_990_pro_2tb`
  （含品牌，避免同規格不同品牌撞名）

> ⚠️ 前端 `DB` 是**唯一主目錄**。新增/修改零件後執行 `python tools/sync_parts.py`，
> 即可自動重算 id 並重建後端 `PARTS_DB`，確保兩邊一致。**請勿手動編輯後端 PARTS_DB。**

目前各分類品項數量（前端 DB＝後端 PARTS_DB，共 166 項）：
- CPU：38 項（Intel Arrow Lake / Raptor Lake / Alder Lake、AMD Ryzen 9000 / 7000 / 5000）
- GPU：41 項（RTX 50/40/30、RX 9000/7000/6000、Arc Battlemage/Alchemist）
- RAM：14 項（DDR5 / DDR4）
- 主機板：21 項（Z890 / Z790 / B760 / X870E / X670E / B650）
- SSD：16 項（PCIe5 / PCIe4 / SATA）
- HDD：10 項
- 電源：12 項
- 散熱：14 項

---

### 後端（pc_scraper_backend.py）

- **Python 3.11+**，使用 `asyncio` + `aiohttp` 非同步爬蟲
- **資料庫**：SQLite（`pc_prices.db`），三張資料表：`listings`、`price_snapshots`、`crawl_log`
- **資料來源**（繼承自 `BaseScraper`）：

| 類別 | 平台 | 方法 | 狀態 |
|------|------|------|------|
| `ShopeeScraper` | 蝦皮購物 | 搜尋 API（JSON） | ✅ 主力 |
| `PTTScraper` | PTT BuyTrade / PC_Shopping | HTML + Regex 解析 | ✅ 啟用 |
| `FBGroupScraper` | FB 公開二手社團 | 匯入式（FB 需登入、禁自動爬） | 🔶 架構預留，僅保留 90 天 |
| `EbayScraper` | eBay 國際站 | 官方 Browse API（需 OAuth token） | 🔶 架構預留，**海外參考價** |

> 露天（`LuTianScraper`）、巴哈（`BahaScraper`）已於 2026-06-03 **移除**（資訊量不足／過於分散）。
> 各來源保留天數見 `SOURCE_RETENTION`（FB＝90 天，其餘預設 365 天）；逾期由 `Database.prune_old_listings` 清除。
> `REFERENCE_SOURCES`（如 eBay）為**海外參考價**：資料仍儲存供對照，但**不計入**台灣二手均價快照。

**後端零件資料庫（`PARTS_DB`）：** 巢狀 dict，結構為 `{分類: {子分類: [零件列表]}}`，每筆含 `id` / `name` / `aliases` / `new_price`。由 `tools/sync_parts.py` **從前端 `DB` 自動產生**，id 與 name 與前端完全一致（原「兩份資料未同步」的技術債已於 2026-06-03 解決，待辦 #2）。

---

## 已知問題與待辦事項

### 🔴 高優先（核心功能缺失）

1. ~~**前後端資料未串接**~~ ✅ 已完成（2026-06-03）：新增 `api_server.py`（Flask），前端載入時呼叫 `/api/report` 取真實資料；`genUsed/genLs/genHist` 改為「有真實資料用真實、否則回退模擬」。API 未啟動時直接開啟 `index.html` 仍可降級運作
2. ~~**前後端零件 ID 不一致**~~ ✅ 已完成（2026-06-03）：統一為 `<cat>_<model>` 規則，前後端共 166 項 id 完全一致；後端 `PARTS_DB` 改由 `tools/sync_parts.py` 自前端 `DB` 產生
3. **後端缺少製造商官網爬蟲**：`runDb()` 按鈕在前端有 Modal 動畫，但後端無對應的製造商產品庫更新邏輯
4. ~~**爬蟲選擇器未驗證**~~ ✅ 已驗證並依結果調整來源策略（2026-06-03，`tools/validate_selectors.py`）：
   - **露天**：搜尋頁已改為 **SPA**，`.item-panel` 等選擇器命中 0（HTML 解析法失效）。
   - **巴哈**：選擇器有效但板號 `C_115` 無效，且無單一二手板。
   - 結論：兩者資訊量不足／過於分散，**已移除**；改以蝦皮 + PTT 為主、規劃 FB 公開二手社團（匯入式、保留 90 天）。

### 🟡 中優先（功能完善）

5. ~~**缺少 Flask/FastAPI 後端伺服器**~~ ✅ 已完成（2026-06-03）：新增 `api_server.py`，提供 `/api/health`、`/api/report`、`/api/part/<id>`，並在 `/` 直接服務前端
6. **價格歷史資料為空**：`price_snapshots` 資料表在首次執行前無資料，折線圖需要累積數天才有意義（開發/展示可先跑 `tools/seed_demo_data.py` 產生示範資料）
7. **搜尋未收錄零件的行情估算過於粗糙**：`estP()` 函式用關鍵字硬比對估價，應改為呼叫後端實際爬蟲
8. ~~**`Reporter.export_json()` 與前端 DB 結構不匹配**~~ ✅ 已處理（2026-06-03）：新增 `Reporter.get_detail()` / `build_report()` 產生與前端一致的扁平 `{part_id: detail}` 結構，供 API 使用

### 🟢 低優先（體驗優化）

9. ~~**缺少 `.gitignore` 與 `requirements.txt`**~~ ✅ 已完成（2026-06-03，commit `e58cfe5`）：新增 `.gitignore`、`requirements.txt`、`.env.example`
10. **前端無法持久化自訂追蹤零件**（重整後消失）
11. **圖表只有折線，缺少最高/最低價區間陰影**
12. **行動裝置版面未優化**（detail panel 在小螢幕會溢出）

---

## 開發規範

### 語言與編碼

- 所有**使用者介面文字**一律使用**繁體中文**
- 程式碼**變數名稱、函式名稱**使用英文
- 程式碼**行內註解**可用繁體中文

### 前端修改原則

- **不引入新的外部框架**（不加 React / Vue / Vite）；保持單一 HTML 檔可直接開啟
- 新增 CSS 樣式時使用現有 CSS 變數（`var(--bg)`、`var(--accent)` 等），不得 hardcode 顏色值
- 修改 JS 時注意：`allP()` 會合併 `DB` 與 `customs` 陣列，兩者都要考慮
- 每個零件物件的 `id` 必須全域唯一

### 後端修改原則

- 新增爬蟲平台時，繼承 `BaseScraper` 並實作 `scrape_part(self, part)`
- 所有 HTTP 請求必須經過 `self.fetch()` 發送（內建隨機延遲與錯誤處理）
- 價格合法範圍：`500 ≤ price ≤ 200000`（TWD），超出範圍一律過濾
- DB 操作集中在 `Database` 類別，不在爬蟲類別內直接寫 SQL

### 安全與金鑰

- `ANTHROPIC_API_KEY` 一律從環境變數讀取，**絕不**寫入任何程式檔
- `.env` 檔不得提交至版本控制

---

## 環境設定

### Python 依賴

```bash
pip install aiohttp beautifulsoup4 lxml python-dotenv
```

### 環境變數

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-你的學校金鑰
```

### 執行方式

```bash
# 執行爬蟲（全部分類）
python pc_scraper_backend.py

# 只爬特定分類（修改 main() 內的 category_filter 參數）
# category_filter=["gpu", "cpu"]

# 直接開啟前端（無需伺服器；API 未啟動則顯示模擬資料）
open index.html       # macOS
start index.html      # Windows
```

### 前後端串接（API server）

```bash
# （首次/開發）產生示範價格資料，讓前端有東西可顯示
python tools/seed_demo_data.py

# 啟動 API server（預設 http://127.0.0.1:5000）
python api_server.py
# 然後瀏覽器開 http://127.0.0.1:5000  （同源，免 CORS）
# 或直接開 index.html（file://）：前端會連 127.0.0.1:5000 的 API
```

- 端點：`/api/health`、`/api/report`（全部）、`/api/part/<id>`（單一）
- 前端載入時自動呼叫 `/api/report`；連線成功右上角顯示「🟢 真實資料」，
  失敗顯示「🟡 模擬資料」並回退本地模擬（`genUsed/genLs/genHist`）
- 真實資料由 `Reporter.get_detail()` 產生，形狀為 `{used, diff_pct, history{1w..1y}, sources[], listings[]}`

### 零件目錄同步（前後端一致性）

```bash
# 改完前端 DB 後，重建後端 PARTS_DB
python tools/sync_parts.py

# 只驗證前後端是否同步（不改檔；不一致回傳非 0）
python tools/sync_parts.py --check
```

**首次 clone 後執行一次**，啟用自動把關的 git pre-commit hook（位於 `hooks/`）：

```bash
git config core.hooksPath hooks
```

啟用後，每次 `git commit` 會自動跑 `--check`，前後端若不同步會**擋下 commit**，
確保不可能提交出 ID 不一致的狀態。

> Windows + 中文路徑：若 `python` 出現路徑亂碼，請先設定 `PYTHONUTF8=1`（hook 內已自動設定）。

---

## 爬蟲平台說明

| 平台 | 注意事項 |
|------|----------|
| 蝦皮購物 | 使用非公開搜尋 API，需帶正確 Referer；價格單位為分×1000 |
| PTT BuyTrade | 需帶 cookie `over18=1`；以 Regex 從文章內容解析售價 |
| FB 社團 | 需登入且禁自動爬取 → 採**匯入式**（已登入瀏覽器匯出貼文後解析寫入）；僅保留近 90 天 |
| eBay | 匿名爬蟲被反機器人擋（實測 403）→ 僅能走**官方 Browse API**（需 `EBAY_OAUTH_TOKEN`）；定位海外參考價（USD、不計入台灣均價） |

### FB 社團資料（待接入）

FB 公開二手社團內容需登入、且自動爬取違反 FB 服務條款，故**不走自動爬蟲**。
架構已預留 `FBGroupScraper`（`name="FB 社團"`、`RETENTION_DAYS=90`），日後採以下其一接入：

1. **匯入式（建議）**：使用者在自己已登入的瀏覽器將社團貼文匯出/貼上，由解析器抽出
   型號與售價，轉成 `Listing(source="FB 社團", ...)` 後呼叫 `Database.save_listing` 寫入。
2. **已登入瀏覽器半自動擷取**：透過使用者授權的瀏覽器操作擷取（仍受 FB 條款限制）。

寫入後，統計快照、API、前端來源分布皆自動沿用；逾 90 天資料由 `SOURCE_RETENTION` +
`Database.prune_old_listings` 於每次爬蟲後清除。

---

## 與 Claude 協作建議

- 修改前端時，請**只提供需要修改的函式或 CSS 區塊**，不需貼整個 HTML 檔案
- 指定修改位置時，可說「`renderChart` 函式」或「`.prow` 樣式」等精確位置
- 新增零件**只改前端 `DB`**（`id` 欄位需保留、先填任意暫值，跑同步器會依規則重算）、`cat` 為既有分類之一、`tags` 使用既有標籤；改完執行 `python tools/sync_parts.py` 同步後端
- 討論後端爬蟲修改時，請說明是哪個爬蟲類別（`ShopeeScraper` / `PTTScraper` / `FBGroupScraper`）
