"""一次性遷移：用「二手分流」邏輯（#2）重算所有仍有原始 listings 的 (part_id, date) 快照。

背景：先前快照把「全新」賣文也算進二手均價，當代卡 / 記憶體因 AI 需求多為全新現貨，
會把二手均價墊高。本工具掃 listings 表中每個 (零件, 日期) 仍存在原始資料者，排除海外
參考源（eBay）與明確全新賣文後，以 robust_price_stats 重算並覆寫該日快照。

- 只覆寫「仍有 listings 的日期」；listings 已逾保留期被清掉的舊日期，其既有快照原樣保留。
- 某 (零件,日期) 排除全新後若無二手 → 刪除該日快照（當天只有全新、無二手成交）。

用法：python tools/rebuild_snapshots.py [--dry-run]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pc_scraper_backend import (
    Database, PriceSnapshot, REFERENCE_SOURCES,
    robust_price_stats, split_used_new, title_is_new,
)


def main(dry_run: bool = False) -> None:
    db = Database("pc_prices.db")
    ref = list(REFERENCE_SOURCES)
    ph = ",".join("?" * len(ref)) if ref else "''"

    rows = db.conn.execute(
        f"SELECT part_id, date, title, price, source FROM listings "
        f"WHERE source NOT IN ({ph})", ref
    ).fetchall()

    # 以 (part_id, date) 聚合
    by_key = {}
    for pid, date, title, price, src in rows:
        d = by_key.setdefault((pid, date), {"rows": [], "sources": set()})
        d["rows"].append((title, price, src))

    rewritten = deleted = skipped = 0
    for (pid, date), d in by_key.items():
        used, new = split_used_new([(t, p) for (t, p, s) in d["rows"]])
        if not used:
            # 當天只有全新賣文 → 刪掉該日（被新品污染的）二手快照
            if not dry_run:
                db.conn.execute(
                    "DELETE FROM price_snapshots WHERE part_id=? AND date=?", (pid, date))
            deleted += 1
            continue
        if new and len(used) < 2:
            # 有全新被排除、但剩下的二手樣本太少(僅 1 筆) → 重算會變單點噪聲，
            # 保守起見保留原快照（既有混合值），不退化成單筆。
            skipped += 1
            continue
        used_srcs = sorted({s for (t, p, s) in d["rows"] if not title_is_new(t or "")})
        avg, mn, mx, _u = robust_price_stats(used)
        if not dry_run:
            db.save_snapshot(PriceSnapshot(
                part_id=pid, date=date, avg_price=avg,
                min_price=mn, max_price=mx, listing_count=len(used),
                sources=used_srcs))
        rewritten += 1

    if not dry_run:
        db.conn.commit()
    tag = "[dry-run] " if dry_run else ""
    print(f"{tag}重算二手快照：覆寫 {rewritten} 筆、刪除（全新-only）{deleted} 筆、"
          f"保留（二手樣本不足）{skipped} 筆，涵蓋 {len(by_key)} 個 (零件,日期)")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
