# -*- coding: utf-8 -*-
"""通用成交資料匯入器（待辦 #1 後續：蝦皮 / FB 改走匯入式）。

由於蝦皮、FB 等資料豐富的平台需登入且禁止匿名爬取，改以「使用者在自己已登入的
瀏覽器取得資料 → 匯入」的半自動方式。本工具把匯入檔寫入 pc_prices.db 的 listings，
之後統計快照、API、前端皆自動沿用；並依 SOURCE_RETENTION 清除逾期資料。

用法
----
1) 通用 CSV（任何來源，含 FB）：
     python tools/import_listings.py --csv imports/sample_listings.csv
   CSV 欄位（標頭）：part_id, source, title, price, condition, location, date, url, sold
   必填：part_id（須為現有零件 id）、source、price；其餘可留空。

2) 蝦皮 search_items 存檔 JSON（登入蝦皮後於瀏覽器開該 API 連結另存）：
     python tools/import_listings.py --shopee imports/shopee_rtx5090.json --part gpu_rtx5090
"""
import os
import sys
import csv
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pc_scraper_backend import (Database, Listing, PriceSnapshot, PARTS_DB,
                                REFERENCE_SOURCES, prune_by_retention,
                                parse_shopee_items)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "pc_prices.db")

PART_BY_ID = {p["id"]: p for cat in PARTS_DB.values()
              for sub in cat.values() for p in sub}


def _valid_price(v) -> bool:
    try:
        return 500 <= int(v) <= 200000
    except (TypeError, ValueError):
        return False


def import_csv(db: Database, path: str) -> int:
    n = 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pid = (row.get("part_id") or "").strip()
            if pid not in PART_BY_ID:
                print(f"  跳過：未知 part_id「{pid}」（title={row.get('title','')[:30]}）")
                continue
            if not _valid_price(row.get("price")):
                print(f"  跳過：價格不合法 {row.get('price')}（{pid}）")
                continue
            db.save_listing(Listing(
                source    = (row.get("source") or "匯入").strip(),
                part_id   = pid,
                title     = (row.get("title") or "").strip(),
                price     = int(row["price"]),
                condition = (row.get("condition") or "成色不明").strip(),
                url       = (row.get("url") or "").strip(),
                location  = (row.get("location") or "").strip(),
                date      = (row.get("date") or datetime.now().strftime("%Y-%m-%d")).strip(),
                sold      = str(row.get("sold", "")).strip().lower() in ("1", "true", "yes", "已售"),
            ))
            n += 1
    return n


def import_shopee_json(db: Database, path: str, part_id: str) -> int:
    if part_id not in PART_BY_ID:
        raise SystemExit(f"--part 須為現有零件 id；「{part_id}」不存在")
    data = json.load(open(path, encoding="utf-8"))
    listings = parse_shopee_items(data, PART_BY_ID[part_id])
    for l in listings:
        db.save_listing(l)
    return len(listings)


def rebuild_today_snapshots(db: Database) -> int:
    """依今日成交資料重算各零件的均價快照（排除海外參考價來源，如 eBay），
    讓 get_detail 的二手均價反映剛匯入的真實資料。"""
    today = datetime.now().strftime("%Y-%m-%d")
    ref = list(REFERENCE_SOURCES)
    ph = ",".join("?" * len(ref)) if ref else "''"
    rows = db.conn.execute(
        f"SELECT part_id, AVG(price), MIN(price), MAX(price), COUNT(*), "
        f"GROUP_CONCAT(DISTINCT source) FROM listings "
        f"WHERE date>=? AND source NOT IN ({ph}) GROUP BY part_id",
        [today] + ref
    ).fetchall()
    for pid, avg, mn, mx, cnt, srcs in rows:
        db.save_snapshot(PriceSnapshot(
            part_id=pid, date=today, avg_price=int(round(avg)),
            min_price=int(mn), max_price=int(mx), listing_count=cnt,
            sources=(srcs or "").split(",")))
    return len(rows)


def main():
    ap = argparse.ArgumentParser(description="成交資料匯入器")
    ap.add_argument("--csv", help="通用 CSV 檔路徑")
    ap.add_argument("--shopee", help="蝦皮 search_items 存檔 JSON 路徑")
    ap.add_argument("--part", help="--shopee 時指定對應零件 id")
    args = ap.parse_args()

    if not args.csv and not args.shopee:
        ap.error("請指定 --csv 或 --shopee")

    db = Database(DB_PATH)
    total = 0
    if args.csv:
        total += import_csv(db, args.csv)
    if args.shopee:
        if not args.part:
            ap.error("--shopee 需搭配 --part <part_id>")
        total += import_shopee_json(db, args.shopee, args.part)

    # 套用保留策略（各來源預設 365 天，FB 90 天）
    prune_by_retention(db)

    snaps = rebuild_today_snapshots(db)
    db.conn.close()
    print(f"匯入完成：寫入 {total} 筆成交資料、重算 {snaps} 個零件今日均價 → {DB_PATH}")


if __name__ == "__main__":
    main()
