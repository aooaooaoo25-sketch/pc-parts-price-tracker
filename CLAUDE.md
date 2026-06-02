# CLAUDE.md — PC 零件二手市場價格追蹤系統

此文件供 Claude Code 在開發本專案時參考。請在每次對話開始前先讀取此文件。

---

## 專案概述

**目標**：追蹤台灣中文圈二手市場（露天、蝦皮、PTT、巴哈姆特）中，消費級 PC 零件的二手成交價格，並與全新定價做差價比較，產生歷史折線圖。

**定位**：個人研究 / 學術用途，非商業產品。請求頻率已加入隨機延遲以避免對平台造成負擔。

---

## 專案結構

```
pc_price_tracker/
├── CLAUDE.md                  # 本文件
├── pc_price_tracker.html      # 前端介面（純靜態，無需伺服器，直接開啟）
├── pc_scraper_backend.py      # 後端爬蟲主程式（Python 非同步）
├── pc_prices.db               # SQLite 資料庫（執行後自動產生）
├── price_report.json          # 匯出報表（執行後自動產生）
├── .env                       # API 金鑰（不得提交至 git）
└── .gitignore                 # 須包含 .env、*.db、price_report.json
```

---

## 技術架構

### 前端（pc_price_tracker.html）

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
| `genUsed(p)` | **【暫時模擬】** 產生二手均價，上線後須替換 |
| `genHist(base)` | **【暫時模擬】** 產生365天歷史數據，上線後須替換 |
| `genLs(p)` | **【暫時模擬】** 產生成交列表，上線後須替換 |

**前端零件資料庫（`DB` 物件）：**

每個零件物件結構如下：
```javascript
{
  id: 'g5090',          // 唯一識別碼，前綴代表分類
  cat: 'gpu',           // 分類：cpu / gpu / ram / mb / ssd / hdd / psu / cooler
  name: 'GeForce RTX 5090',
  spec: '21760 CUDA・32GB GDDR7・575W・PCIe5.0・Blackwell・2025',
  new_price: 89900,     // 全新建議售價 TWD，停售品填 0
  tags: ['NEW','2025','旗艦'],  // 可用標籤：NEW / 熱門 / 旗艦 / CP值 / 高頻 / 頂級 / 年份
}
```

目前各分類品項數量（前端 DB）：
- CPU：37 項（Intel Arrow Lake / Raptor Lake / Alder Lake、AMD Ryzen 9000 / 7000 / 5000）
- GPU：42 項（RTX 50/40/30、RX 9000/7000/6000、Arc Battlemage/Alchemist）
- RAM：14 項（DDR5 / DDR4）
- 主機板：20 項（Z890 / Z790 / B760 / X870E / X670E / B650）
- SSD：16 項（PCIe5 / PCIe4 / SATA）
- HDD：10 項
- 電源：12 項
- 散熱：14 項

---

### 後端（pc_scraper_backend.py）

- **Python 3.11+**，使用 `asyncio` + `aiohttp` 非同步爬蟲
- **資料庫**：SQLite（`pc_prices.db`），三張資料表：`listings`、`price_snapshots`、`crawl_log`
- **爬蟲來源**（四個，繼承自 `BaseScraper`）：

| 類別 | 平台 | 方法 |
|------|------|------|
| `LuTianScraper` | 露天拍賣 | BeautifulSoup HTML 解析 |
| `ShopeeScraper` | 蝦皮購物 | 搜尋 API（JSON） |
| `PTTScraper` | PTT BuyTrade / PC_Shopping | HTML + Regex 解析 |
| `BahaScraper` | 巴哈姆特二手板 | BeautifulSoup HTML 解析 |

**後端零件資料庫（`PARTS_DB`）：** 巢狀 dict，結構為 `{分類: {子分類: [零件列表]}}`，與前端 `DB` 是**各自獨立**的兩份資料，目前**尚未同步**（這是一個待解決的技術債）。

---

## 已知問題與待辦事項

### 🔴 高優先（核心功能缺失）

1. **前後端資料未串接**：前端目前全用模擬數據（`genUsed` / `genHist`），未真正呼叫後端 API，需實作 REST API 或 JSON 檔案讀取橋接層
2. **前後端零件 ID 不一致**：前端用 `g5090`，後端用 `gpu_4090`，兩者命名規則不同，需統一
3. **後端缺少製造商官網爬蟲**：`runDb()` 按鈕在前端有 Modal 動畫，但後端無對應的製造商產品庫更新邏輯
4. **爬蟲選擇器未驗證**：`LuTianScraper` 與 `BahaScraper` 的 CSS 選擇器（如 `.item-panel`、`.b-list__row`）尚未實際驗證是否符合平台目前 DOM 結構

### 🟡 中優先（功能完善）

5. **缺少 Flask/FastAPI 後端伺服器**：目前後端只能直接執行輸出 JSON，前端無法即時取得資料，需加一層 API server
6. **價格歷史資料為空**：`price_snapshots` 資料表在首次執行前無資料，折線圖需要累積數天才有意義
7. **搜尋未收錄零件的行情估算過於粗糙**：`estP()` 函式用關鍵字硬比對估價，應改為呼叫後端實際爬蟲
8. **`Reporter.export_json()` 與前端 DB 結構不匹配**：後端 JSON 鍵名與前端讀取方式不同

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

# 直接開啟前端（無需伺服器）
open pc_price_tracker.html       # macOS
start pc_price_tracker.html      # Windows
```

---

## 爬蟲平台說明

| 平台 | 注意事項 |
|------|----------|
| 露天拍賣 | CSS 選擇器需定期驗證；分類 ID `catg=11` 為電腦零組件 |
| 蝦皮購物 | 使用非公開搜尋 API，需帶正確 Referer；價格單位為分×1000 |
| PTT BuyTrade | 需帶 cookie `over18=1`；以 Regex 從文章內容解析售價 |
| 巴哈姆特 | 板號 `C_115` 為二手交易板；需進入文章頁面才能取得價格 |

---

## 與 Claude 協作建議

- 修改前端時，請**只提供需要修改的函式或 CSS 區塊**，不需貼整個 HTML 檔案
- 指定修改位置時，可說「`renderChart` 函式」或「`.prow` 樣式」等精確位置
- 新增零件到前端 DB 時，請確認 `id` 唯一、`cat` 為既有分類之一、`tags` 使用既有標籤
- 討論後端爬蟲修改時，請說明是哪個爬蟲類別（`LuTianScraper` / `ShopeeScraper` 等）
