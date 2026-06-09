# -*- coding: utf-8 -*-
"""零件目錄同步器：以前端 index.html 的 DB 為唯一主目錄，
產生統一 ID 並重建後端 pc_scraper_backend.py 的 PARTS_DB。

用途
----
前端 `DB`（index.html）是人工維護的主目錄。每次新增/修改零件後執行本腳本，
即可：
  1. 依 `cat_model` 規則為每筆品項重算統一 ID，改寫 index.html 內所有 id
  2. 用同一份資料重建後端 PARTS_DB（id / name / aliases / new_price）
讓前後端的 id 與 name 永遠一致（解決「兩份資料各自獨立」的技術債）。

ID 規則
-------
  CPU   cpu_<tier>_<model>   例：cpu_i9_14900k、cpu_ultra9_285k、cpu_r7_5800x3d
  GPU   gpu_<brand><model>   例：gpu_rtx5090、gpu_rx7900xtx、gpu_arcb580
  其他  <cat>_<full-slug>    例：ram_corsair_vengeance_ddr5_5600_32gb、ssd_samsung_990_pro_2tb
        （RAM/主機板/SSD/HDD/PSU/散熱含品牌，避免同規格不同品牌撞名）

執行
----
  python tools/sync_parts.py
  # 若專案路徑含中文且在 Windows 執行失敗，請設 PYTHONUTF8=1，
  # 或先 `chcp 65001`，或在 ASCII 路徑下執行。
"""
import re, os, sys
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "index.html")
BACKEND = os.path.join(ROOT, "pc_scraper_backend.py")

CAT_ORDER = ["cpu", "gpu", "ram", "ssd", "hdd"]
CAT_LABEL = {"cpu": "CPU", "gpu": "GPU", "ram": "RAM", "ssd": "SSD", "hdd": "HDD"}

ITEM_RE = re.compile(
    r"\{id:'(?P<id>[^']*)',\s*cat:'(?P<cat>[^']*)',\s*name:'(?P<name>[^']*)',"
    r"\s*spec:'(?P<spec>[^']*)',\s*new_price:(?P<price>\d+),\s*tags:\[(?P<tags>[^\]]*)\]\}"
)


# ─────────────────────────── ID 規則 ───────────────────────────
def slug(s):
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s.lower())).strip("_")


def gpu_id(name):
    if "Radeon RX" in name:
        brand, rest = "rx", name.split("Radeon RX", 1)[1]
    elif "Arc" in name:
        brand, rest = "arc", name.split("Arc", 1)[1]
    else:
        brand, rest = "rtx", name.split("RTX", 1)[1]
    base, mem = [], ""
    for t in rest.split():
        m = re.match(r"(\d+)GB$", t)
        if m:
            mem = "_" + m.group(1) + "g"
        else:
            base.append({"SUPER": "s", "Ti": "ti", "XT": "xt", "XTX": "xtx"}.get(t, t.lower()))
    return f"gpu_{brand}{''.join(base)}{mem}"


def cpu_id(name):
    if name.startswith("Core Ultra"):
        m = re.match(r"Core Ultra (\d+) (\S+)", name)
        return f"cpu_ultra{m.group(1)}_{m.group(2).lower()}"
    if name.startswith("Core i"):
        m = re.match(r"Core (i\d+)-(\S+)", name)
        return f"cpu_{m.group(1)}_{m.group(2).lower()}"
    if name.startswith("Ryzen"):
        m = re.match(r"Ryzen (\d+) (\S+)", name)
        return f"cpu_r{m.group(1)}_{m.group(2).lower()}"
    raise ValueError(f"無法解析 CPU 名稱：{name}")


def canonical_id(cat, name):
    if cat == "gpu":
        return gpu_id(name)
    if cat == "cpu":
        return cpu_id(name)
    return f"{cat}_{slug(name)}"


# ─────────────────────── aliases / subcat ───────────────────────
def aliases_for(cat, name):
    if cat == "cpu":
        if "Core Ultra" in name:
            return [name.replace("Core ", ""), name.split()[-1]]
        if "Core i" in name:
            m = re.search(r"i\d+-\S+", name)
            return [m.group(0), m.group(0).split("-", 1)[1]]
        if "Ryzen" in name:
            return [name, name.split()[-1]]
    if cat == "gpu":
        a1 = name.replace("GeForce ", "").replace("Radeon ", "").replace("Intel ", "")
        a2 = a1.replace("RTX ", "").replace("RX ", "").replace("Arc ", "")
        return [a1, a2]
    a1 = name
    a2 = name.split(" ", 1)[1] if " " in name else name
    return [a1, a2]


def subcat_for(cat, name, spec):
    if cat == "cpu":
        if "Ultra" in name:
            return "intel_ultra"
        if name.startswith("Core i"):
            return "intel_" + re.search(r"i\d+-(\d{2})", name).group(1)
        if name.startswith("Ryzen"):
            return "amd_" + re.search(r"Ryzen \d+ (\d)", name).group(1) + "000"
    if cat == "gpu":
        if "RTX" in name:
            return "nvidia_" + re.search(r"RTX (\d)", name).group(1) + "0"
        if "RX" in name:
            return "amd_" + re.search(r"RX (\d)", name).group(1) + "000"
        if "Arc" in name:
            return "intel_arc"
    if cat == "ram":
        return "ddr5" if "DDR5" in name else "ddr4"
    if cat == "mb":
        m = re.search(r"\b([ZBX]\d{3}E?)M?\b", name)
        return m.group(1).lower() if m else "other"
    if cat == "ssd":
        s = spec.upper()
        for k in ("PCIE5", "PCIE4", "SATA"):
            if k in s:
                return k.lower()
        return "other"
    if cat == "cooler":
        liquid = ("360" in name or "240" in name or "AIO" in name
                  or any(x in name for x in ["H150", "H100", "Ryujin", "GALAHAD",
                                             "Nucleus", "CoreLiquid", "LC ", "iCUE H"]))
        return "liquid" if liquid else "air"
    return cat  # hdd / psu 單一桶


def pyq(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build(html, backend):
    """依前端 DB 計算統一 id，回傳 (新 index.html 內容, 新 backend 內容, 品項數)。
    不寫檔；同時負責撞名 / 解析失敗的防呆檢查。"""
    items = [m.groupdict() for m in ITEM_RE.finditer(html)]
    for it in items:
        it["price"] = int(it["price"])
    if not items:
        raise SystemExit("未從 index.html 解析到任何品項，請檢查 DB 格式")

    # 計算統一 id + 撞名檢查
    mapping, seen = {}, {}
    for it in items:
        nid = canonical_id(it["cat"], it["name"])
        if nid in seen:
            raise SystemExit(f"ID 撞名 {nid}：{seen[nid]} / {it['name']}")
        seen[nid] = it["name"]
        it["new_id"] = nid
        mapping[it["id"]] = nid

    # 1) 改寫 index.html 的 id（精確比對、單次掃描）
    new_html, n_sub = re.subn(r"id:'([^']+)'",
                              lambda m: f"id:'{mapping.get(m.group(1), m.group(1))}'", html)
    if n_sub != len(items):
        raise SystemExit(f"id 替換數不符：預期 {len(items)}，實際 {n_sub}")

    # 2) 重建後端 PARTS_DB
    tree = OrderedDict((c, OrderedDict()) for c in CAT_ORDER)
    for it in items:
        sub = subcat_for(it["cat"], it["name"], it["spec"])
        tree[it["cat"]].setdefault(sub, []).append(it)

    lines = ["PARTS_DB = {"]
    for cat in CAT_ORDER:
        lines.append(f"    # ── {CAT_LABEL[cat]} ──")
        lines.append(f"    {pyq(cat)}: {{")
        for sub, lst in tree[cat].items():
            lines.append(f"        {pyq(sub)}: [")
            for it in lst:
                al = "[" + ", ".join(pyq(a) for a in aliases_for(cat, it["name"])) + "]"
                lines.append(
                    f'            {{"id": {pyq(it["new_id"])}, '
                    f'"name": {pyq(it["name"])}, '
                    f'"aliases": {al}, '
                    f'"new_price": {it["price"]}}},'
                )
            lines.append("        ],")
        lines.append("    },")
    lines.append("}")
    block = "\n".join(lines)

    new_backend, n = re.subn(r"PARTS_DB = \{.*?\n\}", block, backend, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("在 pc_scraper_backend.py 找不到 PARTS_DB 區塊")
    new_backend = new_backend.replace("motherboard / ssd", "mb / ssd")
    return new_html, new_backend, len(items)


def main():
    check = "--check" in sys.argv[1:]
    html = open(HTML, encoding="utf-8").read()
    backend = open(BACKEND, encoding="utf-8").read()
    new_html, new_backend, n = build(html, backend)

    if check:
        # 只驗證、不寫檔：有落差即視為前後端不同步
        drift = []
        if new_html != html:
            drift.append("index.html（前端 id 與規則不符）")
        if new_backend != backend:
            drift.append("pc_scraper_backend.py（PARTS_DB 與前端不同步）")
        if drift:
            print("✗ 前後端零件資料不同步：")
            for d in drift:
                print("   - " + d)
            print("  請執行：python tools/sync_parts.py")
            sys.exit(1)
        print(f"✓ 前後端已同步（{n} 筆品項，id 一致）")
        return

    open(HTML, "w", encoding="utf-8").write(new_html)
    open(BACKEND, "w", encoding="utf-8").write(new_backend)
    print(f"同步完成：{n} 筆品項，後端 PARTS_DB 已依前端重建。")


if __name__ == "__main__":
    main()
