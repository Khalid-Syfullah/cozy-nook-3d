"""Portfolio stills from the master file (Cycles by default).

Each entry is (output name, camera, frame). Add ``--clay`` for a clay
(material override) pass of the same shots - useful as a modelling breakdown.

Usage:
    blender -b blend/CozyNook_Master.blend -P scripts/render_stills.py -- \
        [--engine CYCLES] [--samples 256] [--pct 100] [--only Hero_Wide] [--clay]
"""
import argparse
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from cozy import lighting, materials as M  # noqa: E402

SHOTS = [
    ("01_Hero_Wide", "CAM_Hero_Wide", 236),
    ("02_TwoShot_Handoff", "CAM_Close_TwoShot", 222),
    ("03_TwoShot_Sip", "CAM_Close_TwoShot", 258),
    ("04_Pip_Closeup", "CAM_Close_Pip", 134),
    ("05_Tock_Closeup", "CAM_Close_Tock", 190),
    ("06_Opening", "CAM_Anim", 1),
]


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="CYCLES")
    ap.add_argument("--samples", type=int, default=256)
    ap.add_argument("--pct", type=int, default=100)
    ap.add_argument("--only", default=None)
    ap.add_argument("--clay", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "stills"))
    a = ap.parse_args(argv)

    scene = bpy.context.scene
    lighting.render_settings(scene, a.engine, samples=a.samples, pct=a.pct)
    scene.render.use_motion_blur = False          # crisp stills
    if a.clay:
        nb = M.NodeBuilder("Clay_Override")
        nb.set(**{'Base Color': M.hex_lin("#c9c2b8"), 'Roughness': 0.6})
        scene.view_layers[0].material_override = nb.mat
    os.makedirs(a.out, exist_ok=True)
    for name, cam, frame in SHOTS:
        if a.only and a.only not in name:
            continue
        scene.camera = bpy.data.objects[cam]
        scene.frame_set(frame)
        scene.render.filepath = os.path.join(a.out, f"CozyNook_{name}{'_clay' if a.clay else ''}.png")
        bpy.ops.render.render(write_still=True)
        print("[still]", scene.render.filepath)


if __name__ == "__main__":
    main()
