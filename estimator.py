# -*- coding: utf-8 -*-
"""未收錄零件的行情估算（待辦 #7）。

取代前端 estP() 的硬編關鍵字估價：改以真實的 166 項目錄（PARTS_DB）與已累積的
真實成交資料為基礎估算。

估算邏輯（由準到糙）：
  1) 目錄比對：查詢與某零件的名稱/別名相符 → 直接回傳該零件（含真實二手均價）。
  2) 相近型號估算：猜分類後，找同分類中「型號最接近」的零件作為基準，
     以其全新價與（真實或分類比例推得的）二手價估算。
  3) 兜底：該分類無基準時用分類中位數比例粗估。
回傳一律附 basis（依據）與 confidence（信心），由前端據實標示。
"""
import re

from pc_scraper_backend import PARTS_DB

# 各分類「二手/全新」預設比例（無真實資料時的兜底）
DEFAULT_RATIO = {"gpu": 0.62, "cpu": 0.60, "ram": 0.55, "mb": 0.55,
                 "ssd": 0.55, "hdd": 0.50, "psu": 0.60, "cooler": 0.55}

# 註：短代號（i5/r5…）需加詞界，否則 "ddr5" 會誤判為 cpu。RAM/SSD 規則排在 cpu 前。
_CAT_RULES = [
    ("gpu", r"(\brtx|\bgtx|\brx\s*\d|radeon|geforce|\barc\s*[ab])"),
    ("ram", r"(ddr\d|記憶體|\bram\b|dimm)"),
    ("ssd", r"(nvme|\bssd\b|固態|\bsn\d|\bpcie|990\s*pro|980\s*pro|870\s*evo)"),
    ("hdd", r"(\bhdd\b|硬碟|barracuda|ironwolf|toshiba|red\s*plus)"),
    ("mb", r"(主機板|motherboard|z890|z790|b760|x870|x670|b650|tomahawk|aorus|taichi)"),
    ("psu", r"(電源|\bpsu\b|\bwatt\b|瓦|\brm\d|seasonic|focus|vertex)"),
    ("cooler", r"(散熱|cooler|\baio\b|水冷|風冷|noctua|nh-|liquid)"),
    ("cpu", r"(\bcore\b|ryzen|ultra|\bi[3579]\b|\br[3579]\b|處理器|\bcpu\b)"),
]


def guess_cat(q: str) -> str:
    ql = q.lower()
    for cat, pat in _CAT_RULES:
        if re.search(pat, ql):
            return cat
    return "gpu"


def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def _model_num(s: str):
    nums = re.findall(r"\d{3,5}", s)
    return int(nums[0]) if nums else None


def _all_parts():
    for cat, subs in PARTS_DB.items():
        for parts in subs.values():
            for p in parts:
                yield p, cat


def _category_ratio(cat: str, rep) -> float:
    """以該分類有真實成交資料的零件，取 used/new 中位數；無則用預設。"""
    ratios = []
    for p, c in _all_parts():
        if c != cat or p["new_price"] <= 0:
            continue
        detail = rep.get_detail(p["id"])
        if detail and detail.get("used"):
            ratios.append(detail["used"] / p["new_price"])
    if ratios:
        ratios.sort()
        return ratios[len(ratios) // 2]
    return DEFAULT_RATIO.get(cat, 0.6)


def estimate(query: str, rep) -> dict:
    q = (query or "").strip()
    if not q:
        return {"query": q, "matched": False, "cat": "gpu", "new_price": 0,
                "used": 0, "basis": "空查詢", "confidence": "none"}

    qtok = _tokens(q)

    # 1) 目錄比對（名稱或別名）
    for p, cat in _all_parts():
        candidates = [p["name"]] + list(p.get("aliases", []))
        for nm in candidates:
            ntok = _tokens(nm)
            if (qtok and qtok.issubset(ntok)) or q.lower() in nm.lower():
                detail = rep.get_detail(p["id"])
                used = (detail["used"] if detail and detail.get("used")
                        else round(p["new_price"] * DEFAULT_RATIO.get(cat, 0.6)))
                return {"query": q, "matched": True, "part_id": p["id"],
                        "name": p["name"], "cat": cat, "new_price": p["new_price"],
                        "used": used, "basis": "目錄已收錄", "confidence": "high"}

    # 2) 相近型號估算
    cat = guess_cat(q)
    qnum = _model_num(q)
    pool = [p for p, c in _all_parts() if c == cat and p["new_price"] > 0]
    best, best_score = None, -1.0
    for p in pool:
        score = len(qtok & _tokens(p["name"]))
        pnum = _model_num(p["name"])
        if qnum and pnum:
            score += 1.0 / (1 + abs(qnum - pnum) / 1000.0)
        if score > best_score:
            best, best_score = p, score

    ratio = _category_ratio(cat, rep)
    if best and best_score > 0:
        detail = rep.get_detail(best["id"])
        new_est = best["new_price"]
        used_est = round(detail["used"] if detail and detail.get("used")
                         else new_est * ratio)
        return {"query": q, "matched": False, "cat": cat, "new_price": new_est,
                "used": used_est, "basis": f"估自相近型號「{best['name']}」",
                "confidence": "low", "comparable": best["id"]}

    # 3) 兜底
    return {"query": q, "matched": False, "cat": cat, "new_price": 0,
            "used": round(12000 * ratio), "basis": "無相近型號，粗估",
            "confidence": "low"}
