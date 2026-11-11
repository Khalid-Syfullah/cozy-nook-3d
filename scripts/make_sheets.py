"""Compose portfolio sheets from rendered images (requires Pillow: pip install pillow).

  renders/sheets/Pip_ModelSheet.png    turnaround + pose + wireframe + palette + specs
  renders/sheets/Tock_ModelSheet.png
  renders/sheets/Env_Breakdown.png     clay vs final, side by side

Usage:
    python3 scripts/make_sheets.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TURN = os.path.join(ROOT, "renders", "turnarounds")
STILLS = os.path.join(ROOT, "renders", "stills")
OUT = os.path.join(ROOT, "renders", "sheets")

BG = (26, 31, 41)
INK = (240, 233, 222)
MUTED = (150, 158, 172)
ACCENT = (238, 124, 86)

CHARS = {
    "Pip": dict(
        tagline="The sprout. Curious, easily delighted, a sunset watcher.",
        palette=[("Skin", "#7cc89f"), ("Belly", "#fff1d8"), ("Blush", "#f3968a"),
                 ("Leaf", "#93cf5a"), ("Scarf", "#e7a436"), ("Eye", "#1b1820")],
        specs=["Height 0.70 m", "12.7k base tris / 41k subdivided", "16-bone rig, procedural weights",
               "Single skinned body + rigid face parts", "Spring-baked sprout, mug-driven IK arms"],
    ),
    "Tock": dict(
        tagline="The hover-bot. Dutiful, gentle, brings cocoa at sunset.",
        palette=[("Shell", "#f4ecdf"), ("Coral", "#ee7c56"), ("Rubber", "#2f3337"),
                 ("Screen", "#0d1b1d"), ("Glow", "#5ee8d6"), ("Bulb", "#ff9a2e")],
        specs=["Height 0.93 m (hovering 0.10 m)", "12.9k base tris / 23k with bevels",
               "22-bone rig, rigid skinning (engine-ready)", "Expression bones: pill / happy-arc eyes",
               "Baked banking + antenna follow-through"],
    ),
}


def font(size, bold=False):
    candidates = ["/System/Library/Fonts/Avenir Next.ttc", "/System/Library/Fonts/Helvetica.ttc",
                  "/Library/Fonts/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size, index=(1 if bold else 0) if path.endswith(".ttc") else 0)
            except OSError:
                continue
    return ImageFont.load_default()


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def fit(img, w, h):
    im = img.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    return im


def crop_center(img, frac_w=0.74, frac_h=0.86, y_off=0.06):
    w, h = img.size
    cw, ch = int(w * frac_w), int(h * frac_h)
    x0 = (w - cw) // 2
    y0 = int((h - ch) / 2 + h * y_off)
    return img.crop((x0, y0, x0 + cw, y0 + ch))


def model_sheet(name):
    spec = CHARS[name]
    W, H = 3000, 1800
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((80, 60), name.upper(), font=font(96, True), fill=INK)
    d.text((80, 175), spec["tagline"], font=font(36), fill=MUTED)
    d.text((W - 80, 80), "COZY NOOK  ·  CHARACTER MODEL SHEET", font=font(30, True), fill=ACCENT, anchor="ra")

    views = ["front", "threequarter", "side", "back"]
    tile_w, tile_h, y0 = 520, 760, 260
    for i, v in enumerate(views):
        p = os.path.join(TURN, f"{name}_{v}.png")
        if not os.path.exists(p):
            continue
        im = fit(crop_center(Image.open(p).convert("RGB")), tile_w, tile_h)
        x = 80 + i * (tile_w + 24)
        sheet.paste(im, (x, y0))
        d.text((x + 12, y0 + im.size[1] + 14), v.replace("threequarter", "3/4").upper(), font=font(26, True),
               fill=MUTED)

    # pose + wire column
    x_r = 80 + 4 * (tile_w + 24) + 20
    col_w = W - x_r - 80
    pose = os.path.join(TURN, f"{name}_threequarter_pose.png")
    if os.path.exists(pose):
        im = fit(crop_center(Image.open(pose).convert("RGB")), col_w, tile_h)
        sheet.paste(im, (x_r, y0))
        d.text((x_r + 12, y0 + im.size[1] + 14), "HERO POSE", font=font(26, True), fill=MUTED)

    y2 = y0 + tile_h + 90
    wires = [os.path.join(TURN, f"{name}_{v}_wire.png") for v in ("front", "threequarter")]
    for i, p in enumerate(wires):
        if os.path.exists(p):
            im = fit(crop_center(Image.open(p).convert("RGB")), 400, 520)
            x = 80 + i * 424
            sheet.paste(im, (x, y2))
    d.text((80, y2 + 540), "TOPOLOGY (CLAY + WIRE)", font=font(26, True), fill=MUTED)

    # palette
    xp = 80 + 2 * 424 + 40
    d.text((xp, y2), "PALETTE", font=font(30, True), fill=INK)
    for i, (label, hx) in enumerate(spec["palette"]):
        cx = xp + (i % 3) * 230
        cy = y2 + 60 + (i // 3) * 170
        d.rounded_rectangle((cx, cy, cx + 200, cy + 110), radius=18, fill=hex_rgb(hx), outline=(70, 76, 90), width=2)
        d.text((cx, cy + 120), f"{label}  {hx.upper()}", font=font(22), fill=MUTED)

    # specs
    xs = xp + 3 * 230 + 40
    d.text((xs, y2), "SPECS", font=font(30, True), fill=INK)
    for i, line in enumerate(spec["specs"]):
        d.ellipse((xs, y2 + 76 + i * 64, xs + 12, y2 + 88 + i * 64), fill=ACCENT)
        d.text((xs + 28, y2 + 66 + i * 64), line, font=font(28), fill=INK)
    d.text((W - 80, H - 60), "Blender 5.2  ·  EEVEE / Cycles  ·  procedural pipeline", font=font(24),
           fill=MUTED, anchor="ra")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{name}_ModelSheet.png")
    sheet.save(path, optimize=True)
    print("[sheet]", path)


def env_breakdown():
    a = os.path.join(STILLS, "CozyNook_01_Hero_Wide_clay.png")
    b = os.path.join(STILLS, "CozyNook_01_Hero_Wide.png")
    if not (os.path.exists(a) and os.path.exists(b)):
        return
    A, B = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    w, h = 1600, 900
    A, B = A.resize((w, h), Image.LANCZOS), B.resize((w, h), Image.LANCZOS)
    sheet = Image.new("RGB", (w * 2 + 120, h + 260), BG)
    d = ImageDraw.Draw(sheet)
    d.text((40, 40), "COZY NOOK  ·  ENVIRONMENT BREAKDOWN", font=font(56, True), fill=INK)
    sheet.paste(A, (40, 160))
    sheet.paste(B, (w + 80, 160))
    d.text((40, h + 180), "CLAY  ·  206 objects · 39.5k base tris · modelling + light blocking", font=font(28),
           fill=MUTED)
    d.text((w + 80, h + 180), "FINAL  ·  66 procedural materials · sunset sun pool · practicals", font=font(28),
           fill=MUTED)
    path = os.path.join(OUT, "Env_Breakdown.png")
    sheet.save(path, optimize=True)
    print("[sheet]", path)


if __name__ == "__main__":
    for n in CHARS:
        model_sheet(n)
    env_breakdown()
