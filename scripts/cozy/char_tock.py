"""CH_Tock - a retro hover-robot housemate (hard-surface, rigid-skinned).

Design notes (docs/CHARACTER_BIBLE.md):
  * 0.93 m to antenna tip, hovers ~0.1 m above the floor on a thruster saucer.
  * Shape language: soft rounded boxes (friendly), coral accents vs cream shell.
  * Face is an emissive CRT screen; expressions are swapped by scaling eye
    bones (normal pills <-> "happy" arcs) - cheap, readable and game-ready.
  * Every part is single-bone skinned (no deformation), FBX/engine friendly.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import materials as M
from .rig import bone_parent, create_armature, key_pose, rigid_skin
from .utils import (TAU, add_bevel, add_subsurf, append_bm, bm_box, bm_cyl, bm_sphere, bm_torus,
                    bm_tube, mesh_object, new_bm)

HOVER = 0.10
SHOULDER = Vector((0.172, 0.0, 0.385))
ARM_DIR = Vector((0.22, 0.0, -1.0)).normalized()
UPPER, FORE = 0.095, 0.095
SCREEN_Y = -0.137


def _materials():
    return dict(
        shell=M.noisy("Tock_Shell", "#f4ecdf", "#ece2d1", rough=0.28, scale=6, bump=0.004, coat=0.6),
        coral=M.noisy("Tock_Coral", "#ee7c56", "#e2704b", rough=0.32, scale=6, bump=0.004, coat=0.5),
        rubber=M.solid("Tock_Rubber", "#2f3337", rough=0.65),
        metal=M.solid("Tock_Metal", "#b9bec4", rough=0.25, metal=1.0),
        screen=M.solid("Tock_Screen", "#0d1b1d", rough=0.12, coat=1.0),
        glow=M.emission("Tock_FaceGlow", "#5ee8d6", 3.2),
        thruster=M.emission("Tock_Thruster", "#5ee8d6", 6.0),
        bulb=M.emission("Tock_AntennaBulb", "#ff9a2e", 5.0),
        btn_y=M.solid("Tock_Button_Yellow", "#f2c14e", rough=0.25, coat=1.0),
        btn_t=M.solid("Tock_Button_Teal", "#3f9c95", rough=0.25, coat=1.0),
        btn_r=M.emission("Tock_Button_Red", "#ff5a4f", 3.0, base="#e0473e"),
    )


def _bones():
    b = [
        dict(name='root', head=(0, 0, 0), tail=(0, 0.35, 0), widget='root', wsize=0.36),
        dict(name='hover', head=(0, 0, HOVER), tail=(0, 0, 0.2), parent='root', widget='circle', wsize=1.6),
        dict(name='body', head=(0, 0, 0.2), tail=(0, 0, 0.44), parent='hover', widget='circle', wsize=0.9),
        dict(name='neck', head=(0, 0, 0.44), tail=(0, 0, 0.51), parent='body', connect=True,
             widget='circle', wsize=1.2),
        dict(name='head', head=(0, 0, 0.51), tail=(0, 0, 0.78), parent='neck', connect=True,
             widget='circle', wsize=0.9),
        dict(name='antenna.01', head=(0.06, 0, 0.775), tail=(0.06, 0, 0.84), parent='head', widget='circle', wsize=0.6),
        dict(name='antenna.02', head=(0.06, 0, 0.84), tail=(0.07, 0, 0.91), parent='antenna.01', connect=True,
             widget='circle', wsize=0.6),
        dict(name='mouth', head=(0, SCREEN_Y, 0.595), tail=(0, SCREEN_Y, 0.62), parent='head'),
    ]
    for side, sx in (('L', 1), ('R', -1)):
        s = Vector((SHOULDER.x * sx, SHOULDER.y, SHOULDER.z))
        d = Vector((ARM_DIR.x * sx, ARM_DIR.y, ARM_DIR.z))
        e = s + d * UPPER
        w = e + d * FORE
        b += [
            dict(name=f'eye.{side}', head=(0.062 * sx, SCREEN_Y, 0.655), tail=(0.062 * sx, SCREEN_Y, 0.69),
                 parent='head', widget='circle', wsize=0.8),
            dict(name=f'eye_happy.{side}', head=(0.062 * sx, SCREEN_Y, 0.645), tail=(0.062 * sx, SCREEN_Y, 0.68),
                 parent='head', widget='circle', wsize=0.6),
            dict(name=f'upper_arm.{side}', head=s, tail=e, parent='body', widget='circle', wsize=0.45),
            dict(name=f'forearm.{side}', head=e, tail=w, parent=f'upper_arm.{side}', connect=True,
                 widget='circle', wsize=0.45),
            dict(name=f'hand.{side}', head=w, tail=w + d * 0.05, parent=f'forearm.{side}', connect=True,
                 widget='circle', wsize=0.6),
            dict(name=f'claw_front.{side}', head=w + d * 0.025 + Vector((0, -0.02, 0)),
                 tail=w + d * 0.08 + Vector((0, -0.03, 0)), parent=f'hand.{side}', widget='circle', wsize=0.3),
            dict(name=f'claw_back.{side}', head=w + d * 0.025 + Vector((0, 0.02, 0)),
                 tail=w + d * 0.08 + Vector((0, 0.03, 0)), parent=f'hand.{side}', widget='circle', wsize=0.3),
        ]
    return b


def _part(name, bm, col, mat, arm, bone, bevel=0.0, segs=4, subsurf=0):
    obj = mesh_object(f"CH_Tock_{name}", bm, col, mat=mat)
    if bevel:
        add_bevel(obj, bevel, segs, angle=35, harden=False)
    if subsurf:
        add_subsurf(obj, subsurf)
    rigid_skin(obj, arm, bone)
    return obj


def _rot_bm(bm, axis, angle, cent=(0, 0, 0)):
    bmesh.ops.rotate(bm, verts=bm.verts, cent=cent, matrix=Matrix.Rotation(angle, 3, axis))
    return bm


def build(col):
    m = _materials()
    arm = create_armature("RIG_Tock", col, _bones())
    P = lambda *a, **k: _part(*a, arm=arm, **k)  # noqa: E731

    # ---- hover base -----------------------------------------------------------
    P("Saucer", bm_cyl(0.15, 0.075, 48, r2=0.125, offset=(0, 0, HOVER)), col, m['coral'], bone='hover',
      bevel=0.025, segs=5)
    P("SaucerRim", bm_torus(0.145, 0.012, 64, 10, offset=(0, 0, HOVER + 0.012)), col, m['rubber'], bone='hover')
    P("Thruster", bm_cyl(0.085, 0.012, 48, offset=(0, 0, HOVER - 0.008)), col, m['thruster'], bone='hover')
    P("ThrusterRing", bm_torus(0.1, 0.01, 48, 8, offset=(0, 0, HOVER - 0.002)), col, m['metal'], bone='hover')
    P("Waist", bm_cyl(0.07, 0.06, 32, offset=(0, 0, HOVER + 0.07)), col, m['rubber'], bone='body', bevel=0.01)
    glow = bpy.data.lights.new("LGT_Tock_Thruster", 'POINT')
    glow.energy = 6
    glow.color = M.hex_lin("#6cf6e4")[:3]
    glow.shadow_soft_size = 0.05
    gl = bpy.data.objects.new("LGT_Tock_Thruster", glow)
    gl.location = (0, 0, HOVER - 0.04)
    col.objects.link(gl)
    bpy.context.view_layer.update()
    bone_parent(gl, arm, 'hover')

    # ---- torso -----------------------------------------------------------------
    P("Torso", bm_box((0.3, 0.235, 0.24), offset=(0, 0, 0.325)), col, m['shell'], bone='body', bevel=0.06, segs=6)
    P("BellyPanel", bm_box((0.17, 0.02, 0.11), offset=(0, -0.112, 0.315)), col, m['coral'], bone='body',
      bevel=0.03, segs=5)
    for i, (x, mat) in enumerate(((-0.05, m['btn_y']), (0.0, m['btn_t']), (0.05, m['btn_r']))):
        P(f"Button.{i}", _button(x, mat), col, mat, bone='body', bevel=0.004, segs=2)
    grille = new_bm()
    for i in range(4):
        bm_box((0.1, 0.006, 0.006), bm=grille, offset=(0, -0.124, 0.29 - i * 0.014 + 0.0))
    P("Grille", grille, col, m['rubber'], bone='body', bevel=0.002, segs=2)
    P("Backpack", bm_box((0.18, 0.06, 0.16), offset=(0, 0.13, 0.33)), col, m['coral'], bone='body',
      bevel=0.025, segs=4)
    P("BackpackVent", _vent(), col, m['rubber'], bone='body', bevel=0.002, segs=2)

    # ---- neck / head -------------------------------------------------------------
    neck = new_bm()
    for i in range(4):
        bm_torus(0.05 - i * 0.003, 0.011, 32, 8, bm=neck, offset=(0, 0, 0.452 + i * 0.017))
    bm_cyl(0.035, 0.08, 24, bm=neck, offset=(0, 0, 0.44))
    P("Neck", neck, col, m['rubber'], bone='neck')
    P("Head", bm_box((0.38, 0.27, 0.27), offset=(0, 0, 0.64)), col, m['shell'], bone='head', bevel=0.075, segs=7)
    P("ScreenBezel", bm_box((0.315, 0.02, 0.215), offset=(0, -0.128, 0.64)), col, m['coral'], bone='head',
      bevel=0.05, segs=6)
    P("Screen", bm_box((0.285, 0.02, 0.185), offset=(0, SCREEN_Y + 0.004, 0.64)), col, m['screen'], bone='head',
      bevel=0.045, segs=6)
    for side, sx in (('L', 1), ('R', -1)):
        ear = _rot_bm(bm_cyl(0.06, 0.04, 40, origin='center'), 'Y', math.pi / 2)
        bmesh.ops.translate(ear, verts=ear.verts, vec=(0.2 * sx, 0, 0.645))
        P(f"Ear.{side}", ear, col, m['coral'], bone='head', bevel=0.012, segs=3)
        cap = _rot_bm(bm_cyl(0.035, 0.012, 32, origin='center'), 'Y', math.pi / 2)
        bmesh.ops.translate(cap, verts=cap.verts, vec=(0.222 * sx, 0, 0.645))
        P(f"EarCap.{side}", cap, col, m['metal'], bone='head', bevel=0.004, segs=2)
        # face: pill eyes + "happy" arc eyes (hidden by default via bone scale)
        eye = bm_box((0.042, 0.006, 0.07), offset=(0.062 * sx, SCREEN_Y - 0.009, 0.655))
        P(f"Eye.{side}", eye, col, m['glow'], bone=f'eye.{side}', bevel=0.02, segs=5)
        arc = [(0.062 * sx + 0.026 * math.sin(t), SCREEN_Y - 0.01, 0.648 + 0.02 * math.cos(t))
               for t in [-1.25 + 2.5 * i / 14 for i in range(15)]]
        P(f"EyeHappy.{side}", bm_tube(arc, 0.0075, 8), col, m['glow'], bone=f'eye_happy.{side}')
    smile = [(0.022 * math.sin(t), SCREEN_Y - 0.01, 0.598 - 0.008 * math.cos(t))
             for t in [-1.2 + 2.4 * i / 12 for i in range(13)]]
    P("Mouth", bm_tube(smile, 0.0045, 8), col, m['glow'], bone='mouth')

    # antenna
    ant_pts = [(0.06 + 0.01 * (t ** 2), 0, 0.77 + 0.13 * t) for t in [i / 12 for i in range(13)]]
    ant = bm_tube(ant_pts, 0.0055, 8)
    P("AntennaRod", ant, col, m['metal'], bone='antenna.01')
    P("AntennaBase", bm_cyl(0.022, 0.02, 24, offset=(0.06, 0, 0.77)), col, m['coral'], bone='head', bevel=0.006,
      segs=2)
    P("AntennaBulb", bm_sphere(0.024, 24, 12, offset=(0.07, 0, 0.912)), col, m['bulb'], bone='antenna.02')

    # ---- arms ------------------------------------------------------------------------
    for side, sx in (('L', 1), ('R', -1)):
        s = Vector((SHOULDER.x * sx, SHOULDER.y, SHOULDER.z))
        d = Vector((ARM_DIR.x * sx, ARM_DIR.y, ARM_DIR.z))
        e, w = s + d * UPPER, s + d * (UPPER + FORE)
        P(f"Shoulder.{side}", bm_sphere(0.036, 24, 12, offset=s), col, m['metal'], bone='body')
        # ribbed hose upper arm
        hose = [s + d * (UPPER * i / 30) for i in range(31)]
        P(f"UpperArm.{side}", bm_tube(hose, lambda t: 0.019 + 0.004 * abs(math.sin(t * math.pi * 7)), 12),
          col, m['rubber'], bone=f'upper_arm.{side}')
        P(f"Elbow.{side}", bm_sphere(0.026, 20, 10, offset=e), col, m['metal'], bone=f'forearm.{side}')
        fore = [e + d * (FORE * i / 8) for i in range(9)]
        P(f"Forearm.{side}", bm_tube(fore, lambda t: 0.026 + 0.008 * t, 16), col, m['coral'],
          bone=f'forearm.{side}', subsurf=1)
        P(f"Hand.{side}", bm_sphere(0.032, 24, 12, offset=w + d * 0.012), col, m['shell'], bone=f'hand.{side}')
        for tag, sy in (('front', -1), ('back', 1)):
            base = w + d * 0.02 + Vector((0, 0.018 * sy, 0))
            pts = [base + d * (0.06 * t) + Vector((0, sy * 0.022 * math.sin(t * math.pi * 0.8), 0))
                   for t in [i / 10 for i in range(11)]]
            P(f"Claw_{tag}.{side}", bm_tube(pts, lambda t: 0.011 - 0.005 * t, 10), col, m['shell'],
              bone=f'claw_{tag}.{side}')

    # rest expression: happy arcs collapsed
    for side in ('L', 'R'):
        arm.pose.bones[f'eye_happy.{side}'].scale = (0.001, 0.001, 0.001)
    return dict(arm=arm, mats=m)


def _button(x, mat):
    bm = bm_cyl(0.014, 0.014, 24, origin='center')
    _rot_bm(bm, 'X', math.pi / 2)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(x, -0.123, 0.345))
    return bm


def _vent():
    bm = new_bm()
    for i in range(3):
        bm_box((0.11, 0.006, 0.008), bm=bm, offset=(0, 0.162, 0.37 - i * 0.022))
    return bm


def hero_pose(arm, frame=1):
    """Friendly wave - used for the model sheet."""
    key_pose(arm, frame, {
        'upper_arm.L': {'rot': (0, -2.2, 0)},
        'forearm.L': {'rot': (0, -0.5, 0)},
        'claw_front.L': {'rot': (-0.3, 0, 0)},
        'claw_back.L': {'rot': (0.3, 0, 0)},
        'head': {'rot': (0.05, 0, 0.18)},
        'body': {'rot': (0, 0.05, 0)},
        'antenna.02': {'rot': (0, 0.25, 0)},
        'eye.L': {'scale': (1, 0.001, 1)}, 'eye.R': {'scale': (1, 0.001, 1)},
        'eye_happy.L': {'scale': 1.0}, 'eye_happy.R': {'scale': 1.0},
    })
