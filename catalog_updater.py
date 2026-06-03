# -*- coding: utf-8 -*-
"""製造商產品庫更新：偵測官網上「已上市但目錄尚未收錄」的新型號（待辦 #3）。

對應前端 runDb()「更新產品庫」按鈕的後端邏輯。

限制（已實測）：製造商官網**只抓得到型號名稱**，價格抓不到（JS 渲染、且為美金、
非台灣建議售價）。因此本模組只負責「發現新型號」，發現的新品 new_price 留 0 待人工填。
目前可靠來源為 GPU（NVIDIA / AMD）；Intel Arc 常回 403，會優雅略過。
"""
import re
import ssl
import urllib.request

from pc_scraper_backend import PARTS_DB

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
# 製造商頁多為公開 HTML，只擷取型號字串；部分站台（AMD）需放寬憑證驗證
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

# 抓型號用的樣式（GPU）
_GPU_PATTERNS = [
    r"RTX\s?\d{4}(?:\s?Ti)?(?:\s?SUPER)?",
    r"RX\s?\d{4}(?:\s?XTX|\s?XT|\s?GRE)?",
    r"Arc\s?[AB]\d{3}",
]

MANUFACTURER_SOURCES = [
    {"name": "NVIDIA GeForce", "cat": "gpu",
     "url": "https://www.nvidia.com/en-us/geforce/graphics-cards/",
     "pattern": r"RTX\s?\d{4}(?:\s?Ti)?(?:\s?SUPER)?"},
    {"name": "AMD Radeon", "cat": "gpu",
     "url": "https://www.amd.com/en/products/graphics/desktops/radeon.html",
     "pattern": r"RX\s?9\d{3}(?:\s?XTX|\s?XT|\s?GRE)?"},
    {"name": "Intel Arc", "cat": "gpu",
     "url": "https://www.intel.com/content/www/us/en/products/details/discrete-gpus/arc.html",
     "pattern": r"Arc\s?[AB]\d{3}"},
]


def _norm(s: str) -> str:
    """正規化型號字串：收斂空白、轉大寫，便於比對。"""
    return re.sub(r"\s+", " ", s).strip().upper()


def _is_real_model(token: str) -> bool:
    """排除系列名（如 RX 9000）等非實際型號。"""
    m = re.search(r"\d{4}", token)
    return bool(m) and not m.group().endswith("000")


def _fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                               "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        return r.read().decode("utf-8", "replace")


def catalog_models(cat: str) -> set:
    """從現有 PARTS_DB 對應分類的零件名稱中，擷取已收錄的型號集合。"""
    models = set()
    for sub in PARTS_DB.get(cat, {}).values():
        for p in sub:
            for pat in _GPU_PATTERNS:
                for tok in re.findall(pat, p["name"], re.I):
                    models.add(_norm(tok))
    return models


def scan_source(src: dict) -> dict:
    """抓單一製造商頁，回報該來源掃到的型號與「目錄尚未收錄」的新型號。"""
    try:
        html = _fetch(src["url"])
    except Exception as e:
        return {"name": src["name"], "cat": src["cat"], "scanned": 0,
                "new": [], "ok": False, "error": f"{type(e).__name__}: {str(e)[:60]}"}

    found = {_norm(t) for t in re.findall(src["pattern"], html, re.I) if _is_real_model(t)}
    known = catalog_models(src["cat"])
    new = sorted(found - known)
    return {"name": src["name"], "cat": src["cat"], "scanned": len(found),
            "new": new, "ok": True}


def run() -> dict:
    """掃描所有製造商來源，回報新品偵測結果（供 API / runDb 使用）。"""
    sources = [scan_source(s) for s in MANUFACTURER_SOURCES]
    new_total = sum(len(s["new"]) for s in sources)
    return {"sources": sources, "new_total": new_total}


if __name__ == "__main__":
    import json
    print(json.dumps(run(), ensure_ascii=False, indent=2))
