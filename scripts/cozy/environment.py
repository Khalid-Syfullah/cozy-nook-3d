"""ENV - "Cozy Nook" cut-away living room diorama.

Layout (metres, floor top at z=0, front of set is -Y):
  floor    x[-2.5, 2.5]  y[-2.0, 2.0]
  back wall   y[2.0, 2.2]   with window x[0.25, 1.55] z[0.95, 2.15]
  left wall   x[-2.7, -2.5]
Every prop is built around its own root empty (``ENV_<Prop>``) so it can be
moved as one unit, re-used, or linked into another shot file.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import materials as M
from .utils import (TAU, add_bevel, add_solidify, add_subsurf, assign, bm_box, bm_cyl,
                    bm_leaf, bm_sphere, bm_torus, box, collection, curve_from_points, cyl, empty,
                    mesh_object, new_bm, sphere)

WALL_H = 2.6
WIN = dict(x0=0.25, x1=1.55, z0=0.95, z1=2.15)


# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #
def palette():
    return dict(
        plaster=M.noisy("Plaster", "#efe2cc", "#e6d4b8", rough=0.85, scale=3, bump=0.03),
        wainscot=M.noisy("Wainscot_Sage", "#8fa58a", "#87a083", rough=0.55, scale=2, bump=0.01),
        trim=M.solid("Trim_Cream", "#f4ecdc", rough=0.4),
        floor=M.wood("Wood_Floor", "#c99463", "#93603a", rand_attr="board_rand"),
        walnut=M.wood("Wood_Walnut", "#6b4430", "#3d261b", grain=(0.6, 14, 14), coat=0.3),
        oak=M.wood("Wood_Oak", "#d6a876", "#a8784c", grain=(0.6, 12, 12)),
        sofa=M.fabric("Fabric_Terracotta", "#c46f50", "#b5603f"),
        mustard=M.fabric("Fabric_Mustard", "#e2aa3d", "#d39a30"),
        teal=M.fabric("Fabric_Teal", "#3f8f8a", "#367d78"),
        cream_cloth=M.fabric("Fabric_Linen", "#f1e6cf", "#e5d6b8", scale=90),
        curtain=M.fabric("Fabric_Curtain", "#e9c7a0", "#dcb68c", scale=80),
        blanket=M.fabric("Knit_Blanket", "#e9dcc4", "#d8c8a8", scale=25),
        terracotta=M.noisy("Ceramic_Terracotta", "#c56b45", "#ad5a39", rough=0.75, scale=6),
        ceramic=M.noisy("Ceramic_Cream", "#f3ead9", "#e7dcc6", rough=0.25, scale=5, bump=0.005, coat=0.4),
        ceramic_teal=M.noisy("Ceramic_Teal", "#3d8a86", "#2f7470", rough=0.25, scale=5, bump=0.005, coat=0.4),
        leaf=M.noisy("Leaf_Green", "#4f8a46", "#3f7539", rough=0.45, scale=4, bump=0.02, sss=0.1),
        leaf_light=M.noisy("Leaf_LightGreen", "#7fae55", "#6b9c47", rough=0.45, scale=4, bump=0.02, sss=0.1),
        soil=M.noisy("Soil", "#3a281d", "#2b1d14", rough=1.0, scale=40, bump=0.3),
        brass=M.solid("Metal_Brass", "#d9a75a", rough=0.3, metal=1.0),
        black_metal=M.solid("Metal_Black", "#222222", rough=0.45, metal=0.8),
        lamp_shade=M.emission("Lamp_Shade_Glow", "#ffcf8a", 1.2, base="#f3e6c9"),
        bulb=M.emission("Bulb_Warm", "#ffc77a", 25.0),
        sky=M.sky_backdrop("Sky_Backdrop", "#8fb7d9", "#ffd3a1", 3.0),
        tree=M.noisy("Tree_Silhouette", "#3c6b47", "#2e5638", rough=0.9, scale=3),
        rug=M.rings("Rug_Rings", [(0.0, "#f1e2c4"), (0.22, "#c4694a"), (0.30, "#f1e2c4"),
                                   (0.52, "#3f7f7c"), (0.60, "#f1e2c4"), (0.78, "#dca444"),
                                   (0.86, "#f1e2c4")], scale=0.77),
        paper=M.solid("Paper", "#f5efe3", rough=0.8),
        dock_glow=M.emission("Dock_Glow", "#5ff0dd", 6.0),
        cap=M.solid("Diorama_Cap", "#2c1e17", rough=0.6),
    )


def attach(children, root):
    for c in children:
        c.parent = root
    return root


# --------------------------------------------------------------------------- #
# Architecture
# --------------------------------------------------------------------------- #
def build_floor(col, P, seed=7):
    rnd = random.Random(seed)
    bm = new_bm()
    width, gap, thick = 0.2, 0.004, 0.03
    x0, x1, y0, y1 = -2.5, 2.5, -2.0, 2.0
    rand_vals = []
    row = 0
    y = y0
    while y < y1 - 1e-4:
        w = min(width, y1 - y)
        x = x0 - rnd.uniform(0, 1.2) if row else x0
        while x < x1:
            length = rnd.uniform(1.1, 2.0)
            xa, xb = max(x, x0), min(x + length, x1)
            if xb - xa > 0.05:
                before = len(bm.verts)
                bm_box((xb - xa - gap, w - gap, thick), bm=bm,
                       offset=((xa + xb) / 2, y + w / 2, -thick / 2))
                rand_vals.append((before, len(bm.verts), rnd.random()))
            x += length
        y += w
        row += 1
    obj = mesh_object("ENV_Floor", bm, col, mat=P['floor'], smooth=False)
    attr = obj.data.color_attributes.new("board_rand", 'FLOAT_COLOR', 'POINT')
    for a, b, r in rand_vals:
        for i in range(a, b):
            attr.data[i].color = (r, r, r, 1)
    add_bevel(obj, 0.004, 2, harden=False)
    return obj


def build_walls(col, P):
    objs = []
    t = 0.2
    w = WIN
    # back wall pieces around the window opening
    pieces = [
        ("Left", (-2.7, w['x0']), (0, WALL_H)),
        ("Right", (w['x1'], 2.5), (0, WALL_H)),
        ("Sill", (w['x0'], w['x1']), (0, w['z0'])),
        ("Head", (w['x0'], w['x1']), (w['z1'], WALL_H)),
    ]
    for tag, (xa, xb), (za, zb) in pieces:
        objs.append(box(f"ENV_WallBack_{tag}", (xb - xa, t, zb - za), col,
                        loc=((xa + xb) / 2, 2.0 + t / 2, (za + zb) / 2), mat=P['plaster']))
    objs.append(box("ENV_WallLeft", (t, 4.2, WALL_H), col,
                    loc=(-2.5 - t / 2, 0.1, WALL_H / 2), mat=P['plaster']))
    # dark cut-away caps (diorama look)
    objs.append(box("ENV_WallCap_Back", (5.24, t + 0.04, 0.04), col, loc=(-0.1, 2.1, WALL_H + 0.02), mat=P['cap']))
    objs.append(box("ENV_WallCap_Left", (t + 0.04, 4.24, 0.04), col, loc=(-2.6, 0.1, WALL_H + 0.02), mat=P['cap']))
    objs.append(box("ENV_WallCap_LeftEnd", (t + 0.04, 0.04, WALL_H + 0.04), col, loc=(-2.6, -2.0, WALL_H / 2), mat=P['cap']))
    objs.append(box("ENV_WallCap_BackEnd", (0.04, t + 0.04, WALL_H + 0.04), col, loc=(2.5, 2.1, WALL_H / 2), mat=P['cap']))

    # beadboard wainscoting, chair rail and skirting
    bm = new_bm()
    h = 0.9
    x = -2.5
    while x < 2.5 - 0.01:
        bm_box((0.095, 0.018, h), bm=bm, offset=(x + 0.05, 2.0 - 0.009, h / 2))
        x += 0.1
    y = -2.0
    while y < 2.0 - 0.01:
        bm_box((0.018, 0.095, h), bm=bm, offset=(-2.5 + 0.009, y + 0.05, h / 2))
        y += 0.1
    bead = mesh_object("ENV_Wainscot", bm, col, mat=P['wainscot'], smooth=False)
    add_bevel(bead, 0.006, 2, harden=False)
    objs.append(bead)
    for name, size, loc in [
        ("ENV_ChairRail_Back", (5.0, 0.045, 0.05), (0.0, 1.975, 0.92)),
        ("ENV_ChairRail_Left", (0.045, 4.0, 0.05), (-2.475, 0.0, 0.92)),
        ("ENV_Skirting_Back", (5.0, 0.03, 0.12), (0.0, 1.97, 0.06)),
        ("ENV_Skirting_Left", (0.03, 4.0, 0.12), (-2.47, 0.0, 0.06)),
        ("ENV_Cornice_Back", (5.0, 0.05, 0.08), (0.0, 1.975, WALL_H - 0.04)),
        ("ENV_Cornice_Left", (0.05, 4.0, 0.08), (-2.475, 0.0, WALL_H - 0.04)),
    ]:
        objs.append(box(name, size, col, loc=loc, mat=P['trim'], bevel=0.01, segs=2))

    # ceiling: casts shadow / bounce light, hidden from camera (cut-away)
    ceil = box("ENV_Ceiling_Hidden", (5.4, 4.4, 0.1), col, loc=(-0.1, 0.1, WALL_H + 0.1), mat=P['plaster'])
    ceil.visible_camera = False
    objs.append(ceil)
    # same trick for the open right side so the sun only enters via the window
    blocker = box("ENV_WallRight_Hidden", (0.1, 4.6, WALL_H + 0.5), col, loc=(2.65, 0.1, WALL_H / 2 - 0.2),
                  mat=P['plaster'])
    blocker.visible_camera = False
    blocker.visible_diffuse = False
    blocker.visible_glossy = False
    objs.append(blocker)

    # diorama plinth
    objs.append(box("ENV_Plinth", (5.6, 4.6, 0.32), col, loc=(-0.1, 0.1, -0.03 - 0.16),
                    mat=P['walnut'], bevel=0.02, segs=3))
    objs.append(box("ENV_Plinth_Trim", (5.66, 4.66, 0.04), col, loc=(-0.1, 0.1, -0.35),
                    mat=P['brass'], bevel=0.01, segs=2))
    return objs


def build_window(col, P):
    root = empty("ENV_Window", col, (0, 0, 0))
    w = WIN
    fw, d = 0.07, 0.24
    cx, cz = (w['x0'] + w['x1']) / 2, (w['z0'] + w['z1']) / 2
    W, H = w['x1'] - w['x0'], w['z1'] - w['z0']
    parts = [
        box("ENV_Window_FrameTop", (W, d, fw), col, loc=(cx, 2.1, w['z1'] - fw / 2), mat=P['trim'], bevel=0.008),
        box("ENV_Window_FrameBot", (W, d, fw), col, loc=(cx, 2.1, w['z0'] + fw / 2), mat=P['trim'], bevel=0.008),
        box("ENV_Window_FrameL", (fw, d, H), col, loc=(w['x0'] + fw / 2, 2.1, cz), mat=P['trim'], bevel=0.008),
        box("ENV_Window_FrameR", (fw, d, H), col, loc=(w['x1'] - fw / 2, 2.1, cz), mat=P['trim'], bevel=0.008),
        box("ENV_Window_MullionV", (0.035, 0.05, H), col, loc=(cx, 2.12, cz), mat=P['trim'], bevel=0.005),
        box("ENV_Window_MullionH", (W, 0.05, 0.035), col, loc=(cx, 2.12, cz + 0.05), mat=P['trim'], bevel=0.005),
        box("ENV_Window_Sill", (W + 0.24, 0.2, 0.05), col, loc=(cx, 1.93, w['z0'] - 0.01), mat=P['trim'], bevel=0.012),
    ]
    # curtain rod + finials
    parts.append(cyl("ENV_CurtainRod", 0.014, W + 0.6, col, loc=(w['x0'] - 0.3, 1.9, w['z1'] + 0.2),
                     rot=(0, math.pi / 2, 0), mat=P['brass'], segs=16))
    for i, x in enumerate((w['x0'] - 0.32, w['x1'] + 0.32)):
        parts.append(sphere(f"ENV_CurtainFinial_{i}", 0.03, col, loc=(x, 1.9, w['z1'] + 0.2), mat=P['brass'], segs=16, rings=8))
    # wavy curtains (gathered at the bottom by a tie-back)
    for side, xc in (("L", w['x0'] - 0.08), ("R", w['x1'] + 0.08)):
        bm = new_bm()
        nx, nz = 40, 30
        top, bot = w['z1'] + 0.19, 0.55
        verts = []
        for j in range(nz + 1):
            row = []
            t = j / nz
            z = top + (bot - top) * t
            gather = 1.0 - 0.55 * math.sin(min(t / 0.6, 1.0) * math.pi / 2) if t < 0.85 else 0.62
            for i in range(nx + 1):
                u = i / nx - 0.5
                x = xc + u * 0.5 * gather
                y = 1.88 - 0.04 * math.sin(u * TAU * 3.5) * (1.2 - 0.4 * gather)
                row.append(bm.verts.new((x, y, z)))
            verts.append(row)
        uv = bm.loops.layers.uv.active
        for j in range(nz):
            for i in range(nx):
                f = bm.faces.new((verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]))
                for loop, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                    loop[uv].uv = (a / nx, b / nz)
        c = mesh_object(f"ENV_Curtain_{side}", bm, col, mat=P['curtain'])
        add_solidify(c, 0.008, 0)
        add_subsurf(c, 1)
        parts.append(c)
        parts.append(mesh_object(f"ENV_CurtainTie_{side}", bm_torus(0.07, 0.012, 24, 8), col,
                                 loc=(xc, 1.88, 1.05), rot=(0, 0, 0), mat=P['mustard']))
    # outside: sky card + soft tree shapes. Kept inside the wall's silhouette from
    # the hero camera so nothing "leaks" past the diorama edge.
    sky = mesh_object("ENV_Outside_Sky", bm_box((2.75, 0.02, 2.1)), col, loc=(0.57, 3.6, 1.25),
                      mat=P['sky'], smooth=False)
    sky.visible_shadow = False
    parts.append(sky)
    rnd = random.Random(3)
    for i in range(6):
        r = rnd.uniform(0.32, 0.5)
        t = sphere(f"ENV_Outside_Tree_{i:02d}", r, col,
                   loc=(rnd.uniform(-0.2, 1.6), rnd.uniform(2.9, 3.3), rnd.uniform(0.75, 1.5)),
                   mat=P['tree'], scale=(1, 0.8, 1.1), segs=24, rings=12)
        t.visible_shadow = False
        parts.append(t)
    return attach(parts, root)


# --------------------------------------------------------------------------- #
# Furniture
# --------------------------------------------------------------------------- #
def build_sofa(col, P, loc, rot_z):
    root = empty("ENV_Sofa", col, loc)
    root.rotation_euler.z = rot_z
    parts = []
    for i, (x, y) in enumerate([(-0.9, -0.33), (0.9, -0.33), (-0.9, 0.33), (0.9, 0.33)]):
        parts.append(cyl(f"ENV_Sofa_Leg_{i}", 0.03, 0.1, col, loc=(x, y, 0), r2=0.022, mat=P['walnut'], segs=16))
    parts.append(box("ENV_Sofa_Base", (2.0, 0.85, 0.2), col, loc=(0, 0, 0.2), mat=P['sofa'], bevel=0.05, segs=4))
    for s in (-1, 1):
        parts.append(box(f"ENV_Sofa_Arm_{'L' if s < 0 else 'R'}", (0.2, 0.85, 0.5), col,
                         loc=(s * 0.9, 0, 0.37), mat=P['sofa'], bevel=0.085, segs=5))
    parts.append(box("ENV_Sofa_Back", (1.6, 0.2, 0.58), col, loc=(0, 0.325, 0.58), mat=P['sofa'], bevel=0.07, segs=4))
    for i, x in enumerate((-0.4, 0.4)):
        parts.append(box(f"ENV_Sofa_SeatCushion_{i}", (0.79, 0.64, 0.17), col, loc=(x, -0.07, 0.385),
                         mat=P['sofa'], bevel=0.075, segs=5))
        parts.append(box(f"ENV_Sofa_BackCushion_{i}", (0.78, 0.18, 0.44), col, loc=(x, 0.17, 0.69),
                         rot=(-0.2, 0, 0), mat=P['sofa'], bevel=0.08, segs=5))
    for name, x, mat, rz in (("Mustard", -0.66, P['mustard'], 0.25), ("Teal", 0.68, P['teal'], -0.2)):
        p = box(f"ENV_Sofa_Pillow_{name}", (0.34, 0.11, 0.34), col, loc=(x, 0.03, 0.62),
                rot=(-0.3, 0.0, rz), mat=mat, subsurf=2)
        parts.append(p)
    bl = box("ENV_Sofa_Blanket", (0.28, 0.7, 0.05), col, loc=(0.9, -0.02, 0.64), rot=(0, 0, 0),
             mat=P['blanket'], bevel=0.02, segs=3)
    parts.append(bl)
    return attach(parts, root)


def build_mug(name, col, mat, loc=(0, 0, 0), r=0.045, h=0.1):
    bm = bm_cyl(r, h, 32)
    top = [f for f in bm.faces if f.normal.z > 0.9][0]
    bmesh.ops.inset_individual(bm, faces=[top], thickness=0.007)
    bmesh.ops.translate(bm, verts=top.verts, vec=(0, 0, -(h - 0.012)))
    mug = mesh_object(name, bm, col, loc=loc, mat=mat)
    add_bevel(mug, 0.003, 2, angle=60, harden=False)
    hb = bm_torus(0.028, 0.008, 20, 10, arc=math.pi * 1.25)
    bmesh.ops.rotate(hb, verts=hb.verts, cent=(0, 0, 0),
                     matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
    bmesh.ops.rotate(hb, verts=hb.verts, cent=(0, 0, 0),
                     matrix=Matrix.Rotation(-math.pi * 0.625 + math.pi / 2, 3, 'Y'))
    bmesh.ops.translate(hb, verts=hb.verts, vec=(r + 0.008, 0, h * 0.52))
    handle = mesh_object(name + "_Handle", hb, col, mat=mat)
    handle.parent = mug
    return mug


def build_coffee_table(col, P, loc):
    root = empty("ENV_CoffeeTable", col, loc)
    parts = [cyl("ENV_CoffeeTable_Top", 0.46, 0.05, col, loc=(0, 0, 0.38), mat=P['oak'], segs=64, bevel=0.012)]
    for i in range(4):
        a = TAU * i / 4 + math.pi / 4
        leg = cyl(f"ENV_CoffeeTable_Leg_{i}", 0.025, 0.4, col, loc=(math.cos(a) * 0.3, math.sin(a) * 0.3, 0),
                  r2=0.018, mat=P['walnut'], segs=12)
        leg.rotation_euler = (math.sin(a) * -0.12, math.cos(a) * 0.12, 0)
        parts.append(leg)
    parts.append(build_mug("ENV_Mug_Table_A", col, P['ceramic_teal'], loc=(0.18, -0.12, 0.43)))
    m2 = build_mug("ENV_Mug_Table_B", col, P['ceramic'], loc=(0.05, -0.25, 0.43))
    m2.rotation_euler.z = 2.2
    parts.append(m2)
    # teapot
    pot = sphere("ENV_Teapot", 0.1, col, loc=(-0.12, 0.08, 0.43 + 0.085), mat=P['terracotta'], scale=(1, 1, 0.85))
    parts.append(pot)
    parts.append(sphere("ENV_Teapot_Lid", 0.045, col, loc=(-0.12, 0.08, 0.6), mat=P['terracotta'], scale=(1, 1, 0.45)))
    parts.append(sphere("ENV_Teapot_Knob", 0.015, col, loc=(-0.12, 0.08, 0.62), mat=P['brass']))
    spout = curve_from_points("ENV_Teapot_Spout", [(-0.03, 0.08, 0.5), (0.04, 0.08, 0.52), (0.06, 0.08, 0.58)],
                              col, depth=0.016, mat=P['terracotta'], kind='NURBS')
    spout.data.bevel_resolution = 4
    parts.append(spout)
    handle = mesh_object("ENV_Teapot_Handle", bm_torus(0.055, 0.012, 24, 8, arc=math.pi), col,
                         loc=(-0.22, 0.08, 0.52), rot=(math.pi / 2, math.pi / 2, 0), mat=P['terracotta'])
    parts.append(handle)
    # book stack
    z = 0.405
    for i, (c, w, h) in enumerate([("#2f5d62", 0.26, 0.035), ("#d9a441", 0.23, 0.03), ("#c4694a", 0.2, 0.028)]):
        b = box(f"ENV_CoffeeTable_Book_{i}", (w, w * 0.72, h), col, loc=(0.02, 0.22, z + h / 2),
                rot=(0, 0, 0.3 - i * 0.25), mat=M.solid(f"Book_{c}", c, 0.6), bevel=0.004, segs=2)
        parts.append(b)
        z += h
    return attach(parts, root)


def build_bookshelf(col, P, loc, seed=11):
    rnd = random.Random(seed)
    root = empty("ENV_Bookshelf", col, loc)
    W, D, H = 1.1, 0.32, 1.9
    t = 0.035
    parts = [
        box("ENV_Bookshelf_SideL", (t, D, H), col, loc=(-W / 2 + t / 2, 0, H / 2), mat=P['walnut'], bevel=0.006),
        box("ENV_Bookshelf_SideR", (t, D, H), col, loc=(W / 2 - t / 2, 0, H / 2), mat=P['walnut'], bevel=0.006),
        box("ENV_Bookshelf_Back", (W, 0.015, H), col, loc=(0, D / 2 - 0.0075, H / 2), mat=P['walnut']),
    ]
    shelves = [0.06, 0.5, 0.95, 1.4, H - t / 2]
    for i, z in enumerate(shelves):
        parts.append(box(f"ENV_Bookshelf_Shelf_{i}", (W - 2 * t, D - 0.015, t), col, loc=(0, -0.0075, z),
                         mat=P['walnut'], bevel=0.005))
    book_cols = ["#2f5d62", "#d9a441", "#c4694a", "#7b4b6a", "#e9dcc4", "#3f7f7c", "#a83f3f", "#5b6f8f", "#8f9a5b"]
    bm_books = {}
    for si, z in enumerate(shelves[:-1]):
        x = -W / 2 + t + 0.02
        x_end = W / 2 - t - 0.02
        # leave space for a decor item on some shelves
        decor_at = rnd.choice([None, 0.3, -0.25]) if si else None
        while x < x_end - 0.03:
            if decor_at is not None and abs(x - decor_at) < 0.12:
                x += 0.24
                continue
            bw = rnd.uniform(0.025, 0.055)
            bh = rnd.uniform(0.24, 0.36)
            bd = rnd.uniform(0.18, 0.24)
            c = rnd.choice(book_cols)
            lean = 0.0
            if rnd.random() < 0.08 and x + 0.1 < x_end:
                lean = 0.3
            bm = bm_books.setdefault(c, new_bm())
            base = len(bm.verts)
            bm_box((bw, bd, bh), bm=bm, offset=(0, 0, bh / 2))
            bm.verts.ensure_lookup_table()
            vs = [bm.verts[i] for i in range(base, len(bm.verts))]
            if lean:
                bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0),
                                 matrix=Matrix.Rotation(-lean, 3, 'Y'))
            bmesh.ops.translate(bm, verts=vs, vec=(x + bw / 2 + (bh * math.sin(lean) if lean else 0),
                                                   -0.02, z + t / 2))
            x += bw + (0.002 if not lean else bh * math.sin(lean) + 0.01)
        if decor_at is not None:
            # small potted succulent / vase as shelf dressing
            pot = cyl(f"ENV_Bookshelf_Pot_{si}", 0.05, 0.09, col, loc=(decor_at, -0.02, z + t / 2), r2=0.06,
                      mat=P['ceramic'] if si % 2 else P['terracotta'], segs=24, bevel=0.005)
            parts.append(pot)
            plant = sphere(f"ENV_Bookshelf_Succulent_{si}", 0.065, col, loc=(decor_at, -0.02, z + t / 2 + 0.12),
                           mat=P['leaf_light'], scale=(1, 1, 0.8), segs=16, rings=8)
            parts.append(plant)
    for c, bm in bm_books.items():
        b = mesh_object(f"ENV_Bookshelf_Books_{c.strip('#')}", bm, col, mat=M.solid(f"Book_{c}", c, 0.6), smooth=False)
        add_bevel(b, 0.003, 2, harden=False)
        parts.append(b)
    return attach(parts, root)


def build_floor_lamp(col, P, loc):
    root = empty("ENV_FloorLamp", col, loc)
    parts = [
        cyl("ENV_FloorLamp_Base", 0.16, 0.03, col, mat=P['black_metal'], segs=48, bevel=0.008),
        cyl("ENV_FloorLamp_Pole", 0.012, 1.5, col, loc=(0, 0, 0.03), mat=P['brass'], segs=16),
    ]
    bm = bm_cyl(0.24, 0.3, 48, r2=0.15, cap=False)
    shade = mesh_object("ENV_FloorLamp_Shade", bm, col, loc=(0, 0, 1.38), mat=P['lamp_shade'])
    add_solidify(shade, 0.006, 0)
    parts.append(shade)
    parts.append(sphere("ENV_FloorLamp_Bulb", 0.045, col, loc=(0, 0, 1.47), mat=P['bulb'], segs=16, rings=8))
    light = bpy.data.lights.new("LGT_FloorLamp", 'POINT')
    light.energy = 55
    light.color = (1.0, 0.72, 0.42)
    light.shadow_soft_size = 0.06
    lo = bpy.data.objects.new("LGT_FloorLamp", light)
    lo.location = (0, 0, 1.47)
    col.objects.link(lo)
    parts.append(lo)
    return attach(parts, root)


def build_plant(name, col, P, loc, kind='bush', seed=1, scale=1.0, pot_mat=None):
    rnd = random.Random(seed)
    root = empty(name, col, loc)
    pr, ph = 0.16 * scale, 0.3 * scale
    pot = cyl(name + "_Pot", pr * 0.78, ph, col, r2=pr, mat=pot_mat or P['terracotta'], segs=40, bevel=0.01)
    rim = mesh_object(name + "_PotRim", bm_torus(pr * 0.98, 0.018 * scale, 40, 10), col, loc=(0, 0, ph),
                      mat=pot_mat or P['terracotta'])
    soil = cyl(name + "_Soil", pr * 0.95, 0.01, col, loc=(0, 0, ph - 0.03), mat=P['soil'], segs=32)
    parts = [pot, rim, soil]
    leaves = new_bm()
    n = 26 if kind == 'bush' else 14
    for i in range(n):
        if kind == 'bush':
            L, Wd = rnd.uniform(0.22, 0.34) * scale, rnd.uniform(0.09, 0.13) * scale
            pitch = rnd.uniform(0.15, 1.1)
            curl = rnd.uniform(0.2, 0.5)
        else:  # snake plant - tall upright blades
            L, Wd = rnd.uniform(0.55, 0.9) * scale, rnd.uniform(0.06, 0.09) * scale
            pitch = rnd.uniform(1.25, 1.5)
            curl = 0.02
        lb = bm_leaf(L, Wd, curl)
        yaw = TAU * i / n + rnd.uniform(-0.3, 0.3)
        mat = Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(pitch, 4, 'X')
        h = ph - 0.02 + (rnd.uniform(0.05, 0.4) * scale if kind == 'bush' else 0)
        mat = Matrix.Translation((rnd.uniform(-0.04, 0.04) * scale, rnd.uniform(-0.04, 0.04) * scale, h)) @ mat
        bmesh.ops.transform(lb, matrix=mat, verts=lb.verts)
        me = bpy.data.meshes.new("tmp")
        lb.to_mesh(me)
        lb.free()
        leaves.from_mesh(me)
        bpy.data.meshes.remove(me)
    lv = mesh_object(name + "_Leaves", leaves, col, mat=P['leaf'])
    add_solidify(lv, 0.004, 0)
    parts.append(lv)
    return attach(parts, root)


def build_pip_bed(col, P, loc):
    root = empty("ENV_PipBed", col, loc)
    basket = cyl("ENV_PipBed_Basket", 0.36, 0.14, col, r2=0.4, mat=P['oak'], segs=48)
    rim = mesh_object("ENV_PipBed_Rim", bm_torus(0.4, 0.045, 48, 12), col, loc=(0, 0, 0.15), mat=P['oak'])
    cushion = sphere("ENV_PipBed_Cushion", 0.36, col, loc=(0, 0, 0.14), mat=P['cream_cloth'], scale=(1, 1, 0.22))
    pillow = box("ENV_PipBed_Pillow", (0.24, 0.1, 0.12), col, loc=(0, 0.2, 0.22), rot=(0.3, 0, 0),
                 mat=M.checker_cloth("Cloth_Check", "#d9a441", "#f1e2c4", 10), subsurf=2)
    return attach([basket, rim, cushion, pillow], root)


def build_tock_dock(col, P, loc):
    root = empty("ENV_TockDock", col, loc)
    pad = cyl("ENV_TockDock_Pad", 0.34, 0.05, col, mat=M.solid("Plastic_Cream", "#efe4cf", 0.35, coat=0.3), segs=64, bevel=0.015)
    ring = mesh_object("ENV_TockDock_Ring", bm_torus(0.27, 0.012, 64, 8), col, loc=(0, 0, 0.05), mat=P['dock_glow'])
    post = box("ENV_TockDock_Post", (0.1, 0.06, 0.42), col, loc=(0, 0.3, 0.05), mat=M.solid("Plastic_Cream", "#efe4cf"),
               bevel=0.03, segs=4, origin='bottom')
    led = sphere("ENV_TockDock_LED", 0.015, col, loc=(0, 0.268, 0.4), mat=P['dock_glow'], segs=12, rings=6)
    return attach([pad, ring, post, led], root)


def build_wall_decor(col, P):
    objs = []
    # picture frames on the left wall (facing +X)
    frames = [((0.0, 1.55), (0.55, 0.42), ["#f2d7a6", "#e9a96b", "#c4694a", "#3f7f7c", "#2f5d62"]),
              ((-0.62, 1.68), (0.32, 0.42), ["#f1e2c4", "#9fc3c0", "#3f7f7c", "#2f5d62"]),
              ((0.55, 1.75), (0.3, 0.3), ["#f6e3c6", "#dca444", "#c4694a", "#7b4b6a"])]
    for i, ((y, z), (w, h), cols) in enumerate(frames):
        root = empty(f"ENV_Frame_{i}", col, (-2.5 + 0.02, y, z))
        root.rotation_euler.z = math.pi / 2
        fr = box(f"ENV_Frame_{i}_Border", (w, 0.03, h), col, mat=P['walnut'] if i != 1 else P['trim'], bevel=0.006)
        art = box(f"ENV_Frame_{i}_Art", (w - 0.06, 0.006, h - 0.06), col, loc=(0, -0.016, 0),
                  mat=M.painting(f"Painting_{i}", cols, scale=1 + i * 0.3))
        objs.append(attach([fr, art], root))
    # wall clock (back wall, right of window)
    root = empty("ENV_WallClock", col, (2.0, 2.0, 1.95))
    face = cyl("ENV_WallClock_Face", 0.16, 0.025, col, rot=(math.pi / 2, 0, 0), mat=P['paper'], segs=48, origin='center')
    face.location.y = -0.0125
    rim = mesh_object("ENV_WallClock_Rim", bm_torus(0.165, 0.018, 48, 10), col, rot=(math.pi / 2, 0, 0),
                      mat=M.solid("Metal_Mustard", "#d9a441", 0.35, metal=0.3))
    rim.location.y = -0.02
    hands = []
    for j, (ln, ang, wd) in enumerate([(0.09, 0.9, 0.012), (0.13, -1.1, 0.008)]):
        h = box(f"ENV_WallClock_Hand_{j}", (wd, 0.004, ln), col, mat=P['cap'], origin='bottom')
        h.location = (0, -0.03 - j * 0.003, 0)
        h.rotation_euler.y = ang
        hands.append(h)
    for k in range(12):
        a = TAU * k / 12
        tick = box(f"ENV_WallClock_Tick_{k:02d}", (0.008, 0.003, 0.025 if k % 3 else 0.04), col,
                   loc=(math.sin(a) * 0.125, -0.027, math.cos(a) * 0.125), rot=(0, a, 0), mat=P['cap'])
        hands.append(tick)
    objs.append(attach([face, rim] + hands, root))
    # floating shelf (back wall, right) with dressing
    root = empty("ENV_WallShelf", col, (2.0, 1.88, 1.4))
    sh = box("ENV_WallShelf_Board", (0.7, 0.22, 0.035), col, mat=P['oak'], bevel=0.006)
    v1 = cyl("ENV_WallShelf_Vase", 0.04, 0.16, col, loc=(-0.22, 0, 0.0175), r2=0.025, mat=P['ceramic_teal'], segs=24)
    p = build_plant("ENV_WallShelf_Plant", col, P, (0.18, 0.0, 0.0175), 'bush', seed=5, scale=0.45, pot_mat=P['ceramic'])
    books = box("ENV_WallShelf_Books", (0.12, 0.16, 0.05), col, loc=(-0.02, 0, 0.0425), mat=M.solid("Book_#7b4b6a", "#7b4b6a", 0.6), bevel=0.004)
    objs.append(attach([sh, v1, p, books], root))
    return objs


def build_string_lights(col, P):
    """Fairy lights draped along the top of both walls."""
    root = empty("ENV_StringLights", col)
    parts = []
    runs = [((-2.45, 1.93), (2.4, 1.93), 5), ((-2.43, -1.95), (-2.43, 1.9), 4)]
    bulb = M.emission("Bulb_Fairy", "#ffd08a", 18.0)
    wire = M.solid("Wire_Dark", "#2a2622", 0.6)
    k = 0
    for ri, ((xa, ya), (xb, yb), swags) in enumerate(runs):
        pts = []
        N = 140
        for i in range(N + 1):
            t = i / N
            local = (t * swags) % 1.0
            sag = 0.16 * 4 * local * (1 - local)
            pts.append((xa + (xb - xa) * t, ya + (yb - ya) * t, 2.47 - sag))
        parts.append(curve_from_points(f"ENV_StringLights_Wire_{ri}", pts, col, depth=0.004, mat=wire, res=2))
        for i in range(0, N + 1, 5):
            x, y, z = pts[i]
            b = sphere(f"ENV_StringLights_Bulb_{k:03d}", 0.018, col, loc=(x, y, z - 0.02), mat=bulb, scale=(1, 1, 1.3),
                       segs=12, rings=6)
            b.visible_shadow = False
            parts.append(b)
            k += 1
    return attach(parts, root)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def build(env_col):
    P = palette()
    arch = collection("ENV_Architecture", env_col)
    furn = collection("ENV_Furniture", env_col)
    props = collection("ENV_Props", env_col)
    outside = collection("ENV_Outside", env_col)

    build_floor(arch, P)
    build_walls(arch, P)
    build_window(outside, P)

    rug = cyl("ENV_Rug", 1.35, 0.012, furn, loc=(-0.55, -0.05, 0.0), mat=P['rug'], segs=96, bevel=0.005)
    build_sofa(furn, P, (-2.02, 0.2, 0.0), math.pi / 2)
    build_coffee_table(furn, P, (-0.95, 0.35, 0.012))
    build_bookshelf(furn, P, (-1.5, 1.84, 0.0))
    build_floor_lamp(furn, P, (-2.22, 1.6, 0.0))
    build_pip_bed(furn, P, (0.9, 1.45, 0.0))
    build_tock_dock(furn, P, (1.75, 0.65, 0.0))

    build_plant("ENV_Plant_Bush", props, P, (-0.4, 1.68, 0.0), 'bush', seed=2, scale=1.3)
    build_plant("ENV_Plant_Snake", props, P, (2.2, 1.75, 0.0), 'snake', seed=4, scale=1.0, pot_mat=P['ceramic'])
    build_plant("ENV_Plant_Sill", props, P, (1.25, 1.95, 0.955), 'bush', seed=9, scale=0.4, pot_mat=P['ceramic_teal'])
    build_wall_decor(props, P)
    build_string_lights(props, P)
    return P
