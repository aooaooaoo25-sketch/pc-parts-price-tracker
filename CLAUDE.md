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
├── crawl_daily.ps1            # 每日 PTT 自動爬取包裝腳本（Windows 工作排程器呼叫）
├── catalog_updater.py         # 製造商產品庫更新：偵測官網新型號（待辦 #3）
├── estimator.py               # 未收錄零件行情估算：以真實目錄/成交資料估價（待辦 #7）
├── tools/
│   ├── sync_parts.py          # 零件目錄同步器：以前端 DB 為主重建後端 PARTS_DB
│   ├── seed_demo_data.py      # 產生示範用價格資料寫入 pc_prices.db（開發/展示）
│   ├── validate_selectors.py  # 驗證爬蟲選擇器是否符合現行 DOM（待辦 #4）
│   ├── import_listings.py     # 匯入式來源（蝦皮/FB）的成交資料匯入器
│   ├── scrape_coolpc.py       # 原價屋報價單抓取：權威「目前全新行情」來源（#3）
│   ├── make_en.py             # build 時從 index.html 衍生英文 SEO 頁 dist/en.html（/en）
│   ├── make_sitemap.py        # build 時產生 sitemap（首頁+/en+每零件 ?p= 深連結，附 hreflang）
│   ├── rebuild_snapshots.py   # 一次性遷移：用現行分流邏輯重算所有快照
│   └── clear_imports.py       # 一鍵清理 imports/ 累積的暫存檔（保留範本）
├── imports/                   # 匯入資料夾（範本已附；實際資料不提交）
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
| `searchUnknown()` | 未收錄輸入 → 呼叫 `/api/estimate` 估價並顯示詳情預覽（回退 `estP`） |
| `addCustom()` | 將未收錄零件（後端估價）加入自訂追蹤清單 |
| `estUnknown(q)` | 向 `/api/estimate` 取估價，失敗回退本地 `estP` |
| `selP(id)` | 點選零件列表列，展開詳情面板 |
| `showDp(p)` | 渲染右側詳情面板（統計卡 + 圖表 + 來源 + 成交記錄）；含「目前全新行情」卡（`p._newNow`/`_newNowSrc`/`_diffNow`，標來源 + ▲% vs 上市 + 二手省%） |
| `renderChart(p, range)` | 以 Chart.js 繪製折線圖：二手均價線 + 最高/最低區間帶 + **目前全新行情橘線**（`_newHist`）+ 上市定價虛線 + eBay 參考線 |
| `runDb()` | 呼叫 `/api/update_catalog` 偵測製造商官網新型號，於 Modal 顯示「目錄未收錄」的新品 |
| `startCrawl()` | 模擬觸發爬蟲（目前為前端模擬，待串接後端） |
| `loadLive()` | 向 `/api/report` 取真實資料存入 `RPT`，設定 `LIVE` 並重繪；失敗則維持模擬 |
| `genUsed(p)` | 取二手均價：`RPT[p.id]` 有資料用真實（含 `_ls`/`_h`/`_hmin`/`_hmax`/`_newHist`/`_src`/`_newNow`/`_newNowSrc`/`_diffNow`），否則模擬回退 |
| `toggleLang()` / `applyLang()` | 繁中/English 切換（`I18N`+`t()`；`tspec`/`ttag`/`tsrc` 譯規格/標籤/來源）；同步 `<html lang>`/title/meta |
| `genHist(base)` | **【模擬回退】** 無真實資料時產生 365 天歷史 |
| `genLs(p)` | **【模擬回退】** 無真實資料時產生成交列表 |
| `applyMode()` | 依 `LIVE` 切換公開/本地：API 未連線（公開靜態站）時隱藏更新產品庫/自訂搜尋，精簡為單向查詢 |
| `tick()` | 頁尾即時時鐘（每秒更新日期時間） |
| `openFeedback()`/`closeFeedback()`/`submitFeedback()` | 意見回饋彈窗：填主題/內容/(選填)Email → 經 **Web3Forms** AJAX 直送站長信箱（免後端、免郵件程式、不跳轉）。access key 在前端（公開金鑰）、信箱不在原始碼、含 honeypot 擋垃圾 |

**前端零件資料庫（`DB` 物件）：**

每個零件物件結構如下：
```javascript
{
  id: 'gpu_rtx5090',    // 統一識別碼，格式 <cat>_<model>，前後端共用
  cat: 'gpu',           // 分類：cpu / gpu / ram / ssd / hdd
  name: 'GeForce RTX 5090',
  spec: '21760 CUDA・32GB GDDR7・575W・PCIe5.0・Blackwell・2025',
  new_price: 89900,     // 全新售價 TWD：仍在售用現價，停產用「台灣當年建議售價」（2026-06-11 補齊，原為 0 的 26 顆已填）
  tags: ['NEW','2025','旗艦'],  // 可用標籤：NEW / 熱門 / 旗艦 / CP值 / 高頻 / 頂級 / 年份
}
```

**ID 命名規則（前後端統一，2026-06-03 起）：**
- CPU：`cpu_<tier>_<model>` — 例 `cpu_i9_14900k`、`cpu_ultra9_285k`、`cpu_r7_5800x3d`
- GPU：`gpu_<brand><model>` — 例 `gpu_rtx5090`、`gpu_rx7900xtx`、`gpu_arcb580`
- 其他（RAM/SSD/HDD）：`<cat>_<完整名稱 slug>` — 例 `ram_corsair_vengeance_ddr5_5600_32gb`、`ssd_samsung_990_pro_2tb`
  （含品牌，避免同規格不同品牌撞名）

> ⚠️ 前端 `DB` 是**唯一主目錄**。新增/修改零件後執行 `python tools/sync_parts.py`，
> 即可自動重算 id 並重建後端 `PARTS_DB`，確保兩邊一致。**請勿手動編輯後端 PARTS_DB。**

目前各分類品項數量（前端 DB＝後端 PARTS_DB，共 111 項）：
- CPU：38 項（Intel Arrow Lake / Raptor Lake / Alder Lake、AMD Ryzen 9000 / 7000 / 5000）
- GPU：41 項（RTX 50/40/30、RX 9000/7000/6000、Arc Battlemage/Alchemist）
- RAM：6 項（**規格帶**：DDR5 32/16/64GB、DDR4 32/16/8GB；非品牌型號，見下）
- SSD：16 項（PCIe5 / PCIe4 / SATA）
- HDD：10 項

> 主機板 / 電源 / 散熱 已於 2026-06-08 **移除**（廠牌眾多、二手價格帶穩定波動小），
> 聚焦 GPU / CPU / RAM / SSD / HDD 五類。
>
> **RAM 改為規格帶**（2026-06-08）：市場多以「DDR5 32G」這種規格賣、少寫品牌型號，故 RAM
> 不用品牌 SKU，改用容量+世代帶。前端 DB 的 RAM 項目加了**選填 `aliases` 欄位**（市場用語，
> 如 `['DDR5 32G','DDR5 32GB']`），`sync_parts.py` 會優先採用它當後端 aliases / PTT 搜尋詞。
> PTT 抓 RAM 時另排除「夾帶其他零件的組合」與筆電記憶體（`PTTScraper` 內 RAM 專屬過濾），
> 確保均價只算純 RAM 賣文（較乾淨但較稀疏）。
>
> **RAM 蝦皮 + 原價屋資料**（2026-06-23~24）：已匯入蝦皮 6 組規格帶（單次快照、半手動）並接原價屋
> 每日新品價。`title_matches_part` 的 RAM 比對用 kit-aware 容量（`ram_total_capacities()`：「16G*2」=32G、
> 「32G*2」=64G）；`SHOPEE_RAM_NOISE` 排除筆電 SO-DIMM / 伺服器 ECC/REG。RAM 幾無真 C2C 二手 →
> 「目前全新行情」（飆漲主角，DDR5 32G +299% vs 上市）才是 RAM 的重點，「二手」為較便宜零售之代理值。

---

### 後端（pc_scraper_backend.py）

- **Python 3.11+**，使用 `asyncio` + `aiohttp` 非同步爬蟲
- **資料庫**：SQLite（`pc_prices.db`），四張資料表：`listings`、`price_snapshots`（二手）、`new_snapshots`（目前全新行情每日快照）、`crawl_log`
- **資料來源**（繼承自 `BaseScraper`）：

| 類別 | 平台 | 方法 | 狀態 |
|------|------|------|------|
| `PTTScraper` | PTT `hardwaresale`（硬體買賣板） | HTML + Regex 解析 | ✅ 匿名可爬、**每日排程**（唯一全自動真實來源） |
| `ShopeeScraper` | 蝦皮購物 | 搜尋 API（JSON） | 🔶 匿名被擋(403)→改**匯入式**（登入後存 JSON 用匯入器） |
| `FBGroupScraper` | FB 公開二手社團 | **匯入式**（CSV，FB 需登入） | 🔶 僅保留 90 天 |
| `EbayScraper` | eBay 國際站 | 官方 Browse API（client_credentials 自動換 token） | ✅ 已實作，**海外在售參考價**（USD→TWD、不計台灣均價） |
| 原價屋（coolpc） | `evaluate.php` 報價單 | 匿名抓 + Big5/cp950 解析 `<select>` | ✅ **權威「目前全新行情」來源**（每日排程、無 captcha、不計二手） |

> **匯入式來源**（蝦皮 / FB）：資料豐富但需登入、禁匿名爬取 → 由使用者在自己已登入的
> 瀏覽器取得資料，再用 `tools/import_listings.py` 寫入 DB（CSV 或蝦皮 search_items JSON）。
> 解析蝦皮 JSON 與爬蟲共用 `parse_shopee_items()`。匯入後統計／API／前端自動沿用。

> **原價屋（coolpc）＝權威新品價**（待辦 #3，2026-06-24）：`scrape_coolpc_to_db()` 抓 `evaluate.php`
> 報價單，比對 PARTS_DB 命中型號的新品價，以 `source=原價屋` 寫入（列 `REFERENCE_SOURCES`、保留 14 天）。
> `get_detail` 的「目前全新行情」(`new_now`) **優先用原價屋**、停產件原價屋無貨時退回蝦皮全新賣文
> （`new_now_src` 標 原價屋/蝦皮）。`part_new_ref`（二手分流價格天花板）亦優先用原價屋。
> 匿名可抓無 captcha → 已接每日排程；亦可 `python tools/scrape_coolpc.py` 手動跑。
> RAM 比對用 kit-aware 容量 `ram_total_capacities()`（「16G*2」=32G）避免套組容量誤判。

> 露天（`LuTianScraper`）、巴哈（`BahaScraper`）已於 2026-06-03 **移除**（資訊量不足／過於分散）。
> 各來源保留天數：`SOURCE_RETENTION` 指定（FB＝90 天），未列出者用 `DEFAULT_RETENTION_DAYS`（365 天）；
> 每次爬蟲/匯入後由 `prune_by_retention()` 對 DB 中所有來源自動清除逾期 listings。
> `REFERENCE_SOURCES`（如 eBay）為**海外參考價**：資料仍儲存供對照，但**不計入**台灣二手均價快照。

**後端零件資料庫（`PARTS_DB`）：** 巢狀 dict，結構為 `{分類: {子分類: [零件列表]}}`，每筆含 `id` / `name` / `aliases` / `new_price`。由 `tools/sync_parts.py` **從前端 `DB` 自動產生**，id 與 name 與前端完全一致（原「兩份資料未同步」的技術債已於 2026-06-03 解決，待辦 #2）。

---

## 已知問題與待辦事項

> **進度摘要（2026-06-03 ~ 06-04）**
> - ✅ 已完成：#1 前後端串接、#2 ID 統一、#3 製造商新品偵測、#4 選擇器驗證、
>   #5 API server、#7 未收錄估價、#8 報表結構、#9 .gitignore/requirements
> - 🔶 進行中：#6 價格歷史（已可匯入真實資料，待累積天數）
> - ✅ 全部待辦完成：#10 自訂追蹤持久化、#11 圖表區間陰影、#12 行動版面皆已完成
>   （唯 #6 需靠每日排程持續累積天數，屬資料面而非開發面）
> - **資料來源現況**：PTT `hardwaresale` 可匿名自動爬（**已設每日排程**，累積真實歷史）；
>   蝦皮/FB 走「登入瀏覽器擷取 → 匯入」（已實證蝦皮可行，但有反爬蟲節流）；
>   eBay 官方 Browse API 已實作（海外在售參考價，需金鑰）。露天/巴哈已移除。
> - **新增模組**：`api_server.py`、`catalog_updater.py`、`estimator.py`、
>   `tools/{sync_parts,seed_demo_data,validate_selectors,import_listings}.py`、`hooks/pre-commit`

> **🆕 進度摘要（2026-06-23 ~ 06-24）：目前全新行情（新舊分流）**
> 因 AI 需求，全新零件（RAM/GPU）價格飆漲，與二手脫鉤 → 新增「**目前全新行情**」並把
> **全新從二手均價分流**。三步完成（皆已部署上線）：
> - **① 改善偵測**：`classify_listing()` 集中分類規則（'used'/'new'/'exclude'）：
>   明確二手字樣→二手（但喊到≥全新價的「良品」整新店→exclude 剔除）；明確全新/零售字樣→全新；
>   無成色但**價格≥目前全新行情(new_ref)**→全新（蝦皮零售卡無「全新」字樣者）。
>   `is_cross_model_gpu()` 剔除跨型號賣場清單；`_NEW_RE` 擴充零售訊號（庫存/開發票/含稅/終身保固…）。
>   `part_default_new()`：RAM 這種零售為主、二手稀少的品類，無成色**預設全新**（僅用於 new_now 估計，
>   不套到二手快照否則整顆消失）。
> - **② 補蝦皮 RAM**：6 組規格帶（DDR5/DDR4 × 32/16/64/8GB）。`parse_shopee_items` 改**雙階段**：
>   先濾雜訊、再用「本批中位數 ×3.5」**動態價格上限**（取代舊「>2.5×上市價」，否則飆漲品被當整機剔掉）。
>   `title_matches_part` 加 RAM 規格帶比對（世代+kit-aware 容量同時出現）；加筆電/伺服器 RAM 過濾。
> - **③ 接原價屋**：見上方來源表。`new_now` 優先原價屋、退回蝦皮；`part_new_ref`（價格天花板）亦優先原價屋。
> - **後端欄位**：`get_detail` 新增 `new_now`/`new_count`/`new_now_src`(原價屋/蝦皮)/`diff_now_pct`(二手 vs 目前全新)；
>   listings 加 `is_new` 標記；`ebay_ref` 改只查 eBay。二手快照只用價格天花板分流（`rebuild_today_snapshots`/
>   `scrape_one`），全新不計入。
> - **前端**：詳情面板新增「目前全新行情」卡（標來源 + ▲% vs 上市 + 二手省X%）；成交明細「全新」藍標籤。
> - **新增模組**：`tools/scrape_coolpc.py`、`tools/rebuild_snapshots.py`（一次性重算所有快照的遷移）。
> - **誠實限制**：RAM 幾無真 C2C 二手 → 其「二手」是較便宜零售的代理值（顯示二手省%合理但非真二手）；
>   蝦皮 RAM 為單次快照（半手動），原價屋與 PTT 才每日自動刷新。

> **🆕 進度摘要（2026-06-26）：新品價歷史曲線 + 中英雙語**
> - **① 新品價歷史曲線**：把「目前全新行情」從單一數字升級為走勢線（呈現 AI 飆漲）。
>   新增 `new_snapshots` 表（part_id, date, new_price, src, cnt）；`compute_new_now()`（滾動值，
>   原價屋優先退回蝦皮）、`new_price_on_date()`（某日新品價）、`rebuild_new_snapshots()`（掃 listings
>   每日回填，已接 CrawlerScheduler / import_listings / scrape_coolpc / rebuild_snapshots）。
>   `get_detail` 加 `new_history`（對齊二手 history 日期、carry-forward、末點固定為當前 new_now）。
>   前端 `renderChart` 加橘色實線「目前全新行情」（`spanGaps` 連稀疏點）；MSRP 線改標「上市定價」。
>   **現況**：剛接，多數零件 1-2 點，原價屋每日自動跑 → 約一週後成形。
> - **② 中英雙語（i18n A 方案）**：右上 EN/中文 鈕，`I18N{zh,en}` + `t()` + `applyLang()`（記 localStorage）。
>   靜態用 `data-i18n`*；動態走 `t()`；規格 `tspec()`（核→-core…）、tags `ttag()`、來源 `tsrc()`。
>   切語言同步換 `<html lang>`/`document.title`/`meta description`。
> - **③ 英文 SEO（B 方案）**：獨立 `/en`——`tools/make_en.py` build 時從 `index.html` 衍生 `dist/en.html`
>   （英文 head + `window.__FORCE_LANG='en'`，Cloudflare 服務在 `/en`）；`index.html`/`sitemap.xml` 加
>   hreflang(zh-Hant/en/x-default)。⚠️ Search Console 提交 sitemap 要填 `sitemap.xml`（非 `/en`，那是網頁）。

### 🔵 後續可改善（2026-06-26 盤點，皆非阻斷、依價值排序）

- ✅ **折價語意**（2026-06-26 已修）：折價幅度改「二手 vs 目前全新」(真折價)，無新品價才退回 vs 上市價；
  副標隨之切換、新品卡移除重複的「二手省%」。`dispDiff()`。
- ✅ **二手數字跳動**（2026-06-26 已修）：頭條二手改用近 14 快照中位數（`statistics.median`），
  蝦皮日↔PTT 日不再跳（3060 穩定 5000）；圖表仍畫每日真實序列。卡片標題改「二手均價」。
- **CPU 跨型號漏網**（低）：`is_cross_model_gpu` 只擋顯卡；CPU 裸數字多型號清單（「13400F/14400F/…」）仍會漏收 → 比照做 CPU 版。
- ✅ **單元測試**（2026-06-26 已完成）：`tests/test_core.py`（27 項，pytest）涵蓋 `title_is_new`/
  `classify_listing`(used/new/exclude+天花板+default_new)/`ram_total_capacities`(kit-aware)/
  `title_matches_part`(RAM 規格帶+變體後綴)/`gpu_model_set`/`is_cross_model_gpu`/`parse_coolpc`/
  `robust_price_stats`/`split_used_new`/`part_default_new`。執行：`python -m pytest tests/ -q`。
- **原價屋覆蓋率**（低中）：只命中當代品 23/111（停產件本就無新品價，屬正常）；**HDD 0 命中**（別名不合需修）；
  只有原價屋資料、無二手快照的零件（如某 SSD）→ `get_detail` 回 None 而不顯示（可改成「有新品價也顯示」）。
- **新品價曲線需養天數**：原價屋每日自動累積，約一週後曲線才完整（資料面，非開發面）。
- **英文 SEO 後續**：分享圖 `og.png` 兩語共用（圖上中文）；想要英文分享卡可在 `make_og.py` 加英文版、`en.html` 指向它。
- **robots/sitemap BOM**（極低）：`deploy.ps1` 用 PS5.1 `Set-Content -Encoding utf8` 會加 UTF-8 BOM；
  Google 對 robots/sitemap 都會忽略 BOM、不影響，要乾淨可改 `[IO.File]::WriteAllText`（無 BOM）。
- **蝦皮自動化缺口**：蝦皮有 captcha → 無法自動，RAM/蝦皮二手不會自刷新（平台限制，只有 PTT + 原價屋每日自動）。

### 🔴 高優先（核心功能缺失）

1. ~~**前後端資料未串接**~~ ✅ 已完成（2026-06-03）：新增 `api_server.py`（Flask），前端載入時呼叫 `/api/report` 取真實資料；`genUsed/genLs/genHist` 改為「有真實資料用真實、否則回退模擬」。API 未啟動時直接開啟 `index.html` 仍可降級運作
2. ~~**前後端零件 ID 不一致**~~ ✅ 已完成（2026-06-03）：統一為 `<cat>_<model>` 規則，前後端共 166 項 id 完全一致；後端 `PARTS_DB` 改由 `tools/sync_parts.py` 自前端 `DB` 產生
3. ~~**後端缺少製造商官網爬蟲**~~ ✅ 已完成（2026-06-03）：新增 `catalog_updater.py` + `/api/update_catalog`，掃 NVIDIA/AMD 官網型號名，比對目錄回報「官網有、目錄未收錄」的新品（如 RTX 5050、RX 9060）。`runDb()` 改為呼叫真實 API。**限制**：官網只抓得到型號名、抓不到價格（且為美金），新品 `new_price` 留 0 待人工填；Intel Arc 常 403 會略過
4. ~~**爬蟲選擇器未驗證**~~ ✅ 已驗證並依結果調整來源策略（2026-06-03，`tools/validate_selectors.py`）：
   - **露天**：搜尋頁已改為 **SPA**，`.item-panel` 等選擇器命中 0（HTML 解析法失效）。
   - **巴哈**：選擇器有效但板號 `C_115` 無效，且無單一二手板。
   - 結論：兩者資訊量不足／過於分散，**已移除**；改以蝦皮 + PTT 為主、規劃 FB 公開二手社團（匯入式、保留 90 天）。

### 🟡 中優先（功能完善）

5. ~~**缺少 Flask/FastAPI 後端伺服器**~~ ✅ 已完成（2026-06-03）：新增 `api_server.py`，提供 `/api/health`、`/api/report`、`/api/part/<id>`，並在 `/` 直接服務前端
6. 🔶 **價格歷史資料**：`price_snapshots` 首次執行前為空，折線圖需累積數天才有意義。
   - 開發/展示可先跑 `tools/seed_demo_data.py` 產生示範資料（⚠️ 會清空重建，勿在有真實資料時執行）。
   - 已實證可匯入**真實**資料：以 Claude-in-Chrome 從登入蝦皮擷取 RTX 5090 共 40 筆 → `import_listings.py` → 二手均價更新為真實 139,150。匯入後自動依今日成交重算快照。
   - **PTT `hardwaresale` 已設每日排程自動爬**（`crawl_daily.ps1` + 工作排程 `PCPriceTracker_PTTCrawl`）→ 真實歷史逐日累積中。
   - **蝦皮 CPU 匯入（2026-06-11）**：以 Claude-in-Chrome 擷取 5 顆熱門 CPU（5800X3D/13400F/14600K/7600/14900K）共 189 筆原始 → 過濾後 52 筆入庫。新增 `import_listings.py --shopee-multi`（一次匯多顆 `{part_id:{items:[...]}}`）。
     同步強化資料品質：`parse_shopee_items` 加 `SHOPEE_NOISE` 過濾（整機/套裝/分期/夾帶顯卡/「可參考」跨型號），`title_matches_part` 修正後綴+數字漏判（14900K 誤收 14900KF），快照改用 `robust_price_stats`（IQR 去極值）算均價/最高/最低。
     ⚠️ 蝦皮反爬蟲：實測**第 2 個請求**即可能跳流量驗證（captcha），需**不同天分批**冷卻補抓。
   - **蝦皮 CPU 第二波（2026-06-16）**：再補 5 顆（7700X/14700K/5600/12400F/5700X）共 268 筆原始 → 88 筆入庫。
     同步在 `parse_shopee_items` 加**價格上限**（>台灣新品價 2.5x 視為整機/組合排除，同 eBay `_parse`）——
     修掉「7700X 均價被整機拉到 2 萬」之類；CPU 仍有約 28 顆待後續波次。
   - **擷取技巧（補充）**：Claude-in-Chrome 的 `javascript_tool` 這版**async 回傳值會變 `{}`**（promise 序列化問題）；
     解法＝把結果存進 `window.__cpu`/`window.__clip` 等變數，再用**同步**運算式讀回（fetch/clipboard 的副作用仍正常）。
   - **蝦皮 GPU 首批（2026-06-21）**：`SHOPEE_NOISE` 改**分類感知**（`SHOPEE_GPU_COMBO` 只對非顯卡套用）後解鎖 GPU。
     抓 7 顆（4090/4070/3070/3060Ti/7800XT/3080/3060），並增補 GPU 雜訊（模型/手辦/擺飾/散熱模組/伺服器/晶片/配件）。
     **觀察**：蝦皮對**當代卡（4090/4070）多為全新現貨**（折價變正、非二手）；**老卡（3070/3060Ti/3080）才是乾淨二手**（折價 -40~-53%）；冷門卡（7800XT）量少。第 8 個請求觸發 captcha → 當日停手（3050/RX6000 待改天）。
7. ~~**搜尋未收錄零件的行情估算過於粗糙**~~ ✅ 已完成（2026-06-03）：新增 `estimator.py` + `/api/estimate`，以真實 166 項目錄與成交資料估價（目錄比對→相近型號→兜底），附 basis/confidence；前端 `searchUnknown/addCustom` 改呼叫後端、API 未連線回退 `estP`。順帶修好 `searchUnknown` 原本詳情面板不顯示的 bug
8. ~~**`Reporter.export_json()` 與前端 DB 結構不匹配**~~ ✅ 已處理（2026-06-03）：新增 `Reporter.get_detail()` / `build_report()` 產生與前端一致的扁平 `{part_id: detail}` 結構，供 API 使用

### 🟢 低優先（體驗優化）

9. ~~**缺少 `.gitignore` 與 `requirements.txt`**~~ ✅ 已完成（2026-06-03，commit `e58cfe5`）：新增 `.gitignore`、`requirements.txt`、`.env.example`
10. ~~**前端無法持久化自訂追蹤零件**~~ ✅ 已完成（2026-06-08）：`customs` 存入 localStorage（`saveCustoms/loadCustoms`），重整不消失；自訂列加「✕」移除鈕（`removeCustom`），`loadLive` 重抓時不清自訂的估價快取
11. ~~**圖表只有折線，缺少最高/最低價區間陰影**~~ ✅ 已完成（2026-06-11）：後端 `get_detail()` 新增 `history_min` / `history_max`（與 `history` 同結構的各區間每日最高/最低序列，取自 `price_snapshots` 既有的 `min_price` / `max_price`）；前端 `genUsed` 接收真實 min/max（無真實資料時以 `genBand()` 模擬上下浮動帶），`renderChart` 以兩條透明線 + `fill:'-1'` 畫出最高～最低陰影帶、均價線疊於上層，並於圖下新增圖例（均價線／區間帶／全新定價）
12. ~~**行動裝置版面未優化**（detail panel 在小螢幕會溢出）~~ ✅ 已完成（2026-06-11）：根因是 `≤640px` 時 `.detail` 設 `position:fixed; top:52px` 卻**未給高度**，內容會撐破視窗。修正：手機版改 `height:calc(100vh - 52px)` + 內部捲動（`overflow-y:auto`），面板內距/統計數字縮一級；另新增 `≤960px` 平板斷點（detail 380px、sidebar 180px、列表隱藏「筆數/狀態」保留折價幅度）。已用 Preview 在 375/768px 實測：面板不再溢出、可內部捲動、桌機版面不受影響

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
# 執行爬蟲（全部分類；只跑 PTT hardwaresale）
python pc_scraper_backend.py

# 只爬特定分類（命令列指定）
python pc_scraper_backend.py gpu cpu

# 直接開啟前端（無需伺服器；API 未啟動則顯示模擬資料）
open index.html       # macOS
start index.html      # Windows
```

### PTT 每日自動排程（Windows 工作排程器）

PTT `hardwaresale` 是唯一可匿名自動爬的真實來源 → 設成每日自動跑、逐日累積歷史（待辦 #6）。

- 包裝腳本：`crawl_daily.ps1`（設 `PYTHONUTF8=1`、跑 `gpu cpu ram ssd hdd`、輸出到 `logs/crawl_<date>.log`）
- 已註冊工作排程 **`PCPriceTracker_PTTCrawl`**（每日 10:00、登入時執行、錯過補跑）

```powershell
# 立即手動跑一次
powershell -ExecutionPolicy Bypass -File .\crawl_daily.ps1
# 查看 / 改時間 / 移除排程
Get-ScheduledTask -TaskName PCPriceTracker_PTTCrawl
Set-ScheduledTask  -TaskName PCPriceTracker_PTTCrawl -Trigger (New-ScheduledTaskTrigger -Daily -At 9:00am)
Unregister-ScheduledTask -TaskName PCPriceTracker_PTTCrawl -Confirm:$false
```

> 爬蟲與匯入皆呼叫共用的 `rebuild_today_snapshots()`，今日均價會合併**當天所有來源**
> （PTT 自動 ＋ 當天手動匯入的蝦皮）一起算，不會互相覆蓋。

### 前後端串接（API server）

```bash
# （首次/開發）產生示範價格資料，讓前端有東西可顯示
python tools/seed_demo_data.py

# 啟動 API server（預設 http://127.0.0.1:5000）
python api_server.py
# 然後瀏覽器開 http://127.0.0.1:5000  （同源，免 CORS）
# 或直接開 index.html（file://）：前端會連 127.0.0.1:5000 的 API
```

- 端點：`/api/health`、`/api/report`（全部）、`/api/part/<id>`（單一）、`/api/update_catalog`（製造商新品偵測，待辦 #3）、`/api/estimate?q=`（未收錄估價，待辦 #7）
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
| eBay | 匿名爬蟲被反機器人擋（實測 403）→ 走**官方 Browse API**（已實作）。認證用 `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` 以 client_credentials 自動換 token（約 2 小時自動續期）。**限制**：公開 Browse API 只回「在售掛牌價」非成交價（成交須 Marketplace Insights API、限制存取）。USD 以 `EBAY_TWD_RATE`（預設 32）換算台幣入庫、標題附 `[US$原價]`、來源 `eBay` 列 `REFERENCE_SOURCES` 不計入台灣均價。有設金鑰時自動納入每日排程；無金鑰自動略過。**雜訊過濾**：`EBAY_NOISE`（外殼/散熱片/空板等配件 + 整機/準系統/品牌預組/主機板組合/Tower/SFF）＋ `_parse` 價格上限（>台灣新品價 2.5x 視為整機組合排除），避免 eBay 搜尋夾帶的整機（如 HP Z2 Tower）拉高參考價。**前端**：詳情圖表加一條紫色虛線「eBay 海外參考」（`get_detail` 的 `ebay_ref`＝近 30 天 eBay 掛牌去極值均價；eBay 無歷史序列故畫水平線） |

### FB 社團資料（待接入）

FB 公開二手社團內容需登入、且自動爬取違反 FB 服務條款，故**不走自動爬蟲**，改走匯入式：
使用者在自己已登入的瀏覽器整理社團貼文（型號／售價／成色等），存成 CSV 後用匯入器寫入：

```bash
python tools/import_listings.py --csv imports/你的檔.csv
```

CSV 欄位與範例見 `imports/README.md`、`imports/sample_listings.csv`。寫入後統計快照、API、
前端來源分布皆自動沿用；FB 來源逾 90 天資料由 `SOURCE_RETENTION` + `Database.prune_old_listings`
於匯入/爬蟲後自動清除。`FBGroupScraper` 類別保留作為來源定義與保留天數設定。

---

## 公開上線與 SEO

> **🟢 已上線（2026-06-16）**：<https://usedpcpartprice.com>（Cloudflare Pages，自訂網域 + 自動 HTTPS）。
> Google Search Console 已提交 `sitemap.xml`（狀態：成功，探索 1 頁，等收錄）。
> - ✅ 公開匯出：`Reporter.export_public_json()` → 去識別扁平 `report.json`（每日爬蟲與 `tools/export_report.py` 產生）
> - ✅ 前端降級鏈：API → 靜態 `report.json`（`LIVE=false` → 單向查詢精簡）→ 模擬；`DATA_SRC` 標來源
> - ✅ SEO：`<head>` meta/OG/favicon/canonical（皆指向正式網域）、`robots.txt`、`sitemap.xml`、`og.png`（`tools/make_og.py`）
> - ✅ 部署：`deploy.ps1`（重產 report.json→打包 `dist/`→wrangler）、`DEPLOY.md`（步驟）
>
> **維護備忘**
> - **手動更新上線**：`.\deploy.ps1 -BuildOnly` → 把 `dist\` 拖到 Cloudflare（Direct Upload，專案名 `pc-price-tracker`）；
>   或設好金鑰後 `.\deploy.ps1`（CLI）。
> - **每日自動部署**：`crawl_daily.ps1` 末端已接 `deploy.ps1`，只在設了 `CLOUDFLARE_API_TOKEN` 時執行
>   （另需 `CLOUDFLARE_ACCOUNT_ID`、`SITE_DOMAIN`，見 `DEPLOY.md` D 段）。**未設則為手動部署。**
> - **改網域時**要一起改：`robots.txt`、`sitemap.xml`、`index.html` 的 `og:url`/`og:image`/`canonical`/`hreflang`、
>   `tools/make_en.py` 與 `tools/make_sitemap.py` 的 `DOMAIN` → 重新部署 → Search Console 重新提交。
> - **零件深連結（長尾 SEO）**：`?p=<id>`（如 `/?p=gpu_rtx5090`）開啟即展開該零件並換零件專屬
>   title/description/canonical/og（`setPartSeo`/`clearPartSeo`，中英各一套 `partTitle`/`partDesc`）；
>   `selP`/`closeDp` 推 history、`popstate`/`openFromUrl` 支援。`make_sitemap.py` 把有資料的零件
>   都放進 sitemap（附 hreflang）→ Google 可收錄「RTX 5090 二手價格」這類長尾查詢。
> - **重產分享圖**：`python tools/make_og.py`（改文案/配色在該檔）。
>
> **🌐 雙語（2026-06-26）**：前端 i18n（`I18N{zh,en}` + `t()` + `applyLang()`，右上 EN/中文 鈕，記 localStorage）＝
> A 方案（client-side 切換）。**B 方案英文 SEO**：`tools/make_en.py` 於 build 時從 `dist/index.html` 衍生
> `dist/en.html`（英文 head + `window.__FORCE_LANG='en'`，Cloudflare 服務在 `/en`）；`index.html`/`sitemap.xml`
> 已加 hreflang(zh-Hant/en/x-default)。改 UI 字串時兩種語言都要在 `I18N` 補；新增零件規格中文詞需在
> `SPEC_EN`/`TAG_KEY` 補對應（核→-core 等），否則英文模式殘留中文。
> - ⚠️ 公開網址含自訂網域即可；workers.dev 預設網址含帳號代號，勿寫進會提交的檔。

「讓別人在瀏覽器搜尋得到」拆成兩件事：**①上架（公開網址）** 與 **②被搜尋到（SEO）**。

### ① 上架 — 推薦「靜態前端 + 定期匯出 JSON」（免伺服器）

本專案天生適合免伺服器部署：前端是單檔靜態 `index.html`、後端已有 `Reporter.export_json()`、
前端 `loadLive()` 連不到 API 會優雅降級。做法：
- 前端改成抓**靜態 `price_report.json`**（而非 `/api/report`）
- 本機 Windows 排程每天跑完 PTT 爬蟲後，**多一步把 `price_report.json` 推上去**
- 靜態頁即有「每日更新的真實資料」，不必養伺服器

**免費靜態主機**：Cloudflare Pages（推薦，可綁網域+自動 HTTPS）／ GitHub Pages（repo 已在 GitHub，最快）／ Netlify。
> 直接丟 `index.html` 今天就能上線（顯示模擬資料 + 完整目錄）；真實資料只是多「每天推 JSON」一條線。
> 若要即時動態 API 才需 Render / Railway / Fly.io / VPS 跑 Flask —— 對個人研究屬過度工程，不建議。

### ② 被搜尋到 — SEO 待補（皆為小改）
- `<title>`、`<html lang="zh-Hant">`、`<meta name="description">`、Open Graph（og:title/description/image）、favicon
- `robots.txt` + `sitemap.xml`
- 上線後到 **Google Search Console** 提交網址（關鍵步驟，否則不一定被索引）
- 自訂網域（好記、有信任感）

### ⚠️ 上線前必須考量：資料來源的條款/合法風險
- 本專案定位為**個人研究／非商業**；一旦公開且可被搜尋，性質改變。
- **蝦皮、FB 服務條款禁止爬取與轉載**；公開蝦皮成交資料（尤其含賣家標題/賣場連結/地區）風險較高。
- 較安全的公開版做法：**只公開彙總統計**（均價/區間/折價/走勢），**隱去原始 listing 的賣家連結與個資**；
  加**資料來源與免責聲明**；或公開版**只放 PTT**（相對開放），蝦皮/FB 僅本機檢視。

### ③ 公開版功能取捨（靜態站 = 單向查詢）
靜態公開版沒有後端 API，以下兩個依賴後端的互動功能該如何處理（建議用 `LIVE`／API 連線旗標
**自動切換**：本地開發 API 在 → 全功能；公開靜態站 API 不在 → 自動隱藏，不必維護兩份檔）：
- **更新產品庫（`runDb` → `/api/update_catalog`）**：屬**維護端**功能（掃 NVIDIA/AMD 官網新型號給開發者補目錄），
  一般訪客用不到、且靜態站無後端會是死按鈕 → **公開版隱藏**（保留本地維護用）。
- **自訂搜尋／未收錄估價（`searchUnknown`/`addCustom` → `/api/estimate`）**：靜態站只能回退 `estP` 粗估，
  對「研究型行情站」可能反而**誤導**（看起來像真資料的估算）→ 公開版建議**只留目錄搜尋/篩選**，
  未收錄時顯示「尚未收錄」即可；完整自訂追蹤保留本地用。
- 結論：**不刪除、改用 `LIVE` 旗標 gating**——維持單一 HTML、零建置；公開版自動精簡為單向查詢。

---

## 與 Claude 協作建議

- 修改前端時，請**只提供需要修改的函式或 CSS 區塊**，不需貼整個 HTML 檔案
- 指定修改位置時，可說「`renderChart` 函式」或「`.prow` 樣式」等精確位置
- 新增零件**只改前端 `DB`**（`id` 欄位需保留、先填任意暫值，跑同步器會依規則重算）、`cat` 為既有分類之一、`tags` 使用既有標籤；改完執行 `python tools/sync_parts.py` 同步後端
- 討論後端爬蟲修改時，請說明是哪個爬蟲類別（`ShopeeScraper` / `PTTScraper` / `FBGroupScraper`）
