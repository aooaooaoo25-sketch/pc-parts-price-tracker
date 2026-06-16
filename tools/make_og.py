# -*- coding: utf-8 -*-
"""產生 Open Graph 社群分享圖 og.png（1200x630，深色、與站台風格一致）。
執行：python tools/make_og.py  → 專案根目錄產生 og.png
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1200, 630
BG    = (11, 13, 18)     # #0b0d12
TEXT  = (221, 227, 244)  # #dde3f4
TEXT2 = (126, 136, 168)  # #7e88a8
ACCENT= (91, 140, 255)   # #5b8cff
TEAL  = (34, 211, 200)   # #22d3c8
BOLD  = r"C:\Windows\Fonts\msjhbd.ttc"
REG   = r"C:\Windows\Fonts\msjh.ttc"


def font(path, size):
    return ImageFont.truetype(path, size, index=0)


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)
d.rectangle([0, 0, W - 1, H - 1], outline=(37, 40, 54), width=2)

# 右上裝飾走勢線（柔光 + 主線 + 端點）
pts = [(700, 215), (775, 150), (850, 188), (930, 112), (1012, 152), (1104, 92)]
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(glow).line(pts, fill=(91, 140, 255, 70), width=16, joint="curve")
img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
d = ImageDraw.Draw(img)
d.line(pts, fill=ACCENT, width=5, joint="curve")
for p in pts:
    d.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=TEXT)

# logo 方塊
d.rounded_rectangle([80, 70, 184, 174], radius=22, fill=ACCENT)
lf = font(BOLD, 46)
b = d.textbbox((0, 0), "PC", font=lf)
d.text((80 + (104 - (b[2] - b[0])) / 2 - b[0], 70 + (104 - (b[3] - b[1])) / 2 - b[1]),
       "PC", font=lf, fill=(255, 255, 255))

# 文案
d.text((80, 250), "二手 PC 零件行情追蹤", font=font(BOLD, 82), fill=TEXT)
d.text((82, 366), "台灣 GPU・CPU・RAM・SSD・HDD 二手價格走勢", font=font(REG, 35), fill=TEXT2)
d.text((82, 430), "全新定價 × 二手均價 × eBay 海外參考", font=font(REG, 34), fill=ACCENT)
d.text((82, 528), "usedpcpartprice.com", font=font(BOLD, 40), fill=TEAL)

out = os.path.join(ROOT, "og.png")
img.save(out, "PNG")
print("saved", out, img.size, f"{os.path.getsize(out)/1024:.1f} KB")
