# -*- coding: utf-8 -*-
"""產生「示範用」二手價格資料寫入 pc_prices.db（待辦 #1 驗證用）。

⚠️ 這不是真實爬蟲資料，僅供開發/展示，讓前端串接 API 後有東西可顯示。
真實資料請執行 pc_scraper_backend.py。每次執行會先清空再重建（冪等）。

  python tools/seed_demo_data.py            # 預設 180 天歷史
  python tools/seed_demo_data.py --days 365
"""
import os
import sys
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pc_scraper_backend import Database, Listing, PriceSnapshot, PARTS_DB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "pc_prices.db")

SOURCES = ["露天拍賣", "蝦皮購物", "PTT BuyTrade", "巴哈姆特"]
CONDITIONS = ["九成新", "八成新", "盒裝完整", "無盒", "公司貨", "水貨九成新"]
LOCATIONS = ["台北板橋", "高雄左營", "台中西屯", "新北中和", "桃園八德", "台南永康", "基隆信義"]


def all_parts():
    for cat in PARTS_DB.values():
        for sub in cat.values():
            for p in sub:
                yield p


def seed(days: int):
    db = Database(DB_PATH)
    db.conn.execute("DELETE FROM price_snapshots")
    db.conn.execute("DELETE FROM listings")
    db.conn.commit()

    today = datetime.now()
    n_parts = n_snaps = n_list = 0

    for part in all_parts():
        pid, name, new_price = part["id"], part["name"], part["new_price"]
        rng = random.Random(pid)              # 以 id 為種子 → 可重現
        base = new_price if new_price > 500 else 8000
        used = base * rng.uniform(0.55, 0.78)  # 二手基準

        # 歷史快照：溫和隨機漫步
        cur = used * rng.uniform(0.95, 1.05)
        for d in range(days, -1, -1):
            cur += (rng.random() - 0.5) * base * 0.012
            cur = max(base * 0.3, min(base * 0.92, cur))
            avg = round(cur)
            spread = round(avg * rng.uniform(0.04, 0.10))
            date = (today - timedelta(days=d)).strftime("%Y-%m-%d")
            db.save_snapshot(PriceSnapshot(
                part_id=pid, date=date, avg_price=avg,
                min_price=avg - spread, max_price=avg + spread,
                listing_count=rng.randint(3, 18),
                sources=rng.sample(SOURCES, rng.randint(2, 4)),
            ))
            n_snaps += 1

        # 近 3 天成交明細
        for i in range(rng.randint(6, 12)):
            src = rng.choice(SOURCES)
            cond = rng.choice(CONDITIONS)
            loc = rng.choice(LOCATIONS)
            price = round(used * rng.uniform(0.88, 1.16))
            ago = rng.randint(0, 2)
            db.save_listing(Listing(
                source=src, part_id=pid,
                title=f"{name} {cond} {loc}",
                price=price, condition=cond,
                url=f"demo://{pid}/{i}", location=loc,
                date=(today - timedelta(days=ago)).strftime("%Y-%m-%d"),
                sold=False,
            ))
            n_list += 1
        n_parts += 1

    db.conn.close()
    print(f"示範資料完成：{n_parts} 零件、{n_snaps} 筆歷史快照、{n_list} 筆成交明細 → {DB_PATH}")


if __name__ == "__main__":
    days = 180
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    seed(days)
