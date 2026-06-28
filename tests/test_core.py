"""核心分類 / 比對邏輯的回歸測試（純函式、不碰 DB / 網路）。

涵蓋本專案最容易因調整而壞掉、且這次大改過的邏輯：
  - title_is_new / classify_listing（二手分流：used/new/exclude、價格天花板、default_new）
  - ram_total_capacities（kit-aware 容量：16G*2=32、32G*2=64）
  - title_matches_part（RAM 規格帶比對 + GPU/CPU 變體後綴排除）
  - gpu_model_set / is_cross_model_gpu（跨型號賣場清單）
  - parse_coolpc（原價屋 <select> 解析 + 配件過濾 + 價格防呆）
  - robust_price_stats（IQR 去極值）/ split_used_new / part_default_new

執行：python -m pytest tests/ -q     （需 pip install pytest）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pc_scraper_backend import (
    title_is_new, classify_listing, ram_total_capacities, title_matches_part,
    gpu_model_set, is_cross_model_gpu, parse_coolpc, robust_price_stats,
    split_used_new, part_default_new,
)

GPU3070 = {"id": "gpu_rtx3070", "aliases": ["RTX 3070", "3070"]}
GPU3060 = {"id": "gpu_rtx3060", "aliases": ["RTX 3060", "3060"]}
RAM_D5_32 = {"id": "ram_ddr5_32gb", "aliases": ["DDR5 32G", "DDR5 32GB"]}
RAM_D5_16 = {"id": "ram_ddr5_16gb", "aliases": ["DDR5 16G", "DDR5 16GB"]}
RAM_D4_8 = {"id": "ram_ddr4_8gb", "aliases": ["DDR4 8G", "DDR4 8GB"]}
CPU14900K = {"id": "cpu_i9_14900k", "aliases": ["i9-14900K", "14900K"]}


# ── title_is_new ────────────────────────────────────────────
class TestTitleIsNew:
    def test_explicit_new(self):
        assert title_is_new("全新未拆 RTX 4090")
        assert title_is_new("Intel i5 公司貨")
        assert title_is_new("DDR5 32G 含稅 終身保固")

    def test_used_words_block_new(self):
        assert not title_is_new("RTX 3070 二手良品")
        assert not title_is_new("9成新 顯示卡")
        # 「保固30天」是二手賣家話術 → 不算全新
        assert not title_is_new("ASUS RTX3070 二手良品 保固30天")

    def test_plain_title_not_new(self):
        assert not title_is_new("MSI RTX 3060 VENTUS 2X 12G")


# ── ram_total_capacities（kit-aware）─────────────────────────
class TestRamCapacities:
    def test_kit_notation(self):
        assert ram_total_capacities("DDR5-5600 16G*2") == {32}
        assert ram_total_capacities("DDR5 6400 32G*2") == {64}
        assert ram_total_capacities("2x16G DDR5") == {32}
        assert ram_total_capacities("DDR5 6000 (16Gx2) 32GB") == {32}

    def test_single(self):
        assert ram_total_capacities("單條32GB DDR5-5600") == {32}
        assert ram_total_capacities("DDR4 8G") == {8}

    def test_speed_not_mistaken_for_capacity(self):
        # 「5600 16G」不可把 5600 併進容量（曾因去空白而誤判）
        caps = ram_total_capacities("DDR5-5600 16G")
        assert caps == {16}


# ── title_matches_part ──────────────────────────────────────
class TestTitleMatchesPart:
    def test_ram_band_with_speed_between(self):
        # 別名「DDR5 32GB」常被頻率夾在中間
        assert title_matches_part("巨蟒 DDR5 6000 32GB (16G*2)", RAM_D5_32)
        assert title_matches_part("單條32GB DDR5-5600", RAM_D5_32)

    def test_ram_wrong_capacity_excluded(self):
        assert not title_matches_part("DDR5 6400 32G*2", RAM_D5_32)   # 32G*2=64G
        assert not title_matches_part("DDR5 6000 16G", RAM_D5_32)
        assert title_matches_part("DDR5 6000 16G", RAM_D5_16)

    def test_ram_8g_not_16g(self):
        assert title_matches_part("威剛 DDR4 8G 3200", RAM_D4_8)
        assert not title_matches_part("威剛 DDR4 16G 3200", RAM_D4_8)

    def test_gpu_variant_suffix_excluded(self):
        assert title_matches_part("華碩 RTX 3070 O8G", GPU3070)
        assert not title_matches_part("華碩 RTX 3070 Ti O8G", GPU3070)

    def test_cpu_suffix_excluded(self):
        assert title_matches_part("Intel i9-14900K 盒裝", CPU14900K)
        assert not title_matches_part("Intel i9-14900KF 盒裝", CPU14900K)


# ── gpu_model_set / is_cross_model_gpu ──────────────────────
class TestCrossModel:
    def test_model_set(self):
        assert gpu_model_set("RTX3080 RTX3070 RTX3060") == {"3080", "3070", "3060"}
        assert gpu_model_set("RTX 3060 Ti") == {"3060ti"}

    def test_bundle_is_cross(self):
        assert is_cross_model_gpu("顯卡 Rtx3080, Rtx3070, Rtx3060", GPU3060)
        assert is_cross_model_gpu("賣RTX3070（RTX3060、RTX3060ti 參考）", GPU3060)

    def test_single_card_not_cross(self):
        assert not is_cross_model_gpu("微星 MSI RTX3060 VENTUS 2X 12G", GPU3060)

    def test_non_gpu_never_cross(self):
        assert not is_cross_model_gpu("RTX3080 RTX3070 加 DDR5 32G", RAM_D5_32)


# ── classify_listing ────────────────────────────────────────
class TestClassifyListing:
    def test_used_keyword(self):
        assert classify_listing("RTX 3070 二手良品", 7000) == "used"

    def test_new_keyword(self):
        assert classify_listing("RTX 3070 全新未拆", 20000) == "new"

    def test_price_ceiling_makes_new(self):
        # 無成色、但價格 >= 目前全新行情 → 視為零售全新
        assert classify_listing("MSI RTX3060 VENTUS", 13000, new_ref=11841) == "new"
        assert classify_listing("MSI RTX3060 VENTUS", 8000, new_ref=11841) == "used"

    def test_used_word_above_ceiling_excluded(self):
        # 「良品」卻喊到比全新還貴（整新店）→ exclude
        assert classify_listing("天鷹科技 RTX3060 良品", 17980, new_ref=11841) == "exclude"

    def test_default_new_for_retail_category(self):
        # RAM 這種零售為主的品類：無成色預設全新
        assert classify_listing("巨蟒 DDR5 6000 32G", 11000, default_new=True) == "new"
        assert classify_listing("巨蟒 DDR5 6000 32G", 11000, default_new=False) == "used"

    def test_split_used_new(self):
        rows = [("RTX3070 全新", 20000), ("RTX3070 二手", 7000), ("RTX3070 無說明", 8000)]
        used, new = split_used_new(rows)
        assert 7000 in used and 8000 in used and 20000 in new


# ── parse_coolpc ────────────────────────────────────────────
COOLPC_HTML = """
<select name="n6">
  <option disabled>記憶體 RAM</option>
  <option value=1>UMAX 單條32GB DDR5-5600/CL46, $11900 ◆</option>
  <option value=2>威剛 DDR5 6000 16G*2, $5999 ★</option>
  <option value=3>整機優惠超值組, $39900</option>
</select>
<select name="n12">
  <option value=9>華碩 ROG Herculx 顯示卡支撐架, $1290</option>
  <option value=10>技嘉 RTX 5070 GAMING OC 12G, $24900 ★</option>
</select>
"""


class TestParseCoolpc:
    def test_ram_parsed(self):
        out = parse_coolpc(COOLPC_HTML)
        descs = [d for d, p in out["ram"]]
        assert any("UMAX" in d for d in descs)
        assert any("威剛" in d for d in descs)

    def test_accessory_filtered(self):
        out = parse_coolpc(COOLPC_HTML)
        # 顯卡支撐架（配件）應被剔除，留下真顯卡
        descs = [d for d, p in out["gpu"]]
        assert not any("支撐架" in d for d in descs)
        assert any("RTX 5070" in d for d in descs)

    def test_price_extracted(self):
        out = parse_coolpc(COOLPC_HTML)
        prices = dict((d, p) for d, p in out["ram"])
        assert prices["UMAX 單條32GB DDR5-5600/CL46"] == 11900


# ── robust_price_stats ──────────────────────────────────────
class TestRobustStats:
    def test_trims_outlier(self):
        # 樣本夠多時 IQR 才會修剪離群值（小樣本刻意保守不修）
        data = [4800, 4900, 5000, 5000, 5100, 5200, 5000, 5100, 50000]
        avg, mn, mx, n = robust_price_stats(data)
        assert avg < 6000          # 50000 離群值被修掉
        assert mx < 10000 and n == len(data) - 1

    def test_small_sample_no_trim(self):
        avg, mn, mx, n = robust_price_stats([5000, 7000])
        assert avg == 6000 and n == 2


# ── part_default_new ────────────────────────────────────────
def test_part_default_new():
    assert part_default_new("ram_ddr5_32gb") is True
    assert part_default_new("gpu_rtx3060") is False
    assert part_default_new("cpu_i9_14900k") is False
