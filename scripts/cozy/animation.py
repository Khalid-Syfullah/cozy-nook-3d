"""ANIM - "Cocoa Delivery" (300 f @ 24 fps, 12.5 s).

Beat sheet (docs/SHOT_LIST.md):
  001-100  Pip gazes out of the sunset window. Tock wakes on its dock (f30),
           lifts off (f45) and glides over carrying a mug of cocoa.
  100-130  Pip hears Tock: sprout perks, anticipation, head-led turn.
  130-176  Surprise blink, then a happy hop (squash / stretch, arms up).
  176-206  Pip waves; Tock's face switches to "happy" eyes.
  200-222  Tock offers the mug; Pip reaches; hand-off at f220.
  222-300  Pip hugs the mug, sips, sways contentedly. Hold.

Primary motion is keyed pose-to-pose. Secondary motion (sprout/antenna
follow-through, Tock's banking) is *simulated* from the evaluated primary
motion with a damped spring and baked to keys, so it always matches timing.
"""
import math

import bpy
from mathutils import Matrix, Vector

from . import environment, lighting
from . import materials as M
from .rig import key_pose, rot_world
from .utils import TAU, bm_cyl, collection, empty, fcurves_of, mesh_object

FPS = 24
F_START, F_END = 1, 300
HANDOFF = 220

# Staging: the pair sits on a line roughly perpendicular to the camera axis,
# each cheated ~40 deg toward the lens so both faces read (see SHOT_LIST.md).
PIP_POS = Vector((-0.25, -0.55, 0.012))
PIP_YAW_START, PIP_YAW_END = 2.76, 1.53
PAIR_AXIS = Vector((0.83, 0.55, 0.0))
TOCK_DOCK = Vector((1.75, 0.65, 0.05))
TOCK_YAW_START, TOCK_YAW_END = -0.75, -0.36
HAND = 'R'          # Tock carries the mug in the hand nearest Pip


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _forward(yaw):
    return Vector((math.sin(yaw), -math.cos(yaw), 0.0))


def _eye_track(arm, bones, keys):
    """keys: [(frame, scaleY)] applied to all ``bones`` (blinks, squints)."""
    for f, sy in keys:
        for b in bones:
            key_pose(arm, f, {b: {'scale': (1.0, sy, 1.0)}})


def _blink(f, base=1.0):
    return [(f - 1, base), (f + 1, 0.06), (f + 2, 0.06), (f + 4, base)]


def _bone_world(arm, bone, point='head'):
    pb = arm.pose.bones[bone]
    return arm.matrix_world @ (pb.head if point == 'head' else pb.tail)


def _bone_matrix(arm, bone):
    return arm.matrix_world @ arm.pose.bones[bone].matrix


# --------------------------------------------------------------------------- #
# Procedural secondary motion
# --------------------------------------------------------------------------- #
def _sample(scene, arm, bone, frames):
    pos, yaw = {}, {}
    for f in frames:
        scene.frame_set(f)
        pos[f] = _bone_world(arm, bone).copy()
        yaw[f] = arm.pose.bones['root'].matrix.to_euler().z
    return pos, yaw


def _local_accel(pos, yaw, frames):
    acc = {}
    for f in frames:
        a, b = pos.get(f - 1, pos[f]), pos.get(f + 1, pos[f])
        acc_w = (a + b - 2 * pos[f]) * FPS * FPS
        c, s = math.cos(-yaw[f]), math.sin(-yaw[f])
        acc[f] = Vector((acc_w.x * c - acc_w.y * s, acc_w.x * s + acc_w.y * c, acc_w.z))
    return acc


def _spring(acc, frames, gain, k=140.0, damp=7.0, sign=1.0, impulses=None, clamp=0.6, zgain=0.0):
    """Damped spring around a target driven by local acceleration.
    sign=+1 -> lag behind motion (antennae, sprouts); -1 -> lean into it."""
    dt = 1.0 / FPS
    x = Vector((0.0, 0.0))
    v = Vector((0.0, 0.0))
    out = {}
    imp = dict(impulses or {})
    for f in frames:
        a = acc[f]
        target = Vector((sign * gain * a.y + zgain * a.z, -sign * gain * a.x))
        target.x = max(-clamp, min(clamp, target.x))
        target.y = max(-clamp, min(clamp, target.y))
        if f in imp:
            v += Vector(imp[f])
        for _ in range(4):                       # sub-steps for stability
            v += (k * (target - x) - damp * v) * (dt / 4)
            x += v * (dt / 4)
        out[f] = x.copy()
    return out


def _bake_chain(arm, bones_weights, curve, frames, step=1):
    for f in frames[::step]:
        x, y = curve[f]
        for bone, (w, delay) in bones_weights.items():
            xd, yd = curve.get(f - delay, curve[f])
            key_pose(arm, f, {bone: {'rot': (xd * w, yd * w, 0.0)}})


# --------------------------------------------------------------------------- #
# Pip
# --------------------------------------------------------------------------- #
def animate_pip(arm):
    P = PIP_POS
    K = lambda f, pose: key_pose(arm, f, pose)  # noqa: E731

    # --- root: placement, the turn and the hop --------------------------------
    for f, yaw, z in [(1, PIP_YAW_START, 0), (104, PIP_YAW_START, 0), (110, PIP_YAW_START + 0.1, 0),
                      (121, PIP_YAW_END - 0.12, 0), (128, PIP_YAW_END, 0), (146, PIP_YAW_END, 0),
                      (152, PIP_YAW_END, 0.05), (158, PIP_YAW_END, 0.155), (164, PIP_YAW_END, 0.05),
                      (167, PIP_YAW_END, 0.0), (300, PIP_YAW_END, 0)]:
        K(f, {'root': {'loc': (P.x, P.y, P.z + z), 'rot': (0, 0, yaw)}})

    # --- hips: squash & stretch, leans ------------------------------------------
    hips = [
        (1, (1, 1, 1), (0, 0, 0)), (60, (1, 1, 1), (-0.04, 0, 0)), (96, (1, 1, 1), (-0.03, 0, 0)),
        (104, (1.06, 0.92, 1.06), (0.03, 0, 0)), (110, (0.97, 1.05, 0.97), (0, 0, 0)),
        (118, (1.0, 1.0, 1.0), (0, -0.06, 0)), (128, (1, 1, 1), (0, 0.03, 0)),
        (134, (0.96, 1.06, 0.96), (-0.02, 0, 0)), (142, (1, 1, 1), (0, 0, 0)),
        (147, (1.14, 0.8, 1.14), (0.06, 0, 0)), (152, (0.9, 1.16, 0.9), (-0.04, 0, 0)),
        (158, (0.98, 1.03, 0.98), (0, 0, 0)), (164, (0.93, 1.1, 0.93), (0, 0, 0)),
        (167, (1.16, 0.8, 1.16), (0.05, 0, 0)), (172, (0.98, 1.04, 0.98), (0, 0, 0)),
        (177, (1, 1, 1), (0, 0, 0)), (206, (1, 1, 1), (0, 0, 0)),
        (214, (1, 1, 1), (0.12, 0, 0)), (222, (1, 1, 1), (0.1, 0, 0)), (232, (1, 1, 1), (-0.02, 0, 0)),
        (246, (1.02, 0.98, 1.02), (-0.06, 0, 0)), (262, (1, 1, 1), (-0.05, 0, 0)),
        (272, (1, 1, 1), (0, 0.05, 0)), (284, (1, 1, 1), (0, -0.05, 0)), (296, (1, 1, 1), (0, 0.02, 0)),
        (300, (1, 1, 1), (0, 0.0, 0)),
    ]
    for f, sc, rot in hips:
        K(f, {'hips': {'scale': sc, 'rot': rot}})

    # --- breathing on the spine (separate channel so it layers cleanly) --------
    for f in range(F_START, F_END + 1, 6):
        s = math.sin(TAU * f / 52.0)
        K(f, {'spine': {'scale': (1 - 0.012 * s, 1 + 0.025 * s, 1 - 0.012 * s)}})

    # --- head: looks / turn lead / sip ------------------------------------------
    for f, rot in [(1, (-0.12, 0, 0.06)), (40, (-0.14, 0.04, -0.04)), (80, (-0.1, -0.03, 0.08)),
                   (100, (-0.1, 0, 0.05)), (104, (-0.02, 0, 0.0)), (110, (0.0, 0, -0.45)),
                   (121, (0.02, 0.05, 0.12)), (130, (0.02, 0.0, 0.0)), (134, (-0.06, 0.06, 0.0)),
                   (146, (0.05, 0, 0)), (158, (-0.08, 0, 0)), (170, (0.03, 0, 0)),
                   (180, (-0.04, -0.12, 0.05)), (205, (-0.02, 0.1, 0.0)), (220, (0.06, 0, 0.0)),
                   (236, (0.02, 0.06, -0.05)), (250, (-0.14, 0.0, 0)), (262, (-0.12, 0.0, 0)),
                   (274, (0.0, 0.1, 0.05)), (300, (0.0, 0.08, 0.1))]:
        K(f, {'head': {'rot': rot}})

    # --- arms -------------------------------------------------------------------
    rest = {'upper_arm.L': (0, 0, 0), 'forearm.L': (0, 0, 0), 'upper_arm.R': (0, 0, 0), 'forearm.R': (0, 0, 0)}
    reach = {'upper_arm.L': (-1.15, -0.25, -0.62), 'forearm.L': (-0.25, 0, -0.35),
             'upper_arm.R': (-1.15, 0.25, 0.62), 'forearm.R': (-0.25, 0, 0.35)}
    hug = {'upper_arm.L': (-1.05, -0.15, -0.72), 'forearm.L': (-0.55, 0, -0.5),
           'upper_arm.R': (-1.05, 0.15, 0.72), 'forearm.R': (-0.55, 0, 0.5)}
    sip = {'upper_arm.L': (-1.45, -0.1, -0.7), 'forearm.L': (-0.8, 0, -0.5),
           'upper_arm.R': (-1.45, 0.1, 0.7), 'forearm.R': (-0.8, 0, 0.5)}
    hop = {'upper_arm.L': (0, -1.7, 0), 'forearm.L': (0, -0.3, 0),
           'upper_arm.R': (0, 1.7, 0), 'forearm.R': (0, 0.3, 0)}
    idle_a = {'upper_arm.L': (0.05, 0.1, 0), 'forearm.L': (0, 0.05, 0),
              'upper_arm.R': (0.05, -0.1, 0), 'forearm.R': (0, -0.05, 0)}

    def arms(f, pose):
        K(f, {b: {'rot': r} for b, r in pose.items()})

    arms(1, idle_a)
    arms(60, rest)
    arms(104, idle_a)
    arms(112, {'upper_arm.L': (0, -0.35, 0), 'forearm.L': (0, 0, 0),
               'upper_arm.R': (0, 0.35, 0), 'forearm.R': (0, 0, 0)})
    arms(128, rest)
    arms(147, {'upper_arm.L': (0.2, 0.25, 0), 'forearm.L': (0, 0, 0),
               'upper_arm.R': (0.2, -0.25, 0), 'forearm.R': (0, 0, 0)})
    arms(155, hop)
    arms(162, hop)
    arms(170, idle_a)
    # wave with the camera-side (right) arm
    K(176, {'upper_arm.R': {'rot': (0, 0.2, 0)}, 'forearm.R': {'rot': (0, 0, 0)},
            'upper_arm.L': {'rot': (0, 0.0, 0)}, 'forearm.L': {'rot': (0, 0, 0)}})
    K(182, {'upper_arm.R': {'rot': (0, 2.25, 0)}, 'forearm.R': {'rot': (0, 0.55, 0)}})
    for i, f in enumerate(range(187, 205, 4)):
        K(f, {'forearm.R': {'rot': (0, -0.25 if i % 2 == 0 else 0.6, 0)}})
    K(205, {'upper_arm.R': {'rot': (0, 2.1, 0)}, 'forearm.R': {'rot': (0, 0.3, 0)}})
    arms(208, {'upper_arm.L': (-0.3, -0.2, 0), 'forearm.L': (0, 0, 0),
               'upper_arm.R': (-0.4, 0.6, 0), 'forearm.R': (0, 0, 0)})
    arms(215, reach)
    arms(221, reach)
    arms(230, hug)
    arms(242, hug)
    arms(252, sip)
    arms(262, sip)
    arms(272, hug)
    arms(300, hug)

    # --- eyes: blinks, surprise, happy squints ------------------------------------
    eyes = ['eye.L', 'eye.R']
    track = [(1, 1.0)] + _blink(48) + _blink(96) + [(112, 1.0)] + _blink(116) + \
            [(131, 1.0), (134, 1.15), (144, 1.15), (148, 1.0)] + \
            [(158, 0.55), (166, 0.55), (172, 1.0)] + _blink(198) + \
            [(222, 1.0), (228, 0.75), (240, 0.75), (248, 0.12), (264, 0.12), (272, 0.6), (290, 0.6), (300, 0.6)]
    _eye_track(arm, eyes, track)


# --------------------------------------------------------------------------- #
# Tock
# --------------------------------------------------------------------------- #
def tock_path(end):
    d = TOCK_DOCK
    mid1 = Vector((1.5, 0.1, 0.0))
    mid2 = Vector((0.85, -0.3, 0.0))
    return [
        (1, d, TOCK_YAW_START), (44, d, TOCK_YAW_START), (52, d + Vector((0, 0, 0.03)), TOCK_YAW_START),
        (74, mid1 + Vector((0, 0, 0.03)), -0.95), (98, mid2 + Vector((0, 0, 0.02)), -0.75),
        (122, end + Vector((0.06, -0.04, 0.0)), TOCK_YAW_END - 0.1), (134, end, TOCK_YAW_END),
        (300, end, TOCK_YAW_END),
    ]


def animate_tock(arm, end, offer_lift=0.0):
    K = lambda f, pose: key_pose(arm, f, pose)  # noqa: E731
    for f, loc, yaw in tock_path(end):
        K(f, {'root': {'loc': tuple(loc), 'rot': (0, 0, yaw)}})
    # hover bob (procedural sine) with the wake-up rise blended in
    for f in range(F_START, F_END + 1, 4):
        wake = min(1.0, max(0.0, (f - 30) / 22.0))
        wake = wake * wake * (3 - 2 * wake)
        bob = 0.011 * math.sin(TAU * f / 38.0) * (0.25 + 0.75 * wake)
        lift = offer_lift * min(1.0, max(0.0, (f - 196) / 18.0)) * (1 - min(1.0, max(0.0, (f - 228) / 16.0)))
        K(f, {'hover': {'loc': (0, 0, -0.045 * (1 - wake) + bob + lift)}})

    # head: asleep droop -> wake -> look at Pip -> happy tilts
    for f, rot in [(1, (0.22, 0, 0)), (28, (0.22, 0, 0)), (36, (-0.08, 0, 0.0)), (44, (0, 0, 0)),
                   (90, (0.02, 0, -0.12)), (122, (0.05, 0, 0.0)), (140, (0.03, 0.0, 0.0)),
                   (178, (0.0, -0.18, 0.0)), (186, (0.0, 0.14, 0.0)), (196, (0.02, -0.08, 0.0)),
                   (210, (0.1, 0.05, 0)), (224, (0.08, 0.0, 0)), (236, (0.0, -0.16, 0.0)),
                   (262, (0.03, 0.12, 0.0)), (300, (0.03, 0.1, 0.0))]:
        K(f, {'head': {'rot': rot}})
    for f, rot in [(1, (0.06, 0, 0)), (28, (0.06, 0, 0)), (40, (-0.04, 0, 0)), (48, (0, 0, 0)),
                   (180, (0, 0.04, 0)), (190, (0, -0.04, 0)), (200, (0, 0, 0)), (300, (0, 0, 0))]:
        K(f, {'body': {'rot': rot}})

    # arms: one hand carries the mug (hand counter-rotates to keep it upright)
    sx = 1 if HAND == 'L' else -1

    def carry(a1, a2, spread=0.0):
        # a1/a2 = forward raise (radians); negative X swings a hanging limb forward
        return {f'upper_arm.{HAND}': {'rot': (-a1, -spread * sx, 0)}, f'forearm.{HAND}': {'rot': (-a2, 0, 0)},
                f'hand.{HAND}': {'rot': (a1 + a2, spread * sx, 0)}}
    K(1, carry(0.3, 0.45, 0.1))
    K(196, carry(0.3, 0.45, 0.1))
    K(208, carry(0.95, 0.55, -0.12))
    K(221, carry(1.05, 0.45, -0.2))
    K(232, carry(0.5, 0.6, 0.1))
    K(246, carry(0.05, 0.1, 0.05))
    K(300, carry(0.0, 0.05, 0.05))
    # claws: closed on the mug until the hand-off, then open & relax
    claws = {1: 0.0, 214: 0.0, 222: 0.38, 236: 0.2, 300: 0.15}
    for f, a in claws.items():
        K(f, {f'claw_front.{HAND}': {'rot': (-a, 0, 0)}, f'claw_back.{HAND}': {'rot': (a, 0, 0)}})
    # free arm: balance + a little "ta-da" during Pip's wave
    free = 'L' if HAND == 'R' else 'R'
    fx = 1 if free == 'L' else -1
    for f, r in [(1, (0, 0, 0)), (60, (0.15, 0.1, 0)), (110, (-0.1, 0.05, 0)), (176, (0, 0.1, 0)),
                 (184, (-0.3, 1.2, 0)), (198, (-0.3, 1.1, 0)), (210, (0, 0.15, 0)), (300, (0, 0.1, 0))]:
        K(f, {f'upper_arm.{free}': {'rot': (r[0], -fx * r[1], r[2])}})

    # face: asleep -> wake blink -> blinks -> happy -> normal -> happy end
    eyes, happy = ['eye.L', 'eye.R'], ['eye_happy.L', 'eye_happy.R']
    open_ = [(1, 0.05), (30, 0.05), (34, 1.0)] + _blink(40) + _blink(88) + _blink(140) + \
            [(176, 1.0), (178, 0.001), (204, 0.001), (206, 1.0)] + _blink(226) + \
            [(250, 1.0), (252, 0.001), (300, 0.001)]
    _eye_track(arm, eyes, open_)
    for f, s in [(1, 0.001), (176, 0.001), (178, 1.0), (204, 1.0), (206, 0.001), (250, 0.001),
                 (252, 1.0), (300, 1.0)]:
        for b in happy:
            K(f, {b: {'scale': (s, s, s)}})


# --------------------------------------------------------------------------- #
# Props: the mug and its hand-off
# --------------------------------------------------------------------------- #
def build_mug(col):
    mat = M.noisy("Ceramic_Mustard", "#e6ae45", "#d79c35", rough=0.25, scale=5, bump=0.005, coat=0.4)
    mug = environment.build_mug("PROP_Mug_Cocoa", col, mat, r=0.042, h=0.09)
    cocoa = mesh_object("PROP_Mug_Cocoa_Fill", bm_cyl(0.036, 0.004, 32, offset=(0, 0, 0.07)), col,
                        mat=M.noisy("Cocoa", "#6b3f26", "#80513a", rough=0.15, scale=30, bump=0.05))
    cocoa.parent = mug
    return mug


def pip_frame():
    """Pip's final facing basis (world): forward, right, up."""
    f = _forward(PIP_YAW_END)
    r = Vector((-math.cos(PIP_YAW_END), -math.sin(PIP_YAW_END), 0.0))
    return f, r, Vector((0, 0, 1))


def tock_mug_point(scene, tock):
    scene.frame_set(HANDOFF)
    return _bone_matrix(tock, f'hand.{HAND}') @ Vector((0, 0.06, 0))


def handoff_point():
    """Where the mug's centre should be at the hand-off: just in front of Pip's chest."""
    f, _, _ = pip_frame()
    return PIP_POS + f * 0.275 + Vector((0, 0, 0.30))


def rig_mug_handoff(scene, mug, tock, pip, ik_on=208, ik_full=217):
    """Mug hand-off rig.
    * Child Of #1 -> Tock's hand until HANDOFF.
    * Child Of #2 -> ``PROP_Mug_Hold`` control (keyed in world space) afterwards.
      Inverses are matched so the switch is seamless; influences use CONSTANT keys.
    * Pip's arms get 2-bone IK whose targets ride on the mug, so the reach,
      hug and sip all follow the mug (classic prop-driven IK set-up)."""
    col = mug.users_collection[0]
    MUG_H = 0.09
    scene.frame_set(1)
    hand = _bone_matrix(tock, f'hand.{HAND}')
    centre = hand @ Vector((0, 0.06, 0))
    w_attach = Matrix.Translation(centre - Vector((0, 0, MUG_H / 2))) @ Matrix.Rotation(math.radians(-20), 4, 'Z')
    ca = mug.constraints.new('CHILD_OF')
    ca.name = "Hold_Tock"
    ca.target, ca.subtarget = tock, f'hand.{HAND}'
    ca.inverse_matrix = hand.inverted() @ w_attach

    scene.frame_set(HANDOFF)
    w_h = _bone_matrix(tock, f'hand.{HAND}') @ ca.inverse_matrix
    hold = empty("PROP_Mug_Hold", col, (0, 0, 0), 'CUBE', 0.06)
    hold.rotation_mode = 'QUATERNION'
    cb = mug.constraints.new('CHILD_OF')
    cb.name = "Hold_Pip"
    cb.target = hold
    cb.inverse_matrix = Matrix.Identity(4)
    cb.influence = 0.0

    f, r, up = pip_frame()
    rot_h = w_h.to_quaternion()

    def key_hold(frame, centre_pos, tilt=0.0):
        t = Matrix.Rotation(tilt, 4, r)
        m = Matrix.Translation(centre_pos - (t.to_3x3() @ up) * (MUG_H / 2)) @ t @ rot_h.to_matrix().to_4x4()
        hold.matrix_world = m
        hold.keyframe_insert('location', frame=frame)
        hold.keyframe_insert('rotation_quaternion', frame=frame)

    c_h = w_h @ Vector((0, 0, MUG_H / 2))
    base = PIP_POS + Vector((0, 0, 0))
    for fr, c, tilt in [
        (HANDOFF, c_h, 0.0),
        (226, c_h + f * 0.01 + up * 0.015, 0.05),
        (234, base + f * 0.27 + up * 0.29, 0.0),
        (243, base + f * 0.27 + up * 0.29, 0.0),
        (251, base + f * 0.215 + up * 0.37, 0.55),
        (262, base + f * 0.212 + up * 0.375, 0.6),
        (272, base + f * 0.27 + up * 0.3, 0.05),
        (300, base + f * 0.27 + up * 0.295, 0.0),
    ]:
        key_hold(fr, c, tilt)

    for fr, a, b in [(1, 1.0, 0.0), (HANDOFF, 1.0, 0.0), (HANDOFF + 1, 0.0, 1.0)]:
        ca.influence, cb.influence = a, b
        mug.keyframe_insert(f'constraints["{ca.name}"].influence', frame=fr)
        mug.keyframe_insert(f'constraints["{cb.name}"].influence', frame=fr)
    for fc in fcurves_of(mug):
        for kp in fc.keyframe_points:
            kp.interpolation = 'CONSTANT'

    # IK targets live on the mug: one either side, slightly toward Pip
    scene.frame_set(HANDOFF)
    mw = mug.matrix_world.copy()
    c_world = mw @ Vector((0, 0, MUG_H / 2))
    for side, sgn in (('L', -1), ('R', 1)):
        tgt = empty(f"CH_Pip_IK_Hand.{side}", col, (0, 0, 0), 'SPHERE', 0.025)
        tgt.parent = mug
        tgt.location = mw.inverted() @ (c_world + r * (0.068 * sgn) - f * 0.012 - up * 0.01)
        ik = pip.pose.bones[f'forearm.{side}'].constraints.new('IK')
        ik.name = "IK_Mug"
        ik.target = tgt
        ik.chain_count = 2
        ik.use_stretch = True
        for b in (f'upper_arm.{side}', f'forearm.{side}'):
            pip.pose.bones[b].ik_stretch = 0.12      # rubber-hose allowance for the sip
        for fr, v in ((1, 0.0), (ik_on, 0.0), (ik_full, 1.0), (F_END, 1.0)):
            ik.influence = v
            ik.keyframe_insert('influence', frame=fr)
    return hold


# --------------------------------------------------------------------------- #
# Camera
# --------------------------------------------------------------------------- #
def build_anim_camera(cams):
    tgt = empty("CAM_Anim_Target", cams, (0, 0, 0), 'SPHERE', 0.05)
    focus = empty("CAM_Anim_Focus", cams, (0, 0, 0), 'SPHERE', 0.03)
    cam = lighting.camera("CAM_Anim", cams, (3, -4, 1.5), (0, 0, 0.5), lens=40, dof_target=focus, fstop=2.8)
    con = cam.constraints.new('TRACK_TO')
    con.target = tgt
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    keys = [  # frame, cam loc, target, focus, lens
        (1, (1.7, -3.85, 1.75), (0.12, 0.35, 0.5), (-0.25, -0.55, 0.4), 32),
        (60, (1.75, -3.75, 1.65), (0.2, 0.25, 0.5), (0.9, 0.3, 0.45), 33),
        (110, (1.95, -3.05, 1.25), (0.2, -0.3, 0.45), (0.3, -0.25, 0.45), 35),
        (150, (1.5, -2.65, 1.05), (0.02, -0.4, 0.42), (-0.1, -0.45, 0.4), 38),
        (230, (1.3, -2.35, 0.92), (0.02, -0.4, 0.4), (0.0, -0.42, 0.38), 41),
        (300, (1.2, -2.18, 0.86), (0.0, -0.42, 0.4), (-0.1, -0.5, 0.38), 44),
    ]
    for f, loc, t, fo, lens in keys:
        cam.location = loc
        cam.keyframe_insert('location', frame=f)
        tgt.location = t
        tgt.keyframe_insert('location', frame=f)
        focus.location = fo
        focus.keyframe_insert('location', frame=f)
        cam.data.lens = lens
        cam.data.keyframe_insert('lens', frame=f)
    return cam


def build_still_cameras(cams):
    """Static cameras for portfolio stills / review."""
    lighting.camera("CAM_Close_TwoShot", cams, (0.95, -1.95, 0.7), (-0.02, -0.42, 0.38), lens=50)
    # close-ups sit on each character's cheated facing direction (see SHOT_LIST.md)
    lighting.camera("CAM_Close_Pip", cams, (0.45, -1.77, 0.55), (-0.18, -0.55, 0.42), lens=38)
    lighting.camera("CAM_Close_Tock", cams, (0.05, -1.98, 0.72), (0.27, -0.47, 0.58), lens=50)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def build(scene, rigs, cams):
    scene.frame_start, scene.frame_end = F_START, F_END
    scene.render.fps = FPS
    pip, tock = rigs['pip']['arm'], rigs['tock']['arm']
    frames = list(range(F_START, F_END + 1))

    animate_pip(pip)

    # Two-pass placement: evaluate where Tock's mug ends up at the hand-off and
    # shift Tock's arrival point so it lands exactly in front of Pip's chest.
    end0 = PIP_POS + PAIR_AXIS * 0.6
    end0.z = 0.0
    animate_tock(tock, end0)
    grip = handoff_point()
    mugp = tock_mug_point(scene, tock)
    delta = grip - mugp
    tock.animation_data_clear()
    for pb in tock.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)
    lift = max(-0.15, min(0.15, delta.z))
    animate_tock(tock, end0 + Vector((delta.x, delta.y, 0.0)), offer_lift=lift)
    print(f"[anim] hand-off correction xy=({delta.x:.3f}, {delta.y:.3f}) lift={lift:.3f}")

    # secondary motion (simulated, then baked to keys)
    pos, yaw = _sample(scene, pip, 'sprout.01', frames)
    acc = _local_accel(pos, yaw, frames)
    curve = _spring(acc, frames, gain=0.03, k=160, damp=6.5, sign=1.0, clamp=0.55, zgain=-0.012,
                    impulses={100: (-6.0, 0.0), 102: (4.0, 2.0)})
    _bake_chain(pip, {'sprout.01': (0.55, 0), 'sprout.02': (1.0, 2)}, curve, frames)

    pos, yaw = _sample(scene, tock, 'root', frames)
    acc = _local_accel(pos, yaw, frames)
    lean = _spring(acc, frames, gain=0.06, k=60, damp=9.0, sign=-1.0, clamp=0.25)
    _bake_chain(tock, {'hover': (1.0, 0)}, lean, frames, step=2)
    pos, yaw = _sample(scene, tock, 'antenna.01', frames)
    acc = _local_accel(pos, yaw, frames)
    ant = _spring(acc, frames, gain=0.045, k=180, damp=5.0, sign=1.0, clamp=0.7,
                  impulses={34: (8.0, 0.0), 178: (0.0, 6.0), 252: (0.0, -6.0)})
    _bake_chain(tock, {'antenna.01': (0.6, 0), 'antenna.02': (1.0, 2)}, ant, frames)

    props = collection("PROP", scene.collection)
    mug = build_mug(props)
    rig_mug_handoff(scene, mug, tock, pip)

    build_anim_camera(cams)
    build_still_cameras(cams)
    # naming convention: <Char>_<Shot> for actions
    for arm, name in ((pip, "Pip"), (tock, "Tock")):
        arm.animation_data.action.name = f"{name}_CocoaDelivery"
    scene.frame_set(F_START)
