"""CH_Pip - a small sprout creature (organic, skinned character).

Design notes (docs/CHARACTER_BIBLE.md):
  * Height 0.70 m to sprout tip; bean-shaped body doubles as head.
  * Silhouette read: bean body + leaf sprout + stubby limbs + mustard scarf.
  * Body is one skinned mesh (body + arms + legs) with procedural weights,
    so it squashes/stretches smoothly. Face parts are rigid-skinned to the
    head/eye bones, which own 100% of the face region to avoid swimming.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import materials as M
from .materials import NodeBuilder, hex_lin
from .rig import create_armature, key_pose, rigid_skin, skin
from .utils import (TAU, add_subsurf, append_bm, bm_leaf, bm_sphere, bm_tube, empty,
                    mesh_object, new_bm, smoothstep)

# body proportions
CZ, HZ = 0.33, 0.25          # body centre height, half height
RX, RY = 0.205, 0.18         # body half width / depth
SHOULDER = (0.165, -0.01, 0.315)
ARM_LEN = 0.21
ARM_DIR = Vector((0.6, -0.08, -0.8)).normalized()


def _k(nz):
    return 1.0 + 0.11 * (-nz)


def surface(x, z):
    """Point + normal on the front of the body at (x, z)."""
    nz = max(-0.999, min(0.999, (z - CZ) / HZ))
    k = _k(nz)
    s = math.sqrt(1 - nz * nz)
    a, b = RX * k * s, RY * k * s
    y = -b * math.sqrt(max(0.0, 1 - (x / a) ** 2))
    n = Vector((x / a ** 2, y / b ** 2, nz * 2.0)).normalized()
    return Vector((x, y, z)), n


def _skin_material():
    nb = NodeBuilder("Pip_Skin")
    attr = nb.node('ShaderNodeAttribute', attribute_name='rest_pos')
    sub = nb.node('ShaderNodeVectorMath', operation='SUBTRACT')
    sub.inputs[1].default_value = (0.0, -0.2, 0.25)
    nb.link(attr.outputs['Vector'], sub.inputs[0])
    mul = nb.node('ShaderNodeVectorMath', operation='MULTIPLY')
    mul.inputs[1].default_value = (1.05, 0.55, 0.85)
    nb.link(sub.outputs['Vector'], mul.inputs[0])
    ln = nb.node('ShaderNodeVectorMath', operation='LENGTH')
    nb.link(mul.outputs['Vector'], ln.inputs[0])
    belly = nb.node('ShaderNodeMapRange')
    belly.inputs['From Min'].default_value = 0.118
    belly.inputs['From Max'].default_value = 0.108
    nb.link(ln.outputs['Value'], belly.inputs['Value'])
    # subtle mottling so the surface doesn't look like plastic
    nz = nb.node('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 18
    nz.inputs['Detail'].default_value = 4
    nb.link(attr.outputs['Vector'], nz.inputs['Vector'])
    skin_ramp = nb.node('ShaderNodeValToRGB')
    skin_ramp.color_ramp.elements[0].position = 0.35
    skin_ramp.color_ramp.elements[0].color = hex_lin("#6fbf95")
    skin_ramp.color_ramp.elements[1].position = 0.7
    skin_ramp.color_ramp.elements[1].color = hex_lin("#86cfa4")
    nb.link(nz.outputs['Fac'], skin_ramp.inputs['Fac'])
    mix = nb.node('ShaderNodeMix', data_type='RGBA')
    nb.link(belly.outputs['Result'], mix.inputs[0])
    nb.link(skin_ramp.outputs['Color'], mix.inputs[6])
    mix.inputs[7].default_value = hex_lin("#fff1d8")
    nb.link(mix.outputs[2], nb.bsdf.inputs['Base Color'])
    nb.set(**{'Roughness': 0.48, 'Subsurface Weight': 0.25, 'Subsurface Radius': (0.9, 0.5, 0.3),
              'Subsurface Scale': 0.04, 'Sheen Weight': 0.25, 'Sheen Roughness': 0.4,
              'Coat Weight': 0.15, 'Coat Roughness': 0.35})
    b = nb.node('ShaderNodeBump')
    b.inputs['Strength'].default_value = 0.05
    nb.link(nz.outputs['Fac'], b.inputs['Height'])
    nb.link(b.outputs['Normal'], nb.bsdf.inputs['Normal'])
    return nb.mat


def _materials():
    return dict(
        skin=_skin_material(),
        eye=M.solid("Pip_Eye", "#1b1820", rough=0.06, coat=1.0),
        glint=M.emission("Pip_EyeGlint", "#ffffff", 6.0),
        blush=M.solid("Pip_Blush", "#f3968a", rough=0.55, sss=0.2),
        mouth=M.solid("Pip_Mouth", "#3b2130", rough=0.4),
        leaf=M.noisy("Pip_Leaf", "#93cf5a", "#7dbb48", rough=0.4, scale=20, bump=0.02, sss=0.3),
        stem=M.solid("Pip_Stem", "#6aa046", rough=0.5),
        scarf=M.knit("Pip_Scarf", "#e7a436", "#c6852a", stripe="#f6ead2"),
    )


# --------------------------------------------------------------------------- #
# Skeleton
# --------------------------------------------------------------------------- #
def _bones():
    S = Vector(SHOULDER)
    bones = [
        dict(name='root', head=(0, 0, 0), tail=(0, 0.3, 0), widget='root', wsize=0.32),
        dict(name='hips', head=(0, 0, 0.1), tail=(0, 0, 0.24), parent='root', widget='circle', wsize=1.6),
        dict(name='spine', head=(0, 0, 0.24), tail=(0, 0, 0.33), parent='hips', connect=True,
             widget='circle', wsize=2.2),
        dict(name='head', head=(0, 0, 0.33), tail=(0, 0, 0.56), parent='spine', connect=True,
             widget='circle', wsize=1.0),
        dict(name='sprout.01', head=(0, 0, 0.565), tail=(0, 0, 0.62), parent='head', widget='circle', wsize=0.8),
        dict(name='sprout.02', head=(0, 0, 0.62), tail=(0, 0, 0.68), parent='sprout.01', connect=True,
             widget='circle', wsize=1.0),
    ]
    for side, sx in (('L', 1), ('R', -1)):
        d = Vector((ARM_DIR.x * sx, ARM_DIR.y, ARM_DIR.z))
        s = Vector((S.x * sx, S.y, S.z))
        bones += [
            dict(name=f'upper_arm.{side}', head=s, tail=s + d * 0.1, parent='spine', widget='circle', wsize=0.7),
            dict(name=f'forearm.{side}', head=s + d * 0.1, tail=s + d * ARM_LEN, parent=f'upper_arm.{side}',
                 connect=True, widget='circle', wsize=0.8),
            dict(name=f'thigh.{side}', head=(0.085 * sx, 0, 0.16), tail=(0.085 * sx, 0, 0.06), parent='hips',
                 widget='circle', wsize=0.7),
            dict(name=f'foot.{side}', head=(0.085 * sx, 0, 0.06), tail=(0.085 * sx, -0.08, 0.03),
                 parent=f'thigh.{side}', connect=True, widget='circle', wsize=0.9),
        ]
        p, _ = surface(0.072 * sx, 0.44)
        bones.append(dict(name=f'eye.{side}', head=p + Vector((0, 0.012, 0)), tail=p + Vector((0, 0.012, 0.05)),
                          parent='head', widget='circle', wsize=0.9))
    return bones


def _body_weights(z):
    s1 = smoothstep(0.15, 0.27, z)
    s2 = smoothstep(0.25, 0.35, z)
    return {'hips': 1 - s1, 'spine': s1 * (1 - s2), 'head': s1 * s2}


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
def _body_bm():
    bm = new_bm()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=32, radius=1.0, calc_uvs=True)
    for v in bm.verts:
        nx, ny, nz = v.co
        k = _k(nz)
        z = CZ + nz * HZ
        if nz < -0.6:                       # soften the base so Pip sits flat
            z += (nz + 0.6) ** 2 * 0.06
        v.co = Vector((nx * RX * k, ny * RY * k, z))
    return bm


def _arm_bm(sx):
    s = Vector((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2]))
    d = Vector((ARM_DIR.x * sx, ARM_DIR.y, ARM_DIR.z))
    pts = [s - d * 0.03 + d * ((ARM_LEN - 0.01) * i / 14) for i in range(15)]
    bm = bm_tube(pts, lambda t: 0.033 + 0.006 * t, ring=16)
    bm_sphere(0.046, 24, 12, bm=bm, offset=s + d * (ARM_LEN - 0.02), scale=(1.0, 0.85, 1.0))
    return bm


def _leg_bm(sx):
    pts = [(0.085 * sx, 0, 0.17 - 0.12 * i / 8) for i in range(9)]
    bm = bm_tube(pts, 0.042, ring=16)
    bm_sphere(0.06, 24, 12, bm=bm, offset=(0.085 * sx, -0.022, 0.034), scale=(1.0, 1.35, 0.6))
    return bm


def build(col):
    mats = _materials()
    arm = create_armature("RIG_Pip", col, _bones())

    # ---- body (body + arms + legs, one skinned mesh) -------------------------
    bm = new_bm()
    ranges = {'body': append_bm(bm, _body_bm())}
    for side, sx in (('L', 1), ('R', -1)):
        ranges[f'arm.{side}'] = append_bm(bm, _arm_bm(sx))
        ranges[f'leg.{side}'] = append_bm(bm, _leg_bm(sx))
    body = mesh_object("CH_Pip_Body", bm, col, mat=mats['skin'])
    me = body.data
    rest = me.attributes.new("rest_pos", 'FLOAT_VECTOR', 'POINT')
    for v in me.vertices:
        rest.data[v.index].vector = v.co
    weights = {}

    def add(g, i, w):
        weights.setdefault(g, []).append((i, w))

    a, b = ranges['body']
    for i in range(a, b):
        for g, w in _body_weights(me.vertices[i].co.z).items():
            add(g, i, w)
    for side, sx in (('L', 1), ('R', -1)):
        s = Vector((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2]))
        d = Vector((ARM_DIR.x * sx, ARM_DIR.y, ARM_DIR.z))
        a, b = ranges[f'arm.{side}']
        for i in range(a, b):
            t = (me.vertices[i].co - s).dot(d) / ARM_LEN
            wf = smoothstep(0.38, 0.58, t)
            add(f'forearm.{side}', i, wf)
            add(f'upper_arm.{side}', i, 1 - wf)
        a, b = ranges[f'leg.{side}']
        for i in range(a, b):
            z = me.vertices[i].co.z
            wf = 1 - smoothstep(0.045, 0.08, z)
            add(f'foot.{side}', i, wf)
            add(f'thigh.{side}', i, 1 - wf)
    skin(body, arm, weights)
    add_subsurf(body, 1, 2)

    # ---- face ---------------------------------------------------------------
    for side, sx in (('L', 1), ('R', -1)):
        p, n = surface(0.072 * sx, 0.44)
        yaw = math.atan2(-n.x, -n.y)
        eye_bm = bm_sphere(0.04, 32, 16, scale=(1.0, 0.5, 1.28))
        eye = mesh_object(f"CH_Pip_Eye.{side}", eye_bm, col, loc=p + Vector((0, 0.008, 0)),
                          rot=(0.12, 0, -yaw), mat=mats['eye'])
        bpy.context.view_layer.update()
        _bake_transform(eye)
        # catch-lights share one light direction (upper camera-left) on both eyes
        g_bm = bm_sphere(0.0105, 12, 8, offset=(-0.012, -0.016, 0.019))
        bm_sphere(0.005, 10, 6, bm=g_bm, offset=(0.013, -0.017, -0.008))
        glint = mesh_object(f"CH_Pip_EyeGlint.{side}", g_bm, col, loc=p + Vector((0, -0.006, 0)),
                            rot=(0.12, 0, -yaw), mat=mats['glint'])
        _bake_transform(glint)
        for o in (eye, glint):
            rigid_skin(o, arm, f'eye.{side}')
        cp, cn = surface(0.128 * sx, 0.385)
        cyaw = math.atan2(-cn.x, -cn.y)
        cheek = mesh_object(f"CH_Pip_Cheek.{side}", bm_sphere(0.024, 20, 10, scale=(1.25, 0.3, 0.8)), col,
                            loc=cp + cn * -0.002, rot=(0.0, 0, -cyaw), mat=mats['blush'])
        _bake_transform(cheek)
        rigid_skin(cheek, arm, 'head')

    mpts = []
    for i in range(13):
        t = -1.0 + 2.0 * i / 12
        x = 0.021 * math.sin(t)
        z = 0.392 - 0.011 * math.cos(t)
        p, n = surface(x, z)
        mpts.append(p + n * 0.001)
    mouth = mesh_object("CH_Pip_Mouth", bm_tube(mpts, lambda t: 0.0042 * (0.6 + 0.4 * math.sin(math.pi * t)), 8),
                        col, mat=mats['mouth'])
    rigid_skin(mouth, arm, 'head')

    # ---- sprout ---------------------------------------------------------------
    stem_pts = [(0.012 * math.sin(t * 2.2), 0.006 * t, 0.555 + 0.12 * t) for t in [i / 10 for i in range(11)]]
    sbm = bm_tube(stem_pts, lambda t: 0.009 - 0.003 * t, 10)
    stem = mesh_object("CH_Pip_SproutStem", sbm, col, mat=mats['stem'])
    sw = {'sprout.01': [], 'sprout.02': []}
    for v in stem.data.vertices:
        w = smoothstep(0.6, 0.66, v.co.z)
        sw['sprout.02'].append((v.index, w))
        sw['sprout.01'].append((v.index, 1 - w))
    skin(stem, arm, sw)
    tip = Vector(stem_pts[-1])
    lbm = new_bm()
    for side, ang in ((1, 0.9), (-1, -1.0)):
        leaf = bm_leaf(0.11, 0.065, curl=-0.35, segs=12)
        m = Matrix.Translation(tip) @ Matrix.Rotation(ang, 4, 'Z') @ Matrix.Rotation(0.55, 4, 'X') \
            @ Matrix.Rotation(-math.pi / 2, 4, 'Z')
        append_bm(lbm, leaf, m)
    leaves = mesh_object("CH_Pip_SproutLeaves", lbm, col, mat=mats['leaf'])
    leaves.modifiers.new("Solidify", 'SOLIDIFY').thickness = 0.003
    rigid_skin(leaves, arm, 'sprout.02')
    add_subsurf(leaves, 1)

    # ---- scarf ----------------------------------------------------------------
    ring_pts = []
    zc = 0.302
    for i in range(65):
        a = TAU * i / 64
        nz = (zc - CZ) / HZ
        k = _k(nz) * math.sqrt(1 - nz * nz) * 1.04
        ring_pts.append((math.sin(a) * RX * k, -math.cos(a) * RY * k, zc + 0.006 * math.sin(a * 5)))
    scarf_bm = bm_tube(ring_pts, 0.034, 16, cap=False, flatten=0.42)
    tail_pts = [(0.085 + 0.02 * t, -0.19 - 0.025 * math.sin(t * 2.4), 0.30 - 0.13 * t)
                for t in [i / 10 for i in range(11)]]
    bm_tube(tail_pts, lambda t: 0.03 - 0.004 * t, 16, bm=scarf_bm, flatten=0.3)
    scarf = mesh_object("CH_Pip_Scarf", scarf_bm, col, mat=mats['scarf'])
    scw = {}
    for v in scarf.data.vertices:
        for g, w in _body_weights(v.co.z + 0.02).items():
            scw.setdefault(g, []).append((v.index, w))
    skin(scarf, arm, scw)
    add_subsurf(scarf, 1)

    # tidy: rig owns everything, display settings for animators
    arm.data.display_type = 'OCTAHEDRAL'
    arm.data.show_axes = False
    return dict(arm=arm, body=body, mats=mats)


def _bake_transform(obj):
    """Apply object transform into the mesh (clean transforms before skinning)."""
    obj.data.transform(obj.matrix_basis)
    obj.matrix_basis = Matrix.Identity(4)


def hero_pose(arm, frame=1):
    """Cheerful wave - used for the model sheet."""
    key_pose(arm, frame, {
        'upper_arm.L': {'rot': (0, -2.0, 0)},
        'forearm.L': {'rot': (0, -0.45, 0)},
        'upper_arm.R': {'rot': (0, 0.35, 0)},
        'hips': {'rot': (0, 0.06, 0)},
        'head': {'rot': (-0.06, -0.12, 0.1)},
        'sprout.01': {'rot': (0, 0.2, 0)},
        'sprout.02': {'rot': (0, 0.25, 0)},
        'eye.L': {'scale': (1, 0.78, 1)}, 'eye.R': {'scale': (1, 0.78, 1)},
    })
