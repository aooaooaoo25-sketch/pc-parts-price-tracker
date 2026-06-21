# 部署到 Cloudflare Pages（靜態站）

本站是單頁靜態網站：前端連不到後端 API 時，會自動改抓同目錄的 `report.json`
（每日更新、已去識別），並切換成「單向查詢」精簡模式（隱藏更新產品庫/自訂搜尋）。

部署＝把 4 個檔上傳到 Cloudflare Pages：`index.html`、`report.json`、`robots.txt`、`sitemap.xml`。
`deploy.ps1` 會自動重產 `report.json` 並打包成 `dist/`。

---

## A. 第一次上線（最簡單：Dashboard 拖拉，免裝任何東西）

1. 本機打包：
   ```powershell
   .\deploy.ps1 -BuildOnly
   ```
   會產生 `dist\` 資料夾。
2. 到 <https://dash.cloudflare.com> → **Workers & Pages** → **Create** → **Pages** →
   **Upload assets**（Direct Upload）。
3. 專案命名（如 `pc-price-tracker`）→ 把 **`dist\` 資料夾**整個拖進去上傳 → Deploy。
4. 拿到網址 `https://<專案名>.pages.dev`，打開就是你的網站。

> 完成後務必回來做 **C. 補網域** 與 **E. Search Console**。

---

## B. 用 CLI 部署（之後要自動化就用這個）

一次性安裝：
1. 裝 **Node.js**（LTS）：<https://nodejs.org>
2. 登入 Cloudflare：
   ```powershell
   npx wrangler login        # 會開瀏覽器授權（一次即可）
   ```
3. 部署（站台是 **Worker（靜態資產）**，名稱/資產目錄定義在 `wrangler.jsonc`）：
   ```powershell
   .\deploy.ps1
   ```
   非互動授權用 D 段的環境變數（不必 `wrangler login`）。之後每次跑這行就會更新。

---

## C. 上線後補網域到 robots/sitemap/OG（重要）

知道網址後（`xxx.pages.dev` 或自訂網域），用 `-Domain` 重新部署，腳本會自動替換
`robots.txt` / `sitemap.xml` 裡的 `REPLACE-WITH-YOUR-DOMAIN`：
```powershell
.\deploy.ps1 -ProjectName pc-price-tracker -Domain pc-price-tracker.pages.dev
```
另外手動補 `index.html` `<head>` 的兩行（目前留成註解）：
```html
<meta property="og:url" content="https://你的網域/">
<meta property="og:image" content="https://你的網域/og.png">   <!-- 選填：1200x630 分享圖 -->
```

### 自訂網域（選填）
Cloudflare Pages 專案 → **Custom domains** → 加入你的網域，自動配 HTTPS。

---

## D. 每日自動更新資料（已接好，只差設環境變數）

`crawl_daily.ps1` **已自動接上部署**：每天爬完後，若偵測到 `CLOUDFLARE_API_TOKEN` 就會
自動跑 `deploy.ps1` 推上線；沒設則略過（不影響爬蟲）。所以你只要做一次性設定：

1. Cloudflare → **My Profile → API Tokens** → 建 Token（範本「**Edit Cloudflare Workers**」；本站是 Worker）
2. 設**系統層級**環境變數（供工作排程讀取）：
   ```powershell
   setx CLOUDFLARE_API_TOKEN  "你的token"
   setx CLOUDFLARE_ACCOUNT_ID "你的account id"   # Cloudflare → Workers & Pages 右側可見
   setx SITE_DOMAIN           "usedpcpartprice.com"
   ```
   （`setx` 設定後需重開終端/重登才生效。）
3. 完成後，每日排程跑完就會自動部署最新資料；手動測試：`.\deploy.ps1`

---

## E. 讓 Google 搜得到（關鍵）

1. <https://search.google.com/search-console> → 新增資源 → 輸入你的網址
2. 驗證擁有權（Cloudflare 可用 DNS TXT 驗證，或上傳 HTML 檔）
3. 提交 **Sitemap**：`https://你的網域/sitemap.xml`
4. 用「網址審查」要求建立索引

> 索引通常數天到數週。沒提交 Search Console 不一定會被收錄。

---

## ⚠️ 上線前再確認一次（見 CLAUDE.md「公開上線」段）
- 公開版只露**彙總統計 + 去識別掛牌**（`report.json` 已移除賣家連結/地區）。
- 蝦皮/FB 條款禁止轉載；如有疑慮，公開版可只放 PTT 來源的資料。
- 建議在頁面加一行**資料來源與免責聲明**。
