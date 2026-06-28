"""
PC 零件二手市場價格爬蟲後端系統
資料來源：蝦皮購物（API）、PTT BuyTrade/電腦版；FB 公開二手社團（架構預留，需匯入）
"""

import asyncio
import aiohttp
import os
import sys
import json
import re
import time
import random
import sqlite3
import hashlib
import statistics
import base64
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import Optional
from pathlib import Path
from urllib.parse import quote, urljoin
import urllib.request
from bs4 import BeautifulSoup

# 載入 .env（若有安裝 python-dotenv）：讓 EBAY_CLIENT_ID 等金鑰可從 .env 讀取
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ─────────────────────────────────────────────────
# 資料結構
# ─────────────────────────────────────────────────

@dataclass
class Listing:
    source: str          # 來源平台
    part_id: str         # 對應零件ID
    title: str           # 商品標題
    price: int           # 價格 (TWD)
    condition: str       # 成色 (九成新/八成新/全新...)
    url: str             # 商品網址
    location: str        # 賣家地區
    date: str            # 上架日期
    sold: bool           # 是否已售出
    raw_text: str = ""   # 原始文字

@dataclass
class PriceSnapshot:
    part_id: str
    date: str            # YYYY-MM-DD
    avg_price: int
    min_price: int
    max_price: int
    listing_count: int
    sources: list = field(default_factory=list)


# ─────────────────────────────────────────────────
# 零件資料庫（完整版）
# ─────────────────────────────────────────────────

PARTS_DB = {
    # ── CPU ──
    "cpu": {
        "intel_ultra": [
            {"id": "cpu_ultra9_285k", "name": "Core Ultra 9 285K", "aliases": ["Ultra 9 285K", "285K"], "new_price": 17500},
            {"id": "cpu_ultra7_265k", "name": "Core Ultra 7 265K", "aliases": ["Ultra 7 265K", "265K"], "new_price": 12900},
            {"id": "cpu_ultra5_245k", "name": "Core Ultra 5 245K", "aliases": ["Ultra 5 245K", "245K"], "new_price": 9500},
            {"id": "cpu_ultra5_235", "name": "Core Ultra 5 235", "aliases": ["Ultra 5 235", "235"], "new_price": 8200},
        ],
        "intel_14": [
            {"id": "cpu_i9_14900k", "name": "Core i9-14900K", "aliases": ["i9-14900K", "14900K"], "new_price": 15900},
            {"id": "cpu_i9_14900kf", "name": "Core i9-14900KF", "aliases": ["i9-14900KF", "14900KF"], "new_price": 14900},
            {"id": "cpu_i7_14700k", "name": "Core i7-14700K", "aliases": ["i7-14700K", "14700K"], "new_price": 11900},
            {"id": "cpu_i7_14700kf", "name": "Core i7-14700KF", "aliases": ["i7-14700KF", "14700KF"], "new_price": 11000},
            {"id": "cpu_i5_14600k", "name": "Core i5-14600K", "aliases": ["i5-14600K", "14600K"], "new_price": 8500},
            {"id": "cpu_i5_14600kf", "name": "Core i5-14600KF", "aliases": ["i5-14600KF", "14600KF"], "new_price": 7900},
            {"id": "cpu_i5_14400f", "name": "Core i5-14400F", "aliases": ["i5-14400F", "14400F"], "new_price": 5800},
        ],
        "intel_13": [
            {"id": "cpu_i9_13900k", "name": "Core i9-13900K", "aliases": ["i9-13900K", "13900K"], "new_price": 14200},
            {"id": "cpu_i7_13700k", "name": "Core i7-13700K", "aliases": ["i7-13700K", "13700K"], "new_price": 10800},
            {"id": "cpu_i5_13600k", "name": "Core i5-13600K", "aliases": ["i5-13600K", "13600K"], "new_price": 7800},
            {"id": "cpu_i5_13400f", "name": "Core i5-13400F", "aliases": ["i5-13400F", "13400F"], "new_price": 4800},
        ],
        "intel_12": [
            {"id": "cpu_i9_12900k", "name": "Core i9-12900K", "aliases": ["i9-12900K", "12900K"], "new_price": 18700},
            {"id": "cpu_i7_12700k", "name": "Core i7-12700K", "aliases": ["i7-12700K", "12700K"], "new_price": 13200},
            {"id": "cpu_i5_12600k", "name": "Core i5-12600K", "aliases": ["i5-12600K", "12600K"], "new_price": 9700},
            {"id": "cpu_i5_12400f", "name": "Core i5-12400F", "aliases": ["i5-12400F", "12400F"], "new_price": 4490},
        ],
        "amd_9000": [
            {"id": "cpu_r9_9950x", "name": "Ryzen 9 9950X", "aliases": ["Ryzen 9 9950X", "9950X"], "new_price": 20500},
            {"id": "cpu_r9_9900x", "name": "Ryzen 9 9900X", "aliases": ["Ryzen 9 9900X", "9900X"], "new_price": 15500},
            {"id": "cpu_r7_9700x", "name": "Ryzen 7 9700X", "aliases": ["Ryzen 7 9700X", "9700X"], "new_price": 11500},
            {"id": "cpu_r5_9600x", "name": "Ryzen 5 9600X", "aliases": ["Ryzen 5 9600X", "9600X"], "new_price": 8500},
        ],
        "amd_7000": [
            {"id": "cpu_r9_7950x3d", "name": "Ryzen 9 7950X3D", "aliases": ["Ryzen 9 7950X3D", "7950X3D"], "new_price": 22500},
            {"id": "cpu_r9_7950x", "name": "Ryzen 9 7950X", "aliases": ["Ryzen 9 7950X", "7950X"], "new_price": 18500},
            {"id": "cpu_r9_7900x3d", "name": "Ryzen 9 7900X3D", "aliases": ["Ryzen 9 7900X3D", "7900X3D"], "new_price": 16500},
            {"id": "cpu_r9_7900x", "name": "Ryzen 9 7900X", "aliases": ["Ryzen 9 7900X", "7900X"], "new_price": 13500},
            {"id": "cpu_r7_7700x3d", "name": "Ryzen 7 7700X3D", "aliases": ["Ryzen 7 7700X3D", "7700X3D"], "new_price": 11800},
            {"id": "cpu_r7_7700x", "name": "Ryzen 7 7700X", "aliases": ["Ryzen 7 7700X", "7700X"], "new_price": 8900},
            {"id": "cpu_r5_7600x", "name": "Ryzen 5 7600X", "aliases": ["Ryzen 5 7600X", "7600X"], "new_price": 6500},
            {"id": "cpu_r5_7600", "name": "Ryzen 5 7600", "aliases": ["Ryzen 5 7600", "7600"], "new_price": 5800},
        ],
        "amd_5000": [
            {"id": "cpu_r9_5950x", "name": "Ryzen 9 5950X", "aliases": ["Ryzen 9 5950X", "5950X"], "new_price": 25470},
            {"id": "cpu_r9_5900x", "name": "Ryzen 9 5900X", "aliases": ["Ryzen 9 5900X", "5900X"], "new_price": 17470},
            {"id": "cpu_r7_5800x3d", "name": "Ryzen 7 5800X3D", "aliases": ["Ryzen 7 5800X3D", "5800X3D"], "new_price": 10900},
            {"id": "cpu_r7_5800x", "name": "Ryzen 7 5800X", "aliases": ["Ryzen 7 5800X", "5800X"], "new_price": 14470},
            {"id": "cpu_r7_5700x", "name": "Ryzen 7 5700X", "aliases": ["Ryzen 7 5700X", "5700X"], "new_price": 5500},
            {"id": "cpu_r5_5600x", "name": "Ryzen 5 5600X", "aliases": ["Ryzen 5 5600X", "5600X"], "new_price": 4800},
            {"id": "cpu_r5_5600", "name": "Ryzen 5 5600", "aliases": ["Ryzen 5 5600", "5600"], "new_price": 3800},
        ],
    },
    # ── GPU ──
    "gpu": {
        "nvidia_50": [
            {"id": "gpu_rtx5090", "name": "GeForce RTX 5090", "aliases": ["RTX 5090", "5090"], "new_price": 89900},
            {"id": "gpu_rtx5080", "name": "GeForce RTX 5080", "aliases": ["RTX 5080", "5080"], "new_price": 49900},
            {"id": "gpu_rtx5070ti", "name": "GeForce RTX 5070 Ti", "aliases": ["RTX 5070 Ti", "5070 Ti"], "new_price": 35900},
            {"id": "gpu_rtx5070", "name": "GeForce RTX 5070", "aliases": ["RTX 5070", "5070"], "new_price": 25900},
            {"id": "gpu_rtx5060ti", "name": "GeForce RTX 5060 Ti", "aliases": ["RTX 5060 Ti", "5060 Ti"], "new_price": 17900},
            {"id": "gpu_rtx5060", "name": "GeForce RTX 5060", "aliases": ["RTX 5060", "5060"], "new_price": 12900},
        ],
        "nvidia_40": [
            {"id": "gpu_rtx4090", "name": "GeForce RTX 4090", "aliases": ["RTX 4090", "4090"], "new_price": 59900},
            {"id": "gpu_rtx4080s", "name": "GeForce RTX 4080 SUPER", "aliases": ["RTX 4080 SUPER", "4080 SUPER"], "new_price": 36900},
            {"id": "gpu_rtx4080", "name": "GeForce RTX 4080", "aliases": ["RTX 4080", "4080"], "new_price": 33900},
            {"id": "gpu_rtx4070tis", "name": "GeForce RTX 4070 Ti SUPER", "aliases": ["RTX 4070 Ti SUPER", "4070 Ti SUPER"], "new_price": 26900},
            {"id": "gpu_rtx4070ti", "name": "GeForce RTX 4070 Ti", "aliases": ["RTX 4070 Ti", "4070 Ti"], "new_price": 23900},
            {"id": "gpu_rtx4070s", "name": "GeForce RTX 4070 SUPER", "aliases": ["RTX 4070 SUPER", "4070 SUPER"], "new_price": 19900},
            {"id": "gpu_rtx4070", "name": "GeForce RTX 4070", "aliases": ["RTX 4070", "4070"], "new_price": 17900},
            {"id": "gpu_rtx4060ti_16g", "name": "GeForce RTX 4060 Ti 16GB", "aliases": ["RTX 4060 Ti 16GB", "4060 Ti 16GB"], "new_price": 14900},
            {"id": "gpu_rtx4060ti", "name": "GeForce RTX 4060 Ti", "aliases": ["RTX 4060 Ti", "4060 Ti"], "new_price": 12900},
            {"id": "gpu_rtx4060", "name": "GeForce RTX 4060", "aliases": ["RTX 4060", "4060"], "new_price": 9900},
        ],
        "nvidia_30": [
            {"id": "gpu_rtx3090ti", "name": "GeForce RTX 3090 Ti", "aliases": ["RTX 3090 Ti", "3090 Ti"], "new_price": 64900},
            {"id": "gpu_rtx3090", "name": "GeForce RTX 3090", "aliases": ["RTX 3090", "3090"], "new_price": 45900},
            {"id": "gpu_rtx3080ti", "name": "GeForce RTX 3080 Ti", "aliases": ["RTX 3080 Ti", "3080 Ti"], "new_price": 36900},
            {"id": "gpu_rtx3080_12g", "name": "GeForce RTX 3080 12GB", "aliases": ["RTX 3080 12GB", "3080 12GB"], "new_price": 32900},
            {"id": "gpu_rtx3080", "name": "GeForce RTX 3080", "aliases": ["RTX 3080", "3080"], "new_price": 25900},
            {"id": "gpu_rtx3070ti", "name": "GeForce RTX 3070 Ti", "aliases": ["RTX 3070 Ti", "3070 Ti"], "new_price": 19900},
            {"id": "gpu_rtx3070", "name": "GeForce RTX 3070", "aliases": ["RTX 3070", "3070"], "new_price": 15900},
            {"id": "gpu_rtx3060ti", "name": "GeForce RTX 3060 Ti", "aliases": ["RTX 3060 Ti", "3060 Ti"], "new_price": 11900},
            {"id": "gpu_rtx3060", "name": "GeForce RTX 3060", "aliases": ["RTX 3060", "3060"], "new_price": 10900},
            {"id": "gpu_rtx3050", "name": "GeForce RTX 3050", "aliases": ["RTX 3050", "3050"], "new_price": 8490},
        ],
        "amd_9000": [
            {"id": "gpu_rx9070xt", "name": "Radeon RX 9070 XT", "aliases": ["RX 9070 XT", "9070 XT"], "new_price": 22900},
            {"id": "gpu_rx9070", "name": "Radeon RX 9070", "aliases": ["RX 9070", "9070"], "new_price": 18900},
        ],
        "amd_7000": [
            {"id": "gpu_rx7900xtx", "name": "Radeon RX 7900 XTX", "aliases": ["RX 7900 XTX", "7900 XTX"], "new_price": 29900},
            {"id": "gpu_rx7900xt", "name": "Radeon RX 7900 XT", "aliases": ["RX 7900 XT", "7900 XT"], "new_price": 24900},
            {"id": "gpu_rx7800xt", "name": "Radeon RX 7800 XT", "aliases": ["RX 7800 XT", "7800 XT"], "new_price": 15900},
            {"id": "gpu_rx7700xt", "name": "Radeon RX 7700 XT", "aliases": ["RX 7700 XT", "7700 XT"], "new_price": 13900},
            {"id": "gpu_rx7600xt", "name": "Radeon RX 7600 XT", "aliases": ["RX 7600 XT", "7600 XT"], "new_price": 11500},
            {"id": "gpu_rx7600", "name": "Radeon RX 7600", "aliases": ["RX 7600", "7600"], "new_price": 8900},
        ],
        "amd_6000": [
            {"id": "gpu_rx6950xt", "name": "Radeon RX 6950 XT", "aliases": ["RX 6950 XT", "6950 XT"], "new_price": 35900},
            {"id": "gpu_rx6800xt", "name": "Radeon RX 6800 XT", "aliases": ["RX 6800 XT", "6800 XT"], "new_price": 21900},
            {"id": "gpu_rx6700xt", "name": "Radeon RX 6700 XT", "aliases": ["RX 6700 XT", "6700 XT"], "new_price": 15900},
            {"id": "gpu_rx6600xt", "name": "Radeon RX 6600 XT", "aliases": ["RX 6600 XT", "6600 XT"], "new_price": 12490},
        ],
        "intel_arc": [
            {"id": "gpu_arcb580", "name": "Intel Arc B580", "aliases": ["Arc B580", "B580"], "new_price": 11900},
            {"id": "gpu_arcb570", "name": "Intel Arc B570", "aliases": ["Arc B570", "B570"], "new_price": 9500},
            {"id": "gpu_arca770_16g", "name": "Intel Arc A770 16GB", "aliases": ["Arc A770 16GB", "A770 16GB"], "new_price": 11900},
        ],
    },
    # ── RAM ──
    "ram": {
        "ddr5": [
            {"id": "ram_ddr5_32gb", "name": "DDR5 32GB", "aliases": ["DDR5 32G", "DDR5 32GB"], "new_price": 3400},
            {"id": "ram_ddr5_16gb", "name": "DDR5 16GB", "aliases": ["DDR5 16G", "DDR5 16GB"], "new_price": 1700},
            {"id": "ram_ddr5_64gb", "name": "DDR5 64GB", "aliases": ["DDR5 64G", "DDR5 64GB"], "new_price": 6500},
        ],
        "ddr4": [
            {"id": "ram_ddr4_32gb", "name": "DDR4 32GB", "aliases": ["DDR4 32G", "DDR4 32GB"], "new_price": 2300},
            {"id": "ram_ddr4_16gb", "name": "DDR4 16GB", "aliases": ["DDR4 16G", "DDR4 16GB"], "new_price": 1400},
            {"id": "ram_ddr4_8gb", "name": "DDR4 8GB", "aliases": ["DDR4 8G", "DDR4 8GB"], "new_price": 700},
        ],
    },
    # ── SSD ──
    "ssd": {
        "pcie5": [
            {"id": "ssd_crucial_t705_4tb_pcie5", "name": "Crucial T705 4TB PCIe5", "aliases": ["Crucial T705 4TB PCIe5", "T705 4TB PCIe5"], "new_price": 15500},
            {"id": "ssd_crucial_t705_2tb_pcie5", "name": "Crucial T705 2TB PCIe5", "aliases": ["Crucial T705 2TB PCIe5", "T705 2TB PCIe5"], "new_price": 8200},
        ],
        "pcie4": [
            {"id": "ssd_samsung_990_pro_2tb", "name": "Samsung 990 Pro 2TB", "aliases": ["Samsung 990 Pro 2TB", "990 Pro 2TB"], "new_price": 5500},
            {"id": "ssd_samsung_990_pro_1tb", "name": "Samsung 990 Pro 1TB", "aliases": ["Samsung 990 Pro 1TB", "990 Pro 1TB"], "new_price": 3200},
            {"id": "ssd_wd_black_sn850x_2tb", "name": "WD Black SN850X 2TB", "aliases": ["WD Black SN850X 2TB", "Black SN850X 2TB"], "new_price": 4800},
            {"id": "ssd_wd_black_sn850x_1tb", "name": "WD Black SN850X 1TB", "aliases": ["WD Black SN850X 1TB", "Black SN850X 1TB"], "new_price": 2800},
            {"id": "ssd_seagate_firecuda_530_2tb", "name": "Seagate FireCuda 530 2TB", "aliases": ["Seagate FireCuda 530 2TB", "FireCuda 530 2TB"], "new_price": 5200},
            {"id": "ssd_kingston_kc3000_2tb", "name": "Kingston KC3000 2TB", "aliases": ["Kingston KC3000 2TB", "KC3000 2TB"], "new_price": 4500},
            {"id": "ssd_adata_xpg_gammix_s70b_2tb", "name": "ADATA XPG Gammix S70B 2TB", "aliases": ["ADATA XPG Gammix S70B 2TB", "XPG Gammix S70B 2TB"], "new_price": 4800},
            {"id": "ssd_wd_blue_sn580_1tb", "name": "WD Blue SN580 1TB", "aliases": ["WD Blue SN580 1TB", "Blue SN580 1TB"], "new_price": 2200},
            {"id": "ssd_samsung_980_pro_2tb", "name": "Samsung 980 Pro 2TB", "aliases": ["Samsung 980 Pro 2TB", "980 Pro 2TB"], "new_price": 4790},
            {"id": "ssd_samsung_980_pro_1tb", "name": "Samsung 980 Pro 1TB", "aliases": ["Samsung 980 Pro 1TB", "980 Pro 1TB"], "new_price": 2990},
            {"id": "ssd_wd_black_sn770_2tb", "name": "WD Black SN770 2TB", "aliases": ["WD Black SN770 2TB", "Black SN770 2TB"], "new_price": 3600},
        ],
        "sata": [
            {"id": "ssd_samsung_870_evo_4tb", "name": "Samsung 870 EVO 4TB", "aliases": ["Samsung 870 EVO 4TB", "870 EVO 4TB"], "new_price": 7200},
            {"id": "ssd_samsung_870_evo_2tb", "name": "Samsung 870 EVO 2TB", "aliases": ["Samsung 870 EVO 2TB", "870 EVO 2TB"], "new_price": 3800},
            {"id": "ssd_crucial_mx500_2tb", "name": "Crucial MX500 2TB", "aliases": ["Crucial MX500 2TB", "MX500 2TB"], "new_price": 2800},
        ],
    },
    # ── HDD ──
    "hdd": {
        "hdd": [
            {"id": "hdd_seagate_ironwolf_pro_20tb", "name": "Seagate IronWolf Pro 20TB", "aliases": ["Seagate IronWolf Pro 20TB", "IronWolf Pro 20TB"], "new_price": 16500},
            {"id": "hdd_seagate_ironwolf_16tb", "name": "Seagate IronWolf 16TB", "aliases": ["Seagate IronWolf 16TB", "IronWolf 16TB"], "new_price": 11500},
            {"id": "hdd_seagate_barracuda_pro_12tb", "name": "Seagate Barracuda Pro 12TB", "aliases": ["Seagate Barracuda Pro 12TB", "Barracuda Pro 12TB"], "new_price": 8500},
            {"id": "hdd_seagate_barracuda_8tb", "name": "Seagate Barracuda 8TB", "aliases": ["Seagate Barracuda 8TB", "Barracuda 8TB"], "new_price": 4800},
            {"id": "hdd_seagate_barracuda_4tb", "name": "Seagate Barracuda 4TB", "aliases": ["Seagate Barracuda 4TB", "Barracuda 4TB"], "new_price": 2800},
            {"id": "hdd_wd_red_plus_12tb_nas", "name": "WD Red Plus 12TB NAS", "aliases": ["WD Red Plus 12TB NAS", "Red Plus 12TB NAS"], "new_price": 8900},
            {"id": "hdd_wd_gold_8tb", "name": "WD Gold 8TB", "aliases": ["WD Gold 8TB", "Gold 8TB"], "new_price": 6500},
            {"id": "hdd_wd_blue_4tb", "name": "WD Blue 4TB", "aliases": ["WD Blue 4TB", "Blue 4TB"], "new_price": 3200},
            {"id": "hdd_wd_blue_2tb", "name": "WD Blue 2TB", "aliases": ["WD Blue 2TB", "Blue 2TB"], "new_price": 2000},
            {"id": "hdd_toshiba_x300_4tb", "name": "Toshiba X300 4TB", "aliases": ["Toshiba X300 4TB", "X300 4TB"], "new_price": 2600},
        ],
    },
}


# ─────────────────────────────────────────────────
# 資料庫管理
# ─────────────────────────────────────────────────

class Database:
    def __init__(self, db_path: str = "pc_prices.db"):
        self.path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            id          TEXT PRIMARY KEY,
            source      TEXT NOT NULL,
            part_id     TEXT NOT NULL,
            title       TEXT,
            price       INTEGER,
            condition   TEXT,
            url         TEXT,
            location    TEXT,
            date        TEXT,
            sold        INTEGER DEFAULT 0,
            crawled_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS price_snapshots (
            part_id     TEXT NOT NULL,
            date        TEXT NOT NULL,
            avg_price   INTEGER,
            min_price   INTEGER,
            max_price   INTEGER,
            listing_count INTEGER,
            sources     TEXT,
            PRIMARY KEY (part_id, date)
        );

        CREATE TABLE IF NOT EXISTS new_snapshots (
            part_id     TEXT NOT NULL,
            date        TEXT NOT NULL,
            new_price   INTEGER,
            src         TEXT,
            cnt         INTEGER,
            PRIMARY KEY (part_id, date)
        );

        CREATE TABLE IF NOT EXISTS crawl_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT,
            part_id     TEXT,
            status      TEXT,
            count       INTEGER,
            duration    REAL,
            crawled_at  TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_listings_part_id ON listings(part_id);
        CREATE INDEX IF NOT EXISTS idx_listings_date    ON listings(date);
        CREATE INDEX IF NOT EXISTS idx_snapshots_part   ON price_snapshots(part_id);
        """)
        self.conn.commit()

    def save_listing(self, listing: Listing):
        uid = hashlib.md5(f"{listing.source}:{listing.url}:{listing.price}".encode()).hexdigest()
        self.conn.execute("""
            INSERT OR REPLACE INTO listings
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (uid, listing.source, listing.part_id, listing.title, listing.price,
              listing.condition, listing.url, listing.location,
              listing.date, int(listing.sold), datetime.now().isoformat()))
        self.conn.commit()

    def save_snapshot(self, snap: PriceSnapshot):
        self.conn.execute("""
            INSERT OR REPLACE INTO price_snapshots VALUES (?,?,?,?,?,?,?)
        """, (snap.part_id, snap.date, snap.avg_price, snap.min_price,
              snap.max_price, snap.listing_count, json.dumps(snap.sources)))
        self.conn.commit()

    def save_new_snapshot(self, part_id: str, date: str, new_price: int, src: str, cnt: int):
        """寫入某零件某日的『目前全新行情』快照（供新品價歷史曲線）。"""
        self.conn.execute(
            "INSERT OR REPLACE INTO new_snapshots VALUES (?,?,?,?,?)",
            (part_id, date, new_price, src, cnt))
        self.conn.commit()

    def get_new_history(self, part_id: str, days: int = 365) -> list:
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT date, new_price, src FROM new_snapshots "
            "WHERE part_id=? AND date>=? ORDER BY date ASC", (part_id, since)
        ).fetchall()
        return [{"date": r[0], "new": r[1], "src": r[2]} for r in rows]

    def get_today_listings(self, part_id: str) -> list:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT * FROM listings WHERE part_id=? AND date>=?", (part_id, today)
        ).fetchall()
        return rows

    def get_price_history(self, part_id: str, days: int = 365) -> list:
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT date, avg_price, min_price, max_price, listing_count FROM price_snapshots "
            "WHERE part_id=? AND date>=? ORDER BY date ASC", (part_id, since)
        ).fetchall()
        return [{"date":r[0], "avg":r[1], "min":r[2], "max":r[3], "count":r[4]} for r in rows]

    def get_recent_listings(self, part_id: str, days: int = 7, limit: int = 12) -> list:
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT source, title, price, condition, location, date FROM listings "
            "WHERE part_id=? AND date>=? ORDER BY date DESC, price ASC LIMIT ?",
            (part_id, since, limit)
        ).fetchall()
        return [{"source":r[0], "title":r[1], "price":r[2], "condition":r[3],
                 "location":r[4], "date":r[5]} for r in rows]

    def prune_old_listings(self, source: str, days: int) -> int:
        """刪除指定來源中早於保留天數的成交資料（如 FB 來源僅保留近 90 天）。"""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        cur = self.conn.execute(
            "DELETE FROM listings WHERE source=? AND date<?", (source, cutoff)
        )
        self.conn.commit()
        return cur.rowcount


# ─────────────────────────────────────────────────
# 爬蟲工具函式
# ─────────────────────────────────────────────────

class BaseScraper:
    name = "base"
    BASE_URL = ""
    REQUEST_DELAY = (1.5, 3.0)   # 隨機延遲區間 (秒)

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }

    def __init__(self, session: aiohttp.ClientSession, db: Database):
        self.session = session
        self.db = db

    async def fetch(self, url: str, **kwargs) -> Optional[str]:
        delay = random.uniform(*self.REQUEST_DELAY)
        await asyncio.sleep(delay)
        try:
            async with self.session.get(url, headers=self.HEADERS, timeout=aiohttp.ClientTimeout(total=15), **kwargs) as r:
                if r.status == 200:
                    return await r.text()
                print(f"[{self.name}] HTTP {r.status} → {url}")
        except Exception as e:
            print(f"[{self.name}] Error: {e} → {url}")
        return None

    @staticmethod
    def clean_price(text: str) -> Optional[int]:
        """從文字中擷取數字價格"""
        text = re.sub(r'[,，\s]', '', str(text))
        m = re.search(r'\d{3,6}', text)
        return int(m.group()) if m else None

    @staticmethod
    def guess_condition(title: str) -> str:
        title = title.lower()
        if any(k in title for k in ['全新', '未拆', '未開封', '盒裝未開']): return "全新"
        if any(k in title for k in ['九成新', '9成新', '9.5成', '95成']): return "九成新"
        if any(k in title for k in ['八成新', '8成新', '85成', '8.5成']): return "八成新"
        if any(k in title for k in ['七成', '7成']): return "七成新"
        return "成色不明"

    async def scrape_part(self, part: dict) -> list[Listing]:
        raise NotImplementedError


# ─────────────────────────────────────────────────
# 蝦皮購物爬蟲 (使用官方搜尋 API)
# ─────────────────────────────────────────────────

class ShopeeScraper(BaseScraper):
    # ⚠️ 待辦 #4 驗證（2026-06-03）：此搜尋 API 現以反爬蟲擋下匿名請求，
    #    實測回 HTTP 403 + {"error":90309999,"is_login":false}（即使先取 cookie 也一樣）。
    #    匿名請求無法取得資料。可行途徑：登入後帶有效 cookie/簽章，或改用蝦皮
    #    Open Platform 官方 API（需註冊夥伴）。目前遇非 200 會安全回傳空清單。
    name = "蝦皮購物"
    SEARCH_API = "https://shopee.tw/api/v4/search/search_items"

    async def scrape_part(self, part: dict) -> list[Listing]:
        listings = []
        keyword = part["aliases"][0]

        params = {
            "by": "relevancy",
            "keyword": keyword,
            "limit": 30,
            "newest": 0,
            "order": "desc",
            "page_type": "search",
            "scenario": "PAGE_GLOBAL_SEARCH",
            "version": 2,
        }
        headers = {**self.HEADERS,
                   "Referer": f"https://shopee.tw/search?keyword={quote(keyword)}",
                   "X-API-SOURCE": "pc"}

        try:
            await asyncio.sleep(random.uniform(*self.REQUEST_DELAY))
            async with self.session.get(self.SEARCH_API, params=params,
                                        headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return listings
                data = await r.json()
        except Exception as e:
            print(f"[蝦皮] API Error: {e}")
            return listings

        return parse_shopee_items(data, part)


def ram_total_capacities(title: str) -> set:
    """從 RAM 標題推估『總容量(GB)』候選集合，處理套裝(kit)記法避免容量誤判：
      「16G*2」「16Gx2」「2x16G」→ 32（套組總量，非單條 16）；「32G」「32GB」→ 32。
    有套組記法時只認套組總量（忽略單條數字）；否則用標題中所有單條容量。"""
    t = title.lower()
    kits = set()
    for base, cnt in re.findall(r"(?<!\d)(\d+)\s*g[b]?\s*[\*x×]\s*(\d+)\b", t):   # 16g*2
        kits.add(int(base) * int(cnt))
    for cnt, base in re.findall(r"(?<!\d)(\d+)\s*[\*x×]\s*(\d+)\s*g[b]?\b", t):   # 2x16g
        kits.add(int(cnt) * int(base))
    if kits:
        return kits
    return {int(n) for n in re.findall(r"(?<!\d)(\d+)\s*g(?:b|igabyte)?\b", t)}


def title_matches_part(title: str, part: dict) -> bool:
    """判斷賣文標題是否對應到「這個確切型號」，避免基礎型號誤收變體
    （RTX 3070 收到 3070 Ti、14900K 收到 14900KF、Ryzen 5 7600 收到 7600X、5800X 收到 5800X3D）。
    做法：標題與別名去空白/連字號後比對；基礎型號後若緊接 Ti/Super/XT/XTX/GRE/X3D/X/S/K/F 等
    視為「別的 SKU」而不計入。"""
    # RAM 規格帶：別名「DDR5 32GB」常被頻率夾在中間（如「DDR5 6000 32GB」）→ 不能要求相鄰。
    # 改為「世代(DDR5/DDR4) 與 容量(32GB/32G) 同時出現」即視為命中（容量用數字邊界避免誤收 16→32）。
    if part.get("id", "").startswith("ram_"):
        pid = part["id"]                       # ram_ddr5_32gb → gen=ddr5, cap=32
        gen = "ddr5" if "ddr5" in pid else ("ddr4" if "ddr4" in pid else "")
        m = re.search(r"_(\d+)gb$", pid)
        cap = int(m.group(1)) if m else 0
        tl = title.lower()
        return bool(gen and cap and gen in tl and cap in ram_total_capacities(tl))

    t = re.sub(r"[\s\-]+", "", title).lower()
    for a in part.get("aliases", []):
        na = re.sub(r"[\s\-]+", "", a).lower()
        if not na:
            continue
        i = t.find(na)
        if i < 0:
            continue
        if re.search(r"(ti|super|xtx|xt|gre|x3d)$", na):   # 別名本身已是具體變體 → 命中
            return True
        after = t[i + len(na):]
        # 後綴字母（s/x/k/f）若緊接「數字或邊界」即視為變體（如 14900KF24核、7600X）；
        # 若後接英文字母（socket、series…）則非變體，不排除。
        if re.match(r"(ti|super|xtx|xt|gre|x3d|3d)", after) or re.match(r"[sxkf](?![a-z])", after):
            continue                                        # 其實是 Ti/Super/X3D… 等變體
        return True
    return False


# 蝦皮賣文常見的「非單顆零件」雜訊：整機/套裝/分期/含他零件的組合 → 會嚴重污染均價。
# 與 PTT 同精神，但蝦皮文案更雜。命中任一即排除該筆。**所有分類**都套用。
SHOPEE_NOISE = re.compile(
    r"整機|整台|主機板|主板|套裝|套装|套餐|準系統|組裝|組合|搭機|含機|含板|"
    r"桌機|電競主機|電競桌機|電競電腦|繪圖電腦|工作站|完整電腦|電腦一台|遊戲主機|"
    r"遊戲機|準系統|分期|無卡|免卡|可參考|參考價|伺服器|"
    # 配件/裝飾/非單顆零件（顯卡常被做成擺飾、或只賣散熱模組）
    r"模型|手辦|公仔|擺件|裝飾品|玩具|鑰匙圈|散熱模組|水冷頭|顯卡支架|顯卡架|背板|延長線|轉接卡|晶片",
    re.I,
)
# 「夾帶顯卡」的組合雜訊（CPU/RAM/SSD 等賣文常附顯卡 → 拉歪均價）。
# ⚠️ 只對**非顯卡品項**套用——否則會把顯卡本身的賣文（標題必含 RTX/RX）全部誤殺。
SHOPEE_GPU_COMBO = re.compile(
    r"rtx|gtx|radeon|顯卡|\brx\s?\d{3,4}\b|\b(?:30|40|50)[5-9]0(?:\s?ti)?\b|\b\d{4}ti\b",
    re.I,
)
# 記憶體專屬雜訊：筆電 SO-DIMM（與桌機 UDIMM 不同市場）、伺服器 ECC/REG。只對 ram_ 品項套用。
SHOPEE_RAM_NOISE = re.compile(
    r"筆電|筆記型|筆記本|SO-?DIMM|SODIMM|NB專用|NB記憶體|ECC|REG\b|RDIMM|伺服器",
    re.I,
)

# 全新 / 二手 判定（用標題關鍵字）：供「目前全新行情」與二手分流。
# is_new = 命中 NEW 訊號且未命中 USED 訊號（避免「公司貨二手」之類被誤判為全新）。
# ⚠️「保固N天」是二手賣家常見話術 → 不可當全新；只認「保固N年/N年保固」這種零售年保。
_USED_RE = re.compile(r"二手|中古|拆機|福利品|良品|無盒|使用過|用過|九成|9\s?成|八成|8\s?成|七成|7\s?成|六成|6\s?成|盒裝完整|保存良好|保固\s?\d+\s?天", re.I)
_NEW_RE  = re.compile(
    r"全新|未拆|未開封|盒裝全新|公司貨|原廠盒裝|現貨全新|台灣公司貨|全新品|拆封新品|"
    # 零售/通路新品訊號（蝦皮商城常無「全新」二字，但有下列零售用語）
    r"庫存|開立發票|開發票|可開發票|附發票|含發票|含稅|原廠保固|代理商|"
    # 終身/原廠年保＝原廠新品保固（二手賣家多為「保固N天/30天」，已歸 USED）
    r"終身保固|終生保固|終保|原廠終身|保固\s?[一二三四五六七八九十]\s?年|保固\s?\d+\s?年|\d+\s?年(?:原廠)?保固",
    re.I,
)


def title_is_new(title: str) -> bool:
    return bool(_NEW_RE.search(title) and not _USED_RE.search(title))


# 跨型號 / 賣場列表雜訊：一篇標題列出多張不同顯卡（賣場清單、「XX參考」、套組），
# 其價格不對應「這一顆」→ 不該計入該型號均價。保守起見只認「有品牌前綴」的型號
# （rtx/gtx/rx + 數字），避免把記憶體容量(12G)、年份等誤判為型號。
_GPU_MODEL_RE = re.compile(r"(?:rtx|gtx|rx)\s?(\d{3,4})\s?(ti|xtx|xt|super|gre)?", re.I)


def gpu_model_set(title: str) -> set:
    """抽出標題中所有『有品牌前綴』的顯卡型號（正規化為 數字+變體，如 3060 / 3060ti / 6800xt）。"""
    out = set()
    for m in _GPU_MODEL_RE.finditer(title or ""):
        out.add(m.group(1) + (m.group(2) or "").lower())
    return out


def is_cross_model_gpu(title: str, part: dict) -> bool:
    """顯卡賣文是否為『跨型號/賣場清單』（標題含 ≥2 個不同顯卡型號）→ 該價非單卡價，應排除。
    只對顯卡品項判定；非顯卡或型號數 <2 一律 False。"""
    if not (part or {}).get("id", "").startswith("gpu_"):
        return False
    return len(gpu_model_set(title or "")) >= 2


_PART_BY_ID = None


def find_part(part_id: str) -> dict:
    """以 id 取得零件 dict（含 aliases/new_price）。供模組層聚合函式查型號用，結果快取。"""
    global _PART_BY_ID
    if _PART_BY_ID is None:
        _PART_BY_ID = {}
        for cat_data in PARTS_DB.values():
            for subcat_data in cat_data.values():
                for p in subcat_data:
                    _PART_BY_ID[p["id"]] = p
    return _PART_BY_ID.get(part_id)


def classify_listing(title: str, price: int, new_ref: int = None, default_new: bool = False) -> str:
    """把單筆賣文分類為 'used' / 'new' / 'exclude'（供二手分流共用，規則集中一處）。
    規則（由強到弱）：
      1. 明確二手字樣（_USED_RE）：
         - 若給了 new_ref 且 price ≥ new_ref → 'exclude'（「良品/福利」卻喊到比現貨全新還貴
           ＝整新店/喊價，兩邊都不可信 → 整筆剔除，不污染二手也不算全新）。
         - 否則 'used'。
      2. 明確全新字樣（_NEW_RE）→ 'new'。
      3. 無成色賣文：給了 new_ref 且 price ≥ new_ref → 'new'（多為蝦皮商城無「全新」字樣的零售卡）。
      4. 仍無法判定：default_new=True（零售為主、二手稀少的品類如 RAM）→ 'new'；否則 'used'。
    new_ref 用『目前全新行情』而非上市價 → 對 AI 飆漲的 RAM 安全：真實二手仍低於飆漲後的全新。"""
    t = title or ""
    if _USED_RE.search(t):
        return "exclude" if (new_ref and price >= new_ref) else "used"
    if title_is_new(t):
        return "new"
    if new_ref and price >= new_ref:
        return "new"
    return "new" if default_new else "used"


def part_default_new(part_id: str) -> bool:
    """該品類在蝦皮是否『零售為主、二手稀少』→ 無成色賣文預設視為全新。
    RAM 規格帶幾乎全為通路新品（少有 C2C 二手）→ True；其餘維持預設二手。"""
    return (part_id or "").startswith("ram_")


def split_used_new(rows, new_ref: int = None) -> tuple:
    """把 (title, price) 序列分流成 (used_prices, new_prices)。'exclude' 兩邊皆不計。見 classify_listing。"""
    used, new = [], []
    for title, price in rows:
        c = classify_listing(title, price, new_ref)
        if c == "used":
            used.append(price)
        elif c == "new":
            new.append(price)
    return used, new


def part_new_ref(db, part_id: str, days: int = 60) -> int:
    """估某零件『目前全新行情』參考價（供二手分流的價格天花板用）。
    優先用原價屋（權威新品報價）；無原價屋資料時，退回近 days 天在地、非跨型號、
    明確全新賣文的去極值均價。樣本 <3 回 None（不夠可靠就不啟用價格天花板）。"""
    cp = coolpc_new_price(db, part_id)
    if cp:
        return cp
    ref = list(REFERENCE_SOURCES)
    ph = ",".join("?" * len(ref)) if ref else "''"
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = db.conn.execute(
        f"SELECT title, price FROM listings WHERE part_id=? AND date>=? AND source NOT IN ({ph})",
        [part_id, since, *ref]
    ).fetchall()
    part = find_part(part_id)
    dn = part_default_new(part_id)
    new_prices = [p for (t, p) in rows
                  if not is_cross_model_gpu(t or "", part)
                  and classify_listing(t or "", p, None, dn) == "new"]
    if len(new_prices) >= 3:
        return robust_price_stats(new_prices)[0]
    return None


def parse_shopee_items(data: dict, part: dict, source_name: str = "蝦皮購物") -> list[Listing]:
    """解析蝦皮 search_items JSON → Listing 清單。
    被 ShopeeScraper（登入後直連）與 tools/import_listings.py（匯入存檔的 JSON）共用。

    雙階段過濾：先用關鍵字/型號雜訊濾掉非單顆零件，再以「本批中位數」動態算價格上限剔除整機/組合。
    動態上限取代舊的「>2.5×上市價」固定上限 → 對 AI 飆漲（如 RAM 現價達上市價 3 倍）安全：
    不會把飆漲後的真實單顆賣文當成整機剔掉。"""
    is_gpu = part.get("id", "").startswith("gpu_")
    is_ram = part.get("id", "").startswith("ram_")

    # 第一階段：關鍵字/型號雜訊過濾，收集候選 (info, name, price)
    cand = []
    for item in data.get("items") or []:
        info = item.get("item_basic", item)
        raw_price = info.get("price", 0) // 100000  # 蝦皮價格單位為分*1000
        if raw_price < 500:
            raw_price = info.get("price_min", 0) // 100000
        if raw_price < 500 or raw_price > 200000:
            continue
        name = info.get("name", "")
        if not title_matches_part(name, part):
            continue
        if SHOPEE_NOISE.search(name):                       # 整機/套裝/分期等組合
            continue
        if not is_gpu and SHOPEE_GPU_COMBO.search(name):    # 非顯卡品項夾帶顯卡
            continue
        if is_ram and SHOPEE_RAM_NOISE.search(name):        # 桌機 RAM 排除筆電/伺服器記憶體
            continue
        if is_cross_model_gpu(name, part):                  # 顯卡跨型號/賣場清單
            continue
        cand.append((info, name, raw_price))

    # 動態價格上限：以候選中位數推估「單顆合理價」，>中位數 ×3.5 視為整機/組合剔除。
    # 候選太少（<4）時退回舊的上市價 ×2.5 防呆（仍保底，但低 MSRP 飆漲品改用中位數）。
    np = part.get("new_price", 0)
    if len(cand) >= 4:
        med = statistics.median([p for (_i, _n, p) in cand])
        ceil = max(med * 3.5, np * 2.5)
    else:
        ceil = np * 2.5 if np > 0 else 200000

    listings = []
    for info, name, raw_price in cand:
        try:
            if ceil and raw_price > ceil:
                continue
            url = f"https://shopee.tw/product/{info.get('shopid','')}/{info.get('itemid','')}"
            sold = info.get("sold", 0) > 0 or info.get("historical_sold", 0) > 0
            listings.append(Listing(
                source    = source_name,
                part_id   = part["id"],
                title     = name,
                price     = raw_price,
                condition = BaseScraper.guess_condition(name),
                url       = url,
                location  = info.get("shop_location", ""),
                date      = datetime.now().strftime("%Y-%m-%d"),
                sold      = sold,
            ))
        except Exception:
            continue
    return listings


# ─────────────────────────────────────────────────
# PTT BuyTrade 爬蟲
# ─────────────────────────────────────────────────

class PTTScraper(BaseScraper):
    name = "PTT 硬體交易"
    # PTT hardwaresale＝硬體買賣板（實測有大量買賣文）。[賣]/[售] 為出售文（要的），
    # [徵] 為收購（排除）、標題含（已售出）視為已成交。選擇器 .r-ent / .title a /
    # #main-content 經實測有效。（先前誤用不存在的 BuyTrade、討論板 PC_Shopping → 已更正）
    BOARDS = ["hardwaresale"]
    BASE = "https://www.ptt.cc"

    async def scrape_part(self, part: dict) -> list[Listing]:
        listings = []
        for board in self.BOARDS:
            url = f"{self.BASE}/bbs/{board}/search?q={quote(part['aliases'][0])}"
            html = await self.fetch(url, cookies={"over18": "1"})
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            posts = soup.select(".r-ent")[:15]
            for post in posts:
                try:
                    title_el = post.select_one(".title a")
                    date_el  = post.select_one(".date")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    # 只收出售文（[賣]/[售]/WTS），排除收購文（[徵]）
                    if not re.search(r'\[賣|WTS|出售\]', title, re.I):
                        continue
                    # 排除整機/組合/半套貼文（價格非單一零件，會汙染均價）
                    if re.search(r'整機|主機|套裝|準系統|組合|半套|一套|\+', title):
                        continue
                    # RAM 專屬：排除「夾帶其他零件的組合」與筆電記憶體（否則均價失真）
                    if part["id"].startswith("ram_") and re.search(
                            r'顯卡|\bgpu\b|rtx|gtx|rx\s?\d|cpu|處理器|主機板|筆電|nb|sodimm|'
                            r'i[3579]-|\br[3579]\b|[bzx]\d{3}', title, re.I):
                        continue
                    # 精確型號比對：避免基礎型號收到變體（3070 ≠ 3070 Ti）
                    if not title_matches_part(title, part):
                        continue

                    href = urljoin(self.BASE, title_el["href"])
                    # 取得文章內容以解析價格
                    post_html = await self.fetch(href, cookies={"over18": "1"})
                    if not post_html:
                        continue

                    post_soup = BeautifulSoup(post_html, "html.parser")
                    content = post_soup.select_one("#main-content")
                    if not content:
                        continue

                    text = content.get_text()
                    # 找價格：常見格式「售價：XXXX」「$XXXX」「NT XXXX」
                    price_match = re.search(r'(?:售價|價格|賣|NT\$?|＄|\$)\s*[：:＿_\s]*(\d{3,6})', text)
                    if not price_match:
                        continue
                    price = int(price_match.group(1))
                    if price < 500 or price > 200000:
                        continue

                    # 地區
                    loc_match = re.search(r'(?:地區|縣市|所在地)[：:\s]*([^\n]{2,10})', text)
                    loc = loc_match.group(1).strip() if loc_match else ""

                    date_str = date_el.get_text(strip=True) if date_el else ""

                    listings.append(Listing(
                        source    = self.name,
                        part_id   = part["id"],
                        title     = title,
                        price     = price,
                        condition = self.guess_condition(title + text[:200]),
                        url       = href,
                        location  = loc,
                        date      = datetime.now().strftime("%Y-%m-%d"),
                        sold      = ("已售" in title) or ("售出" in title) or ("sold" in title.lower()),
                        raw_text  = text[:500],
                    ))
                except Exception:
                    continue
        return listings


# ─────────────────────────────────────────────────
# Facebook 公開二手社團（架構預留，尚未啟用）
# ─────────────────────────────────────────────────

class FBGroupScraper(BaseScraper):
    """FB 公開二手零件社團資料來源。

    ⚠️ FB 社團內容需登入且有強力反爬蟲，無法像蝦皮那樣以匿名請求自動抓取，
       且自動爬取違反 FB 服務條款。因此本來源不走 self.fetch 自動爬蟲，預計改以下列
       其一接入（見 CLAUDE.md「FB 社團資料」）：
         (a) 匯入器：由使用者在已登入的瀏覽器匯出/貼上社團貼文，解析後寫入 DB
         (b) 已登入瀏覽器半自動擷取
    保留策略：FB 來源僅保留近 RETENTION_DAYS 天（見 SOURCE_RETENTION）。

    日後接入時，將解析後的貼文轉成 Listing（source=self.name）並呼叫
    Database.save_listing 寫入即可，其餘統計／API／前端皆可自動沿用。
    """
    name = "FB 社團"
    RETENTION_DAYS = 90              # FB 來源只保留近 90 天價格資料
    GROUPS: list[str] = []           # 目標公開社團（待填）

    async def scrape_part(self, part: dict) -> list[Listing]:
        # 尚未啟用：FB 需登入，無法自動爬取；資料改由匯入路徑進入（待辦）。
        return []


# ─────────────────────────────────────────────────
# eBay（海外參考價，架構預留，需官方 API 金鑰）
# ─────────────────────────────────────────────────

# eBay 英文標題的雜訊：①非整顆零件的配件（外殼/散熱片/支架/壞品/空板）
# ②整機/準系統/品牌預組電腦/主機板組合（CPU 尤其常見，會嚴重拉高參考價）→ 一律排除
EBAY_NOISE = re.compile(
    # ① 配件 / 故障品 / 空板
    r"shroud|heat\s?sink|back\s?plate|water\s?block|not\s+gpu|"
    r"for\s+parts|parts?\s+only|box\s+only|empty\s+box|\bbroken\b|\bfaulty\b|"
    r"no\s+core|no\s+chip|without\s+(?:core|gpu|chip)|pcb\s+only|chip\s+removed|"
    r"cooler\s+for|fan\s+for|replacement\s+(?:fan|cooler|shroud|heat\s?sink)|"
    r"\bbracket\b|\briser\b|thermal\s?pad|\bsticker|"
    # ② 整機 / 準系統 / 品牌預組 / 主機板組合
    r"desktop\s+pc|gaming\s+pc|prebuilt|pre-built|barebone|workstation|"
    r"mini\s+pc|all.in.one|\baio\b|\bbundle\b|\bcombo\b|motherboard|\bmobo\b|"
    r"\bomen\b|legion|alienware|aurora|trident|predator|\bnuc\b|supermicro|\bserver\b|"
    r"\btower\b|\bsff\b|gaming\s+desktop|slim\s+desktop|optiplex",
    re.I,
)


class EbayScraper(BaseScraper):
    """eBay 國際站資料來源（海外參考價）。

    ⚠️ eBay 匿名爬蟲會被反機器人系統擋下（實測一律 403 / Error Page），且繞過機器人
       偵測不被允許。唯一合規途徑為官方 **Browse API**：
         GET https://api.ebay.com/buy/browse/v1/item_summary/search?q=<關鍵字>
       認證：以 `client_credentials` 換取 OAuth application token（約 2 小時過期，
       本類別會自動快取並續期）。金鑰一律從環境變數讀取（EBAY_CLIENT_ID /
       EBAY_CLIENT_SECRET），不得寫入程式。未設定則自動略過。

    重要限制：公開 Browse API 只回「**在售掛牌價**（asking）」，**非成交價**；成交/已售
    需 Marketplace Insights API（限制存取、須審核）。故 eBay 定位為「海外**在售**參考價」。

    定位：eBay 為國際站、報價多為美金、含跨境運費關稅，與台灣在地行情基準不同，故列為
    「海外參考價」（REFERENCE_SOURCES）：**不計入台灣二手均價快照**，僅供對照。
    幣別：DB 無幣別欄、前端統一台幣顯示 → 以可設定匯率 `EBAY_TWD_RATE`（預設 32）把 USD
    換算為 TWD 入庫，並於標題附 `[US$原價]` 保留原始美金、來源標 `eBay` 以資辨別。
    """
    name = "eBay"
    SEARCH_API = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    OAUTH_URL  = "https://api.ebay.com/identity/v1/oauth2/token"
    OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"

    def __init__(self, session, db):
        super().__init__(session, db)
        self.client_id     = os.environ.get("EBAY_CLIENT_ID", "")
        self.client_secret = os.environ.get("EBAY_CLIENT_SECRET", "")
        self.marketplace   = os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_US")
        self.rate          = float(os.environ.get("EBAY_TWD_RATE", "32"))
        self._token = ""
        self._token_exp = 0.0
        self._token_lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def _get_token(self) -> str:
        """以 client_credentials 取 application token；快取至過期前 60 秒、並發只取一次。"""
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        async with self._token_lock:
            if self._token and time.time() < self._token_exp - 60:
                return self._token
            basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            headers = {"Content-Type": "application/x-www-form-urlencoded",
                       "Authorization": f"Basic {basic}"}
            payload = {"grant_type": "client_credentials", "scope": self.OAUTH_SCOPE}
            try:
                async with self.session.post(self.OAUTH_URL, headers=headers, data=payload,
                                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                    body = await r.text()
                    if r.status != 200:
                        print(f"[{self.name}] 取得 token 失敗 HTTP {r.status}: {body[:200]}")
                        return ""
                    j = json.loads(body)
            except Exception as e:
                print(f"[{self.name}] token 例外: {e}")
                return ""
            self._token = j.get("access_token", "")
            self._token_exp = time.time() + int(j.get("expires_in", 7200))
            return self._token

    async def scrape_part(self, part: dict) -> list[Listing]:
        if not self.enabled:
            return []
        token = await self._get_token()
        if not token:
            return []
        keyword = part["aliases"][0]
        params = {"q": keyword, "filter": "conditions:{USED}", "limit": "50"}
        headers = {"Authorization": f"Bearer {token}",
                   "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
                   "Accept": "application/json"}
        try:
            await asyncio.sleep(random.uniform(*self.REQUEST_DELAY))
            async with self.session.get(self.SEARCH_API, params=params, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    print(f"[{self.name}] HTTP {r.status} → {keyword}")
                    return []
                data = await r.json()
        except Exception as e:
            print(f"[{self.name}] API Error: {e}")
            return []
        return self._parse(data, part)

    def _parse(self, data: dict, part: dict) -> list[Listing]:
        listings = []
        for it in data.get("itemSummaries") or []:
            try:
                title = it.get("title", "")
                if not title_matches_part(title, part):
                    continue
                if EBAY_NOISE.search(title):   # 排除外殼/散熱片/支架等配件雜訊
                    continue
                price = it.get("price") or {}
                if price.get("value") is None:
                    continue
                usd = float(price["value"])
                twd = round(usd * self.rate)          # USD→TWD（海外參考；不入台灣均價）
                if twd < 500 or twd > 200000:
                    continue
                # 價格上限防呆：遠高於台灣新品價（>2.5x）幾乎必是整機/工作站組合 → 排除
                np = part.get("new_price", 0)
                if np > 0 and twd > np * 2.5:
                    continue
                listings.append(Listing(
                    source    = self.name,
                    part_id   = part["id"],
                    title     = f"{title} [US${int(round(usd))}]",
                    price     = twd,
                    condition = it.get("condition", "") or "Used",
                    url       = it.get("itemWebUrl", ""),
                    location  = (it.get("itemLocation") or {}).get("country", ""),
                    date      = datetime.now().strftime("%Y-%m-%d"),
                    sold      = False,   # Browse API 僅在售掛牌，非成交
                ))
            except Exception:
                continue
        return listings


# 原價屋（coolpc）：台灣最完整的『新品』報價單 → 當權威「目前全新行情」來源（非二手）。
COOLPC_SOURCE = "原價屋"

# 各來源的資料保留天數：未列出者沿用 DEFAULT_RETENTION_DAYS。FB 依需求僅保留 90 天。
DEFAULT_RETENTION_DAYS = 365
SOURCE_RETENTION = {
    FBGroupScraper.name: FBGroupScraper.RETENTION_DAYS,
    COOLPC_SOURCE: 14,   # 新品報價每日刷新，僅保留近兩週即可
}

# 不計入台灣二手均價快照的來源：eBay（海外參考）、原價屋（新品報價，非二手）。
EBAY_SOURCE = EbayScraper.name
REFERENCE_SOURCES = {EBAY_SOURCE, COOLPC_SOURCE}


# ─────────────────────────────────────────────────
# 原價屋（coolpc）報價單：權威「目前全新行情」來源
# ─────────────────────────────────────────────────
COOLPC_URL = "https://www.coolpc.com.tw/evaluate.php"
# evaluate.php 的零件分類 <select name>：n4=CPU n6=RAM n7=SSD n8=HDD n12=顯示卡
COOLPC_CATS = {"n4": "cpu", "n6": "ram", "n7": "ssd", "n8": "hdd", "n12": "gpu"}
# 配件雜訊（顯卡支撐架、線材等非零件本體）
COOLPC_ACCESSORY = re.compile(
    r"支撐架|支架|背板|延長線|轉接卡|轉接|水冷頭|風扇|燈條|線材|擴充卡|底座|護板|清潔|測試片?|架$|延長線?",
    re.I,
)


def parse_coolpc(html: str) -> dict:
    """解析原價屋 evaluate.php → {category: [(desc, price)]}。只取零件分類、去配件、價格防呆。"""
    out = {}
    for nm, cat in COOLPC_CATS.items():
        m = re.search(r'<select\b[^>]*name="?%s"?[^>]*>(.*?)</select>' % nm, html, re.I | re.S)
        if not m:
            continue
        items = []
        for o in re.findall(r"<option[^>]*>([^<]*)</option>", m.group(1), re.I):
            o = re.sub(r"&#x[0-9a-fA-F]+;|&\w+;", " ", o).strip()
            mm = re.match(r"^(.*?),\s*\$(\d[\d,]*)", o)
            if not mm:
                continue
            desc, price = mm.group(1).strip(), int(mm.group(2).replace(",", ""))
            if not (500 <= price <= 200000):
                continue
            if COOLPC_ACCESSORY.search(desc):
                continue
            items.append((desc, price))
        out[cat] = items
    return out


def fetch_coolpc_html() -> str:
    """抓原價屋報價單（匿名可抓、Big5/cp950 編碼）。"""
    req = urllib.request.Request(
        COOLPC_URL,
        headers={"User-Agent": BaseScraper.HEADERS["User-Agent"], "Accept-Encoding": "identity"},
    )
    return urllib.request.urlopen(req, timeout=30).read().decode("cp950", "ignore")


def scrape_coolpc_to_db(db: "Database") -> int:
    """抓原價屋報價單，比對 PARTS_DB，命中型號的新品價以 source=原價屋 寫入 listings。
    原價屋列入 REFERENCE_SOURCES（不計二手），供 get_detail 當權威『目前全新行情』。
    匿名可抓、無 captcha → 可納入每日排程自動更新。"""
    try:
        html = fetch_coolpc_html()
    except Exception as e:
        print(f"[原價屋] 抓取失敗：{e}")
        return 0
    parsed = parse_coolpc(html)
    today = datetime.now().strftime("%Y-%m-%d")
    db.conn.execute("DELETE FROM listings WHERE source=? AND date=?", (COOLPC_SOURCE, today))
    n = 0
    for cat, subs in PARTS_DB.items():
        items = parsed.get(cat, [])
        if not items:
            continue
        for parts in subs.values():
            for part in parts:
                for desc, price in items:
                    if title_matches_part(desc, part) and not is_cross_model_gpu(desc, part):
                        db.save_listing(Listing(
                            source=COOLPC_SOURCE, part_id=part["id"], title=desc,
                            price=price, condition="全新", url="", location="",
                            date=today, sold=False))
                        n += 1
    db.conn.commit()
    print(f"[原價屋] 寫入 {n} 筆新品報價（{today}）")
    return n


def coolpc_new_price(db: "Database", part_id: str, days: int = 14) -> int:
    """某零件的原價屋『目前全新行情』：近 days 天原價屋報價的去極值均價；無則 None。"""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = db.conn.execute(
        "SELECT price FROM listings WHERE part_id=? AND source=? AND date>=?",
        (part_id, COOLPC_SOURCE, since)).fetchall()
    return robust_price_stats([r[0] for r in rows])[0] if rows else None


def _shopee_new_prices_rows(rows, part) -> list:
    """從 (title, price) 列挑出蝦皮『全新』賣文價（去跨型號；用 classify_listing 含 default_new）。"""
    dn = part_default_new(part["id"]) if part else False
    return [p for (t, p) in rows
            if not is_cross_model_gpu(t or "", part)
            and classify_listing(t or "", p, None, dn) == "new"]


def compute_new_now(db: "Database", part_id: str) -> tuple:
    """目前全新行情（滾動視窗）：優先原價屋（近 14 天），無則蝦皮『全新』賣文（近 30 天，≥3 筆）。
    回傳 (price, cnt, src)；無資料回 (None, 0, None)。供 get_detail 與每日快照共用。"""
    cp = coolpc_new_price(db, part_id)
    if cp:
        since14 = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        cnt = db.conn.execute(
            "SELECT COUNT(*) FROM listings WHERE part_id=? AND source=? AND date>=?",
            (part_id, COOLPC_SOURCE, since14)).fetchone()[0]
        return cp, cnt, "原價屋"
    since30 = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    refb = list(REFERENCE_SOURCES)
    phb = ",".join("?" * len(refb)) if refb else "''"
    rows = db.conn.execute(
        f"SELECT title, price FROM listings WHERE part_id=? AND date>=? AND source NOT IN ({phb})",
        [part_id, since30, *refb]).fetchall()
    np = _shopee_new_prices_rows(rows, find_part(part_id))
    if len(np) >= 3:
        return robust_price_stats(np)[0], len(np), "蝦皮"
    return None, 0, None


def new_price_on_date(db: "Database", part_id: str, date: str) -> tuple:
    """某零件『某一天』的全新行情：當天原價屋報價優先，否則當天蝦皮全新賣文（≥3 筆）。
    供 rebuild_new_snapshots 回填每日新品價歷史。回傳 (price, cnt, src) 或 (None, 0, None)。"""
    cp_rows = db.conn.execute(
        "SELECT price FROM listings WHERE part_id=? AND source=? AND date=?",
        (part_id, COOLPC_SOURCE, date)).fetchall()
    if cp_rows:
        return robust_price_stats([r[0] for r in cp_rows])[0], len(cp_rows), "原價屋"
    rows = db.conn.execute(
        "SELECT title, price FROM listings WHERE part_id=? AND date=? AND source NOT IN (?, ?)",
        (part_id, date, EBAY_SOURCE, COOLPC_SOURCE)).fetchall()
    np = _shopee_new_prices_rows(rows, find_part(part_id))
    if len(np) >= 3:
        return robust_price_stats(np)[0], len(np), "蝦皮"
    return None, 0, None


def rebuild_new_snapshots(db: "Database") -> int:
    """回填/更新『目前全新行情』每日快照：掃 listings 中每個 (零件, 日期)（排除 eBay），
    用 new_price_on_date 算當日新品價並寫入 new_snapshots。原價屋每日刷新 → 曲線逐日累積。"""
    rows = db.conn.execute(
        "SELECT DISTINCT part_id, date FROM listings WHERE source<>?", (EBAY_SOURCE,)).fetchall()
    n = 0
    for pid, date in rows:
        price, cnt, src = new_price_on_date(db, pid, date)
        if price:
            db.save_new_snapshot(pid, date, price, src, cnt)
            n += 1
    return n


def prune_by_retention(db: "Database") -> int:
    """依保留策略清除過舊的 listings：對 DB 中現有的每個來源，
    用 SOURCE_RETENTION 指定的天數，未指定者用 DEFAULT_RETENTION_DAYS（365）。
    回傳清除總筆數。爬蟲與匯入後皆呼叫，確保各來源舊資料都會自動過期。"""
    sources = [r[0] for r in db.conn.execute(
        "SELECT DISTINCT source FROM listings").fetchall()]
    total = 0
    for src in sources:
        days = SOURCE_RETENTION.get(src, DEFAULT_RETENTION_DAYS)
        removed = db.prune_old_listings(src, days)
        if removed:
            print(f"[保留策略] {src} 清除 {removed} 筆逾 {days} 天資料")
        total += removed
    return total


def robust_price_stats(prices: list) -> tuple:
    """以 IQR 1.5 倍柵欄剔除離群值後，回傳 (avg, min, max, used_count)。
    二手賣文常混入整機/配件/多型號並列等極端價，純平均會被拉歪 → 改用去極值統計。
    樣本太少（<4）時不修剪，直接用原始值。"""
    xs = sorted(prices)
    n = len(xs)
    if n < 4:
        return (int(round(sum(xs) / n)), xs[0], xs[-1], n)
    q1, _, q3 = statistics.quantiles(xs, n=4)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    kept = [x for x in xs if lo <= x <= hi] or xs
    return (int(round(sum(kept) / len(kept))), min(kept), max(kept), len(kept))


def rebuild_today_snapshots(db: "Database") -> int:
    """依「今日所有來源」的成交資料重算各零件均價快照（排除海外參考價，如 eBay）。
    爬蟲與匯入皆呼叫，確保快照反映當天 PTT＋蝦皮匯入等所有真實資料（而非單一來源）。
    均價/最高/最低皆以 robust_price_stats 去極值後計算，避免整機/配件污染。
    **二手分流（#2）**：明確全新的賣文（title_is_new）不計入二手快照，避免新品（尤其
    AI 飆漲的當代卡/記憶體）把二手均價墊高。某零件當天若只有全新賣文 → 當天不產生二手快照。"""
    today = datetime.now().strftime("%Y-%m-%d")
    ref = list(REFERENCE_SOURCES)
    ph = ",".join("?" * len(ref)) if ref else "''"
    rows = db.conn.execute(
        f"SELECT part_id, title, price, source FROM listings "
        f"WHERE date>=? AND source NOT IN ({ph})",
        [today] + ref
    ).fetchall()
    by_part = {}
    for pid, title, price, src in rows:
        # 跨型號/賣場清單賣文（顯卡）→ 非單卡價，整筆剔除
        if is_cross_model_gpu(title, find_part(pid)):
            continue
        d = by_part.setdefault(pid, {"rows": [], "sources": set()})
        d["rows"].append((title, price, src))
        d["sources"].add(src)
    n = 0
    for pid, d in by_part.items():
        nref = part_new_ref(db, pid)   # 目前全新行情參考價（價格天花板，剔除無成色零售全新）
        # 二手快照不套 default_new（否則 RAM 全歸全新→無二手→整顆消失）；只用價格天花板。
        used_rows = [(t, p, s) for (t, p, s) in d["rows"]
                     if classify_listing(t, p, nref) == "used"]
        if not used_rows:   # 當天只有全新賣文 → 無二手成交，不寫快照
            continue
        avg, mn, mx, _u = robust_price_stats([p for (t, p, s) in used_rows])
        db.save_snapshot(PriceSnapshot(
            part_id=pid, date=today, avg_price=avg,
            min_price=mn, max_price=mx, listing_count=len(used_rows),
            sources=sorted({s for (t, p, s) in used_rows})))
        n += 1
    return n


# ─────────────────────────────────────────────────
# 爬蟲調度器
# ─────────────────────────────────────────────────

class CrawlerScheduler:
    def __init__(self, db: Database):
        self.db = db

    def _flatten_parts(self, category_filter: list[str] = None) -> list[dict]:
        """展開所有零件為平面列表"""
        flat = []
        for cat, subcats in PARTS_DB.items():
            if category_filter and cat not in category_filter:
                continue
            for subcat, parts in subcats.items():
                for part in parts:
                    part_copy = {**part, "category": cat, "subcat": subcat}
                    flat.append(part_copy)
        return flat

    async def run(self, category_filter: list[str] = None, max_concurrent: int = 3):
        """主爬蟲流程"""
        parts = self._flatten_parts(category_filter)
        print(f"[調度器] 開始爬蟲，共 {len(parts)} 個零件")

        connector = aiohttp.TCPConnector(limit=max_concurrent, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            # 自動爬蟲跑 PTT（hardwaresale，匿名可爬）。
            # 蝦皮匿名被擋(403)→改匯入式；FB 需登入→匯入式；皆不在自動清單。露天/巴哈已移除。
            scrapers = [
                PTTScraper(session, self.db),
            ]
            # eBay 海外參考價：有設定金鑰才啟用（Browse API、官方合規、USD→TWD、不計入台灣均價）
            ebay = EbayScraper(session, self.db)
            if ebay.enabled:
                scrapers.append(ebay)
                print(f"[調度器] eBay 海外參考價已啟用（{ebay.marketplace}，匯率 {ebay.rate}）")

            sem = asyncio.Semaphore(max_concurrent)

            async def scrape_one(part):
                async with sem:
                    all_listings = []
                    for scraper in scrapers:
                        t0 = time.time()
                        try:
                            result = await scraper.scrape_part(part)
                            all_listings.extend(result)
                            for l in result:
                                self.db.save_listing(l)
                            print(f"  [{scraper.name}] {part['name']} → {len(result)} 筆")
                        except Exception as e:
                            print(f"  [{scraper.name}] {part['name']} 錯誤: {e}")

                    # 計算今日均價快照（排除海外參考價來源如 eBay；去極值、來源亦排除參考源）
                    # 二手分流（#2）：明確全新賣文不計入二手快照，避免新品墊高二手均價。
                    if all_listings:
                        local = [l for l in all_listings
                                 if not l.sold and l.source not in REFERENCE_SOURCES
                                 and not is_cross_model_gpu(l.title or "", part)]
                        nref = part_new_ref(self.db, part["id"])
                        used = [l for l in local
                                if classify_listing(l.title or "", l.price, nref) == "used"]
                        if used:
                            avg, mn, mx, _ = robust_price_stats([l.price for l in used])
                            snap = PriceSnapshot(
                                part_id       = part["id"],
                                date          = datetime.now().strftime("%Y-%m-%d"),
                                avg_price     = avg,
                                min_price     = mn,
                                max_price     = mx,
                                listing_count = len(used),
                                sources       = sorted({l.source for l in used}),
                            )
                            self.db.save_snapshot(snap)

            await asyncio.gather(*[scrape_one(p) for p in parts])

        # 原價屋新品報價（匿名可抓、無 captcha）→ 權威「目前全新行情」來源
        scrape_coolpc_to_db(self.db)

        # 套用保留策略 + 依今日所有來源（PTT＋當天匯入的蝦皮等）重算均價快照
        prune_by_retention(self.db)
        rebuild_today_snapshots(self.db)
        rebuild_new_snapshots(self.db)   # 累積『目前全新行情』每日快照（新品價曲線）

        print("[調度器] 爬蟲完成！")


# ─────────────────────────────────────────────────
# 報表輸出
# ─────────────────────────────────────────────────

class Reporter:
    def __init__(self, db: Database):
        self.db = db

    def get_summary(self, part_id: str, days: int = 365) -> dict:
        history = self.db.get_price_history(part_id, days)
        today   = self.db.get_today_listings(part_id)

        if not history:
            return {}

        last   = history[-1]
        prices = [h["avg"] for h in history]

        # 找對應零件
        part_info = None
        for cat_data in PARTS_DB.values():
            for subcat_data in cat_data.values():
                for p in subcat_data:
                    if p["id"] == part_id:
                        part_info = p
                        break

        new_price = part_info["new_price"] if part_info else 0
        diff_pct  = ((last["avg"] - new_price) / new_price * 100) if new_price > 0 else None

        return {
            "part_id":    part_id,
            "part_name":  part_info["name"] if part_info else part_id,
            "new_price":  new_price,
            "today_avg":  last["avg"],
            "today_min":  last["min"],
            "today_max":  last["max"],
            "diff_pct":   round(diff_pct, 1) if diff_pct else None,
            "listings_today": len(today),
            "price_1y":   prices,
            "price_6m":   prices[-180:],
            "price_3m":   prices[-90:],
            "price_1m":   prices[-30:],
            "price_1w":   prices[-7:],
        }

    def _find_part(self, part_id: str):
        return find_part(part_id)

    def get_detail(self, part_id: str) -> dict:
        """產生前端 detail panel 所需的完整資料（含歷史、來源分布、成交明細）。
        無任何歷史資料時回傳 None。"""
        history = self.db.get_price_history(part_id, 365)
        if not history:
            return None

        prices = [h["avg"] for h in history]
        mins   = [h["min"] for h in history]
        maxs   = [h["max"] for h in history]
        last = history[-1]
        # 二手頭條數字平滑：取近 14 個快照的中位數，避免「蝦皮匯入日 vs PTT 日」單日跳動
        # （PTT 每日、蝦皮偶爾匯入 → 頻繁的 PTT 值主導中位數，單一匯入日不會綁架頭條）。
        # 圖表仍畫每日真實序列；只有頭條卡用平滑值。
        recent = [h["avg"] for h in history[-14:]]
        used_now = int(round(statistics.median(recent))) if recent else last["avg"]
        part = self._find_part(part_id)
        new_price = part["new_price"] if part else 0
        diff_pct = round((used_now - new_price) / new_price * 100, 1) if new_price > 0 else None

        # 抓較多筆（含跨型號雜訊），剔除顯卡跨型號/賣場清單後取前 12 筆呈現
        listings = [l for l in self.db.get_recent_listings(part_id, days=7, limit=40)
                    if not is_cross_model_gpu(l.get("title") or "", part)][:12]
        # 二手分流：以與二手均價相同的規則（含價格天花板）標記全新；
        # 來源分布只計二手筆數/均價，與二手均價的組成一致（全新另由 new_now 呈現）。
        nref = part_new_ref(self.db, part_id)
        dn = part_default_new(part_id)
        for lst in listings:
            # is_new 標記與二手快照同規則（不套 default_new，只用天花板）→ 標記=被排除於二手者
            cls = classify_listing(lst.get("title") or "", lst.get("price") or 0, nref)
            lst["_cls"] = cls
            lst["is_new"] = (cls == "new")

        # 依來源彙整（只計『二手』，全新與剔除項皆不算入二手均價/筆數）
        agg = {}
        for lst in listings:
            if lst["_cls"] != "used":
                continue
            a = agg.setdefault(lst["source"], {"name": lst["source"], "count": 0, "_sum": 0})
            a["count"] += 1
            a["_sum"] += lst["price"]
        sources = [{"name": a["name"], "count": a["count"],
                    "avg": round(a["_sum"] / a["count"])} for a in agg.values()]

        # 海外參考線（eBay）：近 30 天掛牌去極值算單一參考值（TWD）。只取 eBay，與原價屋分開。
        ebay_ref = None
        since30 = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        eb_rows = self.db.conn.execute(
            "SELECT price FROM listings WHERE part_id=? AND date>=? AND source=?",
            [part_id, since30, EBAY_SOURCE]).fetchall()
        if eb_rows:
            ebay_ref = robust_price_stats([r[0] for r in eb_rows])[0]

        # 目前全新行情（滾動值）：優先原價屋、無則蝦皮全新賣文（見 compute_new_now）。
        new_now, new_count, new_now_src = compute_new_now(self.db, part_id)

        # 新品價歷史曲線：對齊二手 history 的日期（carry-forward 補空），讓圖表可疊「新品線」。
        # new_snapshots 由 rebuild_new_snapshots 每日累積（原價屋每天刷新→曲線逐日成形）。
        nh = self.db.get_new_history(part_id, 365)
        used_dates = [h["date"] for h in history]
        new_series, j, cur = [], 0, None
        for d in used_dates:
            while j < len(nh) and nh[j]["date"] <= d:
                cur = nh[j]["new"]
                j += 1
            new_series.append(cur)
        # 末點固定為當前權威 new_now（二手歷史日期可能落後今日 → 否則曲線到不了「今日」最新價）
        if new_now and new_series:
            new_series[-1] = new_now

        # 二手相對「目前全新行情」的折價（買二手比買現貨全新省多少 %）。
        # 與 diff_pct（相對上市價的折舊）不同：此項反映 AI 飆漲下「現在新品多貴」。
        diff_now_pct = round((used_now - new_now) / new_now * 100, 1) if new_now else None

        return {
            "id":         part_id,
            "name":       part["name"] if part else part_id,
            "new_price":  new_price,
            "used":       used_now,
            "ebay_ref":   ebay_ref,
            "new_now":    new_now,
            "new_count":  new_count,
            "new_now_src": new_now_src,
            "diff_now_pct": diff_now_pct,
            "used_min":   last["min"],
            "used_max":   last["max"],
            "diff_pct":   diff_pct,
            "listings_count": last["count"],
            "history": {
                "1w": prices[-7:],   "1m": prices[-30:],  "3m": prices[-90:],
                "6m": prices[-180:], "1y": prices,
            },
            # 最高/最低區間（與 history 同結構，供圖表畫陰影帶；待辦 #11）
            "history_min": {
                "1w": mins[-7:],   "1m": mins[-30:],  "3m": mins[-90:],
                "6m": mins[-180:], "1y": mins,
            },
            "history_max": {
                "1w": maxs[-7:],   "1m": maxs[-30:],  "3m": maxs[-90:],
                "6m": maxs[-180:], "1y": maxs,
            },
            # 目前全新行情歷史（與 history 同結構、同日期對齊）：供圖表疊「新品價」線
            "new_history": {
                "1w": new_series[-7:],   "1m": new_series[-30:],  "3m": new_series[-90:],
                "6m": new_series[-180:], "1y": new_series,
            },
            "sources":  sources,
            "listings": listings,
        }

    @staticmethod
    def _sanitize_public(detail: dict) -> dict:
        """公開版去識別：移除每筆掛牌的賣家連結(url)與地區(location)，僅留 來源/標題/價格/日期。
        彙總統計（sources/history/ebay_ref）維持不變。供公開靜態站使用，降低條款/個資風險。"""
        d = dict(detail)
        d["listings"] = [{"source": l.get("source"), "title": l.get("title", ""),
                          "price": l.get("price"), "date": l.get("date", ""),
                          "is_new": l.get("is_new", False)}
                         for l in detail.get("listings", [])]
        return d

    def build_report(self, public: bool = False) -> dict:
        """攤平成 {part_id: detail}，供 API / 靜態檔輸出。public=True 會去識別（隱賣家連結/地區）。"""
        report = {}
        for cat_data in PARTS_DB.values():
            for parts in cat_data.values():
                for part in parts:
                    detail = self.get_detail(part["id"])
                    if not detail:
                        continue
                    report[part["id"]] = self._sanitize_public(detail) if public else detail
        return report

    def export_public_json(self, output_path: str = "report.json") -> int:
        """輸出『公開靜態站』用的扁平報表（去識別、壓縮）。前端 API 連不到時會改抓此檔。
        另附 `_meta.generated_at`（產生時間）供前端顯示「資料更新於…」。"""
        report = self.build_report(public=True)
        n = len(report)
        report["_meta"] = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, separators=(",", ":"))
        print(f"[公開報表] 已輸出 {n} 項至 {output_path}")
        return n

    def export_json(self, output_path: str = "price_report.json"):
        report = {}
        for cat, subcats in PARTS_DB.items():
            report[cat] = {}
            for subcat, parts in subcats.items():
                report[cat][subcat] = []
                for part in parts:
                    summary = self.get_summary(part["id"])
                    report[cat][subcat].append(summary)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"[報表] 已輸出至 {output_path}")


# ─────────────────────────────────────────────────
# 主程式進入點
# ─────────────────────────────────────────────────

async def main():
    # 可由命令列指定分類：python pc_scraper_backend.py gpu cpu
    # 留空 = 全部分類
    cats = sys.argv[1:] or None
    db = Database("pc_prices.db")
    scheduler = CrawlerScheduler(db)
    await scheduler.run(category_filter=cats, max_concurrent=2)

    reporter = Reporter(db)
    reporter.export_json("price_report.json")       # 舊版巢狀格式（保留）
    reporter.export_public_json("report.json")      # 公開靜態站用（扁平、去識別）
    print(f"[完成] 爬取分類 = {cats or '全部'}")


if __name__ == "__main__":
    # 安裝依賴：
    # pip install aiohttp beautifulsoup4 lxml
    asyncio.run(main())
