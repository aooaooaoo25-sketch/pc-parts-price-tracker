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
            {"id": "cpu_i9_12900k", "name": "Core i9-12900K", "aliases": ["i9-12900K", "12900K"], "new_price": 0},
            {"id": "cpu_i7_12700k", "name": "Core i7-12700K", "aliases": ["i7-12700K", "12700K"], "new_price": 0},
            {"id": "cpu_i5_12600k", "name": "Core i5-12600K", "aliases": ["i5-12600K", "12600K"], "new_price": 0},
            {"id": "cpu_i5_12400f", "name": "Core i5-12400F", "aliases": ["i5-12400F", "12400F"], "new_price": 0},
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
            {"id": "cpu_r9_5950x", "name": "Ryzen 9 5950X", "aliases": ["Ryzen 9 5950X", "5950X"], "new_price": 0},
            {"id": "cpu_r9_5900x", "name": "Ryzen 9 5900X", "aliases": ["Ryzen 9 5900X", "5900X"], "new_price": 0},
            {"id": "cpu_r7_5800x3d", "name": "Ryzen 7 5800X3D", "aliases": ["Ryzen 7 5800X3D", "5800X3D"], "new_price": 0},
            {"id": "cpu_r7_5800x", "name": "Ryzen 7 5800X", "aliases": ["Ryzen 7 5800X", "5800X"], "new_price": 0},
            {"id": "cpu_r7_5700x", "name": "Ryzen 7 5700X", "aliases": ["Ryzen 7 5700X", "5700X"], "new_price": 0},
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
            {"id": "gpu_rtx3090ti", "name": "GeForce RTX 3090 Ti", "aliases": ["RTX 3090 Ti", "3090 Ti"], "new_price": 0},
            {"id": "gpu_rtx3090", "name": "GeForce RTX 3090", "aliases": ["RTX 3090", "3090"], "new_price": 0},
            {"id": "gpu_rtx3080ti", "name": "GeForce RTX 3080 Ti", "aliases": ["RTX 3080 Ti", "3080 Ti"], "new_price": 0},
            {"id": "gpu_rtx3080_12g", "name": "GeForce RTX 3080 12GB", "aliases": ["RTX 3080 12GB", "3080 12GB"], "new_price": 0},
            {"id": "gpu_rtx3080", "name": "GeForce RTX 3080", "aliases": ["RTX 3080", "3080"], "new_price": 0},
            {"id": "gpu_rtx3070ti", "name": "GeForce RTX 3070 Ti", "aliases": ["RTX 3070 Ti", "3070 Ti"], "new_price": 0},
            {"id": "gpu_rtx3070", "name": "GeForce RTX 3070", "aliases": ["RTX 3070", "3070"], "new_price": 0},
            {"id": "gpu_rtx3060ti", "name": "GeForce RTX 3060 Ti", "aliases": ["RTX 3060 Ti", "3060 Ti"], "new_price": 0},
            {"id": "gpu_rtx3060", "name": "GeForce RTX 3060", "aliases": ["RTX 3060", "3060"], "new_price": 0},
            {"id": "gpu_rtx3050", "name": "GeForce RTX 3050", "aliases": ["RTX 3050", "3050"], "new_price": 0},
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
            {"id": "gpu_rx6950xt", "name": "Radeon RX 6950 XT", "aliases": ["RX 6950 XT", "6950 XT"], "new_price": 0},
            {"id": "gpu_rx6800xt", "name": "Radeon RX 6800 XT", "aliases": ["RX 6800 XT", "6800 XT"], "new_price": 0},
            {"id": "gpu_rx6700xt", "name": "Radeon RX 6700 XT", "aliases": ["RX 6700 XT", "6700 XT"], "new_price": 0},
            {"id": "gpu_rx6600xt", "name": "Radeon RX 6600 XT", "aliases": ["RX 6600 XT", "6600 XT"], "new_price": 0},
        ],
        "intel_arc": [
            {"id": "gpu_arcb580", "name": "Intel Arc B580", "aliases": ["Arc B580", "B580"], "new_price": 11900},
            {"id": "gpu_arcb570", "name": "Intel Arc B570", "aliases": ["Arc B570", "B570"], "new_price": 9500},
            {"id": "gpu_arca770_16g", "name": "Intel Arc A770 16GB", "aliases": ["Arc A770 16GB", "A770 16GB"], "new_price": 0},
        ],
    },
    # ── RAM ──
    "ram": {
        "ddr5": [
            {"id": "ram_g_skill_trident_z5_rgb_ddr5_6400_32gb", "name": "G.Skill Trident Z5 RGB DDR5-6400 32GB", "aliases": ["G.Skill Trident Z5 RGB DDR5-6400 32GB", "Trident Z5 RGB DDR5-6400 32GB"], "new_price": 5500},
            {"id": "ram_g_skill_ripjaws_m5_ddr5_6000_32gb", "name": "G.Skill Ripjaws M5 DDR5-6000 32GB", "aliases": ["G.Skill Ripjaws M5 DDR5-6000 32GB", "Ripjaws M5 DDR5-6000 32GB"], "new_price": 4800},
            {"id": "ram_g_skill_ripjaws_m5_ddr5_5600_32gb", "name": "G.Skill Ripjaws M5 DDR5-5600 32GB", "aliases": ["G.Skill Ripjaws M5 DDR5-5600 32GB", "Ripjaws M5 DDR5-5600 32GB"], "new_price": 3900},
            {"id": "ram_corsair_vengeance_ddr5_5600_32gb", "name": "Corsair Vengeance DDR5-5600 32GB", "aliases": ["Corsair Vengeance DDR5-5600 32GB", "Vengeance DDR5-5600 32GB"], "new_price": 3600},
            {"id": "ram_corsair_dominator_titan_ddr5_6000_64gb", "name": "Corsair Dominator Titan DDR5-6000 64GB", "aliases": ["Corsair Dominator Titan DDR5-6000 64GB", "Dominator Titan DDR5-6000 64GB"], "new_price": 9500},
            {"id": "ram_kingston_fury_beast_ddr5_5200_32gb", "name": "Kingston Fury Beast DDR5-5200 32GB", "aliases": ["Kingston Fury Beast DDR5-5200 32GB", "Fury Beast DDR5-5200 32GB"], "new_price": 3200},
            {"id": "ram_kingston_fury_renegade_ddr5_6000_32gb", "name": "Kingston Fury Renegade DDR5-6000 32GB", "aliases": ["Kingston Fury Renegade DDR5-6000 32GB", "Fury Renegade DDR5-6000 32GB"], "new_price": 4600},
            {"id": "ram_teamgroup_t_force_delta_ddr5_5600_32gb", "name": "TeamGroup T-Force Delta DDR5-5600 32GB", "aliases": ["TeamGroup T-Force Delta DDR5-5600 32GB", "T-Force Delta DDR5-5600 32GB"], "new_price": 3500},
            {"id": "ram_adata_xpg_lancer_ddr5_5600_32gb", "name": "ADATA XPG Lancer DDR5-5600 32GB", "aliases": ["ADATA XPG Lancer DDR5-5600 32GB", "XPG Lancer DDR5-5600 32GB"], "new_price": 3400},
        ],
        "ddr4": [
            {"id": "ram_g_skill_ripjaws_v_ddr4_3600_32gb", "name": "G.Skill Ripjaws V DDR4-3600 32GB", "aliases": ["G.Skill Ripjaws V DDR4-3600 32GB", "Ripjaws V DDR4-3600 32GB"], "new_price": 2400},
            {"id": "ram_g_skill_trident_z_rgb_ddr4_3600_32gb", "name": "G.Skill Trident Z RGB DDR4-3600 32GB", "aliases": ["G.Skill Trident Z RGB DDR4-3600 32GB", "Trident Z RGB DDR4-3600 32GB"], "new_price": 2600},
            {"id": "ram_corsair_vengeance_lpx_ddr4_3600_32gb", "name": "Corsair Vengeance LPX DDR4-3600 32GB", "aliases": ["Corsair Vengeance LPX DDR4-3600 32GB", "Vengeance LPX DDR4-3600 32GB"], "new_price": 2200},
            {"id": "ram_corsair_vengeance_lpx_ddr4_3200_16gb", "name": "Corsair Vengeance LPX DDR4-3200 16GB", "aliases": ["Corsair Vengeance LPX DDR4-3200 16GB", "Vengeance LPX DDR4-3200 16GB"], "new_price": 1400},
            {"id": "ram_kingston_fury_beast_ddr4_3200_32gb", "name": "Kingston Fury Beast DDR4-3200 32GB", "aliases": ["Kingston Fury Beast DDR4-3200 32GB", "Fury Beast DDR4-3200 32GB"], "new_price": 2200},
        ],
    },
    # ── 主機板 ──
    "mb": {
        "z890": [
            {"id": "mb_asus_rog_maximus_z890_extreme", "name": "ASUS ROG Maximus Z890 Extreme", "aliases": ["ASUS ROG Maximus Z890 Extreme", "ROG Maximus Z890 Extreme"], "new_price": 29900},
            {"id": "mb_asus_rog_strix_z890_f_gaming_wifi", "name": "ASUS ROG Strix Z890-F Gaming WiFi", "aliases": ["ASUS ROG Strix Z890-F Gaming WiFi", "ROG Strix Z890-F Gaming WiFi"], "new_price": 16500},
            {"id": "mb_msi_meg_z890_ace", "name": "MSI MEG Z890 ACE", "aliases": ["MSI MEG Z890 ACE", "MEG Z890 ACE"], "new_price": 22900},
            {"id": "mb_gigabyte_z890_aorus_master_x", "name": "Gigabyte Z890 AORUS Master X", "aliases": ["Gigabyte Z890 AORUS Master X", "Z890 AORUS Master X"], "new_price": 18900},
            {"id": "mb_asrock_z890_taichi_aqua", "name": "ASRock Z890 Taichi Aqua", "aliases": ["ASRock Z890 Taichi Aqua", "Z890 Taichi Aqua"], "new_price": 21500},
        ],
        "z790": [
            {"id": "mb_asus_rog_maximus_z790_hero", "name": "ASUS ROG Maximus Z790 Hero", "aliases": ["ASUS ROG Maximus Z790 Hero", "ROG Maximus Z790 Hero"], "new_price": 18500},
            {"id": "mb_asus_rog_strix_z790_e_gaming_wifi", "name": "ASUS ROG Strix Z790-E Gaming WiFi", "aliases": ["ASUS ROG Strix Z790-E Gaming WiFi", "ROG Strix Z790-E Gaming WiFi"], "new_price": 14500},
            {"id": "mb_msi_meg_z790_ace", "name": "MSI MEG Z790 ACE", "aliases": ["MSI MEG Z790 ACE", "MEG Z790 ACE"], "new_price": 15900},
            {"id": "mb_gigabyte_z790_aorus_master", "name": "Gigabyte Z790 AORUS Master", "aliases": ["Gigabyte Z790 AORUS Master", "Z790 AORUS Master"], "new_price": 14500},
            {"id": "mb_asrock_z790_taichi_carrara", "name": "ASRock Z790 Taichi Carrara", "aliases": ["ASRock Z790 Taichi Carrara", "Z790 Taichi Carrara"], "new_price": 16800},
        ],
        "b760": [
            {"id": "mb_asus_rog_strix_b760_f_gaming_wifi", "name": "ASUS ROG Strix B760-F Gaming WiFi", "aliases": ["ASUS ROG Strix B760-F Gaming WiFi", "ROG Strix B760-F Gaming WiFi"], "new_price": 8900},
            {"id": "mb_msi_mag_b760m_mortar_wifi_ddr5", "name": "MSI MAG B760M Mortar WiFi DDR5", "aliases": ["MSI MAG B760M Mortar WiFi DDR5", "MAG B760M Mortar WiFi DDR5"], "new_price": 5800},
            {"id": "mb_gigabyte_b760_aorus_elite_ax_ddr5", "name": "Gigabyte B760 AORUS Elite AX DDR5", "aliases": ["Gigabyte B760 AORUS Elite AX DDR5", "B760 AORUS Elite AX DDR5"], "new_price": 7200},
        ],
        "x870e": [
            {"id": "mb_asus_rog_crosshair_x870e_hero", "name": "ASUS ROG Crosshair X870E Hero", "aliases": ["ASUS ROG Crosshair X870E Hero", "ROG Crosshair X870E Hero"], "new_price": 22900},
            {"id": "mb_msi_meg_x870e_ace", "name": "MSI MEG X870E ACE", "aliases": ["MSI MEG X870E ACE", "MEG X870E ACE"], "new_price": 21500},
            {"id": "mb_gigabyte_x870e_aorus_master", "name": "Gigabyte X870E AORUS Master", "aliases": ["Gigabyte X870E AORUS Master", "X870E AORUS Master"], "new_price": 18900},
            {"id": "mb_asrock_x870e_taichi", "name": "ASRock X870E Taichi", "aliases": ["ASRock X870E Taichi", "X870E Taichi"], "new_price": 19500},
        ],
        "x670e": [
            {"id": "mb_asus_rog_crosshair_x670e_hero", "name": "ASUS ROG Crosshair X670E Hero", "aliases": ["ASUS ROG Crosshair X670E Hero", "ROG Crosshair X670E Hero"], "new_price": 17800},
            {"id": "mb_msi_mag_x670e_tomahawk_wifi", "name": "MSI MAG X670E Tomahawk WiFi", "aliases": ["MSI MAG X670E Tomahawk WiFi", "MAG X670E Tomahawk WiFi"], "new_price": 9800},
        ],
        "b650e": [
            {"id": "mb_asus_rog_strix_b650e_f_gaming_wifi", "name": "ASUS ROG Strix B650E-F Gaming WiFi", "aliases": ["ASUS ROG Strix B650E-F Gaming WiFi", "ROG Strix B650E-F Gaming WiFi"], "new_price": 10500},
        ],
        "b650": [
            {"id": "mb_msi_mag_b650_tomahawk_wifi", "name": "MSI MAG B650 Tomahawk WiFi", "aliases": ["MSI MAG B650 Tomahawk WiFi", "MAG B650 Tomahawk WiFi"], "new_price": 7800},
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
            {"id": "ssd_samsung_980_pro_2tb", "name": "Samsung 980 Pro 2TB", "aliases": ["Samsung 980 Pro 2TB", "980 Pro 2TB"], "new_price": 0},
            {"id": "ssd_samsung_980_pro_1tb", "name": "Samsung 980 Pro 1TB", "aliases": ["Samsung 980 Pro 1TB", "980 Pro 1TB"], "new_price": 0},
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
    # ── 電源 ──
    "psu": {
        "psu": [
            {"id": "psu_seasonic_vertex_px_1000", "name": "Seasonic Vertex PX-1000", "aliases": ["Seasonic Vertex PX-1000", "Vertex PX-1000"], "new_price": 6800},
            {"id": "psu_seasonic_vertex_px_850", "name": "Seasonic Vertex PX-850", "aliases": ["Seasonic Vertex PX-850", "Vertex PX-850"], "new_price": 5800},
            {"id": "psu_seasonic_focus_gx_850", "name": "Seasonic Focus GX-850", "aliases": ["Seasonic Focus GX-850", "Focus GX-850"], "new_price": 4800},
            {"id": "psu_seasonic_focus_gx_650", "name": "Seasonic Focus GX-650", "aliases": ["Seasonic Focus GX-650", "Focus GX-650"], "new_price": 3800},
            {"id": "psu_corsair_hx1000", "name": "Corsair HX1000", "aliases": ["Corsair HX1000", "HX1000"], "new_price": 5900},
            {"id": "psu_corsair_rm850x_2024", "name": "Corsair RM850x (2024)", "aliases": ["Corsair RM850x (2024)", "RM850x (2024)"], "new_price": 4200},
            {"id": "psu_corsair_rm750x", "name": "Corsair RM750x", "aliases": ["Corsair RM750x", "RM750x"], "new_price": 3500},
            {"id": "psu_asus_rog_thor_850p2", "name": "ASUS ROG Thor 850P2", "aliases": ["ASUS ROG Thor 850P2", "ROG Thor 850P2"], "new_price": 6200},
            {"id": "psu_be_quiet_dark_power_13_850w", "name": "be quiet! Dark Power 13 850W", "aliases": ["be quiet! Dark Power 13 850W", "quiet! Dark Power 13 850W"], "new_price": 5800},
            {"id": "psu_be_quiet_straight_power_12_750w", "name": "be quiet! Straight Power 12 750W", "aliases": ["be quiet! Straight Power 12 750W", "quiet! Straight Power 12 750W"], "new_price": 4800},
            {"id": "psu_msi_mpg_a850g_pcie5", "name": "MSI MPG A850G PCIE5", "aliases": ["MSI MPG A850G PCIE5", "MPG A850G PCIE5"], "new_price": 4500},
            {"id": "psu_thermalright_tg_1050w", "name": "Thermalright TG-1050W", "aliases": ["Thermalright TG-1050W", "TG-1050W"], "new_price": 3600},
        ],
    },
    # ── 散熱 ──
    "cooler": {
        "air": [
            {"id": "cooler_noctua_nh_d15_g2", "name": "Noctua NH-D15 G2", "aliases": ["Noctua NH-D15 G2", "NH-D15 G2"], "new_price": 4500},
            {"id": "cooler_noctua_nh_d15_chromax_black", "name": "Noctua NH-D15 chromax.black", "aliases": ["Noctua NH-D15 chromax.black", "NH-D15 chromax.black"], "new_price": 3800},
            {"id": "cooler_noctua_nh_u12a_chromax_black", "name": "Noctua NH-U12A chromax.black", "aliases": ["Noctua NH-U12A chromax.black", "NH-U12A chromax.black"], "new_price": 2800},
            {"id": "cooler_be_quiet_dark_rock_pro_5", "name": "be quiet! Dark Rock Pro 5", "aliases": ["be quiet! Dark Rock Pro 5", "quiet! Dark Rock Pro 5"], "new_price": 3600},
            {"id": "cooler_thermalright_pa120_se", "name": "Thermalright PA120 SE", "aliases": ["Thermalright PA120 SE", "PA120 SE"], "new_price": 1200},
            {"id": "cooler_deepcool_ak620_digital", "name": "DeepCool AK620 Digital", "aliases": ["DeepCool AK620 Digital", "AK620 Digital"], "new_price": 1800},
        ],
        "liquid": [
            {"id": "cooler_id_cooling_fx360_pro_argb", "name": "ID-Cooling FX360 Pro ARGB", "aliases": ["ID-Cooling FX360 Pro ARGB", "FX360 Pro ARGB"], "new_price": 3200},
            {"id": "cooler_asus_rog_ryujin_iii_360_argb", "name": "ASUS ROG Ryujin III 360 ARGB", "aliases": ["ASUS ROG Ryujin III 360 ARGB", "ROG Ryujin III 360 ARGB"], "new_price": 12500},
            {"id": "cooler_asus_rog_strix_lc_ii_360_argb", "name": "ASUS ROG Strix LC II 360 ARGB", "aliases": ["ASUS ROG Strix LC II 360 ARGB", "ROG Strix LC II 360 ARGB"], "new_price": 6800},
            {"id": "cooler_corsair_h150i_elite_capellix_xt", "name": "Corsair H150i ELITE CAPELLIX XT", "aliases": ["Corsair H150i ELITE CAPELLIX XT", "H150i ELITE CAPELLIX XT"], "new_price": 7200},
            {"id": "cooler_corsair_icue_h100i_elite_lcd", "name": "Corsair iCUE H100i ELITE LCD", "aliases": ["Corsair iCUE H100i ELITE LCD", "iCUE H100i ELITE LCD"], "new_price": 5200},
            {"id": "cooler_msi_mag_coreliquid_e360", "name": "MSI MAG CoreLiquid E360", "aliases": ["MSI MAG CoreLiquid E360", "MAG CoreLiquid E360"], "new_price": 5800},
            {"id": "cooler_lian_li_galahad_ii_360_rgb", "name": "Lian Li GALAHAD II 360 RGB", "aliases": ["Lian Li GALAHAD II 360 RGB", "Li GALAHAD II 360 RGB"], "new_price": 5500},
            {"id": "cooler_ek_nucleus_aio_cr360_lux_d_rgb", "name": "EK Nucleus AIO CR360 Lux D-RGB", "aliases": ["EK Nucleus AIO CR360 Lux D-RGB", "Nucleus AIO CR360 Lux D-RGB"], "new_price": 6900},
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

    # 可指定分類：cpu / gpu / ram / mb / ssd / hdd / psu / cooler
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
