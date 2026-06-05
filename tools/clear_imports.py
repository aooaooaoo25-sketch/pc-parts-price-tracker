# -*- coding: utf-8 -*-
"""清理 imports/ 內累積的匯入暫存檔（*.csv / *.json）。

這些檔是「搬運用」的暫存資料，匯入 pc_prices.db 後即無作用（DB 才是真資料）。
本工具一鍵清掉它們，但**保留範本**（sample_listings.csv、README.md）。

  python tools/clear_imports.py            # 直接刪除
  python tools/clear_imports.py --archive  # 改為移到 imports/archive/<時間戳>/
  python tools/clear_imports.py --dry-run  # 只列出會處理的檔，不動手
"""
import os
import sys
import shutil
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMPORTS = os.path.join(ROOT, "imports")
KEEP = {"sample_listings.csv", "readme.md"}          # 範本（保留），比對時轉小寫
EXTS = (".csv", ".json")


def targets():
    if not os.path.isdir(IMPORTS):
        return []
    out = []
    for name in os.listdir(IMPORTS):
        path = os.path.join(IMPORTS, name)
        if not os.path.isfile(path):
            continue
        if name.lower() in KEEP:
            continue
        if name.lower().endswith(EXTS):
            out.append(name)
    return sorted(out)


def main():
    archive = "--archive" in sys.argv
    dry = "--dry-run" in sys.argv
    files = targets()

    if not files:
        print("imports/ 沒有可清理的暫存檔（範本已保留）。")
        return

    if dry:
        print(f"[dry-run] 將處理 {len(files)} 個檔：")
        for f in files:
            print("  -", f)
        return

    dest = None
    if archive:
        dest = os.path.join(IMPORTS, "archive", datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(dest, exist_ok=True)

    for f in files:
        src = os.path.join(IMPORTS, f)
        if archive:
            shutil.move(src, os.path.join(dest, f))
        else:
            os.remove(src)

    if archive:
        print(f"已封存 {len(files)} 個檔 → {dest}")
    else:
        print(f"已刪除 {len(files)} 個匯入暫存檔（範本保留）。")


if __name__ == "__main__":
    main()
