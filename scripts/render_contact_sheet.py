"""Render selected frames from the master file and tile them into a contact sheet
(animation review / dailies).

Usage:
    blender -b blend/CozyNook_Master.blend -P scripts/render_contact_sheet.py -- \
        --frames 1,60,110,140,160,190,220,250,280 --camera CAM_Anim --cols 3 \
        --out renders/wip/sheet.png [--pct 30] [--samples 16]
"""
import argparse
import os
import sys

import bpy
import numpy as np


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--camera", default="CAM_Anim")
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--pct", type=int, default=30)
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    scene = bpy.context.scene
    scene.camera = bpy.data.objects[a.camera]
    scene.render.resolution_percentage = a.pct
    if scene.render.engine == 'BLENDER_EEVEE':
        scene.eevee.taa_render_samples = a.samples
    tmp = os.path.join(os.path.dirname(os.path.abspath(a.out)), "_sheet_tmp")
    os.makedirs(tmp, exist_ok=True)
    tiles = []
    for f in [int(x) for x in a.frames.split(",")]:
        scene.frame_set(f)
        scene.render.filepath = os.path.join(tmp, f"f{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(scene.render.filepath)
        w, h = img.size
        tiles.append(np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4))
        bpy.data.images.remove(img)
    rows = (len(tiles) + a.cols - 1) // a.cols
    sheet = np.ones((rows * h, a.cols * w, 4), dtype=np.float32)
    for i, t in enumerate(tiles):
        r, c = divmod(i, a.cols)
        # numpy image origin is bottom-left in Blender pixel order
        y0 = (rows - 1 - r) * h
        sheet[y0:y0 + h, c * w:(c + 1) * w] = t
    out = bpy.data.images.new("sheet", a.cols * w, rows * h)
    out.pixels[:] = sheet.ravel()
    out.filepath_raw = os.path.abspath(a.out)
    out.file_format = 'PNG'
    out.save()
    for fn in os.listdir(tmp):
        os.remove(os.path.join(tmp, fn))
    os.rmdir(tmp)
    print("[sheet]", a.out)


if __name__ == "__main__":
    main()
