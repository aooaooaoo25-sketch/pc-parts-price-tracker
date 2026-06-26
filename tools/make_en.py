"""產生英文 SEO 頁 dist/en.html（從 dist/index.html 衍生，單一來源、build 時生成）。

A 方案的語言切換是前端 client-side（爬蟲看不到）；B 方案再加一個獨立英文網址 /en，
讓 Google 能把英文版當**獨立頁面收錄**。本檔把 index.html 的 <head> SEO 換成英文、
設 lang=en、注入 window.__FORCE_LANG='en'（讓首次載入即英文，含無 localStorage 的爬蟲），
canonical/og:url 指向 /en。hreflang 連結在 index.html 已雙向標好，en.html 沿用即可。

Cloudflare Workers 靜態資產預設會把 en.html 服務在 /en（去 .html）。
deploy.ps1 在打包 dist/ 後呼叫本檔。用法：python tools/make_en.py [dist_dir]
"""
import re
import sys
import os

DOMAIN = "https://usedpcpartprice.com"
EN_TITLE = "Taiwan Used PC Parts Tracker | GPU/CPU/SSD used-price trends"
EN_DESC = ("Track used-market prices (PTT, Shopee, etc.) for GPUs, CPUs, RAM, SSDs and HDDs "
           "in Taiwan, vs launch price and eBay overseas reference, with historical price-trend charts.")
EN_OG_DESC = ("Taiwan used PC parts prices: averages, discount %, history trends, "
              "vs launch price and eBay overseas reference.")
EN_SITE = "Taiwan Used PC Parts Tracker"


def build(dist_dir: str) -> None:
    src = os.path.join(dist_dir, "index.html")
    with open(src, encoding="utf-8") as f:
        h = f.read()

    # 注入語言強制旗標（須在主 <script> 執行前）→ 放 <head> 開頭
    h = h.replace("<head>", "<head>\n<script>window.__FORCE_LANG='en';</script>", 1)
    # lang 屬性
    h = h.replace('<html lang="zh-TW">', '<html lang="en">', 1)
    # 標題 / 描述
    h = re.sub(r"<title>.*?</title>", f"<title>{EN_TITLE}</title>", h, count=1, flags=re.S)
    h = re.sub(r'(<meta name="description" content=")[^"]*(">)', rf'\1{EN_DESC}\2', h, count=1)
    # Open Graph
    h = h.replace('content="zh_TW"', 'content="en_US"', 1)
    h = re.sub(r'(<meta property="og:site_name" content=")[^"]*(">)', rf'\1{EN_SITE}\2', h, count=1)
    h = re.sub(r'(<meta property="og:title" content=")[^"]*(">)', rf'\1{EN_TITLE}\2', h, count=1)
    h = re.sub(r'(<meta property="og:description" content=")[^"]*(">)', rf'\1{EN_OG_DESC}\2', h, count=1)
    # canonical / og:url 指向 /en
    h = h.replace(f'<link rel="canonical" href="{DOMAIN}/">',
                  f'<link rel="canonical" href="{DOMAIN}/en">', 1)
    h = h.replace(f'<meta property="og:url" content="{DOMAIN}/">',
                  f'<meta property="og:url" content="{DOMAIN}/en">', 1)

    out = os.path.join(dist_dir, "en.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(h)
    print(f"[make_en] 產生英文頁 {out}（{len(h)//1024} KB）")


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "dist"
    build(d)
