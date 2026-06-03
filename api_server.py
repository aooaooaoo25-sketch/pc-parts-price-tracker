# -*- coding: utf-8 -*-
"""PC 零件二手價格追蹤 — 本地 API server（待辦 #1 / #5）。

提供前端取用真實爬蟲資料的橋接層：
  GET /                 → 直接服務 index.html（同源，免 CORS）
  GET /api/health       → 服務狀態與資料筆數
  GET /api/report       → 所有零件的價格資料，攤平成 {part_id: detail}
  GET /api/part/<id>    → 單一零件的完整 detail

資料來自 pc_prices.db（由爬蟲 pc_scraper_backend.py 或 tools/seed_demo_data.py 產生）。
前端在 server 未啟動時會自動回退為模擬資料，因此直接開啟 index.html 仍可運作（降級）。

執行：
  pip install -r requirements.txt
  python api_server.py            # 預設 http://127.0.0.1:5000
  # 自訂埠：  PORT=8000 python api_server.py
"""
import os
from flask import Flask, jsonify, send_from_directory

from pc_scraper_backend import Database, Reporter, PARTS_DB

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "pc_prices.db")

app = Flask(__name__, static_folder=None)

ALL_PART_IDS = [p["id"] for cat in PARTS_DB.values() for sub in cat.values() for p in sub]


@app.after_request
def add_cors(resp):
    # 允許以 file:// 直接開啟的前端跨來源呼叫
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return resp


def _reporter():
    db = Database(DB_PATH)
    return db, Reporter(db)


@app.route("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.route("/api/health")
def health():
    db, rep = _reporter()
    try:
        with_data = sum(1 for pid in ALL_PART_IDS if rep.get_detail(pid))
    finally:
        db.conn.close()
    return jsonify({
        "ok": True,
        "parts_total": len(ALL_PART_IDS),
        "parts_with_data": with_data,
    })


@app.route("/api/report")
def report():
    db, rep = _reporter()
    try:
        data = rep.build_report()
    finally:
        db.conn.close()
    return jsonify(data)


@app.route("/api/part/<part_id>")
def part(part_id):
    db, rep = _reporter()
    try:
        detail = rep.get_detail(part_id)
    finally:
        db.conn.close()
    if not detail:
        return jsonify({"error": "no data", "part_id": part_id}), 404
    return jsonify(detail)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"[API] 啟動於 http://127.0.0.1:{port}  （Ctrl+C 結束）")
    app.run(host="127.0.0.1", port=port, debug=False)
