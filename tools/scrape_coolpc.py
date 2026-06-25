"""原價屋（coolpc）新品報價抓取器（獨立執行）。

抓 evaluate.php 報價單，比對前端 PARTS_DB，將命中型號的『新品價』以 source=原價屋
寫入 pc_prices.db。原價屋列入 REFERENCE_SOURCES（不計二手），供前端「目前全新行情」
當權威來源（優先於蝦皮全新賣文）。匿名可抓、無 captcha → 已納入每日排程，亦可手動跑。

用法：python tools/scrape_coolpc.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pc_scraper_backend import (Database, scrape_coolpc_to_db,
                                rebuild_today_snapshots, rebuild_new_snapshots)


def main() -> None:
    db = Database("pc_prices.db")
    n = scrape_coolpc_to_db(db)
    if n:
        # 原價屋不計二手，但重算今日快照可讓「目前全新行情」的價格天花板即時生效
        rebuild_today_snapshots(db)
        rebuild_new_snapshots(db)   # 累積新品價曲線
    print(f"完成：原價屋新品報價 {n} 筆已更新")


if __name__ == "__main__":
    main()
