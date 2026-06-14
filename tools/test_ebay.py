# -*- coding: utf-8 -*-
"""快速驗證 eBay Browse API：換取 OAuth token + 抓兩顆型號，印出筆數與樣本。

用法：先把 EBAY_CLIENT_ID / EBAY_CLIENT_SECRET 填進 .env，再執行：
    python tools/test_ebay.py
（本腳本不寫入資料庫，只做連線/解析驗證。）
"""
import os
import sys
import asyncio
import aiohttp

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pc_scraper_backend import EbayScraper

# 用幾顆國際市場常見、好查的型號測試
TEST_PARTS = [
    {"id": "gpu_rtx4090", "name": "GeForce RTX 4090", "aliases": ["RTX 4090", "4090"]},
    {"id": "cpu_r7_5800x3d", "name": "Ryzen 7 5800X3D", "aliases": ["Ryzen 7 5800X3D", "5800X3D"]},
]


async def main():
    async with aiohttp.ClientSession() as session:
        ebay = EbayScraper(session, None)   # 不需 DB（只驗證查詢/解析）
        if not ebay.enabled:
            print("✗ 未讀到金鑰：請確認 .env（不是 .env.example）內的 "
                  "EBAY_CLIENT_ID / EBAY_CLIENT_SECRET 已填。")
            return
        print(f"金鑰已載入，marketplace={ebay.marketplace}，匯率={ebay.rate}")

        token = await ebay._get_token()
        if not token:
            print("✗ 換取 OAuth token 失敗（見上方錯誤）。常見原因：\n"
                  "   - Production keyset 尚未啟用（需先送出 Marketplace Account Deletion 豁免）\n"
                  "   - Client ID/Secret 貼錯或多了空格")
            return
        print(f"✓ token OK（長度 {len(token)}）\n")

        for p in TEST_PARTS:
            rows = await ebay.scrape_part(p)
            print(f"[{p['name']}] 回傳 {len(rows)} 筆")
            for l in rows[:3]:
                print(f"   NT${l.price:>7}  {l.condition:<12} {l.title[:60]}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
