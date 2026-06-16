# PC 零件二手行情追蹤

> 追蹤台灣中文圈二手市場（PTT、蝦皮等）消費級 PC 零件的二手成交行情，與全新定價、eBay 海外參考價對比，並繪製歷史價格走勢。

**🟢 線上版：<https://usedpcpartprice.com>**

個人研究／非商業用途。價格為公開掛牌／貼文之彙整估算，非保證成交價，亦不構成交易或投資建議。

---

## 功能
- **五大分類**：GPU / CPU / RAM / SSD / HDD，共 111 項目錄
- **二手均價 + 區間 + 歷史走勢**（Chart.js），對比**全新定價**與 **eBay 海外在售參考**
- **去極值統計**（IQR）抵抗整機/配件等離群價；多來源雜訊過濾
- 桌機/平板/手機 RWD；深色主題

## 架構
- **前端**：單一靜態 `index.html`（無框架、無建置），Chart.js 由 CDN 載入
- **後端**：Python `asyncio` 爬蟲（`pc_scraper_backend.py`）→ SQLite（`pc_prices.db`）
- **API**：Flask（`api_server.py`）做本地前後端橋接
- **降級鏈**：前端連不到 API → 改抓靜態 `report.json`（去識別）→ 模擬；公開靜態站自動精簡為單向查詢

## 資料來源
| 來源 | 方式 | 狀態 |
|------|------|------|
| PTT `hardwaresale` | 匿名 HTML 解析 | ✅ 每日排程自動爬 |
| 蝦皮購物 | 登入瀏覽器擷取 → 匯入 | 🔶 半手動（反爬蟲節流） |
| FB 公開二手社團 | 匯入式（需登入） | 🔶 保留 90 天 |
| eBay | 官方 Browse API | ✅ 海外在售參考價（USD→TWD、不計台灣均價） |

## 本地執行
```bash
pip install -r requirements.txt

# 跑爬蟲（只跑 PTT；可指定分類）
python pc_scraper_backend.py            # 全部
python pc_scraper_backend.py gpu cpu    # 指定分類

# 啟動本地 API + 前端（http://127.0.0.1:5000）
python api_server.py
```
直接開 `index.html` 亦可（無 API 時顯示模擬資料或靜態 `report.json`）。

## 開發備註
- 前端 `DB` 是**唯一主目錄**；改完跑 `python tools/sync_parts.py` 重建後端 `PARTS_DB`（git pre-commit hook 會把關一致性）。
- 金鑰（eBay / Anthropic）放 `.env`（已被 `.gitignore` 忽略）。
- 部署到 Cloudflare Pages 見 **[DEPLOY.md](DEPLOY.md)**；開發脈絡與待辦見 **[CLAUDE.md](CLAUDE.md)**。
