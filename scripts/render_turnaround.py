"""Character turnaround / model-sheet renders on a neutral studio cyclorama.

Builds the character fresh from the pipeline modules (no dependency on the
master file) so the sheet always matches the current asset.

Usage:
    blender -b --factory-startup -P scripts/render_turnaround.py -- --char pip
        [--views front,threequarter,side,back] [--engine CYCLES] [--samples 128]
        [--pose] [--clay] [--wire] [--out renders/turnarounds] [--pct 100]
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from cozy import lighting, materials as M, utils  # noqa: E402
from cozy import char_pip, char_tock  # noqa: E402
from cozy.rig import key_pose  # noqa: E402

VIEWS = {'front': 0, 'threequarter': 35, 'side': 90, 'back': 180, 'threequarter_back': 145}
CHARS = {
    'pip': dict(mod=char_pip, height=0.72, title="Pip"),
    'tock': dict(mod=char_tock, height=0.95, title="Tock"),
}


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", default="pip")
    ap.add_argument("--views", default="front,threequarter,side,back")
    ap.add_argument("--engine", default="EEVEE")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--pct", type=int, default=50)
    ap.add_argument("--res", default="1080x1350")
    ap.add_argument("--pose", action="store_true", help="apply the character's hero pose")
    ap.add_argument("--clay", action="store_true", help="clay material override")
    ap.add_argument("--wire", action="store_true", help="clay + wireframe overlay (Cycles)")
    ap.add_argument("--out", default=os.path.join(ROOT, "renders", "turnarounds"))
    ap.add_argument("--save", default=None, help="optionally save the .blend")
    return ap.parse_args(argv)


def studio(col, height):
    # curved cyclorama
    bm = utils.new_bm()
    rows, R = 24, 1.2
    pts = [(-6.0, 0.0)] + [(2.0 - R + math.sin((math.pi / 2) * i / rows) * R,
                             R - math.cos((math.pi / 2) * i / rows) * R) for i in range(rows + 1)] + [(2.0, 6.0)]
    vs = [[bm.verts.new((x, y, z)) for (y, z) in pts] for x in (-6, 6)]
    for i in range(len(pts) - 1):
        bm.faces.new((vs[0][i], vs[1][i], vs[1][i + 1], vs[0][i + 1]))
    cyc = utils.mesh_object("STU_Cyclorama", bm, col, mat=M.solid("Studio_Backdrop", "#e9e1d3", rough=0.8))
    cyc.data.shade_smooth()
    key = lighting._light("STU_Key", 'AREA', col, (-1.4, -1.8, 1.8), 120, "#fff2e2", size=1.2,
                          target=(0, 0, height * 0.5))
    fill = lighting._light("STU_Fill", 'AREA', col, (1.8, -1.2, 0.9), 45, "#e4ecff", size=1.5,
                           target=(0, 0, height * 0.45))
    rim = lighting._light("STU_Rim", 'AREA', col, (0.6, 1.4, 1.6), 90, "#ffe0c0", size=0.8,
                          target=(0, 0, height * 0.6))
    world = bpy.data.worlds.new("WLD_Studio_Neutral")
    world.node_tree.nodes['Background'].inputs['Color'].default_value = M.hex_lin("#b8b2a8")
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.35
    bpy.context.scene.world = world
    return key, fill, rim


def clay_override(wire=False):
    nb = M.NodeBuilder("Clay_Override")
    nb.set(**{'Base Color': M.hex_lin("#bdb6ad"), 'Roughness': 0.55})
    if wire:
        wf = nb.node('ShaderNodeWireframe', use_pixel_size=True)
        wf.inputs['Size'].default_value = 0.6
        mix = nb.node('ShaderNodeMix', data_type='RGBA')
        nb.link(wf.outputs['Fac'], mix.inputs[0])
        mix.inputs[6].default_value = M.hex_lin("#bdb6ad")
        mix.inputs[7].default_value = M.hex_lin("#30343c")
        nb.link(mix.outputs[2], nb.bsdf.inputs['Base Color'])
    bpy.context.view_layer.material_override = nb.mat


def main():
    a = parse()
    spec = CHARS[a.char]
    scene = utils.reset_scene()
    col = utils.collection(f"CH_{spec['title']}")
    stu = utils.collection("STU")
    rig = spec['mod'].build(col)
    if a.pose and hasattr(spec['mod'], 'hero_pose'):
        spec['mod'].hero_pose(rig['arm'], 1)
    studio(stu, spec['height'])
    h = spec['height']
    target = utils.empty("STU_Target", stu, (0, 0, h * 0.48))
    cam = lighting.camera("CAM_Turnaround", stu, (0, -h * 3.4, h * 0.62), target.location, lens=70)
    scene.camera = cam
    w, hres = (int(x) for x in a.res.split("x"))
    lighting.render_settings(scene, 'CYCLES' if a.wire else a.engine, res=(w, hres), samples=a.samples, pct=a.pct)
    if a.clay or a.wire:
        clay_override(a.wire)
    os.makedirs(a.out, exist_ok=True)
    arm = rig['arm']
    suffix = "_wire" if a.wire else "_clay" if a.clay else ("_pose" if a.pose else "")
    for v in a.views.split(","):
        arm.rotation_euler.z = math.radians(VIEWS[v])
        scene.render.filepath = os.path.join(a.out, f"{spec['title']}_{v}{suffix}.png")
        bpy.ops.render.render(write_still=True)
        print("[turnaround]", scene.render.filepath)
    arm.rotation_euler.z = 0
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=a.save, compress=True)


if __name__ == "__main__":
    main()
