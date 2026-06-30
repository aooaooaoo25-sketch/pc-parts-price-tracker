"""產生 sitemap.xml（首頁 + /en + 每個有資料的零件深連結 ?p=<id>）。

零件深連結（前端 ?p=<id> 會自動展開該零件並換成零件專屬 title/description/canonical）
讓 Google 能收錄長尾查詢（「RTX 5090 二手價格」之類）。從 dist/report.json 取「有資料」
的零件清單，每顆出一條 <url>，附 zh/en hreflang。build 時由 deploy.ps1 呼叫，覆寫 dist/sitemap.xml。

用法：python tools/make_sitemap.py [dist_dir]
"""
import json
import os
import sys

DOMAIN = "https://usedpcpartprice.com"


def _alt(zh: str, en: str) -> str:
    return ('    <xhtml:link rel="alternate" hreflang="zh-Hant" href="%s"/>\n'
            '    <xhtml:link rel="alternate" hreflang="en" href="%s"/>\n'
            '    <xhtml:link rel="alternate" hreflang="x-default" href="%s"/>\n' % (zh, en, zh))


def _url(loc: str, zh: str, en: str, freq: str, pri: str) -> str:
    return ('  <url>\n    <loc>%s</loc>\n%s    <changefreq>%s</changefreq>\n'
            '    <priority>%s</priority>\n  </url>' % (loc, _alt(zh, en), freq, pri))


def build(dist_dir: str) -> None:
    with open(os.path.join(dist_dir, "report.json"), encoding="utf-8") as f:
        rep = json.load(f)
    ids = [k for k in rep if k != "_meta"]

    urls = [
        _url(f"{DOMAIN}/", f"{DOMAIN}/", f"{DOMAIN}/en", "daily", "1.0"),
        _url(f"{DOMAIN}/en", f"{DOMAIN}/", f"{DOMAIN}/en", "daily", "0.9"),
    ]
    for pid in ids:
        zh, en = f"{DOMAIN}/?p={pid}", f"{DOMAIN}/en?p={pid}"
        urls.append(_url(zh, zh, en, "weekly", "0.7"))

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
           '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
           + "\n".join(urls) + "\n</urlset>\n")
    with open(os.path.join(dist_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"[make_sitemap] {len(ids)} 個零件深連結 + 2 主頁 → sitemap.xml")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "dist")
