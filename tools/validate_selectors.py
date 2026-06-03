# -*- coding: utf-8 -*-
"""驗證露天 / 巴哈爬蟲的 CSS 選擇器是否符合現行 DOM（待辦 #4）。
僅作少量請求並加延遲；純檢查、不寫入資料庫。
  python tools/validate_selectors.py
"""
import time
import json
import random
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"}


def get(url, headers=None, timeout=15):
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def sel_count(soup, sel):
    try:
        return len(soup.select(sel))
    except Exception as e:
        return f"ERR {e}"


def section(t):
    print("\n" + "=" * 60 + f"\n{t}\n" + "=" * 60)


def check_ruten():
    section("露天拍賣 LuTianScraper")
    q = "RTX 5090"
    url = f"https://www.ruten.com.tw/find/?q={urllib.parse.quote(q)}&sort=prc%2Fasc&catg=11"
    print("search URL:", url)
    st, html = get(url)
    print("HTTP", st, "len", len(html))
    soup = BeautifulSoup(html, "html.parser")
    print("\n[現行程式碼的選擇器命中數]")
    for sel in [".item-panel", ".rt-grid-item", "[data-item-id]",
                ".item-title", ".rt-item-title", ".price", ".rt-price", ".item-price"]:
        print(f"  {sel:18} -> {sel_count(soup, sel)}")
    # 是否為 SPA（資料由 JS/API 載入）
    spa = any(k in html for k in ["window.__INITIAL", "rt-search", "id=\"app\"", "rapi.ruten", "/api/search"])
    print("\nSPA 跡象（可能走 API）：", spa)
    print("頁面內含 'rapi.ruten'：", "rapi.ruten" in html)

    # 測試露天官方搜尋 API
    section("露天官方搜尋 API (rapi)")
    api = ("https://rapi.ruten.com.tw/api/search/v3/index.php/core/prod"
           f"?q={urllib.parse.quote(q)}&type=direct&sort=prc/asc&offset=1&limit=5")
    print("api URL:", api)
    try:
        st, body = get(api, headers={"Referer": "https://www.ruten.com.tw/"})
        print("HTTP", st, "len", len(body))
        data = json.loads(body)
        print("JSON keys:", list(data.keys())[:8])
        rows = data.get("Rows") or data.get("rows") or []
        print("Rows 數:", len(rows), " 範例:", rows[0] if rows else None)
        if rows and ("Id" in rows[0] or "ProdId" in rows[0]):
            pid = rows[0].get("Id") or rows[0].get("ProdId")
            di = ("https://rapi.ruten.com.tw/api/prod/v2/index.php/prod"
                  f"?id={pid}")
            st2, body2 = get(di, headers={"Referer": "https://www.ruten.com.tw/"})
            d2 = json.loads(body2)
            sample = (d2.get("data") or [d2])[0] if isinstance(d2.get("data"), list) else d2
            print("商品明細欄位範例:", {k: sample.get(k) for k in list(sample)[:8]} if isinstance(sample, dict) else sample)
    except Exception as e:
        print("API ERR:", type(e).__name__, e)


def check_baha():
    section("巴哈姆特 BahaScraper")
    for bsn, note in [("C_115", "現行程式碼值"), ("60404", "二手交易（疑似正確 bsn）")]:
        kw = "RTX 5090"
        url = f"https://forum.gamer.com.tw/B.php?bsn={bsn}&q={urllib.parse.quote(kw)}&search=content"
        print(f"\n[bsn={bsn} {note}] {url}")
        try:
            st, html = get(url)
            print("  HTTP", st, "len", len(html))
            soup = BeautifulSoup(html, "html.parser")
            for sel in [".b-list__row", ".b-forum__title", "tr.b-list__row",
                        "a[href*='C.php']", ".b-list__main"]:
                print(f"    {sel:22} -> {sel_count(soup, sel)}")
            # 標題列上層常見容器
            print("    table.b-list count ->", sel_count(soup, "table.b-list"))
        except Exception as e:
            print("  ERR", type(e).__name__, e)
        time.sleep(random.uniform(1.5, 3.0))


if __name__ == "__main__":
    check_ruten()
    time.sleep(random.uniform(1.5, 3.0))
    check_baha()
    print("\n完成。")
