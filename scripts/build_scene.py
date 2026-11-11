"""Build the Cozy Nook master scene from scratch and save it.

Usage:
    blender -b --factory-startup -P scripts/build_scene.py -- [--out blend/CozyNook_Master.blend]
                                                              [--preview renders/wip/env.png]
"""
import argparse
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import cozy  # noqa: E402
from cozy import environment, lighting, utils  # noqa: E402

for mod in (utils, cozy.materials, environment, lighting):
    importlib.reload(mod)

try:
    from cozy import char_pip, char_tock, animation  # noqa: E402
    for mod in (char_pip, char_tock, animation):
        importlib.reload(mod)
except ImportError:
    char_pip = char_tock = animation = None


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "blend", "CozyNook_Master.blend"))
    ap.add_argument("--preview", default=None)
    ap.add_argument("--camera", default="CAM_Hero_Wide")
    ap.add_argument("--engine", default="EEVEE")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--pct", type=int, default=50)
    ap.add_argument("--frame", type=int, default=1)
    ap.add_argument("--no-chars", action="store_true")
    return ap.parse_args(argv)


def main():
    args = parse_args()
    scene = utils.reset_scene()
    scene.name = "SCN_CozyNook"

    env = utils.collection("ENV")
    chars = utils.collection("CH")
    lgt = utils.collection("LGT")
    cams = utils.collection("CAM")

    environment.build(env)
    lighting.build_world()
    lighting.build_lights(lgt)

    rigs = {}
    if char_pip and not args.no_chars:
        rigs['pip'] = char_pip.build(utils.collection("CH_Pip", chars))
        rigs['tock'] = char_tock.build(utils.collection("CH_Tock", chars))
        animation.build(scene, rigs, cams)

    hero = lighting.camera("CAM_Hero_Wide", cams, (6.2, -7.4, 4.6), (-0.35, 0.25, 0.85), lens=42)
    scene.camera = bpy.data.objects.get(args.camera) or hero
    lighting.render_settings(scene, args.engine, samples=args.samples, pct=args.pct)
    scene.frame_set(args.frame)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.out, compress=True, relative_remap=True)
    print(f"[build] saved {args.out}")

    if args.preview:
        scene.render.filepath = args.preview
        bpy.ops.render.render(write_still=True)
        print(f"[build] preview {args.preview}")


if __name__ == "__main__":
    main()
