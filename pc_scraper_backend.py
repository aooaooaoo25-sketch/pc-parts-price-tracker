"""
PC 零件二手市場價格爬蟲後端系統
支援平台：露天拍賣、蝦皮購物、PTT BuyTrade/電腦版、巴哈姆特、591電腦板
"""

import asyncio
import aiohttp
import json
import re
import time
import random
import sqlite3
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import Optional
from pathlib import Path
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup


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
    # ── CPU ──────────────────────────────────────
    "cpu": {
        "intel_14": [
            {"id":"cpu_i9_14900k", "name":"Intel Core i9-14900K",    "aliases":["i9-14900K","14900K"],             "new_price":15900, "socket":"LGA1700"},
            {"id":"cpu_i7_14700k", "name":"Intel Core i7-14700K",    "aliases":["i7-14700K","14700K"],             "new_price":11900, "socket":"LGA1700"},
            {"id":"cpu_i5_14600k", "name":"Intel Core i5-14600K",    "aliases":["i5-14600K","14600K"],             "new_price":8500,  "socket":"LGA1700"},
            {"id":"cpu_i5_14400f", "name":"Intel Core i5-14400F",    "aliases":["i5-14400F","14400F"],             "new_price":5900,  "socket":"LGA1700"},
        ],
        "intel_13": [
            {"id":"cpu_i9_13900k", "name":"Intel Core i9-13900K",    "aliases":["i9-13900K","13900K"],             "new_price":14200, "socket":"LGA1700"},
            {"id":"cpu_i7_13700k", "name":"Intel Core i7-13700K",    "aliases":["i7-13700K","13700K"],             "new_price":10800, "socket":"LGA1700"},
            {"id":"cpu_i5_13600k", "name":"Intel Core i5-13600K",    "aliases":["i5-13600K","13600K"],             "new_price":7800,  "socket":"LGA1700"},
            {"id":"cpu_i5_13400f", "name":"Intel Core i5-13400F",    "aliases":["i5-13400F","13400F"],             "new_price":4800,  "socket":"LGA1700"},
        ],
        "intel_12": [
            {"id":"cpu_i9_12900k", "name":"Intel Core i9-12900K",    "aliases":["i9-12900K","12900K"],             "new_price":0,     "socket":"LGA1700"},
            {"id":"cpu_i7_12700k", "name":"Intel Core i7-12700K",    "aliases":["i7-12700K","12700K"],             "new_price":0,     "socket":"LGA1700"},
            {"id":"cpu_i5_12600k", "name":"Intel Core i5-12600K",    "aliases":["i5-12600K","12600K"],             "new_price":0,     "socket":"LGA1700"},
        ],
        "amd_7000": [
            {"id":"cpu_r9_7950x",  "name":"AMD Ryzen 9 7950X",       "aliases":["R9 7950X","7950X"],               "new_price":18500, "socket":"AM5"},
            {"id":"cpu_r9_7900x",  "name":"AMD Ryzen 9 7900X",       "aliases":["R9 7900X","7900X"],               "new_price":13500, "socket":"AM5"},
            {"id":"cpu_r7_7700x",  "name":"AMD Ryzen 7 7700X",       "aliases":["R7 7700X","7700X"],               "new_price":8900,  "socket":"AM5"},
            {"id":"cpu_r5_7600x",  "name":"AMD Ryzen 5 7600X",       "aliases":["R5 7600X","7600X"],               "new_price":6500,  "socket":"AM5"},
            {"id":"cpu_r5_7600",   "name":"AMD Ryzen 5 7600",        "aliases":["R5 7600","Ryzen 5 7600"],         "new_price":5800,  "socket":"AM5"},
        ],
        "amd_5000": [
            {"id":"cpu_r9_5950x",  "name":"AMD Ryzen 9 5950X",       "aliases":["R9 5950X","5950X"],               "new_price":0,     "socket":"AM4"},
            {"id":"cpu_r9_5900x",  "name":"AMD Ryzen 9 5900X",       "aliases":["R9 5900X","5900X"],               "new_price":0,     "socket":"AM4"},
            {"id":"cpu_r7_5800x3d","name":"AMD Ryzen 7 5800X3D",     "aliases":["R7 5800X3D","5800X3D"],          "new_price":0,     "socket":"AM4"},
            {"id":"cpu_r5_5600x",  "name":"AMD Ryzen 5 5600X",       "aliases":["R5 5600X","5600X"],               "new_price":4800,  "socket":"AM4"},
            {"id":"cpu_r5_5600",   "name":"AMD Ryzen 5 5600",        "aliases":["R5 5600"],                        "new_price":3800,  "socket":"AM4"},
        ],
    },

    # ── GPU ──────────────────────────────────────
    "gpu": {
        "nvidia_40": [
            {"id":"gpu_4090",        "name":"NVIDIA GeForce RTX 4090",      "aliases":["RTX 4090","4090"],           "new_price":59900, "vram":"24GB"},
            {"id":"gpu_4080s",       "name":"NVIDIA GeForce RTX 4080 SUPER", "aliases":["RTX 4080S","4080 SUPER"],   "new_price":36900, "vram":"16GB"},
            {"id":"gpu_4080",        "name":"NVIDIA GeForce RTX 4080",      "aliases":["RTX 4080","4080"],           "new_price":33900, "vram":"16GB"},
            {"id":"gpu_4070tis",     "name":"NVIDIA GeForce RTX 4070 Ti SUPER","aliases":["RTX 4070Ti Super","4070Ti Super"],"new_price":26900,"vram":"16GB"},
            {"id":"gpu_4070ti",      "name":"NVIDIA GeForce RTX 4070 Ti",   "aliases":["RTX 4070Ti","4070Ti"],       "new_price":23900, "vram":"12GB"},
            {"id":"gpu_4070s",       "name":"NVIDIA GeForce RTX 4070 SUPER","aliases":["RTX 4070S","4070 Super"],    "new_price":19900, "vram":"12GB"},
            {"id":"gpu_4070",        "name":"NVIDIA GeForce RTX 4070",      "aliases":["RTX 4070","4070"],           "new_price":17900, "vram":"12GB"},
            {"id":"gpu_4060ti_16g",  "name":"NVIDIA GeForce RTX 4060 Ti 16G","aliases":["RTX 4060Ti 16G","4060Ti 16GB"],"new_price":14900,"vram":"16GB"},
            {"id":"gpu_4060ti",      "name":"NVIDIA GeForce RTX 4060 Ti",   "aliases":["RTX 4060Ti","4060Ti"],       "new_price":12900, "vram":"8GB"},
            {"id":"gpu_4060",        "name":"NVIDIA GeForce RTX 4060",      "aliases":["RTX 4060","4060"],           "new_price":9900,  "vram":"8GB"},
        ],
        "nvidia_30": [
            {"id":"gpu_3090ti",      "name":"NVIDIA GeForce RTX 3090 Ti",   "aliases":["RTX 3090Ti","3090Ti"],       "new_price":0,     "vram":"24GB"},
            {"id":"gpu_3090",        "name":"NVIDIA GeForce RTX 3090",      "aliases":["RTX 3090","3090"],           "new_price":0,     "vram":"24GB"},
            {"id":"gpu_3080_12g",    "name":"NVIDIA GeForce RTX 3080 12GB", "aliases":["RTX 3080 12G","3080 12GB"],  "new_price":0,     "vram":"12GB"},
            {"id":"gpu_3080",        "name":"NVIDIA GeForce RTX 3080",      "aliases":["RTX 3080 10G","3080 10GB"],  "new_price":0,     "vram":"10GB"},
            {"id":"gpu_3070ti",      "name":"NVIDIA GeForce RTX 3070 Ti",   "aliases":["RTX 3070Ti","3070Ti"],       "new_price":0,     "vram":"8GB"},
            {"id":"gpu_3070",        "name":"NVIDIA GeForce RTX 3070",      "aliases":["RTX 3070","3070"],           "new_price":0,     "vram":"8GB"},
            {"id":"gpu_3060ti",      "name":"NVIDIA GeForce RTX 3060 Ti",   "aliases":["RTX 3060Ti","3060Ti"],       "new_price":0,     "vram":"8GB"},
            {"id":"gpu_3060",        "name":"NVIDIA GeForce RTX 3060",      "aliases":["RTX 3060","3060"],           "new_price":0,     "vram":"12GB"},
        ],
        "amd_7000": [
            {"id":"gpu_rx7900xtx",   "name":"AMD Radeon RX 7900 XTX",       "aliases":["RX 7900XTX","7900XTX"],     "new_price":29900, "vram":"24GB"},
            {"id":"gpu_rx7900xt",    "name":"AMD Radeon RX 7900 XT",        "aliases":["RX 7900XT","7900XT"],       "new_price":24900, "vram":"20GB"},
            {"id":"gpu_rx7800xt",    "name":"AMD Radeon RX 7800 XT",        "aliases":["RX 7800XT","7800XT"],       "new_price":15900, "vram":"16GB"},
            {"id":"gpu_rx7700xt",    "name":"AMD Radeon RX 7700 XT",        "aliases":["RX 7700XT","7700XT"],       "new_price":13900, "vram":"12GB"},
            {"id":"gpu_rx7600",      "name":"AMD Radeon RX 7600",           "aliases":["RX 7600"],                  "new_price":8900,  "vram":"8GB"},
        ],
    },

    # ── RAM ──────────────────────────────────────
    "ram": {
        "ddr5": [
            {"id":"ram_ddr5_6000_32","name":"DDR5-6000 32GB (16GBx2)","aliases":["DDR5 6000 32GB","DDR5-6000"],"new_price":4800,"type":"DDR5"},
            {"id":"ram_ddr5_5600_32","name":"DDR5-5600 32GB (16GBx2)","aliases":["DDR5 5600 32GB"],             "new_price":3600,"type":"DDR5"},
            {"id":"ram_ddr5_5200_32","name":"DDR5-5200 32GB (16GBx2)","aliases":["DDR5 5200 32GB"],             "new_price":3200,"type":"DDR5"},
            {"id":"ram_ddr5_4800_16","name":"DDR5-4800 16GB (8GBx2)", "aliases":["DDR5 4800 16GB"],             "new_price":1800,"type":"DDR5"},
        ],
        "ddr4": [
            {"id":"ram_ddr4_3600_32","name":"DDR4-3600 32GB (16GBx2)","aliases":["DDR4 3600 32GB"],             "new_price":2400,"type":"DDR4"},
            {"id":"ram_ddr4_3200_32","name":"DDR4-3200 32GB (16GBx2)","aliases":["DDR4 3200 32GB"],             "new_price":2200,"type":"DDR4"},
            {"id":"ram_ddr4_3200_16","name":"DDR4-3200 16GB (8GBx2)", "aliases":["DDR4 3200 16GB"],             "new_price":1600,"type":"DDR4"},
            {"id":"ram_ddr4_2666_16","name":"DDR4-2666 16GB (8GBx2)", "aliases":["DDR4 2666 16GB"],             "new_price":1200,"type":"DDR4"},
        ],
    },

    # ── 主機板 ────────────────────────────────────
    "motherboard": {
        "intel_z790": [
            {"id":"mb_rog_z790_hero",  "name":"ASUS ROG Maximus Z790 Hero",   "aliases":["Z790 Hero","ROG Z790"],    "new_price":18500,"socket":"LGA1700"},
            {"id":"mb_msi_z790_ace",   "name":"MSI MEG Z790 ACE",             "aliases":["Z790 ACE","MEG Z790"],     "new_price":15900,"socket":"LGA1700"},
            {"id":"mb_giga_z790_aorus","name":"Gigabyte Z790 AORUS Master",   "aliases":["Z790 AORUS","Z790 Master"],"new_price":14500,"socket":"LGA1700"},
        ],
        "amd_x670": [
            {"id":"mb_rog_x670e_hero", "name":"ASUS ROG Crosshair X670E Hero","aliases":["X670E Hero"],              "new_price":17800,"socket":"AM5"},
            {"id":"mb_msi_x670e_tom",  "name":"MSI MAG X670E Tomahawk",       "aliases":["X670E Tomahawk"],          "new_price":9800, "socket":"AM5"},
        ],
        "intel_b660": [
            {"id":"mb_asus_b660m",     "name":"ASUS Prime B660M-A",           "aliases":["B660M-A","ASUS B660M"],    "new_price":4200, "socket":"LGA1700"},
            {"id":"mb_msi_b660",       "name":"MSI MAG B660M Mortar",         "aliases":["B660M Mortar"],            "new_price":3800, "socket":"LGA1700"},
        ],
    },

    # ── SSD ──────────────────────────────────────
    "ssd": {
        "nvme_pcie5": [
            {"id":"ssd_crucial_t705_2t","name":"Crucial T705 2TB NVMe PCIe5","aliases":["T705 2TB","Crucial T705"], "new_price":8200,"interface":"PCIe 5.0"},
            {"id":"ssd_wd_sn850x_2t",   "name":"WD Black SN850X 2TB",        "aliases":["SN850X 2TB","WD SN850X"], "new_price":4800,"interface":"PCIe 4.0"},
        ],
        "nvme_pcie4": [
            {"id":"ssd_samsung_990_2t", "name":"Samsung 990 Pro 2TB",         "aliases":["990 Pro 2TB","990Pro"],   "new_price":5500,"interface":"PCIe 4.0"},
            {"id":"ssd_samsung_990_1t", "name":"Samsung 990 Pro 1TB",         "aliases":["990 Pro 1TB"],            "new_price":3200,"interface":"PCIe 4.0"},
            {"id":"ssd_wd_sn580_1t",    "name":"WD Blue SN580 1TB",           "aliases":["SN580 1TB"],              "new_price":2200,"interface":"PCIe 4.0"},
            {"id":"ssd_kingston_kc3000","name":"Kingston KC3000 2TB",         "aliases":["KC3000 2TB"],             "new_price":4500,"interface":"PCIe 4.0"},
        ],
        "sata": [
            {"id":"ssd_samsung_870_4t", "name":"Samsung 870 EVO 4TB SATA",   "aliases":["870 EVO 4TB"],            "new_price":7200,"interface":"SATA"},
            {"id":"ssd_samsung_870_2t", "name":"Samsung 870 EVO 2TB SATA",   "aliases":["870 EVO 2TB"],            "new_price":3800,"interface":"SATA"},
            {"id":"ssd_crucial_mx500",  "name":"Crucial MX500 1TB SATA",     "aliases":["MX500 1TB"],              "new_price":1800,"interface":"SATA"},
        ],
    },

    # ── HDD ──────────────────────────────────────
    "hdd": {
        "seagate": [
            {"id":"hdd_sg_ironwolf_20t","name":"Seagate IronWolf Pro 20TB",  "aliases":["IronWolf 20TB"],          "new_price":16500,"rpm":"7200"},
            {"id":"hdd_sg_barra_8t",    "name":"Seagate Barracuda 8TB",      "aliases":["Barracuda 8TB"],          "new_price":4800, "rpm":"5400"},
            {"id":"hdd_sg_barra_4t",    "name":"Seagate Barracuda 4TB",      "aliases":["Barracuda 4TB"],          "new_price":2800, "rpm":"5400"},
        ],
        "wd": [
            {"id":"hdd_wd_red_12t",     "name":"WD Red Plus 12TB NAS",       "aliases":["WD Red 12TB"],            "new_price":8900,"rpm":"5400"},
            {"id":"hdd_wd_blue_4t",     "name":"WD Blue 4TB",                "aliases":["WD Blue 4TB"],            "new_price":3200,"rpm":"5400"},
        ],
    },

    # ── 電源 ──────────────────────────────────────
    "psu": {
        "1000w": [
            {"id":"psu_seasonic_px1000", "name":"Seasonic Vertex PX-1000",   "aliases":["PX-1000","Seasonic PX1000"], "new_price":6800,"watt":1000,"cert":"Platinum"},
            {"id":"psu_corsair_hx1000",  "name":"Corsair HX1000",            "aliases":["HX1000"],                    "new_price":5900,"watt":1000,"cert":"Platinum"},
        ],
        "850w": [
            {"id":"psu_asus_thor_850",   "name":"ASUS ROG Thor 850P2",        "aliases":["ROG Thor 850","Thor 850P2"], "new_price":6200,"watt":850,"cert":"Platinum"},
            {"id":"psu_bequiet_dp13_850","name":"be quiet! Dark Power 13 850W","aliases":["Dark Power 850W"],          "new_price":5800,"watt":850,"cert":"Titanium"},
        ],
        "750w": [
            {"id":"psu_seasonic_gx650",  "name":"Seasonic Focus GX-650",     "aliases":["GX-650","Focus GX 650"],     "new_price":3800,"watt":650,"cert":"Gold"},
            {"id":"psu_corsair_rm750x",  "name":"Corsair RM750x",            "aliases":["RM750x","RM750"],            "new_price":3500,"watt":750,"cert":"Gold"},
        ],
    },

    # ── 散熱 ──────────────────────────────────────
    "cooler": {
        "air": [
            {"id":"cool_noctua_nh_d15",  "name":"Noctua NH-D15 chromax.black","aliases":["NH-D15","NH D15"],          "new_price":3800,"type":"風冷"},
            {"id":"cool_bequiet_drp4",   "name":"be quiet! Dark Rock Pro 4",  "aliases":["Dark Rock Pro 4"],          "new_price":3200,"type":"風冷"},
            {"id":"cool_thermalright_pa","name":"Thermalright Peerless Assassin 120","aliases":["PA120","PA 120 SE"], "new_price":1200,"type":"風冷"},
        ],
        "aio": [
            {"id":"cool_asus_ryujin360", "name":"ASUS ROG Ryujin III 360",   "aliases":["Ryujin III 360","ROG 360"],  "new_price":9800,"type":"水冷"},
            {"id":"cool_corsair_h150i",  "name":"Corsair H150i ELITE XT",    "aliases":["H150i","Corsair H150"],      "new_price":7200,"type":"水冷"},
            {"id":"cool_corsair_h115i",  "name":"Corsair H115i RGB Platinum", "aliases":["H115i","Corsair H115"],     "new_price":5500,"type":"水冷"},
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
# 露天拍賣爬蟲
# ─────────────────────────────────────────────────

class LuTianScraper(BaseScraper):
    name = "露天拍賣"
    BASE_URL = "https://www.ruten.com.tw"

    async def scrape_part(self, part: dict) -> list[Listing]:
        listings = []
        for alias in part["aliases"][:2]:
            url = f"{self.BASE_URL}/find/?q={quote(alias)}&sort=prc%2Fasc&catg=11"
            html = await self.fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            # 露天商品卡片選擇器 (依實際頁面結構調整)
            cards = soup.select(".item-panel, .rt-grid-item, [data-item-id]")[:20]
            for card in cards:
                try:
                    title_el = card.select_one(".item-title, .rt-item-title, h3")
                    price_el = card.select_one(".price, .rt-price, .item-price")
                    link_el  = card.select_one("a[href]")

                    if not (title_el and price_el):
                        continue

                    price = self.clean_price(price_el.get_text())
                    if not price or price < 500 or price > 200000:
                        continue

                    href = link_el["href"] if link_el else ""
                    if href and not href.startswith("http"):
                        href = urljoin(self.BASE_URL, href)

                    title = title_el.get_text(strip=True)
                    # 過濾：確認標題包含零件關鍵字
                    if not any(a.lower() in title.lower() for a in part["aliases"]):
                        continue

                    listings.append(Listing(
                        source    = self.name,
                        part_id   = part["id"],
                        title     = title,
                        price     = price,
                        condition = self.guess_condition(title),
                        url       = href,
                        location  = "",
                        date      = datetime.now().strftime("%Y-%m-%d"),
                        sold      = False,
                    ))
                except Exception:
                    continue
        return listings


# ─────────────────────────────────────────────────
# 蝦皮購物爬蟲 (使用官方搜尋 API)
# ─────────────────────────────────────────────────

class ShopeeScraper(BaseScraper):
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

        items = data.get("items") or []
        for item in items:
            try:
                info = item.get("item_basic", item)
                raw_price = info.get("price", 0) // 100000  # 蝦皮價格單位為分*1000
                if raw_price < 500:
                    raw_price = info.get("price_min", 0) // 100000

                if raw_price < 500 or raw_price > 200000:
                    continue

                name  = info.get("name", "")
                shopid = info.get("shopid", "")
                itemid = info.get("itemid", "")
                url   = f"https://shopee.tw/product/{shopid}/{itemid}"
                sold  = info.get("sold", 0) > 0 or info.get("historical_sold", 0) > 0

                if not any(a.lower() in name.lower() for a in part["aliases"]):
                    continue

                listings.append(Listing(
                    source    = self.name,
                    part_id   = part["id"],
                    title     = name,
                    price     = raw_price,
                    condition = self.guess_condition(name),
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
    name = "PTT BuyTrade"
    BOARDS = ["BuyTrade", "PC_Shopping"]
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
                    # PTT 格式：[賣/WTS] [買/WTB]
                    if not re.search(r'\[賣|WTS|出售\]', title, re.I):
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
                        sold      = "[已售]" in title or "[sold]" in title.lower(),
                        raw_text  = text[:500],
                    ))
                except Exception:
                    continue
        return listings


# ─────────────────────────────────────────────────
# 巴哈姆特哈拉版/交易所爬蟲
# ─────────────────────────────────────────────────

class BahaScraper(BaseScraper):
    name = "巴哈姆特"
    BASE = "https://forum.gamer.com.tw"
    BOARD_ID = "C_115"  # 二手交易板

    async def scrape_part(self, part: dict) -> list[Listing]:
        listings = []
        keyword = part["aliases"][0]
        url = f"{self.BASE}/B.php?bsn={self.BOARD_ID}&q={quote(keyword)}&search=content"
        html = await self.fetch(url)
        if not html:
            return listings

        soup = BeautifulSoup(html, "html.parser")
        posts = soup.select(".b-list__row, .b-forum__title")[:15]

        for post in posts:
            try:
                link = post.select_one("a[href*='C.php']")
                if not link:
                    continue
                title = link.get_text(strip=True)
                href = urljoin(self.BASE, link["href"])

                post_html = await self.fetch(href)
                if not post_html:
                    continue
                post_soup = BeautifulSoup(post_html, "html.parser")
                content_el = post_soup.select_one(".c-article__content, .content")
                if not content_el:
                    continue

                text = content_el.get_text()
                price_match = re.search(r'(?:售價|叫價|賣出|\$|NT)[：:\s]*(\d{3,6})', text)
                if not price_match:
                    continue
                price = int(price_match.group(1))
                if price < 500 or price > 200000:
                    continue

                if not any(a.lower() in (title+text).lower() for a in part["aliases"]):
                    continue

                listings.append(Listing(
                    source    = self.name,
                    part_id   = part["id"],
                    title     = title,
                    price     = price,
                    condition = self.guess_condition(title + text[:200]),
                    url       = href,
                    location  = "",
                    date      = datetime.now().strftime("%Y-%m-%d"),
                    sold      = "已售" in text or "sold" in text.lower(),
                ))
            except Exception:
                continue
        return listings


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
            scrapers = [
                LuTianScraper(session, self.db),
                ShopeeScraper(session, self.db),
                PTTScraper(session, self.db),
                BahaScraper(session, self.db),
            ]

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

                    # 計算今日均價快照
                    if all_listings:
                        prices = [l.price for l in all_listings if not l.sold]
                        if prices:
                            snap = PriceSnapshot(
                                part_id       = part["id"],
                                date          = datetime.now().strftime("%Y-%m-%d"),
                                avg_price     = int(sum(prices) / len(prices)),
                                min_price     = min(prices),
                                max_price     = max(prices),
                                listing_count = len(prices),
                                sources       = list({l.source for l in all_listings}),
                            )
                            self.db.save_snapshot(snap)

            await asyncio.gather(*[scrape_one(p) for p in parts])

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
    db = Database("pc_prices.db")
    scheduler = CrawlerScheduler(db)

    # 可指定分類：cpu / gpu / ram / motherboard / ssd / hdd / psu / cooler
    # 留空 = 全部爬取
    await scheduler.run(
        category_filter=None,   # 改為 ["gpu","cpu"] 可只爬特定分類
        max_concurrent=2        # 降低並發數以避免被封鎖
    )

    reporter = Reporter(db)
    reporter.export_json("price_report.json")


if __name__ == "__main__":
    # 安裝依賴：
    # pip install aiohttp beautifulsoup4 lxml
    asyncio.run(main())
