# -*- coding: utf-8 -*-
"""輸出公開靜態站用的 report.json（扁平、去識別）——免跑爬蟲，直接由現有 DB 產生。

用途：靜態部署時，前端 API 連不到會改抓同目錄的 report.json。把這支的輸出推上靜態主機即可。
用法：
    python tools/export_report.py            # 寫到專案根目錄 report.json
    python tools/export_report.py out.json    # 自訂路徑
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pc_scraper_backend import Database, Reporter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "report.json")
    db = Database(os.path.join(ROOT, "pc_prices.db"))
    n = Reporter(db).export_public_json(out)
    size = os.path.getsize(out)
    print(f"完成：{n} 項、{size/1024:.1f} KB → {out}")


if __name__ == "__main__":
    main()
